from datetime import datetime

from app.extensions import db


class ReportHistory(db.Model):
    __tablename__ = "report_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    case_id = db.Column(db.Integer, nullable=True)
    case_name = db.Column(db.String(500), nullable=True)
    report_type = db.Column(db.String(50), default="case_summary")
    file_path = db.Column(db.String(500), nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ReportHistory case_id={self.case_id} type={self.report_type}>"
