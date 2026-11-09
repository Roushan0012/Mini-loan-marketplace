import logging
from typing import List, Literal, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.integrations.mock_lenders import (
    MockLenderAdapterError,
    mock_lender_client,
)
from app.models.lender_decision import LenderDecision
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.models.offer import Offer
from app.models.offer_submission import OfferSubmission
from app.schemas.offer import OfferSubmissionResponse, OfferSubmissionStatusResponse
from app.services.consent_service import (
    get_missing_required_consents,
    has_required_active_consents,
)

logger = logging.getLogger(__name__)


class SubmissionApplicationNotFoundError(ValueError):
    """Raised when an application is not found or not owned by customer."""

    pass


class SubmissionOfferNotFoundError(ValueError):
    """Raised when an offer is not found or does not belong to the application."""

    pass


class SubmissionConflictError(ValueError):
    """Raised when submission cannot proceed due to lifecycle state or idempotency conflict."""

    pass


class SubmissionConsentConflictError(ValueError):
    """Raised when mandatory consents are missing, revoked, or outdated."""

    def __init__(self, message: str, missing_purposes: Optional[List[str]] = None):
        super().__init__(message)
        self.missing_purposes = missing_purposes or []


class SubmissionAdapterError(RuntimeError):
    """Raised when the mock lender adapter encounters an error or misconfiguration."""

    pass


def _build_submission_response(
    submission: OfferSubmission,
    submission_result: Literal["created", "replayed"],
) -> OfferSubmissionResponse:
    """Build OfferSubmissionResponse from ORM model and snapshot relationships."""
    decision = submission.offer.lender_decision if submission.offer else None
    policy = decision.lender_policy if decision else None

    lender_code = policy.lender_code if policy else ""
    lender_name = policy.lender_name if policy else ""
    policy_version = (
        decision.policy_version_snapshot
        if decision and decision.policy_version_snapshot
        else (policy.policy_version if policy else "")
    )

    return OfferSubmissionResponse(
        id=submission.id,
        application_id=submission.application_id,
        offer_id=submission.offer_id,
        lender_code=lender_code,
        lender_name=lender_name,
        policy_version=policy_version,
        status=submission.status,
        mock_reference=submission.mock_reference,
        submitted_at=submission.submitted_at,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
        submission_result=submission_result,
    )


def submit_selected_offer(
    db: Session,
    customer_id: int,
    application_id: int,
    offer_id: int,
    idempotency_key: str,
) -> OfferSubmissionResponse:
    """Submit the selected loan offer of an application to a mock lender idempotently.

    Enforces:
    - Normalization and validation of client-provided Idempotency-Key.
    - Application row locking using SELECT FOR UPDATE.
    - Customer ownership filtering.
    - Idempotency check on existing key and existing application submission.
    - Application status check ('offer_selected').
    - Selected offer status check ('selected') and eligible decision.
    - Single selected offer integrity check.
    - Active mandatory consent verification (bypassed on exact idempotent replay).
    - Creation of OfferSubmission record in 'pending' status.
    - Invocation of deterministic local mock lender adapter with minimal non-PII payload.
    - On success: OfferSubmission.status -> 'submitted', LoanApplication.status -> 'submitted'.
    - On failure: full transaction rollback preserving offer_selected status and permitting retries.
    - Atomic commit.
    """
    # 1. Validate and normalize idempotency key
    if not isinstance(idempotency_key, str):
        raise SubmissionConflictError("Idempotency key must be a valid string.")
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise SubmissionConflictError("Idempotency key cannot be empty or whitespace.")
    if len(normalized_key) < 8 or len(normalized_key) > 128:
        raise SubmissionConflictError("Idempotency key length must be between 8 and 128 characters.")

    try:
        # 2. Lock and load LoanApplication using SELECT FOR UPDATE
        app = (
            db.query(LoanApplication)
            .filter(
                LoanApplication.id == application_id,
                LoanApplication.customer_id == customer_id,
            )
            .with_for_update()
            .first()
        )
        if app is None:
            raise SubmissionApplicationNotFoundError(
                f"Loan application {application_id} not found or not owned by customer."
            )

        # 3. Check for existing record with the supplied idempotency_key
        existing_by_key = (
            db.query(OfferSubmission)
            .options(
                joinedload(OfferSubmission.offer)
                .joinedload(Offer.lender_decision)
                .joinedload(LenderDecision.lender_policy)
            )
            .filter(OfferSubmission.idempotency_key == normalized_key)
            .first()
        )
        if existing_by_key is not None:
            if (
                existing_by_key.application_id == application_id
                and existing_by_key.offer_id == offer_id
            ):
                return _build_submission_response(existing_by_key, submission_result="replayed")
            raise SubmissionConflictError(
                "The provided Idempotency-Key has already been used for a different application or offer."
            )

        # 4. Check whether the application already has an OfferSubmission
        existing_by_app = (
            db.query(OfferSubmission)
            .options(
                joinedload(OfferSubmission.offer)
                .joinedload(Offer.lender_decision)
                .joinedload(LenderDecision.lender_policy)
            )
            .filter(OfferSubmission.application_id == application_id)
            .first()
        )
        if existing_by_app is not None:
            if (
                existing_by_app.offer_id == offer_id
                and existing_by_app.idempotency_key == normalized_key
            ):
                return _build_submission_response(existing_by_app, submission_result="replayed")
            elif existing_by_app.offer_id == offer_id:
                raise SubmissionConflictError(
                    "This application has already been submitted with a different Idempotency-Key. "
                    "The original Idempotency-Key must be reused for retries."
                )
            else:
                raise SubmissionConflictError(
                    "This application has already been submitted with a different offer."
                )

        # 5. Validate application state (must be 'offer_selected')
        if app.status != "offer_selected":
            raise SubmissionConflictError(
                f"Application {application_id} is in status '{app.status}', expected 'offer_selected'."
            )

        # 6. Verify requested offer exists and belongs to this application
        selected_offer = (
            db.query(Offer)
            .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
            .join(MatchRun, LenderDecision.match_run_id == MatchRun.id)
            .options(
                joinedload(Offer.lender_decision).joinedload(LenderDecision.lender_policy),
                joinedload(Offer.lender_decision).joinedload(LenderDecision.match_run),
            )
            .filter(
                Offer.id == offer_id,
                MatchRun.application_id == application_id,
            )
            .first()
        )
        if selected_offer is None:
            raise SubmissionOfferNotFoundError(
                f"Offer {offer_id} not found for loan application {application_id}."
            )

        # 7. Validate selection state
        if selected_offer.status != "selected":
            raise SubmissionConflictError(
                f"Offer {offer_id} is in status '{selected_offer.status}', expected 'selected'."
            )

        if selected_offer.lender_decision.decision_status != "eligible":
            raise SubmissionConflictError(
                f"Offer {offer_id} decision status is '{selected_offer.lender_decision.decision_status}', not 'eligible'."
            )

        # Verify exactly one offer is selected for this application
        selected_count = (
            db.query(Offer.id)
            .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
            .join(MatchRun, LenderDecision.match_run_id == MatchRun.id)
            .filter(
                MatchRun.application_id == application_id,
                Offer.status == "selected",
            )
            .count()
        )
        if selected_count != 1:
            raise SubmissionConflictError(
                f"Application {application_id} has inconsistent selection state ({selected_count} selected offers, expected 1)."
            )

        # 8. Recheck active mandatory consents
        if not has_required_active_consents(db, app.id):
            missing = get_missing_required_consents(db, app.id)
            raise SubmissionConsentConflictError(
                f"Offer submission requires active consent for all mandatory purposes. Missing: {missing}",
                missing_purposes=missing,
            )

        # 9. Retrieve referenced policy and lender code
        decision = selected_offer.lender_decision
        policy = decision.lender_policy
        if policy is None or not policy.lender_code:
            raise SubmissionAdapterError(
                f"Selected offer {offer_id} does not have an associated lender policy."
            )
        lender_code = policy.lender_code

        # 10. Create OfferSubmission in 'pending' status
        submission = OfferSubmission(
            application_id=app.id,
            offer_id=selected_offer.id,
            idempotency_key=normalized_key,
            status="pending",
        )
        db.add(submission)
        db.flush()

        # 11. Invoke local deterministic mock lender adapter
        try:
            receipt = mock_lender_client.submit_offer(
                lender_code=lender_code,
                submission_id=submission.id,
            )
        except MockLenderAdapterError as exc:
            db.rollback()
            raise SubmissionAdapterError(f"Mock lender adapter error: {exc}") from exc
        except Exception as exc:
            db.rollback()
            raise SubmissionAdapterError(f"Unexpected adapter failure: {exc}") from exc

        # 12. On successful receipt, update submission and application statuses
        submission.status = receipt.status
        submission.mock_reference = receipt.mock_reference
        app.status = "submitted"
        # Offer.status remains "selected"

        db.commit()
        db.refresh(submission)
        db.refresh(app)

        return _build_submission_response(submission, submission_result="created")

    except IntegrityError as exc:
        db.rollback()
        # Handle database concurrency race
        existing = (
            db.query(OfferSubmission)
            .options(
                joinedload(OfferSubmission.offer)
                .joinedload(Offer.lender_decision)
                .joinedload(LenderDecision.lender_policy)
            )
            .filter(
                OfferSubmission.application_id == application_id,
                OfferSubmission.offer_id == offer_id,
                OfferSubmission.idempotency_key == normalized_key,
            )
            .first()
        )
        if existing is not None:
            return _build_submission_response(existing, submission_result="replayed")
        raise SubmissionConflictError(
            "Concurrent conflict occurred while creating offer submission."
        ) from exc
    except (
        SubmissionApplicationNotFoundError,
        SubmissionOfferNotFoundError,
        SubmissionConflictError,
        SubmissionConsentConflictError,
        SubmissionAdapterError,
    ):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def get_application_submission_status(
    db: Session,
    customer_id: int,
    application_id: int,
) -> Optional[OfferSubmissionStatusResponse]:
    """Retrieve the current submission status for an owned loan application.

    Enforces:
    - Application exists and belongs to customer_id (raises SubmissionApplicationNotFoundError -> 404).
    - If application has no submission, returns None (serializes to HTTP 200 null).
    - Eagerly loads offer -> lender_decision -> lender_policy to extract exact lender attributes.
    - Read-only: does not modify any records, statuses, or timestamps.
    """
    app = (
        db.query(LoanApplication)
        .filter(
            LoanApplication.id == application_id,
            LoanApplication.customer_id == customer_id,
        )
        .first()
    )
    if app is None:
        raise SubmissionApplicationNotFoundError("Loan application not found.")

    submission = (
        db.query(OfferSubmission)
        .options(
            joinedload(OfferSubmission.offer)
            .joinedload(Offer.lender_decision)
            .joinedload(LenderDecision.lender_policy)
        )
        .filter(OfferSubmission.application_id == application_id)
        .first()
    )
    if submission is None:
        return None

    decision = submission.offer.lender_decision if submission.offer else None
    policy = decision.lender_policy if decision else None

    lender_code = policy.lender_code if policy else ""
    lender_name = policy.lender_name if policy else ""
    policy_version = (
        decision.policy_version_snapshot
        if decision and decision.policy_version_snapshot
        else (policy.policy_version if policy else "")
    )

    return OfferSubmissionStatusResponse(
        id=submission.id,
        application_id=submission.application_id,
        offer_id=submission.offer_id,
        lender_code=lender_code,
        lender_name=lender_name,
        policy_version=policy_version,
        status=submission.status,
        mock_reference=submission.mock_reference,
        submitted_at=submission.submitted_at,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )
