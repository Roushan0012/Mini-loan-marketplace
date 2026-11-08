"""add mock offer terms to lender policies

Revision ID: 62f763cdf956
Revises: ab9b854a29f8
Create Date: 2026-11-08 10:06:58.596052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '62f763cdf956'
down_revision: Union[str, Sequence[str], None] = 'ab9b854a29f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Canonical mock offer terms for fictional training policies
MOCK_OFFER_TERMS_BACKFILL = [
    (
        "APEX_FINANCIAL",
        "v1.0",
        {
            "apr_percent": "18.0000",
            "term_months": 24,
            "max_loan_amount": "250000.00",
        },
    ),
    (
        "HORIZON_CREDIT",
        "v1.0",
        {
            "apr_percent": "16.0000",
            "term_months": 36,
            "max_loan_amount": "300000.00",
        },
    ),
    (
        "STERLING_LOANS",
        "v1.0",
        {
            "apr_percent": "20.0000",
            "term_months": 18,
            "max_loan_amount": "150000.00",
        },
    ),
]


def upgrade() -> None:
    """Upgrade schema: add offer_terms column and backfill known initial mock policies."""
    # 1. Add nullable JSONB column
    op.add_column(
        'lender_policies',
        sa.Column('offer_terms', JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 2. Backfill only matching known fictional v1.0 training policies where offer_terms IS NULL
    lender_policies_table = sa.table(
        'lender_policies',
        sa.column('lender_code', sa.String),
        sa.column('policy_version', sa.String),
        sa.column('offer_terms', JSONB),
    )

    for lender_code, version, terms in MOCK_OFFER_TERMS_BACKFILL:
        op.execute(
            lender_policies_table.update()
            .where(
                sa.and_(
                    lender_policies_table.c.lender_code == lender_code,
                    lender_policies_table.c.policy_version == version,
                    lender_policies_table.c.offer_terms.is_(None),
                )
            )
            .values(offer_terms=terms)
        )


def downgrade() -> None:
    """Downgrade schema: remove offer_terms column."""
    op.drop_column('lender_policies', 'offer_terms')
