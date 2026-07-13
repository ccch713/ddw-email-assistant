"""DDW Email Assistant — bridge entry point.

The DDW platform discovers plugins via this module's ``register(app)`` function.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from main import DDWEmailAssistant


def register(app: FastAPI) -> None:
    """Called by the DDW plugin loader to mount the email assistant."""
    plugin = DDWEmailAssistant(app)
    # Routes are already mounted inside __init__ → setup → register
