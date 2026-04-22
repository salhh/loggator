"""merge heads

Revision ID: d0e1f2a3b4c5
Revises: c1a2b3d4e5f6, c9d1e2f3a4b5
Create Date: 2026-04-22 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = ('c1a2b3d4e5f6', 'c9d1e2f3a4b5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
