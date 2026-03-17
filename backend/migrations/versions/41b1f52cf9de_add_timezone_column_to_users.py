"""Add timezone column to users

Revision ID: 41b1f52cf9de
Revises: 4cd923f64657
Create Date: 2026-03-17 01:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41b1f52cf9de'
down_revision = '4cd923f64657'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('timezone')
