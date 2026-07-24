"""add mcp connector tables (clients, auth codes, tokens)

Revision ID: c4d8f1a92e57
Revises: b7e2c1a4f9d0
Create Date: 2026-07-24 12:00:00.000000

Tables backing "CaseRaft for Claude" (the hosted MCP connector). The MCP
service (mcp-service/) reads and writes these through the shared Postgres.
Auth codes and tokens store SHA-256 hashes only, never raw values.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d8f1a92e57'
down_revision = 'b7e2c1a4f9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'mcp_clients',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('client_id', sa.Text(), nullable=False),
        sa.Column('client_name', sa.Text(), nullable=True),
        sa.Column('redirect_uris', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id'),
    )
    op.create_table(
        'mcp_auth_codes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Text(), nullable=False),
        sa.Column('code_challenge', sa.Text(), nullable=False),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('redirect_uri', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_hash'),
    )
    op.create_table(
        'mcp_tokens',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=64), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Text(), nullable=False),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
        sa.UniqueConstraint('refresh_token_hash'),
    )


def downgrade():
    op.drop_table('mcp_tokens')
    op.drop_table('mcp_auth_codes')
    op.drop_table('mcp_clients')
