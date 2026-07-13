"""Comprehensive tests for DDW Email Assistant plugin.

Covers: models, crypto, services (account/email/ai/audit), providers, and router.
All IMAP/SMTP connections are mocked. 15+ test cases.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# Set env before importing app modules
os.environ["DDW_EMAIL_SECRET_KEY"] = "test-secret-key-for-unit-tests"

from models import Base, EmailAccount, EmailMessage, AuditLog
from crypto_utils import encrypt_credentials, decrypt_credentials
from providers.base import EmailProvider, ProviderRegistry
from providers.qq_mail import QQMailProvider
from providers.generic_imap import GenericIMAPProvider
from services.account_service import AccountService
from services.email_service import EmailService
from services.ai_service import AIService
from services.audit_service import AuditService

# ==================================================================
# Fixtures
# ==================================================================

@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def app():
    """Create a FastAPI test app with email routes."""
    from router import init_db, router as email_router
    import router

    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    router._engine = engine
    router._SessionLocal = sessionmaker(bind=engine)

    _app = FastAPI()
    _app.include_router(email_router)
    return _app


@pytest.fixture
def client(app):
    """TestClient for the email API."""
    return TestClient(app)


@pytest.fixture
def sample_account_data():
    return {
        "name": "Test Work Email",
        "email": "test@example.com",
        "provider": "qq",
        "password": "test-auth-code-123",
    }


@pytest.fixture
def created_account(db_session, sample_account_data):
    """Create and return a sample account in the DB."""
    svc = AccountService(db_session)
    return svc.create_account(sample_account_data)


# ==================================================================
# Test: Models
# ==================================================================

class TestModels:
    def test_email_account_to_dict(self, db_session, created_account):
        """EmailAccount.to_dict() returns expected keys without credentials."""
        assert created_account["name"] == "Test Work Email"
        assert created_account["email"] == "test@example.com"
        assert created_account["provider"] == "qq"
        assert "encrypted_creds" not in created_account
        assert created_account["is_active"] is True

    def test_email_message_to_dict(self, db_session, created_account):
        """EmailMessage.to_dict() returns correct fields."""
        msg = EmailMessage(
            account_id=created_account["id"],
            message_id="<test-001@example.com>",
            subject="Hello",
            sender="alice@example.com",
            body_text="Hi there",
            classification="need_reply",
            confidence=0.85,
            status="pending",
        )
        db_session.add(msg)
        db_session.commit()
        d = msg.to_dict()
        assert d["subject"] == "Hello"
        assert d["classification"] == "need_reply"
        assert d["confidence"] == 0.85

    def test_audit_log_to_dict(self, db_session, created_account):
        """AuditLog.to_dict() returns correct structure."""
        log = AuditLog(
            account_id=created_account["id"],
            action="classify",
            details=json.dumps({"result": "need_reply"}),
            operator="system",
        )
        db_session.add(log)
        db_session.commit()
        d = log.to_dict()
        assert d["action"] == "classify"
        assert d["operator"] == "system"


# ==================================================================
# Test: Crypto Utils
# ==================================================================

class TestCryptoUtils:
    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt returns the original dict."""
        original = {"username": "user@example.com", "password": "s3cret"}
        token = encrypt_credentials(original)
        restored = decrypt_credentials(token)
        assert restored == original

    def test_different_keys_produce_different_tokens(self):
        """Different secret keys produce different ciphertexts."""
        data = {"password": "abc"}
        t1 = encrypt_credentials(data)
        os.environ["DDW_EMAIL_SECRET_KEY"] = "another-key"
        t2 = encrypt_credentials(data)
        os.environ["DDW_EMAIL_SECRET_KEY"] = "test-secret-key-for-unit-tests"
        # Tokens should differ (different keys)
        assert t1 != t2
        # But both should decrypt correctly with their own key
        assert decrypt_credentials(t1) == data
        os.environ["DDW_EMAIL_SECRET_KEY"] = "another-key"
        assert decrypt_credentials(t2) == data
        os.environ["DDW_EMAIL_SECRET_KEY"] = "test-secret-key-for-unit-tests"


# ==================================================================
# Test: Providers
# ==================================================================

class TestProviders:
    def test_registry_contains_qq_and_generic(self):
        """ProviderRegistry has both QQ and generic providers."""
        providers = ProviderRegistry.list_providers()
        assert "qq" in providers
        assert "generic" in providers

    def test_qq_mail_provider_defaults(self):
        """QQMailProvider has correct server defaults."""
        p = QQMailProvider()
        assert p.imap_host == "imap.qq.com"
        assert p.imap_port == 993
        assert p.smtp_host == "smtp.qq.com"
        assert p.smtp_port == 465

    def test_generic_imap_for_server_factory(self):
        """GenericIMAPProvider.for_server() creates configured instance."""
        p = GenericIMAPProvider.for_server(
            imap_host="imap.custom.com",
            imap_port=993,
            smtp_host="smtp.custom.com",
            smtp_port=587,
        )
        assert p.imap_host == "imap.custom.com"
        assert p.smtp_port == 587

    @patch("providers.base.imaplib.IMAP4_SSL")
    def test_provider_test_connection_success(self, mock_imap):
        """Provider.test_connection() returns success when both IMAP and SMTP connect."""
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn

        with patch("providers.base.smtplib.SMTP_SSL") as mock_smtp:
            mock_smtp.return_value = MagicMock()
            p = QQMailProvider()
            result = p.test_connection("test@qq.com", "code123")
            assert result["imap"] is True
            assert result["smtp"] is True
            assert result["success"] is True

    @patch("providers.base.imaplib.IMAP4_SSL")
    def test_provider_test_connection_failure(self, mock_imap):
        """Provider.test_connection() reports errors gracefully."""
        mock_imap.side_effect = ConnectionError("IMAP refused")
        with patch("providers.base.smtplib.SMTP_SSL") as mock_smtp:
            mock_smtp.side_effect = ConnectionError("SMTP refused")
            p = QQMailProvider()
            result = p.test_connection("test@qq.com", "code123")
            assert result["success"] is False
            assert len(result["errors"]) == 2


# ==================================================================
# Test: Account Service
# ==================================================================

class TestAccountService:
    def test_create_account(self, db_session, sample_account_data):
        """Create account stores encrypted credentials."""
        svc = AccountService(db_session)
        account = svc.create_account(sample_account_data)
        assert account["id"] is not None
        assert account["email"] == "test@example.com"
        # Verify credentials are encrypted in DB
        db_account = db_session.get(EmailAccount, account["id"])
        assert db_account.encrypted_creds != "test-auth-code-123"

    def test_list_accounts(self, db_session, created_account):
        """list_accounts returns all accounts."""
        svc = AccountService(db_session)
        accounts = svc.list_accounts()
        assert len(accounts) >= 1

    def test_update_account(self, db_session, created_account):
        """update_account modifies fields correctly."""
        svc = AccountService(db_session)
        updated = svc.update_account(created_account["id"], {"name": "Updated Name"})
        assert updated["name"] == "Updated Name"

    def test_delete_account(self, db_session, created_account):
        """delete_account removes the account."""
        svc = AccountService(db_session)
        assert svc.delete_account(created_account["id"]) is True
        assert svc.get_account(created_account["id"]) is None

    def test_delete_nonexistent_account(self, db_session):
        """Deleting a nonexistent account returns False."""
        svc = AccountService(db_session)
        assert svc.delete_account(99999) is False


# ==================================================================
# Test: AI Service
# ==================================================================

class TestAIService:
    def test_classify_spam(self):
        """AI service detects spam emails."""
        ai = AIService()
        result = ai.classify(
            subject="You won the lottery!",
            sender="spam@bogus.com",
            recipients="victim@example.com",
            cc="",
            body="Congratulations, you won $1,000,000!",
        )
        assert result["classification"] == "spam"
        assert result["confidence"] > 0.8

    def test_classify_newsletter(self):
        """AI service detects newsletter emails."""
        ai = AIService()
        result = ai.classify(
            subject="Weekly Tech Digest",
            sender="newsletter@techblog.com",
            recipients="me@example.com",
            cc="",
            body="Here is this week's update. To unsubscribe, click here.",
        )
        assert result["classification"] == "newsletter"

    def test_classify_info_only(self):
        """AI service detects notification emails."""
        ai = AIService()
        result = ai.classify(
            subject="Deploy succeeded",
            sender="noreply@ci.example.com",
            recipients="team@example.com",
            cc="",
            body="Build #42 completed successfully.",
        )
        assert result["classification"] == "info_only"

    def test_classify_simple_confirm(self):
        """AI service detects simple confirmation emails."""
        ai = AIService()
        result = ai.classify(
            subject="Re: Meeting Notes",
            sender="colleague@company.com",
            recipients="me@company.com",
            cc="",
            body="收到，已确认。",
        )
        assert result["classification"] == "simple_confirm"

    def test_classify_need_reply(self):
        """AI service classifies as need_reply by default."""
        ai = AIService()
        result = ai.classify(
            subject="Q3 Budget Review",
            sender="boss@company.com",
            recipients="me@company.com",
            cc="",
            body="请在周五前提交Q3预算报告。",
        )
        assert result["classification"] == "need_reply"

    def test_generate_draft_simple_confirm(self):
        """AI generates a simple confirmation draft."""
        ai = AIService()
        draft = ai.generate_draft(
            subject="Re: Meeting",
            sender="colleague@co.com",
            body="OK",
            classification="simple_confirm",
        )
        assert "收到" in draft or "谢谢" in draft

    def test_generate_draft_need_reply(self):
        """AI generates a professional reply draft."""
        ai = AIService()
        draft = ai.generate_draft(
            subject="Project Status",
            sender="pm@company.com",
            body="What is the current status of the project?",
            classification="need_reply",
        )
        assert len(draft) > 10
        assert "您好" in draft or "感谢" in draft


# ==================================================================
# Test: Audit Service
# ==================================================================

class TestAuditService:
    def test_log_and_query(self, db_session, created_account):
        """AuditService logs and queries audit entries."""
        svc = AuditService(db_session)
        svc.log("classify", {"result": "spam"}, account_id=created_account["id"])
        svc.log("draft", {"length": 200}, account_id=created_account["id"])
        logs = svc.query(account_id=created_account["id"])
        assert len(logs) == 2
        assert logs[0]["action"] == "draft"  # desc order

    def test_log_filter_by_action(self, db_session, created_account):
        """Audit query filters by action type."""
        svc = AuditService(db_session)
        svc.log("classify", account_id=created_account["id"])
        svc.log("reply", account_id=created_account["id"])
        svc.log("classify", account_id=created_account["id"])
        classify_logs = svc.query(action="classify", account_id=created_account["id"])
        assert len(classify_logs) == 2


# ==================================================================
# Test: Email Service (with mocked IMAP/SMTP)
# ==================================================================

class TestEmailService:
    def test_test_connection_returns_not_found(self, db_session):
        """test_connection for nonexistent account returns error."""
        svc = EmailService(db_session)
        result = svc.test_connection(99999)
        assert result["success"] is False

    def test_sync_messages_with_mocked_imap(self, db_session, created_account):
        """sync_messages fetches and stores parsed emails."""
        from email.mime.text import MIMEText

        # Create a mock email message
        mime = MIMEText("Hello world", "plain", "utf-8")
        mime["From"] = "alice@example.com"
        mime["To"] = "test@example.com"
        mime["Subject"] = "Test Subject"
        mime["Message-ID"] = "<mock-001@example.com>"
        mime["Date"] = "Mon, 13 Jul 2026 10:00:00 +0800"

        mock_raw = mime.as_bytes()

        with patch("providers.base.imaplib.IMAP4_SSL") as mock_imap:
            mock_conn = MagicMock()
            mock_imap.return_value = mock_conn
            mock_conn.search.return_value = ("OK", [b"1"])
            mock_conn.fetch.return_value = ("OK", [(b"1", (b"RFC822", mock_raw))])

            with patch("providers.base.smtplib.SMTP_SSL"):
                svc = EmailService(db_session)
                msgs = svc.sync_messages(created_account["id"])
                assert len(msgs) == 1
                assert msgs[0]["subject"] == "Test Subject"


# ==================================================================
# Test: API Router (via TestClient)
# ==================================================================

class TestRouter:
    def test_list_accounts_empty(self, client):
        """GET /api/email/accounts returns empty list initially."""
        resp = client.get("/api/email/accounts")
        assert resp.status_code == 200
        assert resp.json()["accounts"] == []

    def test_create_and_get_account(self, client):
        """POST then GET account via API."""
        resp = client.post("/api/email/accounts", json={
            "name": "API Test",
            "email": "api@test.com",
            "provider": "qq",
            "password": "code123",
        })
        assert resp.status_code == 200
        acct = resp.json()["account"]
        assert acct["email"] == "api@test.com"
        assert acct["provider"] == "qq"
        assert acct["imap_host"] == "imap.qq.com"
        assert acct["smtp_host"] == "smtp.qq.com"

    def test_update_account(self, client):
        """PUT update account name via API."""
        resp = client.post("/api/email/accounts", json={
            "name": "Old Name",
            "email": "upd@test.com",
            "provider": "generic",
            "password": "pw",
        })
        account_id = resp.json()["account"]["id"]
        resp = client.put(f"/api/email/accounts/{account_id}", json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["account"]["name"] == "New Name"

    def test_delete_account(self, client):
        """DELETE account via API."""
        resp = client.post("/api/email/accounts", json={
            "name": "To Delete",
            "email": "del@test.com",
            "provider": "generic",
            "password": "pw",
        })
        account_id = resp.json()["account"]["id"]
        resp = client.delete(f"/api/email/accounts/{account_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_list_messages_empty(self, client):
        """GET /api/email/messages returns empty list."""
        resp = client.get("/api/email/messages")
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    def test_stats(self, client):
        """GET /api/email/stats returns zero counts."""
        resp = client.get("/api/email/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_accounts"] == 0
        assert data["total_messages"] == 0

    def test_audit_log_empty(self, client):
        """GET /api/email/audit returns empty list."""
        resp = client.get("/api/email/audit")
        assert resp.status_code == 200
        assert resp.json()["logs"] == []

    def test_classify_nonexistent_message(self, client):
        """POST classify on nonexistent message returns 404."""
        resp = client.post("/api/email/messages/99999/classify", json={"classification": "spam"})
        assert resp.status_code == 404
