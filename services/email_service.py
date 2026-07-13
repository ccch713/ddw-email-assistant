"""Email service — IMAP/SMTP operations.

Handles syncing, fetching, and sending emails via provider adapters.
"""

from __future__ import annotations

import json
import logging
from email import message_from_bytes
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from crypto_utils import decrypt_credentials
from models import EmailAccount, EmailMessage
from providers.base import EmailProvider, ProviderRegistry

logger = logging.getLogger(__name__)


def _decode_header_value(raw: Any) -> str:
    """Decode MIME-encoded header to a plain string."""
    if raw is None:
        return ""
    parts = decode_header(str(raw))
    decoded: list[str] = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


class EmailService:
    """High-level email operations backed by provider adapters."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_provider(self, account: EmailAccount) -> EmailProvider:
        """Resolve a provider instance from the account record."""
        pcls = ProviderRegistry.get(account.provider)
        if pcls is None:
            # Fall back to generic
            pcls = ProviderRegistry.get("generic")
        inst = pcls()
        # Override server settings from account (user may have custom hosts)
        inst.imap_host = account.imap_host
        inst.imap_port = account.imap_port
        inst.smtp_host = account.smtp_host
        inst.smtp_port = account.smtp_port
        return inst

    def _decrypt_password(self, account: EmailAccount) -> str:
        """Decrypt the stored credentials to get the password/auth-code."""
        creds = decrypt_credentials(account.encrypted_creds)
        return creds.get("password", "")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def test_connection(self, account_id: int) -> Dict[str, Any]:
        """Test IMAP + SMTP connectivity for an account."""
        account = self.db.get(EmailAccount, account_id)
        if not account:
            return {"success": False, "errors": ["Account not found"]}
        provider = self._get_provider(account)
        password = self._decrypt_password(account)
        return provider.test_connection(account.email, password)

    def sync_messages(self, account_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch unseen messages, parse, store in DB, return summaries."""
        account = self.db.get(EmailAccount, account_id)
        if not account:
            return []
        provider = self._get_provider(account)
        password = self._decrypt_password(account)

        raw_msgs = provider.fetch_unseen(account.email, password, limit=limit)
        saved: List[Dict[str, Any]] = []

        for raw in raw_msgs:
            msg = message_from_bytes(raw["raw"])
            message_id = msg.get("Message-ID", raw["id"])
            # Skip duplicates
            existing = self.db.query(EmailMessage).filter_by(message_id=message_id).first()
            if existing:
                continue

            body_text = ""
            body_html = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue
                    text = payload.decode("utf-8", errors="replace")
                    if ct == "text/plain":
                        body_text = text
                    elif ct == "text/html":
                        body_html = text
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body_text = payload.decode("utf-8", errors="replace")

            email_msg = EmailMessage(
                account_id=account_id,
                message_id=message_id,
                subject=_decode_header_value(msg.get("Subject")),
                sender=_decode_header_value(msg.get("From")),
                recipients=json.dumps([_decode_header_value(msg.get("To"))]),
                cc=json.dumps([_decode_header_value(msg.get("Cc"))]),
                body_text=body_text,
                body_html=body_html,
                received_at=parsedate_to_datetime(msg["Date"]) if msg.get("Date") else None,
                status="pending",
            )
            self.db.add(email_msg)
            self.db.flush()
            saved.append(email_msg.to_dict())

        self.db.commit()
        return saved

    def send_reply(
        self,
        account_id: int,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str = "",
    ) -> bool:
        """Send a reply via SMTP."""
        account = self.db.get(EmailAccount, account_id)
        if not account:
            return False
        provider = self._get_provider(account)
        password = self._decrypt_password(account)
        return provider.send_reply(
            account.email, password, to, subject, body, in_reply_to
        )

    def archive_message(self, account_id: int, uid: str) -> bool:
        """Archive (move) a message via IMAP."""
        account = self.db.get(EmailAccount, account_id)
        if not account:
            return False
        provider = self._get_provider(account)
        password = self._decrypt_password(account)
        return provider.archive_message(account.email, password, uid)
