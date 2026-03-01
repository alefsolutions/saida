class SaidaCoreError(Exception):
    """Base exception for SAIDA Core."""


class ProviderNotRegisteredError(SaidaCoreError):
    pass