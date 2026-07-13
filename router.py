"""FastAPI router for DDW Email Assistant — 14 API endpoints.

All routes are mounted under /api/v1/plugins/ddw-email-assistant/api/email/.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from models import EmailAccount, EmailMessage, AuditLog, Base
from services.account_service import AccountService
from services.email_service import EmailService
from services.ai_service import AIService
from services.audit_service import AuditService

router = APIRouter(prefix="/api/email", tags=["email-assistant"])

# ------------------------------------------------------------------
# DB session factory (set up by the plugin main class)
# ------------------------------------------------------------------
_engine = None
_SessionLocal = None


def init_db(db_url: str = "sqlite:///email_assistant.db") -> None:
    """Initialize database engine and session factory."""
    global _engine, _SessionLocal
    _engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine)


def _db() -> Session:
    """Get a new DB session."""
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


# ------------------------------------------------------------------
# Pydantic request models
# ------------------------------------------------------------------
class AccountCreate(BaseModel):
    name: str
    email: str
    provider: str = "generic"
    password: str
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    auth_type: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    provider: Optional[str] = None
    password: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    is_active: Optional[bool] = None


class ReplyRequest(BaseModel):
    to: str
    body: str
    subject: Optional[str] = None


class ClassifyRequest(BaseModel):
    classification: str = Field(..., description="手动指定的分类结果")


# ==================================================================
# 1. GET /api/email/accounts — list all accounts
# ==================================================================
@router.get("/accounts")
def list_accounts() -> Dict[str, Any]:
    db = _db()
    try:
        svc = AccountService(db)
        return {"accounts": svc.list_accounts()}
    finally:
        db.close()


# ==================================================================
# 2. POST /api/email/accounts — create account
# ==================================================================
@router.post("/accounts")
def create_account(body: AccountCreate) -> Dict[str, Any]:
    db = _db()
    try:
        svc = AccountService(db)
        account = svc.create_account(body.model_dump())
        audit = AuditService(db)
        audit.log("create_account", {"email": body.email})
        return {"account": account}
    finally:
        db.close()


# ==================================================================
# 3. PUT /api/email/accounts/{id} — update account
# ==================================================================
@router.put("/accounts/{account_id}")
def update_account(account_id: int, body: AccountUpdate) -> Dict[str, Any]:
    db = _db()
    try:
        svc = AccountService(db)
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        account = svc.update_account(account_id, data)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"account": account}
    finally:
        db.close()


# ==================================================================
# 4. DELETE /api/email/accounts/{id} — delete account
# ==================================================================
@router.delete("/accounts/{account_id}")
def delete_account(account_id: int) -> Dict[str, Any]:
    db = _db()
    try:
        svc = AccountService(db)
        if not svc.delete_account(account_id):
            raise HTTPException(status_code=404, detail="Account not found")
        return {"deleted": True}
    finally:
        db.close()


# ==================================================================
# 5. POST /api/email/accounts/{id}/test — test connection
# ==================================================================
@router.post("/accounts/{account_id}/test")
def test_connection(account_id: int) -> Dict[str, Any]:
    db = _db()
    try:
        svc = EmailService(db)
        result = svc.test_connection(account_id)
        audit = AuditService(db)
        audit.log("test_connection", result, account_id=account_id)
        return result
    finally:
        db.close()


# ==================================================================
# 6. GET /api/email/messages — list messages (pagination + filter)
# ==================================================================
@router.get("/messages")
def list_messages(
    account_id: Optional[int] = Query(None),
    classification: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    db = _db()
    try:
        q = db.query(EmailMessage)
        if account_id is not None:
            q = q.filter(EmailMessage.account_id == account_id)
        if classification is not None:
            q = q.filter(EmailMessage.classification == classification)
        if status is not None:
            q = q.filter(EmailMessage.status == status)

        total = q.count()
        offset = (page - 1) * page_size
        messages = q.order_by(EmailMessage.received_at.desc()).offset(offset).limit(page_size).all()

        return {
            "messages": [m.to_dict() for m in messages],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        db.close()


# ==================================================================
# 7. GET /api/email/messages/{id} — message detail
# ==================================================================
@router.get("/messages/{message_id}")
def get_message(message_id: int) -> Dict[str, Any]:
    db = _db()
    try:
        msg = db.get(EmailMessage, message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"message": msg.to_dict()}
    finally:
        db.close()


# ==================================================================
# 8. POST /api/email/messages/{id}/classify — manual reclassify
# ==================================================================
@router.post("/messages/{message_id}/classify")
def classify_message(message_id: int, body: ClassifyRequest) -> Dict[str, Any]:
    db = _db()
    try:
        msg = db.get(EmailMessage, message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        msg.classification = body.classification
        msg.confidence = 1.0
        db.commit()
        audit = AuditService(db)
        audit.log("classify", {"classification": body.classification}, message_id=message_id, operator="user")
        return {"message": msg.to_dict()}
    finally:
        db.close()


# ==================================================================
# 9. POST /api/email/messages/{id}/draft — generate reply draft
# ==================================================================
@router.post("/messages/{message_id}/draft")
def generate_draft(message_id: int) -> Dict[str, Any]:
    db = _db()
    try:
        msg = db.get(EmailMessage, message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        ai = AIService()
        draft = ai.generate_draft(
            subject=msg.subject,
            sender=msg.sender,
            body=msg.body_text,
            classification=msg.classification,
        )
        msg.auto_reply_draft = draft
        msg.status = "drafted"
        db.commit()

        audit = AuditService(db)
        audit.log("draft", {"draft_length": len(draft)}, message_id=message_id)
        return {"draft": draft, "message": msg.to_dict()}
    finally:
        db.close()


# ==================================================================
# 10. POST /api/email/messages/{id}/reply — send reply (after confirm)
# ==================================================================
@router.post("/messages/{message_id}/reply")
def send_reply(message_id: int, body: ReplyRequest) -> Dict[str, Any]:
    db = _db()
    try:
        msg = db.get(EmailMessage, message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        email_svc = EmailService(db)
        subject = body.subject or msg.subject
        success = email_svc.send_reply(
            account_id=msg.account_id,
            to=body.to,
            subject=subject,
            body=body.body,
            in_reply_to=msg.message_id,
        )

        if success:
            msg.status = "replied"
            db.commit()

        audit = AuditService(db)
        audit.log(
            "reply",
            {"to": body.to, "subject": subject, "success": success},
            account_id=msg.account_id,
            message_id=message_id,
            operator="user",
        )
        return {"success": success}
    finally:
        db.close()


# ==================================================================
# 11. POST /api/email/messages/{id}/archive — archive message
# ==================================================================
@router.post("/messages/{message_id}/archive")
def archive_message(message_id: int) -> Dict[str, Any]:
    db = _db()
    try:
        msg = db.get(EmailMessage, message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        msg.status = "archived"
        db.commit()
        audit = AuditService(db)
        audit.log("archive", {}, message_id=message_id)
        return {"archived": True, "message": msg.to_dict()}
    finally:
        db.close()


# ==================================================================
# 12. POST /api/email/sync/{account_id} — manual sync
# ==================================================================
@router.post("/sync/{account_id}")
def sync_messages(account_id: int) -> Dict[str, Any]:
    db = _db()
    try:
        svc = EmailService(db)
        messages = svc.sync_messages(account_id)
        audit = AuditService(db)
        audit.log("sync", {"count": len(messages)}, account_id=account_id)
        return {"synced": len(messages), "messages": messages}
    finally:
        db.close()


# ==================================================================
# 13. GET /api/email/stats — statistics
# ==================================================================
@router.get("/stats")
def get_stats() -> Dict[str, Any]:
    db = _db()
    try:
        total_accounts = db.query(func.count(EmailAccount.id)).scalar() or 0
        total_messages = db.query(func.count(EmailMessage.id)).scalar() or 0

        # Classification breakdown
        class_rows = (
            db.query(EmailMessage.classification, func.count(EmailMessage.id))
            .group_by(EmailMessage.classification)
            .all()
        )
        by_classification = {row[0]: row[1] for row in class_rows}

        # Status breakdown
        status_rows = (
            db.query(EmailMessage.status, func.count(EmailMessage.id))
            .group_by(EmailMessage.status)
            .all()
        )
        by_status = {row[0]: row[1] for row in status_rows}

        # Audit stats
        total_audit = db.query(func.count(AuditLog.id)).scalar() or 0

        return {
            "total_accounts": total_accounts,
            "total_messages": total_messages,
            "by_classification": by_classification,
            "by_status": by_status,
            "total_audit_logs": total_audit,
        }
    finally:
        db.close()


# ==================================================================
# 14. GET /api/email/audit — audit log query
# ==================================================================
@router.get("/audit")
def get_audit_logs(
    account_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    db = _db()
    try:
        svc = AuditService(db)
        offset = (page - 1) * page_size
        logs = svc.query(account_id=account_id, action=action, limit=page_size, offset=offset)
        total = svc.count(account_id=account_id)
        return {
            "logs": logs,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        db.close()
