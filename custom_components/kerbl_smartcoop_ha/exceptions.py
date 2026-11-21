"""Exceptions for the Kerbl SmartCoop integration."""


class KerblSmartCoopError(Exception):
    """Base error."""


class KerblAuthError(KerblSmartCoopError):
    """Invalid credentials or expired session."""


class KerblApiError(KerblSmartCoopError):
    """API returned an unexpected error."""


class KerblConnectionError(KerblSmartCoopError):
    """Network/connection problem."""
