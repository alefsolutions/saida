"""ML backend adapter placeholders for future implementation."""

from __future__ import annotations

from saida.adapters.interfaces import ComputeInterface, ComputeRequest, ComputeResponse
from saida.exceptions import ModelTrainingError
from saida.core.contracts import ForecastResult, ModelSpec, ModelTrainingResult, PredictionResult

DEFERRED_ML_MESSAGE = (
    "ML features are deferred in the current SAIDA build. "
    "Use analyze(), profile(), and load_context() for the active non-ML surface."
)


class MlAdapter(ComputeInterface):
    """Reserve the ML adapter surface for a later implementation pass."""

    @property
    def tool_family(self) -> str:
        return "ml"

    def supported_methods(self) -> tuple[str, ...]:
        return ("forecast",)

    def execute(self, request: ComputeRequest) -> ComputeResponse:
        if request.method_id != "forecast":
            raise ModelTrainingError(f"ML method {request.method_id!r} is not implemented yet. {DEFERRED_ML_MESSAGE}")
        target = request.parameters.get("target")
        horizon = request.parameters.get("horizon", 3)
        if not isinstance(target, str):
            raise ModelTrainingError(f"ML forecast target is required. {DEFERRED_ML_MESSAGE}")
        self.forecast(target, int(horizon))
        return ComputeResponse()

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
