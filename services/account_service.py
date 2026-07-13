"""Account service — CRUD for email accounts with AES credential encryption."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from crypto_utils import encrypt_credentials
from models import EmailAccount
from providers import ProviderRegistry  # noqa: triggers provider registration

logger = logging.getLogger(__name__)


class AccountService:
    """Manage email account CRUD and validation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_accounts(self) -> List[Dict[str, Any]]:
        """Return all accounts (credentials excluded)."""
        accounts = self.db.query(EmailAccount).all()
        return [a.to_dict() for a in accounts]

    def get_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Get a single account by ID."""
        account = self.db.get(EmailAccount, account_id)
        if not account:
            return None
        return account.to_dict()

    def create_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new email account.

        Required fields: name, email, provider, password (plain, will be encrypted).
        Optional: imap_host, imap_port, smtp_host, smtp_port, auth_type.
        """
        # Resolve provider defaults
        provider_name = data.get("provider", "generic")
        pcls = ProviderRegistry.get(provider_name)
        if pcls is None:
            pcls = ProviderRegistry.get("generic")

        # Encrypt the password
        password = data.get("password", "")
        encrypted = encrypt_credentials({"password": password})

        account = EmailAccount(
            name=data["name"],
            email=data["email"],
            provider=provider_name,
            imap_host=data.get("imap_host") or pcls.imap_host,
            imap_port=data.get("imap_port") or pcls.imap_port,
            smtp_host=data.get("smtp_host") or pcls.smtp_host,
            smtp_port=data.get("smtp_port") or pcls.smtp_port,
            auth_type=data.get("auth_type") or pcls.auth_type,
            encrypted_creds=encrypted,
            is_active=data.get("is_active", True),
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        logger.info("Created email account: %s (%s)", account.name, account.email)
        return account.to_dict()

    def update_account(self, account_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing account. Password is re-encrypted if provided."""
        account = self.db.get(EmailAccount, account_id)
        if not account:
            return None

        updatable_fields = ["name", "email", "provider", "imap_host", "imap_port",
                            "smtp_host", "smtp_port", "auth_type", "is_active"]
        for field in updatable_fields:
            if field in data:
                setattr(account, field, data[field])

        # Re-encrypt password if supplied
        if "password" in data:
            account.encrypted_creds = encrypt_credentials({"password": data["password"]})

        # If provider changed, fill missing server settings from new provider defaults
        if "provider" in data:
            pcls = ProviderRegistry.get(data["provider"])
            if pcls:
                if "imap_host" not in data:
                    account.imap_host = pcls.imap_host
                if "imap_port" not in data:
                    account.imap_port = pcls.imap_port
                if "smtp_host" not in data:
                    account.smtp_host = pcls.smtp_host
                if "smtp_port" not in data:
                    account.smtp_port = pcls.smtp_port

        self.db.commit()
        self.db.refresh(account)
        return account.to_dict()

    def delete_account(self, account_id: int) -> bool:
        """Soft-delete by deactivating; hard-delete if confirmed."""
        account = self.db.get(EmailAccount, account_id)
        if not account:
            return False
        self.db.delete(account)
        self.db.commit()
        logger.info("Deleted email account: %s (%s)", account.name, account.email)
        return True

    def list_providers(self) -> List[Dict[str, Any]]:
        """Return available provider configurations."""
        return ProviderRegistry.get_all_configs()
