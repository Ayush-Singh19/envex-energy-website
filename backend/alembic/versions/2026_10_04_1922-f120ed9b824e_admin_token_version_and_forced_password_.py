"""admin token version and forced password change

Revision ID: f120ed9b824e
Revises: d91cfcb35f86
Create Date: 2026-10-04 19:22:01.911532

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f120ed9b824e'
down_revision: Union[str, Sequence[str], None] = 'd91cfcb35f86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Session token version (revoke on password change) and forced first-login change."""
    op.add_column(
        "admin_users",
        sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "admin_users",
        sa.Column(
            "must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("admin_users", "must_change_password")
    op.drop_column("admin_users", "token_version")
