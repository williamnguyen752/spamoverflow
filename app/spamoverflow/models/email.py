from datetime import datetime
from .import db

class Email(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.now, onupdate=datetime.now)
    customer_id = db.Column(db.String(36), nullable=False)
    to_email = db.Column(db.String(255), nullable=False)
    from_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    malicious = db.Column(db.Boolean, nullable=False, default=False)
    domains = db.Column(db.JSON, nullable=False, default=[])
    email_metadata = db.Column(db.JSON, nullable=False, default={})

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "customer_id": self.customer_id,
            "to": self.to_email,
            "from": self.from_email,
            "subject": self.subject,
            "body": self.body,
            "status": self.status,
            "malicious": self.malicious,
            "domains": self.domains,
            "email_metadata": self.email_metadata
        }

    def __repr__(self):
        return f'<Email {self.id} {self.subject}>'

class MaliciousEmail(db.Model):
    id = db.Column(db.String(36), db.ForeignKey('email.id'), primary_key=True)
    body = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<MaliciousEmail {self.id}>'