"""add stripe_webhook_events table

Revision ID: 8c2f0a3d1e7b
Revises: 41b1f52cf9de
Create Date: 2026-04-10 18:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c2f0a3d1e7b'
down_revision = '41b1f52cf9de'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'stripe_webhook_events',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('stripe_webhook_events')
