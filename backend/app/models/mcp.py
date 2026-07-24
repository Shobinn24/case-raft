"""MCP connector tables (CaseRaft for Claude).

Three tables shared with the MCP service (mcp-service/, a separate Railway
service reading the same Postgres):

  mcp_clients     Dynamic Client Registration records created by the MCP
                  service's /register endpoint.
  mcp_auth_codes  Authorization codes minted by the /connect/authorize
                  consent page here. SHA-256 hash only, never the raw code.
  mcp_tokens      CaseRaft-issued access/refresh tokens minted by the MCP
                  service's /token endpoint. Hashes only. A revoke button in
                  settings (Phase 4) just flips `revoked` on these rows.

The Flask app owns the schema (Alembic migration lives here); the MCP
service mirrors these models read-write in caseraft_mcp/db.py.
"""

import uuid
from datetime import datetime

from app.extensions import db


def _new_uuid():
    return str(uuid.uuid4())


class MCPClient(db.Model):
    __tablename__ = "mcp_clients"

    id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    client_id = db.Column(db.Text, unique=True, nullable=False)
    client_name = db.Column(db.Text, nullable=True)
    redirect_uris = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MCPClient {self.client_id} ({self.client_name})>"


class MCPAuthCode(db.Model):
    __tablename__ = "mcp_auth_codes"

    id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    code_hash = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    client_id = db.Column(db.Text, nullable=False)
    code_challenge = db.Column(db.Text, nullable=False)
    scopes = db.Column(db.Text, nullable=True)
    redirect_uri = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MCPToken(db.Model):
    __tablename__ = "mcp_tokens"

    id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    refresh_token_hash = db.Column(db.String(64), unique=True, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    client_id = db.Column(db.Text, nullable=False)
    scopes = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, nullable=False, default=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
