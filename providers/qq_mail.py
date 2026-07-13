"""QQ Mail provider adapter.

QQ 邮箱 requires an authorization code (授权码) instead of the account password.
IMAP: imap.qq.com:993 (SSL)
SMTP: smtp.qq.com:465 (SSL)
"""

from __future__ import annotations

import imaplib
import smtplib
from typing import Any, Dict

from providers.base import EmailProvider, ProviderRegistry


@ProviderRegistry.register
class QQMailProvider(EmailProvider):
    """QQ Mail (imap.qq.com / smtp.qq.com) provider."""

    provider_name = "qq"
    imap_host = "imap.qq.com"
    imap_port = 993
    smtp_host = "smtp.qq.com"
    smtp_port = 465
    auth_type = "authorization_code"
    use_ssl = True

    def connect_imap(self, email: str, password: str) -> imaplib.IMAP4_SSL:
        """Connect to QQ IMAP with authorization code."""
        conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        conn.login(email, password)
        return conn

    def connect_smtp(self, email: str, password: str) -> smtplib.SMTP_SSL:
        """Connect to QQ SMTP with authorization code."""
        conn = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        conn.login(email, password)
        return conn
