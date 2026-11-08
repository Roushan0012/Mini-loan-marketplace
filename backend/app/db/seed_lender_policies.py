import sys
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.lender_policy import LenderPolicy
from app.schemas.lender_policy import LenderPolicyRules
from app.schemas.offer import MockOfferTerms

INITIAL_LENDER_POLICIES: List[Dict[str, Any]] = [
    {
        "lender_code": "APEX_FINANCIAL",
        "lender_name": "Apex Financial",
        "policy_version": "v1.0",
        "is_active": True,
        "rules": {
            "min_age": 21,
            "min_monthly_income": "25000.00",
            "allowed_work_types": [
                "salaried",
                "self_employed",
            ],
        },
        "offer_terms": {
            "apr_percent": "18.0000",
            "term_months": 24,
            "max_loan_amount": "250000.00",
        },
    },
    {
        "lender_code": "HORIZON_CREDIT",
        "lender_name": "Horizon Credit",
        "policy_version": "v1.0",
        "is_active": True,
        "rules": {
            "min_age": 23,
            "min_monthly_income": "30000.00",
            "allowed_work_types": [
                "salaried",
            ],
        },
        "offer_terms": {
            "apr_percent": "16.0000",
            "term_months": 36,
            "max_loan_amount": "300000.00",
        },
    },
    {
        "lender_code": "STERLING_LOANS",
        "lender_name": "Sterling Loans",
        "policy_version": "v1.0",
        "is_active": True,
        "rules": {
            "min_age": 25,
            "min_monthly_income": "40000.00",
            "allowed_work_types": [
                "salaried",
                "self_employed",
            ],
        },
        "offer_terms": {
            "apr_percent": "20.0000",
            "term_months": 18,
            "max_loan_amount": "150000.00",
        },
    },
]


def seed_lender_policies(
    session: Optional[Session] = None,
    enforce_dev_guard: bool = True,
) -> List[Tuple[str, str, str]]:
    """Seed initial fictional lender underwriting policies idempotently.

    Args:
        session: Optional SQLAlchemy session. If None, creates a new SessionLocal.
        enforce_dev_guard: When True, enforces that ENVIRONMENT == 'development'
            and POSTGRES_DB == 'mini_loan_marketplace'.

    Returns:
        List of tuples: (lender_code, policy_version, result_status) where
        result_status is 'inserted' or 'skipped'.

    Raises:
        RuntimeError: If safety guards fail.
        ValueError: If existing policy has mismatched definitions or rules.
    """
    if enforce_dev_guard:
        if settings.ENVIRONMENT != "development" or settings.POSTGRES_DB != "mini_loan_marketplace":
            raise RuntimeError(
                f"Safety guard violation: Seeding is only permitted when "
                f"ENVIRONMENT='development' and POSTGRES_DB='mini_loan_marketplace'. "
                f"Current settings: ENVIRONMENT='{settings.ENVIRONMENT}', "
                f"POSTGRES_DB='{settings.POSTGRES_DB}'."
            )

    close_session = False
    db = session
    if db is None:
        db = SessionLocal()
        close_session = True

    results: List[Tuple[str, str, str]] = []

    try:
        for policy_def in INITIAL_LENDER_POLICIES:
            lender_code = policy_def["lender_code"]
            policy_version = policy_def["policy_version"]
            expected_name = policy_def["lender_name"]
            expected_rules_model = LenderPolicyRules.model_validate(policy_def["rules"])
            expected_rules_dict = expected_rules_model.model_dump(mode="json")

            expected_terms_dict = None
            if "offer_terms" in policy_def and policy_def["offer_terms"] is not None:
                expected_terms_model = MockOfferTerms.model_validate(policy_def["offer_terms"])
                expected_terms_dict = expected_terms_model.model_dump(mode="json")

            # Check if record exists
            stmt = select(LenderPolicy).where(
                LenderPolicy.lender_code == lender_code,
                LenderPolicy.policy_version == policy_version,
            )
            existing = db.execute(stmt).scalar_one_or_none()

            if existing is not None:
                # Check for metadata, status, rules, and offer terms mismatch
                expected_is_active = policy_def.get("is_active", True)
                mismatch_reasons = []
                if existing.lender_name != expected_name:
                    mismatch_reasons.append(
                        f"lender_name mismatch (existing: '{existing.lender_name}', expected: '{expected_name}')"
                    )
                if existing.is_active != expected_is_active:
                    mismatch_reasons.append(
                        f"is_active mismatch (existing: {existing.is_active}, expected: {expected_is_active})"
                    )

                try:
                    existing_rules_model = LenderPolicyRules.model_validate(existing.rules)
                    existing_rules_dict = existing_rules_model.model_dump(mode="json")
                    if existing_rules_dict != expected_rules_dict:
                        mismatch_reasons.append(
                            f"rules mismatch (existing: {existing_rules_dict}, expected: {expected_rules_dict})"
                        )
                except Exception as exc:
                    mismatch_reasons.append(f"existing rules invalid: {exc}")

                if expected_terms_dict is not None:
                    if existing.offer_terms is None:
                        mismatch_reasons.append(
                            "offer_terms mismatch (existing is None, expected offer terms configured)"
                        )
                    else:
                        try:
                            existing_terms_model = MockOfferTerms.model_validate(existing.offer_terms)
                            existing_terms_dict = existing_terms_model.model_dump(mode="json")
                            if existing_terms_dict != expected_terms_dict:
                                mismatch_reasons.append(
                                    f"offer_terms mismatch (existing: {existing_terms_dict}, expected: {expected_terms_dict})"
                                )
                        except Exception as exc:
                            mismatch_reasons.append(f"existing offer_terms invalid: {exc}")
                elif existing.offer_terms is not None:
                    mismatch_reasons.append("offer_terms mismatch (existing has terms, expected None)")

                if mismatch_reasons:
                    raise ValueError(
                        f"Seed mismatch for {lender_code} {policy_version}: {'; '.join(mismatch_reasons)}"
                    )

                results.append((lender_code, policy_version, "skipped"))
            else:
                # Insert new record
                new_policy = LenderPolicy(
                    lender_code=lender_code,
                    lender_name=expected_name,
                    policy_version=policy_version,
                    rules=expected_rules_dict,
                    offer_terms=expected_terms_dict,
                    is_active=policy_def.get("is_active", True),
                )
                db.add(new_policy)
                results.append((lender_code, policy_version, "inserted"))

        db.commit()
        return results
    except Exception:
        db.rollback()
        raise
    finally:
        if close_session:
            db.close()


def main() -> None:
    try:
        results = seed_lender_policies(enforce_dev_guard=True)
        for code, ver, res in results:
            print(f"{code} {ver}: {res}")
    except Exception as e:
        print(f"Error seeding lender policies: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
