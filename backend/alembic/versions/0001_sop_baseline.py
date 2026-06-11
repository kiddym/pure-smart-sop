"""SOP baseline: create all SOP tables from current ORM metadata.

剥离 CMMS 后的单一基线。直接用 ORM metadata 建表，保证与模型一致、仅含 SOP 表。
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "0001_sop_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 导入以填充 Base.metadata（env.py 已 import app.models，但此处再次确保）
    import app.models  # noqa: F401
    from app.models.base import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    import app.models  # noqa: F401
    from app.models.base import Base

    Base.metadata.drop_all(bind=op.get_bind())
