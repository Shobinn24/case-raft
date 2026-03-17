from datetime import datetime

from app.extensions import db


class ErrorLog(db.Model):
    __tablename__ = "error_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user_email = db.Column(db.String(255), nullable=True)
    endpoint = db.Column(db.String(255))
    method = db.Column(db.String(10))
    status_code = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    request_body = db.Column(db.Text, nullable=True)
    traceback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="error_logs", lazy=True)

    def __repr__(self):
        return f"<ErrorLog {self.id} {self.status_code} {self.endpoint}>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "request_body": self.request_body,
            "traceback": self.traceback,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
