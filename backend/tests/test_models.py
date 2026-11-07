import pytest
from sqlalchemy import BigInteger
from sqlalchemy.orm import configure_mappers

from app.db.base import Base
import app.models  # Registers all models in Base.metadata
from app.models import Consent, Lead, LeadAssignment, LoanApplication, User


@pytest.fixture(scope="module", autouse=True)
def setup_mappers():
    """Ensure all SQLAlchemy relationships and mappers are configured."""
    configure_mappers()


def test_expected_tables_in_metadata():
    """Verify that all five expected table names are registered in Base.metadata."""
    expected_tables = {
        "users",
        "leads",
        "lead_assignments",
        "loan_applications",
        "consents",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), (
        f"Missing tables: {expected_tables - actual_tables}"
    )


def test_primary_keys_defined():
    """Verify that every foundational model defines an 'id' BigInteger primary key."""
    expected_tables = [
        "users",
        "leads",
        "lead_assignments",
        "loan_applications",
        "consents",
    ]
    for table_name in expected_tables:
        table = Base.metadata.tables[table_name]
        assert "id" in table.c, f"Table '{table_name}' does not have an 'id' column."
        pk_col = table.c.id
        assert pk_col.primary_key, f"Column 'id' on '{table_name}' is not marked as primary key."
        assert isinstance(pk_col.type, BigInteger), (
            f"Primary key 'id' on '{table_name}' is not BigInteger."
        )


def test_foreign_keys_present():
    """Verify that all required foreign key references exist across models."""
    tables = Base.metadata.tables

    # lead_assignments foreign keys
    la_table = tables["lead_assignments"]
    la_fks = {fk.target_fullname for fk in la_table.foreign_keys}
    assert "leads.id" in la_fks, "lead_assignments.lead_id must reference leads.id"
    assert "users.id" in la_fks, "lead_assignments.caller_id must reference users.id"

    # loan_applications foreign keys
    app_table = tables["loan_applications"]
    app_fks = {fk.target_fullname for fk in app_table.foreign_keys}
    assert "users.id" in app_fks, "loan_applications.customer_id must reference users.id"
    assert "leads.id" in app_fks, "loan_applications.lead_id must reference leads.id"

    # consents foreign keys
    consent_table = tables["consents"]
    consent_fks = {fk.target_fullname for fk in consent_table.foreign_keys}
    assert "loan_applications.id" in consent_fks, (
        "consents.application_id must reference loan_applications.id"
    )


def test_unique_constraints_present():
    """Verify unique constraints on required columns and composite keys."""
    tables = Base.metadata.tables

    # users.email must be unique
    assert tables["users"].c.email.unique, "users.email must be unique"

    # leads.synthetic_reference must be unique
    assert tables["leads"].c.synthetic_reference.unique, (
        "leads.synthetic_reference must be unique"
    )

    # lead_assignments.lead_id must be unique (one current assignment per lead)
    assert tables["lead_assignments"].c.lead_id.unique, (
        "lead_assignments.lead_id must be unique"
    )

    # consents: unique composite constraint on (application_id, purpose, notice_version)
    consent_table = tables["consents"]
    unique_col_sets = [
        set(c.name for c in uc.columns) for uc in consent_table.constraints if hasattr(uc, "columns") and getattr(uc, "name", "") and "uq" in uc.name.lower()
    ]
    # Check if (application_id, purpose, notice_version) exists in unique constraints
    expected_set = {"application_id", "purpose", "notice_version"}
    found = any(expected_set == cols for cols in unique_col_sets)
    assert found, (
        f"Expected composite unique constraint on {expected_set} not found in consents constraints."
    )


def test_check_constraints_present():
    """Verify named CHECK constraints for allowed values and positive bounds."""
    tables = Base.metadata.tables

    # users: role in ('customer', 'caller', 'admin')
    user_ck_names = [ck.name for ck in tables["users"].constraints if hasattr(ck, "sqltext")]
    assert "ck_users_role" in user_ck_names, "Missing 'ck_users_role' check constraint."

    # consents: status in ('pending', 'granted', 'revoked')
    consent_ck_names = [ck.name for ck in tables["consents"].constraints if hasattr(ck, "sqltext")]
    assert "ck_consents_status" in consent_ck_names, (
        "Missing 'ck_consents_status' check constraint."
    )

    # leads: positive age, non-negative income, positive requested amount
    leads_ck_names = [ck.name for ck in tables["leads"].constraints if hasattr(ck, "sqltext")]
    assert "ck_leads_age_positive" in leads_ck_names, "Missing 'ck_leads_age_positive'"
    assert "ck_leads_monthly_income_non_negative" in leads_ck_names, (
        "Missing 'ck_leads_monthly_income_non_negative'"
    )
    assert "ck_leads_requested_amount_positive" in leads_ck_names, (
        "Missing 'ck_leads_requested_amount_positive'"
    )

    # loan_applications: positive age, non-negative income, positive requested amount
    app_ck_names = [ck.name for ck in tables["loan_applications"].constraints if hasattr(ck, "sqltext")]
    assert "ck_loan_applications_age_positive" in app_ck_names, (
        "Missing 'ck_loan_applications_age_positive'"
    )
    assert "ck_loan_applications_monthly_income_non_negative" in app_ck_names, (
        "Missing 'ck_loan_applications_monthly_income_non_negative'"
    )
    assert "ck_loan_applications_requested_amount_positive" in app_ck_names, (
        "Missing 'ck_loan_applications_requested_amount_positive'"
    )


def test_model_relationships():
    """Verify bidirectional relationship mapping across all five entities."""
    # User relationships
    assert hasattr(User, "assigned_leads")
    assert hasattr(User, "loan_applications")

    # Lead relationships
    assert hasattr(Lead, "assignment")
    assert hasattr(Lead, "loan_applications")

    # LeadAssignment relationships
    assert hasattr(LeadAssignment, "lead")
    assert hasattr(LeadAssignment, "caller")

    # LoanApplication relationships
    assert hasattr(LoanApplication, "customer")
    assert hasattr(LoanApplication, "lead")
    assert hasattr(LoanApplication, "consents")

    # Consent relationship
    assert hasattr(Consent, "application")
