"""ML backend adapter placeholders for future implementation."""

from __future__ import annotations

from saida.exceptions import ModelTrainingError
from saida.core.contracts import ForecastResult, ModelSpec, ModelTrainingResult, PredictionResult

DEFERRED_ML_MESSAGE = (
    "ML features are deferred in the current SAIDA build. "
    "Use analyze(), profile(), and load_context() for the active non-ML surface."
)


class MlAdapter:
    """Reserve the ML adapter surface for a later implementation pass."""

    def train(self, spec: ModelSpec) -> ModelTrainingResult:
        """Raise a clear error until the ML layer is implemented."""
        raise ModelTrainingError(
            f"Model training for target '{spec.target}' is not implemented yet. "
            f"{DEFERRED_ML_MESSAGE}"
        )

    def predict(self) -> PredictionResult:
        """Raise a clear error until the prediction layer is implemented."""
        raise ModelTrainingError(f"Prediction is not implemented yet. {DEFERRED_ML_MESSAGE}")

    def forecast(self, target: str, horizon: int) -> ForecastResult:
        """Raise a clear error until the forecasting layer is implemented."""
        raise ModelTrainingError(
            f"Forecasting for target '{target}' with horizon {horizon} is not implemented yet. "
            f"{DEFERRED_ML_MESSAGE}"
        )


BaselineMlEngine = MlAdapter
