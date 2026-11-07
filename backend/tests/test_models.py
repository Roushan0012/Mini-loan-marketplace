import pytest
from sqlalchemy import BigInteger
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import configure_mappers

from app.db.base import Base
import app.models  # Registers all 11 models in Base.metadata
from app.models import (
    Consent,
    Lead,
    LeadAssignment,
    LenderDecision,
    LenderEvent,
    LenderPolicy,
    LoanApplication,
    MatchRun,
    Offer,
    OfferSubmission,
    User,
)


@pytest.fixture(scope="module", autouse=True)
def setup_mappers():
    """Ensure all SQLAlchemy relationships and mappers are configured."""
    configure_mappers()


def test_expected_tables_in_metadata():
    """Verify that all eleven expected table names are registered in Base.metadata."""
    expected_tables = {
        "users",
        "leads",
        "lead_assignments",
        "loan_applications",
        "consents",
        "lender_policies",
        "match_runs",
        "lender_decisions",
        "offers",
        "offer_submissions",
        "lender_events",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables == actual_tables, (
        f"Mismatch in registered tables. Expected: {expected_tables}, got: {actual_tables}"
    )


def test_primary_keys_defined():
    """Verify that every foundational and workflow model defines an 'id' BigInteger primary key."""
    expected_tables = [
        "users",
        "leads",
        "lead_assignments",
        "loan_applications",
        "consents",
        "lender_policies",
        "match_runs",
        "lender_decisions",
        "offers",
        "offer_submissions",
        "lender_events",
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
    la_fks = {fk.target_fullname for fk in tables["lead_assignments"].foreign_keys}
    assert "leads.id" in la_fks, "lead_assignments.lead_id must reference leads.id"
    assert "users.id" in la_fks, "lead_assignments.caller_id must reference users.id"

    # loan_applications foreign keys
    app_fks = {fk.target_fullname for fk in tables["loan_applications"].foreign_keys}
    assert "users.id" in app_fks, "loan_applications.customer_id must reference users.id"
    assert "leads.id" in app_fks, "loan_applications.lead_id must reference leads.id"

    # consents foreign keys
    consent_fks = {fk.target_fullname for fk in tables["consents"].foreign_keys}
    assert "loan_applications.id" in consent_fks, (
        "consents.application_id must reference loan_applications.id"
    )

    # match_runs foreign keys
    mr_fks = {fk.target_fullname for fk in tables["match_runs"].foreign_keys}
    assert "loan_applications.id" in mr_fks, (
        "match_runs.application_id must reference loan_applications.id"
    )
    assert "consents.id" in mr_fks, "match_runs.consent_id must reference consents.id"

    # lender_decisions foreign keys
    ld_fks = {fk.target_fullname for fk in tables["lender_decisions"].foreign_keys}
    assert "match_runs.id" in ld_fks, (
        "lender_decisions.match_run_id must reference match_runs.id"
    )
    assert "lender_policies.id" in ld_fks, (
        "lender_decisions.lender_policy_id must reference lender_policies.id"
    )

    # offers foreign keys
    offer_fks = {fk.target_fullname for fk in tables["offers"].foreign_keys}
    assert "lender_decisions.id" in offer_fks, (
        "offers.lender_decision_id must reference lender_decisions.id"
    )

    # offer_submissions foreign keys
    os_fks = {fk.target_fullname for fk in tables["offer_submissions"].foreign_keys}
    assert "loan_applications.id" in os_fks, (
        "offer_submissions.application_id must reference loan_applications.id"
    )
    assert "offers.id" in os_fks, "offer_submissions.offer_id must reference offers.id"

    # lender_events foreign keys
    le_fks = {fk.target_fullname for fk in tables["lender_events"].foreign_keys}
    assert "offer_submissions.id" in le_fks, (
        "lender_events.submission_id must reference offer_submissions.id"
    )


def test_unique_constraints_present():
    """Verify unique constraints on required columns and composite keys."""
    tables = Base.metadata.tables

    # users: email unique and password_hash required
    assert tables["users"].c.email.unique, "users.email must be unique"
    assert "password_hash" in tables["users"].c, "users.password_hash column must exist"
    assert not tables["users"].c.password_hash.nullable, "users.password_hash must be NOT NULL"

    # leads.synthetic_reference must be unique
    assert tables["leads"].c.synthetic_reference.unique, (
        "leads.synthetic_reference must be unique"
    )

    # lead_assignments.lead_id must be unique (one current assignment per lead)
    assert tables["lead_assignments"].c.lead_id.unique, (
        "lead_assignments.lead_id must be unique"
    )

    # consents: unique composite constraint on (application_id, purpose, notice_version)
    consent_ucs = [
        set(c.name for c in uc.columns)
        for uc in tables["consents"].constraints
        if hasattr(uc, "columns") and getattr(uc, "name", "") and "uq" in uc.name.lower()
    ]
    assert {"application_id", "purpose", "notice_version"} in consent_ucs

    # lender_policies: unique composite constraint on (lender_code, policy_version)
    policy_ucs = [
        set(c.name for c in uc.columns)
        for uc in tables["lender_policies"].constraints
        if hasattr(uc, "columns") and getattr(uc, "name", "") and "uq" in uc.name.lower()
    ]
    assert {"lender_code", "policy_version"} in policy_ucs

    # match_runs: unique composite constraint on (application_id, run_number)
    mr_ucs = [
        set(c.name for c in uc.columns)
        for uc in tables["match_runs"].constraints
        if hasattr(uc, "columns") and getattr(uc, "name", "") and "uq" in uc.name.lower()
    ]
    assert {"application_id", "run_number"} in mr_ucs

    # lender_decisions: unique composite constraint on (match_run_id, lender_policy_id)
    ld_ucs = [
        set(c.name for c in uc.columns)
        for uc in tables["lender_decisions"].constraints
        if hasattr(uc, "columns") and getattr(uc, "name", "") and "uq" in uc.name.lower()
    ]
    assert {"match_run_id", "lender_policy_id"} in ld_ucs

    # offers.lender_decision_id must be unique
    assert tables["offers"].c.lender_decision_id.unique, (
        "offers.lender_decision_id must be unique"
    )

    # offer_submissions unique fields
    os_table = tables["offer_submissions"]
    assert os_table.c.application_id.unique, "offer_submissions.application_id must be unique"
    assert os_table.c.offer_id.unique, "offer_submissions.offer_id must be unique"
    assert os_table.c.idempotency_key.unique, "offer_submissions.idempotency_key must be unique"

    # lender_events.event_id must be unique
    assert tables["lender_events"].c.event_id.unique, "lender_events.event_id must be unique"


def test_check_constraints_present():
    """Verify named CHECK constraints for allowed values, positive bounds, and business rules."""
    tables = Base.metadata.tables

    # users: role in ('customer', 'caller', 'admin')
    user_ck = [ck.name for ck in tables["users"].constraints if hasattr(ck, "sqltext")]
    assert "ck_users_role" in user_ck

    # consents: status in ('pending', 'granted', 'revoked')
    consent_ck = [ck.name for ck in tables["consents"].constraints if hasattr(ck, "sqltext")]
    assert "ck_consents_status" in consent_ck

    # leads: positive age, non-negative income, positive requested amount
    leads_ck = [ck.name for ck in tables["leads"].constraints if hasattr(ck, "sqltext")]
    assert "ck_leads_age_positive" in leads_ck
    assert "ck_leads_monthly_income_non_negative" in leads_ck
    assert "ck_leads_requested_amount_positive" in leads_ck

    # loan_applications: positive age, non-negative income, positive requested amount
    app_ck = [ck.name for ck in tables["loan_applications"].constraints if hasattr(ck, "sqltext")]
    assert "ck_loan_applications_age_positive" in app_ck
    assert "ck_loan_applications_monthly_income_non_negative" in app_ck
    assert "ck_loan_applications_requested_amount_positive" in app_ck

    # match_runs: status in ('started', 'completed', 'failed')
    mr_ck = [ck.name for ck in tables["match_runs"].constraints if hasattr(ck, "sqltext")]
    assert "ck_match_runs_status" in mr_ck

    # lender_decisions: status and strengthened exclusion rules
    ld_ck_map = {ck.name: str(ck.sqltext) for ck in tables["lender_decisions"].constraints if hasattr(ck, "sqltext")}
    assert "ck_lender_decisions_decision_status" in ld_ck_map
    assert "ck_lender_decisions_decision_exclusion_rules" in ld_ck_map
    exclusion_sql = ld_ck_map["ck_lender_decisions_decision_exclusion_rules"]
    assert "exclusion_reason IS NULL" in exclusion_sql
    assert "exclusion_reason_code IS NULL" in exclusion_sql
    assert "exclusion_reason_code IS NOT NULL" in exclusion_sql

    # offers: financial positive bounds and status
    offer_ck = [ck.name for ck in tables["offers"].constraints if hasattr(ck, "sqltext")]
    assert "ck_offers_loan_amount_positive" in offer_ck
    assert "ck_offers_apr_non_negative" in offer_ck
    assert "ck_offers_term_months_positive" in offer_ck
    assert "ck_offers_monthly_installment_positive" in offer_ck
    assert "ck_offers_status" in offer_ck

    # offer_submissions: status in allowed values
    os_ck = [ck.name for ck in tables["offer_submissions"].constraints if hasattr(ck, "sqltext")]
    assert "ck_offer_submissions_status" in os_ck

    # lender_events: processing_status and sequence_number_positive
    le_ck = [ck.name for ck in tables["lender_events"].constraints if hasattr(ck, "sqltext")]
    assert "ck_lender_events_processing_status" in le_ck
    assert "ck_lender_events_sequence_number_positive" in le_ck


def test_model_relationships():
    """Verify bidirectional relationship mapping across all eleven entities."""
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
    assert hasattr(LoanApplication, "match_runs")
    assert hasattr(LoanApplication, "offer_submissions")

    # Consent relationships
    assert hasattr(Consent, "application")
    assert hasattr(Consent, "match_runs")

    # LenderPolicy relationships
    assert hasattr(LenderPolicy, "decisions")

    # MatchRun relationships
    assert hasattr(MatchRun, "application")
    assert hasattr(MatchRun, "consent")
    assert hasattr(MatchRun, "decisions")

    # LenderDecision relationships
    assert hasattr(LenderDecision, "match_run")
    assert hasattr(LenderDecision, "lender_policy")
    assert hasattr(LenderDecision, "offer")

    # Offer relationships
    assert hasattr(Offer, "lender_decision")
    assert hasattr(Offer, "submission")

    # OfferSubmission relationships
    assert hasattr(OfferSubmission, "application")
    assert hasattr(OfferSubmission, "offer")
    assert hasattr(OfferSubmission, "events")

    # LenderEvent relationships
    assert hasattr(LenderEvent, "submission")


def test_audit_history_relationships_no_delete_cascade():
    """Verify that historical and audit relationships do NOT have delete or delete-orphan cascades."""
    # LoanApplication audit relationships: consents, match_runs, offer_submissions
    app_mapper = inspect(LoanApplication)
    for rel_name in ("consents", "match_runs", "offer_submissions"):
        rel = app_mapper.relationships[rel_name]
        cascade = rel.cascade
        assert not cascade.delete, f"LoanApplication.{rel_name} must not have delete cascade"
        assert not cascade.delete_orphan, f"LoanApplication.{rel_name} must not have delete-orphan cascade"

    # MatchRun historical decisions
    mr_mapper = inspect(MatchRun)
    rel = mr_mapper.relationships["decisions"]
    assert not rel.cascade.delete, "MatchRun.decisions must not have delete cascade"
    assert not rel.cascade.delete_orphan, "MatchRun.decisions must not have delete-orphan cascade"

    # OfferSubmission webhook event ledger
    sub_mapper = inspect(OfferSubmission)
    rel = sub_mapper.relationships["events"]
    assert not rel.cascade.delete, "OfferSubmission.events must not have delete cascade"
    assert not rel.cascade.delete_orphan, "OfferSubmission.events must not have delete-orphan cascade"
