"""DDW Email Assistant — main plugin class.

Inherits PluginBase and wires up services + routes.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI

from models import Base, init_db

logger = logging.getLogger(__name__)

# Avoid circular import by doing a lazy import of PluginBase
# The SDK may not be on sys.path in all environments (tests, standalone)
try:
    from sdk.plugin_base import PluginBase
except ImportError:
    # Standalone / test mode — provide a minimal shim
    class PluginBase:  # type: ignore[no-redef]
        name = "unnamed-plugin"
        version = "0.1.0"
        router_prefix = ""
        def __init__(self, app: Any, config: Any = None, manifest: Any = None) -> None:
            from fastapi import APIRouter
            self.app = app
            self.manifest = manifest or {}
            self.config = config or {}
            self.router = APIRouter(prefix=self.router_prefix or f"/api/v1/plugins/{self.name}", tags=[self.name])
        def setup(self) -> None: pass
        def register(self) -> None: self.app.include_router(self.router)


class DDWEmailAssistant(PluginBase):
    """DDW Email Assistant plugin — enterprise email automation."""

    name = "ddw-email-assistant"
    version = "1.0.0"
    router_prefix = "/api/v1/plugins/ddw-email-assistant"

    def __init__(
        self,
        app: FastAPI,
        config: Optional[Dict[str, Any]] = None,
        manifest: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(app, config=config, manifest=manifest)
        # Initialize database
        db_path = os.environ.get(
            "DDW_EMAIL_DB_PATH",
            os.path.join(os.path.dirname(__file__), "email_assistant.db"),
        )
        db_url = f"sqlite:///{db_path}"
        self.engine = init_db(db_url)
        logger.info("DDW Email Assistant initialized (db=%s)", db_path)

    def setup(self) -> None:
        """Mount email routes onto the plugin router."""
        from router import router as email_router

        # Include the email sub-router under the plugin prefix
        self.router.include_router(email_router)
        self.register()
        logger.info("DDW Email Assistant routes registered")
