"""Optional SHAP explainability module for ML-based quality classification."""
from typing import Dict, Any, Optional, List
import numpy as np

class QualityShapExplainer:
    """Explainer for machine learning quality models with graceful fallback."""

    def __init__(self, model: Optional[Any] = None, feature_names: Optional[List[str]] = None):
        self.model = model
        self.feature_names = feature_names or []
        self._shap_available = False
        self._explainer = None

        if self.model is not None:
            try:
                import shap
                self._shap_available = True
                self._explainer = shap.TreeExplainer(self.model)
            except Exception:
                self._shap_available = False

    def is_configured(self) -> bool:
        return self.model is not None and self._shap_available and self._explainer is not None

    def explain_sample(self, features: np.ndarray) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "NOT_CONFIGURED",
                "message": "No machine-learning quality classification model is configured. Rule-based DSP explainability is active."
            }

        try:
            shap_values = self._explainer.shap_values(features)
            contributions = {}
            flat_shap = np.array(shap_values).flatten()
            for idx, val in enumerate(flat_shap):
                name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
                contributions[name] = float(val)

            return {
                "status": "EXPLAINED",
                "feature_contributions": contributions,
                "base_value": float(self._explainer.expected_value) if hasattr(self._explainer, "expected_value") else 0.0
            }
        except Exception as exc:
            return {
                "status": "ERROR",
                "message": f"SHAP calculation failure: {str(exc)}"
            }
