import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.consent import Consent
from app.models.lender_decision import LenderDecision
from app.models.lender_policy import LenderPolicy
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.schemas.lender_policy import LenderPolicyRules
from app.schemas.matching import MatchRunResponse, MatchRunSummaryResponse
from app.services.application_service import get_customer_application
from app.services.consent_notices import (
    PURPOSE_ELIGIBILITY_MATCHING,
    get_current_version,
)
from app.services.consent_service import (
    get_missing_required_consents,
    has_required_active_consents,
)

logger = logging.getLogger(__name__)


class ApplicationNotFoundError(ValueError):
    """Raised when an application is not found or not owned by the authenticated customer."""

    pass


class MatchingStatusConflictError(ValueError):
    """Raised when application is in a lifecycle state that does not permit matching."""

    pass


class MatchingConsentConflictError(ValueError):
    """Raised when required consents are missing, revoked, or outdated."""

    def __init__(self, message: str, missing_purposes: Optional[List[str]] = None):
        super().__init__(message)
        self.missing_purposes = missing_purposes or []


class MatchingConfigurationError(RuntimeError):
    """Raised when lender policy configuration is missing or ambiguous."""

    pass


class MatchingConcurrencyConflictError(RuntimeError):
    """Raised when a concurrent matching run causes a race condition or constraint conflict."""

    pass


def evaluate_lender_policy(
    application: LoanApplication,
    policy: LenderPolicy,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Deterministically evaluate applicant parameters against a single lender underwriting policy.

    Returns:
        (decision_status, exclusion_reason_code, exclusion_reason)
        Where:
            - decision_status: 'eligible' or 'ineligible'
            - exclusion_reason_code: Specific code or None
            - exclusion_reason: Diagnostic human-readable string or None
    """
    try:
        rules_model = LenderPolicyRules.model_validate(policy.rules)
    except Exception as exc:
        logger.warning(
            "Malformed lender policy configuration for lender=%s version=%s id=%s: %s",
            policy.lender_code,
            policy.policy_version,
            policy.id,
            exc,
        )
        return (
            "ineligible",
            "POLICY_CONFIGURATION_INVALID",
            f"Lender policy configuration failed schema validation: {exc}",
        )

    failed_reasons: List[Tuple[str, str]] = []

    # 1. Applicant age check
    if application.age < rules_model.min_age:
        failed_reasons.append(
            (
                "AGE_BELOW_MINIMUM",
                f"Applicant age ({application.age}) is below policy minimum ({rules_model.min_age}).",
            )
        )

    # 2. Monthly income check (exact Decimal comparison, no Float conversion)
    app_income = Decimal(str(application.monthly_income))
    if app_income < rules_model.min_monthly_income:
        failed_reasons.append(
            (
                "INCOME_BELOW_MINIMUM",
                f"Applicant monthly income ({app_income}) is below policy minimum ({rules_model.min_monthly_income}).",
            )
        )

    # 3. Work type check
    app_work_type = (application.work_type or "").strip().lower()
    if app_work_type not in rules_model.allowed_work_types:
        failed_reasons.append(
            (
                "WORK_TYPE_NOT_ALLOWED",
                f"Applicant work type '{application.work_type}' is not allowed by policy. "
                f"Permitted work types: {sorted(rules_model.allowed_work_types)}.",
            )
        )

    # Decision synthesis enforcing database check constraints
    if not failed_reasons:
        return ("eligible", None, None)

    if len(failed_reasons) == 1:
        code, text = failed_reasons[0]
        return ("ineligible", code, text)

    # Multiple rules failed
    combined_reasons = "; ".join(text for _, text in failed_reasons)
    return ("ineligible", "MULTIPLE_RULES_FAILED", combined_reasons)


def get_active_lender_policies(db: Session) -> List[LenderPolicy]:
    """Retrieve all active lender underwriting policies in deterministic lender_code order.

    Raises:
        MatchingConfigurationError: If no active policies exist or if multiple active
            versions exist for any single lender code.
    """
    policies = (
        db.query(LenderPolicy)
        .filter(LenderPolicy.is_active == True)  # noqa: E712
        .order_by(LenderPolicy.lender_code.asc())
        .all()
    )

    if not policies:
        raise MatchingConfigurationError(
            "No active lender underwriting policies are configured in the marketplace."
        )

    # Check for multiple active policy versions per lender_code
    seen_codes = set()
    for p in policies:
        if p.lender_code in seen_codes:
            raise MatchingConfigurationError(
                f"Multiple active policy versions detected for lender '{p.lender_code}'. "
                "Active lender policy configuration is ambiguous."
            )
        seen_codes.add(p.lender_code)

    return policies


def run_matching(
    db: Session,
    customer_id: int,
    application_id: int,
) -> MatchRun:
    """Execute deterministic multi-lender eligibility matching for an owned loan application.

    Enforces:
    - Ownership verification (application owned by authenticated customer).
    - Status verification (application in 'draft' or 'matched' status).
    - Consent verification (both required current notice versions granted).
    - PostgreSQL row-level locking via SELECT ... FOR UPDATE.
    - Sequential run numbering per application.
    - Deterministic per-lender policy evaluation.
    - Atomic transaction commitment (rollback on failure).
    """
    try:
        # Acquire row-level lock on the LoanApplication
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

        # Allow matching only when application status is 'draft' or 'matched'
        if app.status not in {"draft", "matched"}:
            raise MatchingStatusConflictError(
                f"Application {application_id} in status '{app.status}' cannot be matched. "
                "Matching is permitted only when application status is 'draft' or 'matched'."
            )

        # Verify active required consents
        if not has_required_active_consents(db, app.id):
            missing = get_missing_required_consents(db, app.id)
            raise MatchingConsentConflictError(
                f"Matching requires active granted consent for all mandatory purposes. Missing: {missing}",
                missing_purposes=missing,
            )

        # Resolve primary consent reference for MatchRun (eligibility_matching)
        current_ver = get_current_version(PURPOSE_ELIGIBILITY_MATCHING)
        eligibility_consent = (
            db.query(Consent)
            .filter(
                Consent.application_id == app.id,
                Consent.purpose == PURPOSE_ELIGIBILITY_MATCHING,
                Consent.notice_version == current_ver,
                Consent.status == "granted",
            )
            .first()
        )

        if eligibility_consent is None:
            missing = get_missing_required_consents(db, app.id)
            raise MatchingConsentConflictError(
                "Primary eligibility matching consent record could not be resolved.",
                missing_purposes=missing,
            )

        # Load active lender underwriting policies
        policies = get_active_lender_policies(db)

        # Determine next sequential run number holding the row lock
        max_run = (
            db.query(func.max(MatchRun.run_number))
            .filter(MatchRun.application_id == app.id)
            .scalar()
        )
        next_run_number = (max_run or 0) + 1

        now_utc = datetime.now(timezone.utc)

        # Create MatchRun
        match_run = MatchRun(
            application_id=app.id,
            consent_id=eligibility_consent.id,
            run_number=next_run_number,
            status="started",
            started_at=now_utc,
            completed_at=None,
        )
        db.add(match_run)
        app.status = "matching"
        db.flush()

        # Evaluate each active policy and record decision
        for policy in policies:
            decision_status, reason_code, reason_text = evaluate_lender_policy(app, policy)
            decision = LenderDecision(
                match_run_id=match_run.id,
                lender_policy_id=policy.id,
                policy_version_snapshot=policy.policy_version,
                decision_status=decision_status,
                exclusion_reason_code=reason_code,
                exclusion_reason=reason_text,
                evaluated_at=datetime.now(timezone.utc),
            )
            db.add(decision)

        # Mark match run completed and application matched
        match_run.status = "completed"
        match_run.completed_at = datetime.now(timezone.utc)
        app.status = "matched"

        db.commit()

        # Re-fetch match run with decisions and policy eagerly loaded
        refreshed = (
            db.query(MatchRun)
            .options(
                joinedload(MatchRun.decisions).joinedload(LenderDecision.lender_policy)
            )
            .filter(MatchRun.id == match_run.id)
            .one()
        )
        return refreshed

    except (
        ApplicationNotFoundError,
        MatchingStatusConflictError,
        MatchingConsentConflictError,
        MatchingConfigurationError,
    ):
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise MatchingConcurrencyConflictError(
            "Concurrent matching execution conflict detected. Please retry."
        ) from exc
    except Exception:
        db.rollback()
        raise


def list_match_run_history(
    db: Session,
    customer_id: int,
    application_id: int,
) -> MatchRunSummaryResponse:
    """Retrieve full chronological matching history for an owned loan application."""
    app = get_customer_application(db, customer_id=customer_id, application_id=application_id)
    if app is None:
        raise ApplicationNotFoundError(
            f"Loan application {application_id} not found or not owned by customer."
        )

    runs = (
        db.query(MatchRun)
        .options(
            joinedload(MatchRun.decisions).joinedload(LenderDecision.lender_policy)
        )
        .filter(MatchRun.application_id == application_id)
        .order_by(MatchRun.run_number.asc())
        .all()
    )

    return MatchRunSummaryResponse(
        total_runs=len(runs),
        runs=[MatchRunResponse.model_validate(r) for r in runs],
    )
