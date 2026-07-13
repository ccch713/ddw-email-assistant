"""DDW Email Assistant providers package."""

from providers.base import EmailProvider, ProviderRegistry
from providers.qq_mail import QQMailProvider
from providers.generic_imap import GenericIMAPProvider

__all__ = ["EmailProvider", "ProviderRegistry", "QQMailProvider", "GenericIMAPProvider"]
