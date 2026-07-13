"""Generic IMAP/SMTP provider adapter.

Handles any standard IMAP server (163, 126, Gmail, Outlook, self-hosted, etc.)
Users supply the IMAP/SMTP host and port themselves.
"""

from __future__ import annotations

import imaplib
import smtplib
from typing import Any, Dict, Optional

from providers.base import EmailProvider, ProviderRegistry


@ProviderRegistry.register
class GenericIMAPProvider(EmailProvider):
    """Generic IMAP/SMTP provider — configurable server addresses."""

    provider_name = "generic"
    imap_host = "imap.example.com"
    imap_port = 993
    smtp_host = "smtp.example.com"
    smtp_port = 465
    auth_type = "authorization_code"
    use_ssl = True

    def connect_imap(self, email: str, password: str) -> imaplib.IMAP4_SSL:
        """Connect to a generic IMAP server."""
        conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        conn.login(email, password)
        return conn

    def connect_smtp(self, email: str, password: str) -> smtplib.SMTP_SSL:
        """Connect to a generic SMTP server."""
        conn = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        conn.login(email, password)
        return conn

    @classmethod
    def for_server(
        cls,
        imap_host: str,
        imap_port: int = 993,
        smtp_host: str = "",
        smtp_port: int = 465,
        auth_type: str = "authorization_code",
    ) -> "GenericIMAPProvider":
        """Factory: create an instance with custom server settings."""
        inst = cls()
        inst.imap_host = imap_host
        inst.imap_port = imap_port
        inst.smtp_host = smtp_host or imap_host.replace("imap.", "smtp.")
        inst.smtp_port = smtp_port
        inst.auth_type = auth_type
        return inst
