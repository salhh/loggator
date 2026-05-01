"""MSP operator tenants: parent_tenant_id, is_operator, deleted_at

Revision ID: l1m2n3o4p5
Revises: j8k9l0m1n2o3
Create Date: 2026-05-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l1m2n3o4p5"
down_revision: Union[str, None] = "j8k9l0m1n2o3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("parent_tenant_id", sa.UUID(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("is_operator", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("tenants", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_tenants_parent_tenant_id",
        "tenants",
        "tenants",
        ["parent_tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_tenants_parent_tenant_id", "tenants", ["parent_tenant_id"])
    op.create_check_constraint(
        "ck_tenants_operator_has_no_parent",
        "tenants",
        "NOT is_operator OR parent_tenant_id IS NULL",
    )

    # Backfill: oldest tenant by created_at becomes operator root; others become its customers.
    op.execute(
        sa.text(
            """
            WITH op AS (
                SELECT id FROM tenants ORDER BY created_at ASC LIMIT 1
            )
            UPDATE tenants t SET
                is_operator = (t.id = (SELECT id FROM op)),
                parent_tenant_id = CASE
                    WHEN t.id = (SELECT id FROM op) THEN NULL
                    ELSE (SELECT id FROM op)
                END
            """
        )
    )

    op.alter_column("tenants", "is_operator", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_tenants_operator_has_no_parent", "tenants", type_="check")
    op.drop_index("ix_tenants_parent_tenant_id", table_name="tenants")
    op.drop_constraint("fk_tenants_parent_tenant_id", "tenants", type_="foreignkey")
    op.drop_column("tenants", "deleted_at")
    op.drop_column("tenants", "is_operator")
    op.drop_column("tenants", "parent_tenant_id")
