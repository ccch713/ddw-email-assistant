"""Audit service — immutable compliance logging."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Create and query audit logs for compliance."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        account_id: Optional[int] = None,
        message_id: Optional[int] = None,
        operator: str = "system",
    ) -> AuditLog:
        """Record an audit event. Audit logs are append-only."""
        entry = AuditLog(
            account_id=account_id,
            message_id=message_id,
            action=action,
            details=json.dumps(details or {}, ensure_ascii=False),
            operator=operator,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def query(
        self,
        account_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query audit logs with optional filters."""
        q = self.db.query(AuditLog)
        if account_id is not None:
            q = q.filter(AuditLog.account_id == account_id)
        if action is not None:
            q = q.filter(AuditLog.action == action)
        q = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        return [entry.to_dict() for entry in q.all()]

    def count(self, account_id: Optional[int] = None) -> int:
        """Count audit log entries."""
        q = self.db.query(AuditLog)
        if account_id is not None:
            q = q.filter(AuditLog.account_id == account_id)
        return q.count()
