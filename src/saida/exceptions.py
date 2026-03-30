"""Library-specific exception hierarchy."""


class SaidaError(Exception):
    """Base exception for SAIDA."""


class ValidationError(SaidaError):
    """Raised when user input or dataset shape is invalid."""


class AdapterError(SaidaError):
    """Raised when data loading fails."""


class ContextError(SaidaError):
    """Raised when semantic context parsing fails."""


class ProfileError(SaidaError):
    """Raised when dataset profiling fails."""


class PlanningError(SaidaError):
    """Raised when request planning fails."""


class ComputeError(SaidaError):
    """Raised when deterministic computation fails."""


class ModelTrainingError(SaidaError):
    """Raised when model training fails."""


class LlmIntegrationError(SaidaError):
    """Raised when optional LLM integration fails."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "integration_error",
        provider: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.provider = provider
