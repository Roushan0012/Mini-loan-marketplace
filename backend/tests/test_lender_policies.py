from decimal import Decimal
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seed_lender_policies import INITIAL_LENDER_POLICIES, seed_lender_policies
from app.models.lender_policy import LenderPolicy
from app.schemas.lender_policy import ALLOWED_WORK_TYPES, LenderPolicyRules

TEST_LENDER_CODES = ["APEX_FINANCIAL", "HORIZON_CREDIT", "STERLING_LOANS", "MISMATCH_LENDER"]


@pytest.fixture(autouse=True)
def clean_test_policies(db_session: Session):
    """Ensure test lender policies are isolated and cleaned up before and after each test."""
    db_session.query(LenderPolicy).filter(
        LenderPolicy.lender_code.in_(TEST_LENDER_CODES)
    ).delete(synchronize_session=False)
    db_session.commit()
    yield
    db_session.query(LenderPolicy).filter(
        LenderPolicy.lender_code.in_(TEST_LENDER_CODES)
    ).delete(synchronize_session=False)
    db_session.commit()


# ---------------------------------------------------------------------------
# Schema Validation Tests
# ---------------------------------------------------------------------------


def test_valid_policy_json_parses_successfully():
    """1. Valid policy JSON parses successfully."""
    valid_data = {
        "min_age": 21,
        "min_monthly_income": "25000.00",
        "allowed_work_types": ["salaried", "self_employed"],
    }
    rules = LenderPolicyRules.model_validate(valid_data)
    assert rules.min_age == 21
    assert rules.min_monthly_income == Decimal("25000.00")
    assert rules.allowed_work_types == ["salaried", "self_employed"]


def test_invalid_age_is_rejected():
    """2. Invalid age is rejected (<= 0 or > 100)."""
    with pytest.raises(ValidationError):
        LenderPolicyRules(
            min_age=0,
            min_monthly_income=Decimal("25000.00"),
            allowed_work_types=["salaried"],
        )

    with pytest.raises(ValidationError):
        LenderPolicyRules(
            min_age=-5,
            min_monthly_income=Decimal("25000.00"),
            allowed_work_types=["salaried"],
        )

    with pytest.raises(ValidationError):
        LenderPolicyRules(
            min_age=101,
            min_monthly_income=Decimal("25000.00"),
            allowed_work_types=["salaried"],
        )


def test_negative_income_is_rejected():
    """3. Negative income is rejected."""
    with pytest.raises(ValidationError):
        LenderPolicyRules(
            min_age=25,
            min_monthly_income=Decimal("-1.00"),
            allowed_work_types=["salaried"],
        )


def test_unsupported_work_type_is_rejected():
    """4. Unsupported work type is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        LenderPolicyRules(
            min_age=25,
            min_monthly_income=Decimal("30000.00"),
            allowed_work_types=["freelancer"],
        )
    assert "Invalid work type 'freelancer'" in str(exc_info.value)


def test_empty_allowed_work_types_is_rejected():
    """5. Empty allowed_work_types is rejected."""
    with pytest.raises(ValidationError):
        LenderPolicyRules(
            min_age=25,
            min_monthly_income=Decimal("30000.00"),
            allowed_work_types=[],
        )


def test_duplicate_work_types_are_rejected():
    """6. Duplicate work types are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        LenderPolicyRules(
            min_age=25,
            min_monthly_income=Decimal("30000.00"),
            allowed_work_types=["salaried", "salaried"],
        )
    assert "Duplicate work type 'salaried'" in str(exc_info.value)

    # Also test case-insensitive duplicate
    with pytest.raises(ValidationError) as exc_info2:
        LenderPolicyRules(
            min_age=25,
            min_monthly_income=Decimal("30000.00"),
            allowed_work_types=["Salaried", "salaried"],
        )
    assert "Duplicate work type 'salaried'" in str(exc_info2.value)


def test_extra_json_keys_are_rejected():
    """7. Extra JSON keys are rejected."""
    raw_data = {
        "min_age": 21,
        "min_monthly_income": "25000.00",
        "allowed_work_types": ["salaried"],
        "unexpected_field": "disallowed",
    }
    with pytest.raises(ValidationError) as exc_info:
        LenderPolicyRules.model_validate(raw_data)
    assert "extra_forbidden" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Seed Configuration Tests
# ---------------------------------------------------------------------------


def test_exactly_three_initial_lender_definitions():
    """8. Exactly three initial lender definitions exist in seed configuration."""
    assert len(INITIAL_LENDER_POLICIES) == 3


def test_correct_lender_codes_are_used():
    """9. Correct lender codes are used."""
    expected_codes = {"APEX_FINANCIAL", "HORIZON_CREDIT", "STERLING_LOANS"}
    actual_codes = {p["lender_code"] for p in INITIAL_LENDER_POLICIES}
    assert actual_codes == expected_codes


def test_correct_policy_versions_are_used():
    """10. Correct policy versions are used."""
    for p in INITIAL_LENDER_POLICIES:
        assert p["policy_version"] == "v1.0"
        assert p["is_active"] is True
        # Verify rules parse cleanly
        LenderPolicyRules.model_validate(p["rules"])


# ---------------------------------------------------------------------------
# Seeding Execution and Idempotency Tests
# ---------------------------------------------------------------------------


def test_repeated_seeding_does_not_create_duplicates(db_session: Session):
    """11. Repeated seeding does not create duplicate rows."""
    # First seeding run
    res1 = seed_lender_policies(session=db_session, enforce_dev_guard=False)
    assert len(res1) == 3
    assert all(status == "inserted" for _, _, status in res1)

    # Verify count in database
    count1 = db_session.query(LenderPolicy).filter(
        LenderPolicy.lender_code.in_(TEST_LENDER_CODES)
    ).count()
    assert count1 == 3

    # Second seeding run
    res2 = seed_lender_policies(session=db_session, enforce_dev_guard=False)
    assert len(res2) == 3
    assert all(status == "skipped" for _, _, status in res2)

    # Verify count remains exactly 3
    count2 = db_session.query(LenderPolicy).filter(
        LenderPolicy.lender_code.in_(TEST_LENDER_CODES)
    ).count()
    assert count2 == 3


def test_existing_matching_policy_records_are_skipped_unchanged(db_session: Session):
    """12. Existing matching policy records are skipped unchanged."""
    seed_lender_policies(session=db_session, enforce_dev_guard=False)

    # Record created_at before repeat
    stmt = select(LenderPolicy).where(
        LenderPolicy.lender_code == "APEX_FINANCIAL",
        LenderPolicy.policy_version == "v1.0",
    )
    p_before = db_session.execute(stmt).scalar_one()
    id_before = p_before.id
    rules_before = p_before.rules

    res = seed_lender_policies(session=db_session, enforce_dev_guard=False)
    assert ("APEX_FINANCIAL", "v1.0", "skipped") in res

    p_after = db_session.execute(stmt).scalar_one()
    assert p_after.id == id_before
    assert p_after.rules == rules_before


def test_mismatched_existing_policy_causes_safe_failure(db_session: Session):
    """13. Mismatched existing policy definitions cause a safe failure without overwrite."""
    # Insert APEX_FINANCIAL with different rules
    mismatched_policy = LenderPolicy(
        lender_code="APEX_FINANCIAL",
        lender_name="Apex Financial",
        policy_version="v1.0",
        rules={
            "min_age": 30,  # Different from expected 21
            "min_monthly_income": "99999.00",
            "allowed_work_types": ["salaried"],
        },
        is_active=True,
    )
    db_session.add(mismatched_policy)
    db_session.commit()

    with pytest.raises(ValueError) as exc_info:
        seed_lender_policies(session=db_session, enforce_dev_guard=False)

    assert "Seed mismatch for APEX_FINANCIAL v1.0" in str(exc_info.value)

    # Verify existing row was not overwritten or corrupted
    stmt = select(LenderPolicy).where(
        LenderPolicy.lender_code == "APEX_FINANCIAL",
        LenderPolicy.policy_version == "v1.0",
    )
    current = db_session.execute(stmt).scalar_one()
    assert current.rules["min_age"] == 30
    assert current.rules["min_monthly_income"] == "99999.00"


def test_seed_transaction_rolls_back_on_failure(db_session: Session):
    """14. Seed transaction rolls back on failure."""
    # Pre-insert a conflicting STERLING_LOANS record with invalid metadata
    conflicting = LenderPolicy(
        lender_code="STERLING_LOANS",
        lender_name="Different Conflicting Name",
        policy_version="v1.0",
        rules={
            "min_age": 25,
            "min_monthly_income": "40000.00",
            "allowed_work_types": ["salaried", "self_employed"],
        },
        is_active=True,
    )
    db_session.add(conflicting)
    db_session.commit()

    # APEX_FINANCIAL and HORIZON_CREDIT would be evaluated first in the loop
    # When STERLING_LOANS raises ValueError, the transaction rolls back
    with pytest.raises(ValueError):
        seed_lender_policies(session=db_session, enforce_dev_guard=False)

    # Ensure APEX_FINANCIAL was NOT committed due to rollback
    apex = db_session.execute(
        select(LenderPolicy).where(LenderPolicy.lender_code == "APEX_FINANCIAL")
    ).scalar_one_or_none()
    assert apex is None


def test_safety_guard_rejects_non_dev_environment(db_session: Session):
    """15. Safety guard blocks seeding when database or environment is not local development."""
    # Since tests run with POSTGRES_DB='mini_loan_marketplace_test',
    # enforce_dev_guard=True must reject execution
    with pytest.raises(RuntimeError) as exc_info:
        seed_lender_policies(session=db_session, enforce_dev_guard=True)
    assert "Safety guard violation" in str(exc_info.value)
