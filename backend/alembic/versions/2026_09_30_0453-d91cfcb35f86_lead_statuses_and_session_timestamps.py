"""lead statuses and session timestamps

Revision ID: d91cfcb35f86
Revises: d17215abc9ab
Create Date: 2026-09-30 04:53:55.575646

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd91cfcb35f86'
down_revision: Union[str, Sequence[str], None] = 'd17215abc9ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename lead statuses to the client's pipeline and add session/status timestamps."""
    op.execute("ALTER TYPE enquiry_status RENAME VALUE 'contacted' TO 'called'")
    op.execute("ALTER TYPE enquiry_status RENAME VALUE 'quoted' TO 'quote_sent'")
    op.execute("ALTER TYPE enquiry_status RENAME VALUE 'spam' TO 'not_relevant'")
    op.execute("ALTER TYPE enquiry_status ADD VALUE IF NOT EXISTS 'site_visit' BEFORE 'quote_sent'")
    op.add_column(
        "enquiries", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "admin_users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Postgres can't drop an enum value, so rebuild the old type and map values back."""
    op.drop_column("admin_users", "password_changed_at")
    op.drop_column("enquiries", "status_changed_at")
    op.execute("ALTER TYPE enquiry_status RENAME TO enquiry_status_v2")
    op.execute(
        "CREATE TYPE enquiry_status AS ENUM "
        "('new', 'contacted', 'quoted', 'won', 'lost', 'spam')"
    )
    op.execute("ALTER TABLE enquiries ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE enquiries ALTER COLUMN status TYPE enquiry_status USING ("
        "CASE status::text "
        "WHEN 'called' THEN 'contacted' WHEN 'site_visit' THEN 'contacted' "
        "WHEN 'quote_sent' THEN 'quoted' WHEN 'not_relevant' THEN 'spam' "
        "ELSE status::text END)::enquiry_status"
    )
    op.execute("ALTER TABLE enquiries ALTER COLUMN status SET DEFAULT 'new'")
    op.execute("DROP TYPE enquiry_status_v2")
