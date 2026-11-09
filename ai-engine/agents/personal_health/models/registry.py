"""Registry of production ML artifacts and clinical telemetry models."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from ..config.settings import get_settings
from ..schemas.ml_prediction import ModelMetadata

class ModelRegistry:
    """Registry maintaining metadata and loading paths for production models."""

    def __init__(self, artifacts_dir: Optional[Path] = None):
        cfg = get_settings()
        self.artifacts_dir = artifacts_dir or cfg.ml_artifacts_dir

    def get_selected_features(self) -> List[str]:
        """Load ordered 14 core features required for inference."""
        config_path = self.artifacts_dir / "configurations" / "selected_features.json"
        if not config_path.exists():
            return [
                "hr_mean_bpm", "hr_std_bpm", "hrv_rmssd_ms", "hrv_sdnn_ms",
                "eda_mean", "eda_std", "eda_iqr", "resp_rate_bpm", "resp_std",
                "temp_mean", "temp_std", "emg_rms", "acc_magnitude_mean", "acc_magnitude_std"
            ]
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_champion_model_metadata(self) -> ModelMetadata:
        """Retrieve metadata for primary production classifier."""
        features = self.get_selected_features()
        return ModelMetadata(
            model_id="HGB-WESAD-PROD-V1",
            model_name="HistGradientBoosting Stress Classifier",
            version="1.0.0",
            model_type="HistGradientBoostingClassifier",
            target_definition="Binary acute psychological/cognitive stress state vs non-stress baseline",
            decision_threshold=0.50,
            expected_features=features,
            training_dataset="WESAD (Wearable Stress and Affect Detection) Benchmark",
            known_limitations=(
                "Trained on laboratory stress induction protocols (TSST) from the WESAD benchmark. "
                "Predicts acute sympathovagal stress activation; not validated as general health or disease anomaly detector. "
                "Requires valid Core 14 physiological features centered with production RobustScaler."
            ),
            is_active=True
        )

    def get_model_file_path(self, model_filename: str = "best_hist_gradient_boosting.pkl") -> Path:
        """Resolve absolute path to model binary pickle."""
        path = self.artifacts_dir / "final_models" / model_filename
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at: {path}")
        return path

    def get_scaler_file_path(self) -> Path:
        """Resolve path to production RobustScaler."""
        path = self.artifacts_dir / "scalers" / "final_robust_scaler.pkl"
        if not path.exists():
            raise FileNotFoundError(f"RobustScaler artifact not found at: {path}")
        return path

    def get_imputer_file_path(self) -> Path:
        """Resolve path to production SimpleImputer."""
        path = self.artifacts_dir / "imputers" / "final_imputer.pkl"
        if not path.exists():
            raise FileNotFoundError(f"Imputer artifact not found at: {path}")
        return path
