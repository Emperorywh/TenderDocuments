"""create outbox_events table

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-23

outbox_events 表：事务性事件记录。event_id 全表唯一，使重复业务事件不产生重复
投递（幂等基础，SPEC.md 第 11.3 节）。payload 为消息信封（JSON），delivery_status
与 attempts 支持补偿重投（D-011）。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=32), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("delivery_status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
        sa.UniqueConstraint("event_id", name=op.f("uq_outbox_events_event_id")),
    )
    op.create_index(
        op.f("ix_outbox_events_delivery_status"),
        "outbox_events",
        ["delivery_status"],
    )
    op.create_index(
        op.f("ix_outbox_events_aggregate"),
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_events_aggregate"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_delivery_status"), table_name="outbox_events")
    op.drop_table("outbox_events")
