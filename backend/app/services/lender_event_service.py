import logging
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.lender_decision import LenderDecision
from app.models.lender_event import LenderEvent
from app.models.loan_application import LoanApplication
from app.models.offer import Offer
from app.models.offer_submission import OfferSubmission
from app.schemas.lender_event import LenderEventResponse, MockLenderWebhookEvent

logger = logging.getLogger(__name__)


class SubmissionNotFoundError(ValueError):
    """Raised when an offer submission is not found or does not match reference/lender."""

    pass


class LenderEventConflictError(ValueError):
    """Raised when an event ID is reused with conflicting data or invalid sequence/state."""

    pass


class LenderEventConfigurationError(RuntimeError):
    """Raised when mock lender configuration or policy reference is invalid."""

    pass


def process_mock_lender_event(
    db: Session,
    event: MockLenderWebhookEvent,
) -> LenderEventResponse:
    """Ingest and process an asynchronous mock lender outcome event.

    Enforces:
    - Verifies OfferSubmission existence and exact mock_reference match.
    - Verifies event lender_code matches the policy referenced by the decision.
    - Serialized row locking: acquires lock on LoanApplication first, then OfferSubmission.
    - Idempotent duplicate event_id handling: identical event returns duplicate=True without side-effects;
      reused event_id with different content raises LenderEventConflictError.
    - Authoritative sequence numbers: sequence numbers control ordering rather than arrival time.
      Stale or duplicate sequence numbers are recorded with processing_status='ignored' without mutating state.
    - State transitions on valid newer sequence:
        lender.accepted   -> OfferSubmission: accepted,  LoanApplication: accepted
        lender.declined   -> OfferSubmission: declined,  LoanApplication: declined
        lender.timed_out  -> OfferSubmission: timed_out, LoanApplication: timed_out
        lender.failed     -> OfferSubmission: failed,    LoanApplication: failed
    - Offer.status remains 'selected' and financial terms remain unchanged.
    - Persists only sanitized, allowlisted event payload without PII or signatures.
    - Commits event record and lifecycle state changes in one atomic database transaction.
    """
    sanitized_payload: Dict[str, Any] = {
        "mock_reference": event.mock_reference,
        "lender_code": event.lender_code,
        "reason_code": event.reason_code,
        "simulation": True,
    }

    try:
        # 1. Locate OfferSubmission by submission_id
        submission = (
            db.query(OfferSubmission)
            .options(
                joinedload(OfferSubmission.offer)
                .joinedload(Offer.lender_decision)
                .joinedload(LenderDecision.lender_policy)
            )
            .filter(OfferSubmission.id == event.submission_id)
            .first()
        )
        if submission is None:
            raise SubmissionNotFoundError(
                f"Offer submission {event.submission_id} not found."
            )

        # 2. Verify mock_reference matches
        if submission.mock_reference != event.mock_reference:
            raise SubmissionNotFoundError(
                f"Mock reference '{event.mock_reference}' does not match submission {event.submission_id}."
            )

        # 3. Verify lender_code matches exact referenced policy
        offer = submission.offer
        decision = offer.lender_decision if offer else None
        policy = decision.lender_policy if decision else None
        if policy is None or policy.lender_code != event.lender_code:
            raise SubmissionNotFoundError(
                f"Lender code '{event.lender_code}' does not match referenced policy for submission {event.submission_id}."
            )

        # 4. Acquire row locks in canonical order: LoanApplication first, then OfferSubmission
        app = (
            db.query(LoanApplication)
            .filter(LoanApplication.id == submission.application_id)
            .with_for_update()
            .first()
        )
        locked_sub = (
            db.query(OfferSubmission)
            .filter(OfferSubmission.id == event.submission_id)
            .with_for_update()
            .first()
        )
        if app is None or locked_sub is None:
            raise SubmissionNotFoundError("Application or submission record not found under lock.")

        # 5. Check for existing event by event_id (Duplicate event_id handling)
        existing_event = (
            db.query(LenderEvent)
            .filter(LenderEvent.event_id == event.event_id)
            .first()
        )
        if existing_event is not None:
            # Check if all fields match exactly
            if (
                existing_event.submission_id == event.submission_id
                and existing_event.event_type == event.event_type
                and existing_event.sequence_number == event.sequence_number
                and existing_event.occurred_at == event.occurred_at
                and existing_event.event_payload == sanitized_payload
            ):
                return LenderEventResponse(
                    event_id=existing_event.event_id,
                    submission_id=existing_event.submission_id,
                    event_type=existing_event.event_type,
                    sequence_number=existing_event.sequence_number,
                    processing_status=existing_event.processing_status,
                    submission_status=locked_sub.status,
                    application_status=app.status,
                    duplicate=True,
                    received_at=existing_event.received_at,
                )
            raise LenderEventConflictError(
                f"Event ID '{event.event_id}' has already been processed with different content."
            )

        # 6. Retrieve highest sequence_number among previously processed events
        # Note on event sequencing: In asynchronous networks, provider webhooks may arrive
        # out-of-order or with retries. Sequence numbers assigned by the provider represent
        # the authoritative timeline. Lower or equal sequence numbers are recorded as 'ignored'.
        max_processed_seq = (
            db.query(func.max(LenderEvent.sequence_number))
            .filter(
                LenderEvent.submission_id == locked_sub.id,
                LenderEvent.processing_status == "processed",
            )
            .scalar()
        )

        # 7. Check if sequence is stale or already superseded
        if max_processed_seq is not None and event.sequence_number <= max_processed_seq:
            # Stale / out-of-order event: record as ignored, do not alter lifecycle statuses
            ignored_event = LenderEvent(
                submission_id=locked_sub.id,
                event_id=event.event_id,
                event_type=event.event_type,
                sequence_number=event.sequence_number,
                event_payload=sanitized_payload,
                processing_status="ignored",
                occurred_at=event.occurred_at,
            )
            db.add(ignored_event)
            db.commit()
            db.refresh(ignored_event)

            return LenderEventResponse(
                event_id=ignored_event.event_id,
                submission_id=ignored_event.submission_id,
                event_type=ignored_event.event_type,
                sequence_number=ignored_event.sequence_number,
                processing_status="ignored",
                submission_status=locked_sub.status,
                application_status=app.status,
                duplicate=False,
                received_at=ignored_event.received_at,
            )

        # 8. First outcome validation: submission must be in 'submitted' status to receive first outcome
        if max_processed_seq is None and locked_sub.status != "submitted":
            raise LenderEventConflictError(
                f"Submission {locked_sub.id} is in status '{locked_sub.status}', expected 'submitted' to receive first outcome."
            )

        # 9. Map event outcome to target statuses
        status_mapping = {
            "lender.accepted": "accepted",
            "lender.declined": "declined",
            "lender.timed_out": "timed_out",
            "lender.failed": "failed",
        }
        target_status = status_mapping[event.event_type]

        # 10. Persist event as 'processed' and update submission/application statuses atomically
        processed_event = LenderEvent(
            submission_id=locked_sub.id,
            event_id=event.event_id,
            event_type=event.event_type,
            sequence_number=event.sequence_number,
            event_payload=sanitized_payload,
            processing_status="processed",
            occurred_at=event.occurred_at,
        )
        db.add(processed_event)

        locked_sub.status = target_status
        app.status = target_status
        # Offer.status remains 'selected' and financial terms remain unchanged

        db.commit()
        db.refresh(processed_event)
        db.refresh(locked_sub)
        db.refresh(app)

        return LenderEventResponse(
            event_id=processed_event.event_id,
            submission_id=processed_event.submission_id,
            event_type=processed_event.event_type,
            sequence_number=processed_event.sequence_number,
            processing_status="processed",
            submission_status=locked_sub.status,
            application_status=app.status,
            duplicate=False,
            received_at=processed_event.received_at,
        )

    except IntegrityError as exc:
        db.rollback()
        # Handle concurrent delivery race condition
        existing_event = (
            db.query(LenderEvent)
            .filter(LenderEvent.event_id == event.event_id)
            .first()
        )
        if existing_event is not None:
            if (
                existing_event.submission_id == event.submission_id
                and existing_event.event_type == event.event_type
                and existing_event.sequence_number == event.sequence_number
                and existing_event.occurred_at == event.occurred_at
                and existing_event.event_payload == sanitized_payload
            ):
                sub_rec = db.query(OfferSubmission).filter(OfferSubmission.id == event.submission_id).first()
                app_rec = db.query(LoanApplication).filter(LoanApplication.id == sub_rec.application_id).first() if sub_rec else None
                return LenderEventResponse(
                    event_id=existing_event.event_id,
                    submission_id=existing_event.submission_id,
                    event_type=existing_event.event_type,
                    sequence_number=existing_event.sequence_number,
                    processing_status=existing_event.processing_status,
                    submission_status=sub_rec.status if sub_rec else None,
                    application_status=app_rec.status if app_rec else None,
                    duplicate=True,
                    received_at=existing_event.received_at,
                )
            raise LenderEventConflictError(
                f"Event ID '{event.event_id}' has already been processed with different content."
            ) from exc
        raise LenderEventConflictError("Database integrity conflict occurred during event processing.") from exc

    except (SubmissionNotFoundError, LenderEventConflictError, LenderEventConfigurationError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
