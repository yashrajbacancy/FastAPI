"""Initialize database

Revision ID: b79475b8ac56
Revises: b3d0c9a8ea2e
Create Date: 2026-03-05 18:15:49.593739
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b79475b8ac56"
down_revision: Union[str, Sequence[str], None] = "b3d0c9a8ea2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Step 1: Add column as nullable
    op.add_column(
        "users",
        sa.Column("country", sa.String(), nullable=True)
    )

    # Step 2: Set value for existing rows
    op.execute(
        "UPDATE users SET country = 'India' WHERE country IS NULL"
    )

    # Step 3: Make column NOT NULL
    op.alter_column(
        "users",
        "country",
        existing_type=sa.String(),
        nullable=False
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("users", "country")