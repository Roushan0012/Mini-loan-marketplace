from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.services.application_service import get_customer_application
from app.services.consent_notices import (
    get_current_version,
    get_required_purposes,
    is_current_version,
    is_valid_purpose,
)

CLOSED_APPLICATION_STATUSES = {
    "submitted",
    "accepted",
    "declined",
    "finalized",
    "timed_out",
    "failed",
}


class ConsentConflictError(ValueError):
    """Raised when an invalid consent state transition or conflict occurs."""

    pass


class ConsentValidationError(ValueError):
    """Raised when consent parameters violate registry or validation rules."""

    pass


def is_consent_change_permitted(application_status: str) -> bool:
    """Determine whether consent grant or revoke operations are allowed for an application.

    Consent modifications are permitted during all pre-submission lifecycle states
    (e.g., 'draft', 'matching', 'matched', 'offers_ready', 'offer_selected').
    Once an application is finalized or submitted, consent records are closed.
    """
    return application_status not in CLOSED_APPLICATION_STATUSES


def list_application_consents(
    db: Session,
    customer_id: int,
    application_id: int,
) -> Optional[List[Consent]]:
    """Retrieve all historical consent records for an owned loan application.

    Returns None if the application does not exist or belongs to another customer.
    """
    app = get_customer_application(db, customer_id=customer_id, application_id=application_id)
    if app is None:
        return None

    return (
        db.query(Consent)
        .filter(Consent.application_id == application_id)
        .order_by(Consent.created_at.asc(), Consent.id.asc())
        .all()
    )


def grant_application_consent(
    db: Session,
    customer_id: int,
    application_id: int,
    purpose: str,
    notice_version: str,
    accepted: bool,
) -> Tuple[Optional[Consent], bool]:
    """Grant customer consent for a specific purpose and current notice version.

    Returns:
        (consent_record, is_new):
            - (Consent, True): newly created grant (HTTP 201)
            - (Consent, False): idempotent repeat of existing active grant (HTTP 200)
            - (None, False): application not found or not owned (HTTP 404)

    Raises:
        ConsentValidationError: if purpose or version is invalid/outdated, or accepted=False.
        ConsentConflictError: if application is finalized or a revoked record exists for the same version.
    """
    app = get_customer_application(db, customer_id=customer_id, application_id=application_id)
    if app is None:
        return None, False

    if not is_consent_change_permitted(app.status):
        raise ConsentConflictError(
            f"Consent cannot be granted because application {application_id} is in closed status '{app.status}'."
        )

    if not is_valid_purpose(purpose):
        raise ConsentValidationError(f"Invalid consent purpose '{purpose}'.")

    if not is_current_version(purpose, notice_version):
        raise ConsentValidationError(
            f"Notice version '{notice_version}' is not the currently published active version for purpose '{purpose}'."
        )

    if not accepted:
        raise ConsentValidationError("Consent must be explicitly accepted (accepted=true).")

    # Check for existing record matching (application_id, purpose, notice_version)
    existing = (
        db.query(Consent)
        .filter(
            Consent.application_id == application_id,
            Consent.purpose == purpose,
            Consent.notice_version == notice_version,
        )
        .first()
    )

    now_utc = datetime.now(timezone.utc)

    if existing is not None:
        if existing.status == "granted":
            # Idempotent repeat: return active record without creating duplicate
            return existing, False
        if existing.status == "revoked":
            # Cannot re-grant against a previously revoked notice version
            raise ConsentConflictError(
                f"Consent for purpose '{purpose}' version '{notice_version}' was previously revoked. "
                "A new grant requires a newly published notice version."
            )
        # Pending transition to granted
        existing.status = "granted"
        existing.granted_at = now_utc
        existing.revoked_at = None
        try:
            db.commit()
            db.refresh(existing)
            return existing, True
        except Exception:
            db.rollback()
            raise

    # Create new consent record
    new_consent = Consent(
        application_id=application_id,
        purpose=purpose,
        notice_version=notice_version,
        status="granted",
        granted_at=now_utc,
        revoked_at=None,
    )
    db.add(new_consent)
    try:
        db.commit()
        db.refresh(new_consent)
        return new_consent, True
    except Exception:
        db.rollback()
        raise


def revoke_application_consent(
    db: Session,
    customer_id: int,
    application_id: int,
    consent_id: int,
) -> Optional[Consent]:
    """Revoke a previously granted consent record.

    Returns:
        Consent: the updated or already-revoked consent record.
        None: if application or consent record is not found or not owned.

    Raises:
        ConsentConflictError: if application is closed or consent is in an invalid state.
    """
    app = get_customer_application(db, customer_id=customer_id, application_id=application_id)
    if app is None:
        return None

    if not is_consent_change_permitted(app.status):
        raise ConsentConflictError(
            f"Consent cannot be revoked because application {application_id} is in closed status '{app.status}'."
        )

    consent = (
        db.query(Consent)
        .filter(
            Consent.id == consent_id,
            Consent.application_id == application_id,
        )
        .first()
    )
    if consent is None:
        return None

    if consent.status == "revoked":
        # Idempotent repeat of revocation
        return consent

    if consent.status != "granted":
        raise ConsentConflictError(
            f"Cannot revoke consent {consent_id} in state '{consent.status}'."
        )

    consent.status = "revoked"
    consent.revoked_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(consent)
        return consent
    except Exception:
        db.rollback()
        raise


def has_required_active_consents(db: Session, application_id: int) -> bool:
    """Verify whether an application has active 'granted' consent for all required purposes with current versions."""
    required = get_required_purposes()
    if not required:
        return True

    active_consents = (
        db.query(Consent)
        .filter(
            Consent.application_id == application_id,
            Consent.status == "granted",
        )
        .all()
    )

    active_map = {c.purpose: c.notice_version for c in active_consents}

    for purpose in required:
        current_ver = get_current_version(purpose)
        if purpose not in active_map or active_map[purpose] != current_ver:
            return False

    return True


def get_missing_required_consents(db: Session, application_id: int) -> List[str]:
    """Return a list of missing or inactive required consent purpose codes."""
    required = get_required_purposes()
    active_consents = (
        db.query(Consent)
        .filter(
            Consent.application_id == application_id,
            Consent.status == "granted",
        )
        .all()
    )

    active_map = {c.purpose: c.notice_version for c in active_consents}

    missing: List[str] = []
    for purpose in sorted(required):
        current_ver = get_current_version(purpose)
        if purpose not in active_map or active_map[purpose] != current_ver:
            missing.append(purpose)

    return missing
