"""ML inference service executing production WESAD stress classification."""
from datetime import datetime
from typing import Dict, List, Optional, Any
import joblib
import numpy as np
import pandas as pd
from ..models.registry import ModelRegistry
from ..schemas.physiological_features import Core14Features
from ..schemas.ml_prediction import MLInferenceResult

class MLInferenceService:
    """Production inference engine for physiological stress telemetry."""

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or ModelRegistry()
        self._load_artifacts()

    def _load_artifacts(self):
        """Load and cache binary model, imputer, and scaler artifacts."""
        model_path = self.registry.get_model_file_path("best_hist_gradient_boosting.pkl")
        scaler_path = self.registry.get_scaler_file_path()
        imputer_path = self.registry.get_imputer_file_path()

        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        self.imputer = joblib.load(imputer_path)
        self.expected_features = self.registry.get_selected_features()
        self.metadata = self.registry.get_champion_model_metadata()

    def predict_stress(self, features: Core14Features) -> MLInferenceResult:
        """Execute calibrated prediction using verified 14-feature vector."""
        feat_dict = features.to_feature_dict()
        df = pd.DataFrame([feat_dict], columns=self.expected_features)
        x_imputed = self.imputer.transform(df[self.expected_features])
        x_scaled = self.scaler.transform(x_imputed)

        probabilities = self.model.predict_proba(x_scaled)
        stress_prob = float(probabilities[0, 1])
        stress_prob = round(stress_prob, 4)

        threshold = self.metadata.decision_threshold
        verdict = "STRESS_ALERT" if stress_prob >= threshold else "NORMAL"

        return MLInferenceResult(
            model_id=self.metadata.model_id,
            model_name=self.metadata.model_name,
            version=self.metadata.version,
            target_definition=self.metadata.target_definition,
            stress_probability=stress_prob,
            verdict=verdict,
            threshold_applied=threshold,
            raw_feature_values=feat_dict,
            inference_timestamp=datetime.utcnow(),
            validity_status="VALID",
            clinical_disclaimer=self.metadata.known_limitations
        )

    def predict_from_dict(self, feature_map: Dict[str, float]) -> Optional[MLInferenceResult]:
        """Validate input map and generate prediction if core features are present."""
        for feat in self.expected_features:
            if feat not in feature_map or feature_map[feat] is None or np.isnan(feature_map[feat]):
                return None

        core = Core14Features(**{k: float(feature_map[k]) for k in self.expected_features})
        return self.predict_stress(core)
