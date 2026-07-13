"""SQLAlchemy ORM models for DDW Email Assistant.

Tables:
- EmailAccount: mailbox connection configs (IMAP/SMTP)
- EmailMessage: synced & classified messages
- AuditLog: immutable audit trail for compliance
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all DDW Email Assistant models."""


class EmailAccount(Base):
    """Mailbox account with encrypted credentials."""

    __tablename__ = "email_accounts"

    id: Optional[int] = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(128), nullable=False, comment="账户显示名")
    email: str = Column(String(256), nullable=False, unique=True, comment="邮箱地址")
    provider: str = Column(String(32), nullable=False, comment="提供商类型(qq/163/exmail/generic)")
    imap_host: str = Column(String(128), nullable=False)
    imap_port: int = Column(Integer, nullable=False, default=993)
    smtp_host: str = Column(String(128), nullable=False)
    smtp_port: int = Column(Integer, nullable=False, default=465)
    auth_type: str = Column(String(32), nullable=False, default="authorization_code")
    encrypted_creds: str = Column(Text, nullable=False, comment="AES 加密后的凭证 JSON")
    is_active: bool = Column(Boolean, nullable=False, default=True)
    created_at: _dt.datetime = Column(
        DateTime, nullable=False, default=_dt.datetime.utcnow
    )
    updated_at: _dt.datetime = Column(
        DateTime, nullable=False, default=_dt.datetime.utcnow, onupdate=_dt.datetime.utcnow
    )

    # relationships
    messages = relationship("EmailMessage", back_populates="account", lazy="dynamic")
    audit_logs = relationship("AuditLog", back_populates="account", lazy="dynamic")

    def to_dict(self) -> dict:
        """Serialize (exclude encrypted credentials)."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "provider": self.provider,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "auth_type": self.auth_type,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EmailMessage(Base):
    """Synced email message with classification metadata."""

    __tablename__ = "email_messages"

    id: Optional[int] = Column(Integer, primary_key=True, autoincrement=True)
    account_id: int = Column(Integer, ForeignKey("email_accounts.id"), nullable=False)
    message_id: str = Column(String(512), nullable=False, unique=True, comment="邮件 Message-ID")
    subject: str = Column(String(1024), nullable=False, default="")
    sender: str = Column(String(256), nullable=False, comment="发件人")
    recipients: str = Column(Text, nullable=False, default="[]", comment="收件人 JSON 数组")
    cc: str = Column(Text, nullable=False, default="[]", comment="抄送 JSON 数组")
    body_text: str = Column(Text, nullable=False, default="")
    body_html: str = Column(Text, nullable=False, default="")
    received_at: Optional[_dt.datetime] = Column(DateTime, nullable=True)
    classification: str = Column(
        String(32), nullable=False, default="pending",
        comment="need_reply/simple_confirm/info_only/newsletter/spam/pending"
    )
    confidence: float = Column(Float, nullable=False, default=0.0)
    auto_reply_draft: str = Column(Text, nullable=False, default="")
    status: str = Column(
        String(32), nullable=False, default="pending",
        comment="pending/drafted/replied/archived"
    )
    created_at: _dt.datetime = Column(
        DateTime, nullable=False, default=_dt.datetime.utcnow
    )

    # relationships
    account = relationship("EmailAccount", back_populates="messages")

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "message_id": self.message_id,
            "subject": self.subject,
            "sender": self.sender,
            "recipients": self.recipients,
            "cc": self.cc,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "classification": self.classification,
            "confidence": self.confidence,
            "auto_reply_draft": self.auto_reply_draft,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(Base):
    """Immutable audit log for compliance tracking."""

    __tablename__ = "audit_logs"

    id: Optional[int] = Column(Integer, primary_key=True, autoincrement=True)
    account_id: Optional[int] = Column(
        Integer, ForeignKey("email_accounts.id"), nullable=True
    )
    message_id: Optional[int] = Column(
        Integer, ForeignKey("email_messages.id"), nullable=True
    )
    action: str = Column(String(32), nullable=False, comment="classify/draft/reply/archive/delete")
    details: str = Column(Text, nullable=False, default="{}", comment="操作详情 JSON")
    operator: str = Column(String(32), nullable=False, default="system", comment="system/user")
    created_at: _dt.datetime = Column(
        DateTime, nullable=False, default=_dt.datetime.utcnow
    )

    # relationships
    account = relationship("EmailAccount", back_populates="audit_logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "message_id": self.message_id,
            "action": self.action,
            "details": self.details,
            "operator": self.operator,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db(db_url: str = "sqlite:///email_assistant.db"):
    """Create all tables and return engine."""
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine
