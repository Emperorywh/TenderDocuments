"""create operation_logs table (append-only)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-23

operation_logs 表为只追加审计记录。数据库层以触发器强制禁止 UPDATE/DELETE，
使“既有记录无法通过应用仓储或数据库连接更新或删除”（B-014 验证点）。
SQLite 与 PostgreSQL 触发器语法不同，按 dialect 分支创建。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operation_logs")),
    )
    op.create_index(
        op.f("ix_operation_logs_resource"),
        "operation_logs",
        ["resource_type", "resource_id"],
    )
    _create_append_only_triggers(op)


def downgrade() -> None:
    _drop_append_only_triggers(op)
    op.drop_index(op.f("ix_operation_logs_resource"), table_name="operation_logs")
    op.drop_table("operation_logs")


def _create_append_only_triggers(op) -> None:
    """按 dialect 创建禁止 UPDATE/DELETE 的触发器，保证只追加。"""
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER operation_logs_no_update BEFORE UPDATE ON operation_logs "
            "BEGIN SELECT RAISE(ABORT, 'operation_logs is append-only'); END"
        )
        op.execute(
            "CREATE TRIGGER operation_logs_no_delete BEFORE DELETE ON operation_logs "
            "BEGIN SELECT RAISE(ABORT, 'operation_logs is append-only'); END"
        )
    elif dialect == "postgresql":
        op.execute(
            "CREATE OR REPLACE FUNCTION prevent_operation_logs_mutation() "
            "RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION 'operation_logs is append-only: % forbidden', TG_OP; END; "
            "$$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER operation_logs_no_mutation "
            "BEFORE UPDATE OR DELETE ON operation_logs "
            "FOR EACH ROW EXECUTE FUNCTION prevent_operation_logs_mutation()"
        )


def _drop_append_only_triggers(op) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS operation_logs_no_update")
        op.execute("DROP TRIGGER IF EXISTS operation_logs_no_delete")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS operation_logs_no_mutation ON operation_logs")
        op.execute("DROP FUNCTION IF EXISTS prevent_operation_logs_mutation()")
