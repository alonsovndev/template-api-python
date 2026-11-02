"""Test-only Item schema; not discoverable by production Alembic."""

import sqlalchemy as sa
from alembic import op

revision: str = "0002_example_item"
down_revision: str = "0001_baseline"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("identifier", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_items_name_not_blank"),
        sa.PrimaryKeyConstraint("identifier"),
    )


def downgrade() -> None:
    op.drop_table("items")
