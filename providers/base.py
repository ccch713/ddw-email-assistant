"""Abstract base class for email providers.

Each provider (QQ, 163, generic IMAP, …) subclasses EmailProvider
and supplies IMAP/SMTP server defaults plus any provider-specific logic.
"""

from __future__ import annotations

import imaplib
import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional


class EmailProvider(ABC):
    """Base class for email provider adapters."""

    provider_name: str = "generic"
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 465
    auth_type: str = "authorization_code"
    use_ssl: bool = True

    @abstractmethod
    def connect_imap(self, email: str, password: str) -> imaplib.IMAP4_SSL:
        """Open and return an authenticated IMAP connection."""
        ...

    @abstractmethod
    def connect_smtp(self, email: str, password: str) -> smtplib.SMTP_SSL:
        """Open and return an authenticated SMTP connection."""
        ...

    def test_connection(self, email: str, password: str) -> Dict[str, Any]:
        """Test both IMAP and SMTP connections. Returns status dict."""
        result: Dict[str, Any] = {"imap": False, "smtp": False, "errors": []}
        # Test IMAP
        try:
            conn = self.connect_imap(email, password)
            conn.logout()
            result["imap"] = True
        except Exception as exc:
            result["errors"].append(f"IMAP: {exc}")
        # Test SMTP
        try:
            conn = self.connect_smtp(email, password)
            conn.quit()
            result["smtp"] = True
        except Exception as exc:
            result["errors"].append(f"SMTP: {exc}")
        result["success"] = result["imap"] and result["smtp"]
        return result

    def fetch_folders(self, email: str, password: str) -> List[str]:
        """List IMAP folders."""
        conn = self.connect_imap(email, password)
        try:
            status, folders = conn.list()
            return [f.decode() for f in folders] if folders else []
        finally:
            conn.logout()

    def fetch_unseen(self, email: str, password: str, folder: str = "INBOX", limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch unseen messages from a folder. Returns list of raw dicts."""
        conn = self.connect_imap(email, password)
        try:
            conn.select(folder, readonly=True)
            status, data = conn.search(None, "UNSEEN")
            if status != "OK" or not data[0]:
                return []
            msg_ids = data[0].split()[:limit]
            messages: List[Dict[str, Any]] = []
            for mid in msg_ids:
                status, msg_data = conn.fetch(mid, "(RFC822)")
                if status == "OK" and msg_data and msg_data[0]:
                    item = msg_data[0]
                    # item is (uid, (b'RFC822', raw_bytes))
                    if isinstance(item, tuple) and len(item) >= 2:
                        body_part = item[1]
                        if isinstance(body_part, tuple) and len(body_part) >= 2:
                            raw = body_part[1]
                        else:
                            raw = body_part
                    else:
                        raw = item
                    if raw:
                        messages.append({"id": mid.decode(), "raw": raw})
            return messages
        finally:
            conn.logout()

    def send_reply(
        self,
        email: str,
        password: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str = "",
    ) -> bool:
        """Send a reply email via SMTP."""
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = email
        msg["To"] = to
        msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to
        conn = self.connect_smtp(email, password)
        try:
            conn.sendmail(email, [to], msg.as_string())
            return True
        except Exception:
            return False
        finally:
            conn.quit()

    def archive_message(self, email_addr: str, password: str, uid: str, folder: str = "INBOX") -> bool:
        """Move message to Archive folder via IMAP copy+delete."""
        conn = self.connect_imap(email_addr, password)
        try:
            conn.select(folder, readonly=False)
            # Try to copy to Archive
            status, _ = conn.copy(uid, "Archive")
            if status == "OK":
                conn.store(uid, "+FLAGS", "\\Deleted")
                conn.expunge()
                return True
            return False
        except Exception:
            return False
        finally:
            conn.logout()


class ProviderRegistry:
    """Registry of email provider adapters."""

    _providers: Dict[str, type] = {}

    @classmethod
    def register(cls, provider_cls: type) -> type:
        cls._providers[provider_cls.provider_name] = provider_cls
        return provider_cls

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        return cls._providers.get(name)

    @classmethod
    def list_providers(cls) -> List[str]:
        return list(cls._providers.keys())

    @classmethod
    def get_all_configs(cls) -> List[Dict[str, Any]]:
        """Return server configs for all registered providers."""
        configs = []
        for name, pcls in cls._providers.items():
            configs.append({
                "name": name,
                "imap_host": pcls.imap_host,
                "imap_port": pcls.imap_port,
                "smtp_host": pcls.smtp_host,
                "smtp_port": pcls.smtp_port,
                "auth_type": pcls.auth_type,
            })
        return configs
