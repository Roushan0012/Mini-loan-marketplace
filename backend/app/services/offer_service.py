import logging
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.lender_decision import LenderDecision
from app.models.lender_policy import LenderPolicy
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.models.offer import Offer
from app.schemas.offer import (
    MockKFSResponse,
    MockOfferTerms,
    OfferGenerationResponse,
    OfferResponse,
    OfferSelectionResponse,
)
from app.services.application_service import get_customer_application
from app.services.consent_service import (
    get_missing_required_consents,
    has_required_active_consents,
)
from app.services.offer_calculator import (
    calculate_monthly_installment,
    calculate_offer_amount,
)

logger = logging.getLogger(__name__)


class ApplicationNotFoundError(ValueError):
    """Raised when an application is not found or not owned by the authenticated customer."""

    pass


class OfferStatusConflictError(ValueError):
    """Raised when application lifecycle status is not 'matched'."""

    pass


class OfferConsentConflictError(ValueError):
    """Raised when required consents are missing, revoked, or outdated."""

    def __init__(self, message: str, missing_purposes: Optional[List[str]] = None):
        super().__init__(message)
        self.missing_purposes = missing_purposes or []


class OfferMatchRunConflictError(ValueError):
    """Raised when no match run exists or the latest match run is incomplete/failed."""

    pass


class OfferConfigurationError(RuntimeError):
    """Raised when lender offer terms configuration is missing, malformed, or mismatched."""

    pass


class OfferNotFoundError(ValueError):
    """Raised when an offer is not found or does not belong to the supplied loan application."""

    pass


class OfferSelectionConflictError(ValueError):
    """Raised when an offer cannot be selected due to state, run, or availability conflicts."""

    pass


MOCK_KFS_DOCUMENT_TYPE = "TRAINING_ONLY_MOCK_KFS"
MOCK_KFS_DOCUMENT_VERSION = "training-v1"
MOCK_KFS_PAYMENT_FREQUENCY = "Monthly"
MOCK_KFS_AMORTIZATION_METHOD = "Monthly reducing-balance"

MOCK_KFS_FEE_DISCLOSURE = (
    "Processing fees, origination charges, insurance premiums, taxes, late payment fees, "
    "penalties, and other ancillary charges are not modeled or included in this training simulation."
)

MOCK_KFS_CALCULATION_DISCLOSURE = (
    "Monthly installment and repayment totals are illustrative calculations based on the "
    "stored offer terms. Monetary values are rounded to two decimal places. "
    "In rare low-positive-APR cases, estimated repayment is floored at principal to prevent "
    "displaying negative estimated interest caused by cent rounding. "
    "Final-installment adjustments and additional charges are not modeled."
)

MOCK_KFS_TRAINING_DISCLOSURE = (
    "This is a fictional software-training document only. It is not an actual credit offer, "
    "loan agreement, legal disclosure, or regulatory Key Facts Statement. "
    "No real lender or financial institution is involved."
)


def generate_application_offers(
    db: Session,
    customer_id: int,
    application_id: int,
) -> OfferGenerationResponse:
    """Generate credit offers for all eligible lender decisions of the latest completed match run.

    Enforces:
    - Row-level locking on LoanApplication (SELECT ... FOR UPDATE).
    - Application ownership verification.
    - Application status check ('matched').
    - Verification of active current-version consents.
    - Retrieval of latest completed MatchRun.
    - Pre-validation of offer terms across all eligible lenders before persistence.
    - Idempotency: reuses existing offers without mutation or duplication.
    - Single atomic database transaction.
    """
    try:
        # 1. Lock and load the loan application
        stmt = (
            select(LoanApplication)
            .where(
                LoanApplication.id == application_id,
                LoanApplication.customer_id == customer_id,
            )
            .with_for_update()
        )
        app = db.execute(stmt).scalar_one_or_none()

        if app is None:
            raise ApplicationNotFoundError(
                f"Loan application {application_id} not found or not owned by customer."
            )

        # 2. Verify application status
        if app.status != "matched":
            raise OfferStatusConflictError(
                f"Offers can only be generated when application status is 'matched', "
                f"but application {application_id} is in status '{app.status}'."
            )

        # 3. Recheck both required current active consents
        if not has_required_active_consents(db, app.id):
            missing = get_missing_required_consents(db, app.id)
            raise OfferConsentConflictError(
                f"Offer generation requires active consent for all mandatory purposes. Missing: {missing}",
                missing_purposes=missing,
            )

        # 4. Retrieve the latest MatchRun by run_number descending
        latest_run = (
            db.query(MatchRun)
            .filter(MatchRun.application_id == app.id)
            .order_by(MatchRun.run_number.desc())
            .first()
        )

        if latest_run is None:
            raise OfferMatchRunConflictError(
                f"No match run found for application {application_id}. "
                "Matching must be executed before generating offers."
            )

        if latest_run.status != "completed":
            raise OfferMatchRunConflictError(
                f"Latest match run {latest_run.id} (run #{latest_run.run_number}) is in status '{latest_run.status}'. "
                "Offers can only be generated from a completed match run."
            )

        # 5. Retrieve decisions for that exact match run with LenderPolicy eagerly loaded
        decisions = (
            db.query(LenderDecision)
            .options(
                joinedload(LenderDecision.lender_policy),
                joinedload(LenderDecision.offer),
            )
            .filter(LenderDecision.match_run_id == latest_run.id)
            .all()
        )

        # 6. Consider only decisions with decision_status == 'eligible'
        eligible_decisions = [d for d in decisions if d.decision_status == "eligible"]

        if not eligible_decisions:
            return OfferGenerationResponse(
                application_id=app.id,
                match_run_id=latest_run.id,
                run_number=latest_run.run_number,
                generated_count=0,
                offers=[],
            )

        # 7. Pre-validate every eligible lender's offer configuration before inserting
        validated_configs: List[Tuple[LenderDecision, LenderPolicy, MockOfferTerms]] = []
        for decision in eligible_decisions:
            policy = decision.lender_policy
            if policy is None:
                raise OfferConfigurationError(
                    f"Lender decision {decision.id} references missing policy {decision.lender_policy_id}."
                )

            # Verify policy_version matches decision.policy_version_snapshot
            if policy.policy_version != decision.policy_version_snapshot:
                raise OfferConfigurationError(
                    f"Policy version mismatch for lender {policy.lender_code}: "
                    f"decision snapshot is '{decision.policy_version_snapshot}', "
                    f"but policy record version is '{policy.policy_version}'."
                )

            # Validate offer_terms
            if not policy.offer_terms:
                raise OfferConfigurationError(
                    f"Lender {policy.lender_code} policy version {policy.policy_version} "
                    "is missing required 'offer_terms' configuration."
                )

            try:
                terms = MockOfferTerms.model_validate(policy.offer_terms)
            except Exception as exc:
                raise OfferConfigurationError(
                    f"Lender {policy.lender_code} offer_terms failed validation: {exc}"
                ) from exc

            validated_configs.append((decision, policy, terms))

        # Sort configs deterministically by lender_code
        validated_configs.sort(key=lambda item: item[1].lender_code)

        offers_to_return: List[Offer] = []
        generated_count = 0

        # 8–10. Calculate terms and persist Offer records
        app_requested = Decimal(str(app.requested_amount))

        for decision, policy, terms in validated_configs:
            # 11. Idempotency check: if an offer already exists, reuse it
            if decision.offer is not None:
                offers_to_return.append(decision.offer)
                continue

            existing_offer = (
                db.query(Offer)
                .filter(Offer.lender_decision_id == decision.id)
                .first()
            )
            if existing_offer is not None:
                offers_to_return.append(existing_offer)
                continue

            # Calculate offer amount as min(requested, policy_max)
            offer_amount = calculate_offer_amount(app_requested, terms.max_loan_amount)

            # Calculate monthly installment
            emi = calculate_monthly_installment(
                principal=offer_amount,
                apr_percent=terms.apr_percent,
                term_months=terms.term_months,
            )

            new_offer = Offer(
                lender_decision_id=decision.id,
                loan_amount=offer_amount,
                apr=terms.apr_percent,
                term_months=terms.term_months,
                monthly_installment=emi,
                mock_kfs_reference=f"TRAINING-MOCK-KFS-D{decision.id}",
                status="available",
                valid_until=None,
            )
            db.add(new_offer)
            offers_to_return.append(new_offer)
            generated_count += 1

        # 12. Commit all new offers atomically
        db.commit()

        # Eagerly refresh all returned offers
        for o in offers_to_return:
            db.refresh(o)

        return OfferGenerationResponse(
            application_id=app.id,
            match_run_id=latest_run.id,
            run_number=latest_run.run_number,
            generated_count=generated_count,
            offers=[OfferResponse.model_validate(o) for o in offers_to_return],
        )

    except (
        ApplicationNotFoundError,
        OfferStatusConflictError,
        OfferConsentConflictError,
        OfferMatchRunConflictError,
        OfferConfigurationError,
    ):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def list_application_offers(
    db: Session,
    customer_id: int,
    application_id: int,
) -> List[OfferResponse]:
    """Retrieve all credit offers belonging to the latest completed match run of an owned application.

    Enforces:
    - Application ownership verification.
    - Scopes offers strictly to the latest completed MatchRun by run_number.
    - Deterministic lender_code ordering.
    - Eager loading of decision and policy relationships.
    - Returns empty list if no match run exists or latest match run is not completed.
    """
    app = get_customer_application(db, customer_id=customer_id, application_id=application_id)
    if app is None:
        raise ApplicationNotFoundError(
            f"Loan application {application_id} not found or not owned by customer."
        )

    latest_run = (
        db.query(MatchRun)
        .filter(MatchRun.application_id == application_id)
        .order_by(MatchRun.run_number.desc())
        .first()
    )

    if latest_run is None or latest_run.status != "completed":
        return []

    offers = (
        db.query(Offer)
        .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
        .join(LenderPolicy, LenderDecision.lender_policy_id == LenderPolicy.id)
        .options(
            joinedload(Offer.lender_decision).joinedload(LenderDecision.lender_policy)
        )
        .filter(LenderDecision.match_run_id == latest_run.id)
        .order_by(LenderPolicy.lender_code.asc())
        .all()
    )

    return [OfferResponse.model_validate(o) for o in offers]


def get_mock_kfs_details(
    db: Session,
    customer_id: int,
    application_id: int,
    offer_id: int,
) -> MockKFSResponse:
    """Retrieve Key Facts Statement (KFS) details for a specific loan offer.

    Enforces:
    - Application ownership verification.
    - Verified relationship: Offer -> LenderDecision -> MatchRun -> LoanApplication.
    - Scoped strictly to application_id and customer_id within the database query.
    - Eager loading of LenderDecision, MatchRun, and LenderPolicy.
    - Uses exact policy referenced by decision and decision.policy_version_snapshot.
    - Read-only: does not modify or re-create offers, match runs, or decisions.
    - Accurately computes estimated total repayment and interest using Decimal precision.
    - Supports historical offers belonging to earlier completed match runs.
    """
    app = get_customer_application(db, customer_id=customer_id, application_id=application_id)
    if app is None:
        raise ApplicationNotFoundError(
            f"Loan application {application_id} not found or not owned by customer."
        )

    stmt = (
        select(Offer)
        .join(Offer.lender_decision)
        .join(LenderDecision.match_run)
        .join(MatchRun.application)
        .options(
            joinedload(Offer.lender_decision).joinedload(LenderDecision.lender_policy),
            joinedload(Offer.lender_decision).joinedload(LenderDecision.match_run),
        )
        .where(
            Offer.id == offer_id,
            LoanApplication.id == application_id,
            LoanApplication.customer_id == customer_id,
        )
    )
    offer = db.execute(stmt).scalar_one_or_none()
    if offer is None:
        raise OfferNotFoundError(
            f"Offer {offer_id} not found for loan application {application_id}."
        )

    decision = offer.lender_decision
    policy = decision.lender_policy if decision else None
    policy_version = decision.policy_version_snapshot if decision else ""
    lender_code = policy.lender_code if policy else ""
    lender_name = policy.lender_name if policy else ""

    with localcontext() as ctx:
        ctx.prec = 35
        stored_loan_amount = Decimal(str(offer.loan_amount)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        stored_apr = Decimal(str(offer.apr))
        stored_term_months = offer.term_months
        stored_emi = Decimal(str(offer.monthly_installment)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        number_of_installments = stored_term_months

        if stored_apr > Decimal("0"):
            installment_total = stored_emi * Decimal(stored_term_months)
            estimated_total_repayment = max(
                installment_total, stored_loan_amount
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            estimated_total_interest = (
                estimated_total_repayment - stored_loan_amount
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            estimated_total_interest = Decimal("0.00")
            estimated_total_repayment = stored_loan_amount

    return MockKFSResponse(
        document_type=MOCK_KFS_DOCUMENT_TYPE,
        document_version=MOCK_KFS_DOCUMENT_VERSION,
        mock_kfs_reference=offer.mock_kfs_reference,
        offer_id=offer.id,
        application_id=application_id,
        lender_code=lender_code,
        lender_name=lender_name,
        policy_version=policy_version,
        offer_status=offer.status,
        offer_created_at=offer.created_at,
        valid_until=offer.valid_until,
        loan_amount=stored_loan_amount,
        nominal_annual_apr_percent=stored_apr,
        term_months=stored_term_months,
        number_of_installments=number_of_installments,
        payment_frequency=MOCK_KFS_PAYMENT_FREQUENCY,
        monthly_installment=stored_emi,
        estimated_total_repayment=estimated_total_repayment,
        estimated_total_interest=estimated_total_interest,
        amortization_method=MOCK_KFS_AMORTIZATION_METHOD,
        fee_disclosure=MOCK_KFS_FEE_DISCLOSURE,
        calculation_disclosure=MOCK_KFS_CALCULATION_DISCLOSURE,
        training_disclosure=MOCK_KFS_TRAINING_DISCLOSURE,
    )


def select_application_offer(
    db: Session,
    customer_id: int,
    application_id: int,
    offer_id: int,
) -> OfferSelectionResponse:
    """Select exactly one available loan offer for a matched loan application.

    Enforces:
    - Application row locking via SELECT FOR UPDATE.
    - Application ownership verification (customer_id).
    - Idempotent return if already selected.
    - Application status check ('matched' or idempotent 'offer_selected').
    - Verification of active current-version consents (for new selection).
    - Presence and validity of latest completed match run.
    - Scopes offer strictly to application_id and latest completed match run.
    - Decision status must be 'eligible'.
    - Offer status must be 'available'.
    - Atomic transition: offer -> 'selected', application -> 'offer_selected'.
    - Atomic withdrawal of other available offers for this application across all match runs.
    - Full transaction rollback on any failure.
    - Preserves historical records, decisions, match runs, and KFS accessibility.
    """
    try:
        # 1. Lock and load application row using SELECT FOR UPDATE
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
            raise ApplicationNotFoundError(
                f"Loan application {application_id} not found or not owned by customer."
            )

        # 2. Verify requested offer exists and belongs to this application
        requested_offer = (
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
        if requested_offer is None:
            raise OfferNotFoundError(
                f"Offer {offer_id} not found for loan application {application_id}."
            )

        # 3. Handle application state
        if app.status == "offer_selected":
            # Find the already selected offer for this application
            already_selected = (
                db.query(Offer)
                .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
                .join(MatchRun, LenderDecision.match_run_id == MatchRun.id)
                .options(
                    joinedload(Offer.lender_decision).joinedload(LenderDecision.lender_policy),
                    joinedload(Offer.lender_decision).joinedload(LenderDecision.match_run),
                )
                .filter(
                    MatchRun.application_id == application_id,
                    Offer.status == "selected",
                )
                .first()
            )
            if already_selected is not None and already_selected.id == requested_offer.id:
                return OfferSelectionResponse(
                    application_id=app.id,
                    application_status="offer_selected",
                    selected_offer=OfferResponse.model_validate(already_selected),
                    withdrawn_offer_count=0,
                    selection_result="already_selected",
                )
            raise OfferSelectionConflictError(
                f"Application {application_id} already has a selected offer and cannot select offer {offer_id}."
            )

        if app.status != "matched":
            raise OfferStatusConflictError(
                f"Application {application_id} is in status '{app.status}' and cannot select offers."
            )

        # 4. Inconsistent state check: application is 'matched' but an offer is already marked 'selected'
        existing_selected = (
            db.query(Offer)
            .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
            .join(MatchRun, LenderDecision.match_run_id == MatchRun.id)
            .filter(
                MatchRun.application_id == application_id,
                Offer.status == "selected",
            )
            .first()
        )
        if existing_selected is not None:
            raise OfferSelectionConflictError(
                f"Application {application_id} is in status '{app.status}' but already has an offer marked as selected."
            )

        # 5. Retrieve latest MatchRun by run_number descending
        latest_run = (
            db.query(MatchRun)
            .filter(MatchRun.application_id == application_id)
            .order_by(MatchRun.run_number.desc())
            .first()
        )
        if latest_run is None:
            raise OfferMatchRunConflictError(
                f"Application {application_id} does not have any match run."
            )
        if latest_run.status != "completed":
            raise OfferMatchRunConflictError(
                f"Latest match run {latest_run.id} for application {application_id} is in status '{latest_run.status}', not completed."
            )

        # 6. Verify requested Offer belongs to this exact latest completed MatchRun
        if requested_offer.lender_decision.match_run_id != latest_run.id:
            raise OfferSelectionConflictError(
                f"Offer {offer_id} belongs to an older match run and is no longer selectable."
            )

        # 7. Verify lender decision is eligible
        if requested_offer.lender_decision.decision_status != "eligible":
            raise OfferSelectionConflictError(
                f"Offer {offer_id} decision status is '{requested_offer.lender_decision.decision_status}', not eligible."
            )

        # 8. Check offer status (must be 'available')
        if requested_offer.status != "available":
            raise OfferSelectionConflictError(
                f"Offer {offer_id} is in status '{requested_offer.status}' and cannot be selected."
            )

        # 9. Recheck active consent purposes
        if not has_required_active_consents(db, app.id):
            missing = get_missing_required_consents(db, app.id)
            raise OfferConsentConflictError(
                f"Active consent required for mandatory purposes. Missing/invalid: {missing}",
                missing_purposes=missing,
            )

        # 10. Atomically update requested offer and application status
        requested_offer.status = "selected"
        app.status = "offer_selected"

        # 11. Withdraw all other available offers for this application across all match runs
        other_available_offers = (
            db.query(Offer)
            .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
            .join(MatchRun, LenderDecision.match_run_id == MatchRun.id)
            .filter(
                MatchRun.application_id == application_id,
                Offer.id != requested_offer.id,
                Offer.status == "available",
            )
            .all()
        )
        for o in other_available_offers:
            o.status = "withdrawn"
        withdrawn_count = len(other_available_offers)

        # 12. Commit transaction
        db.commit()
        db.refresh(requested_offer)
        db.refresh(app)

        return OfferSelectionResponse(
            application_id=app.id,
            application_status="offer_selected",
            selected_offer=OfferResponse.model_validate(requested_offer),
            withdrawn_offer_count=withdrawn_count,
            selection_result="selected",
        )

    except (
        ApplicationNotFoundError,
        OfferNotFoundError,
        OfferStatusConflictError,
        OfferMatchRunConflictError,
        OfferSelectionConflictError,
        OfferConsentConflictError,
    ):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
