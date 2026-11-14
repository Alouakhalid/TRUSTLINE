"""Local ML Model Benchmarking: Evaluates Random Forest, HistGradientBoosting, and Isolation Forest."""
import time
import gc
import os
import joblib
import psutil
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, accuracy_score, precision_score, recall_score

from ..space_environment.space_assessment_bridge import SpaceAssessmentBridge


class MLBenchmarkRunner:
    """Rigorous evaluation harness comparing ML performance on real WESAD vs synthetic simulator datasets."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        real_data_path: Optional[Path] = None,
        models_dir: Optional[Path] = None,
        scalers_dir: Optional[Path] = None
    ):
        self.root = repo_root or Path(__file__).resolve().parents[3]
        self.real_data_path = real_data_path or (
            self.root / "ai-engine/ml/data/processed/wesad_window_features.csv"
        )
        self.models_dir = models_dir or (
            self.root / "ai-engine/ml/artifacts/final_models"
        )
        self.scalers_dir = scalers_dir or (
            self.root / "ai-engine/ml/artifacts/evaluation_v2"
        )

        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Load trained model binaries and preprocessors."""
        rf_path = self.models_dir / "best_supervised_random_forest.pkl"
        hgb_path = self.models_dir / "best_hist_gradient_boosting.pkl"
        iso_path = self.models_dir / "best_unsupervised_isolation_forest.pkl"

        self.rf_model = joblib.load(str(rf_path)) if rf_path.exists() else None
        self.hgb_model = joblib.load(str(hgb_path)) if hgb_path.exists() else None
        self.iso_model = joblib.load(str(iso_path)) if iso_path.exists() else None

        features_json = self.root / "ai-engine/ml/artifacts/configurations/selected_features.json"
        features_csv = self.scalers_dir / "selected_features.csv"

        if features_json.exists():
            import json
            with open(features_json, "r") as f:
                self.feature_columns = json.load(f)
        elif features_csv.exists():
            feat_df = pd.read_csv(str(features_csv))
            self.feature_columns = feat_df["Feature"].tolist()[:14]
        else:
            self.feature_columns = [
                "hr_mean_bpm", "hr_std_bpm", "hrv_rmssd_ms", "hrv_sdnn_ms",
                "eda_mean", "eda_std", "eda_iqr", "resp_rate_bpm",
                "resp_std", "temp_mean", "temp_std", "emg_rms",
                "acc_magnitude_mean", "acc_magnitude_std"
            ]

    def verify_radiation_isolation(self) -> bool:
        """Formally verifies that space radiation parameters are 100% absent from ML feature vectors."""
        is_isolated = SpaceAssessmentBridge.verify_ml_isolation(self.feature_columns)
        if not is_isolated:
            raise AssertionError("CRITICAL VIOLATION: Space radiation detected in physiological ML feature vector!")
        return is_isolated

    def load_real_wesad_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """Load and prepare real WESAD dataset."""
        if not self.real_data_path.exists():
            raise FileNotFoundError(f"Real WESAD dataset not found at {self.real_data_path}")

        df = pd.read_csv(str(self.real_data_path))
        y = df["label"]
        available_feats = [c for c in self.feature_columns if c in df.columns]
        X = df[available_feats].copy()
        X = X.fillna(X.median())
        return X, y

    def generate_synthetic_benchmark_dataset(self, n_windows: int = 150) -> Tuple[pd.DataFrame, pd.Series]:
        """Generate synthetic feature windows matching WESAD schema across Scenarios A-D."""
        rng = np.random.default_rng(42)
        rows = []
        labels = []

        for i in range(n_windows):
            # Equal distribution across Baseline (1), Stress (2), Amusement/Activity (3)
            label = (i % 3) + 1
            labels.append(label)

            row: Dict[str, float] = {}
            if label == 1:  # Baseline Rest
                hr_base = rng.normal(70.0, 4.0)
                rmssd_base = rng.normal(52.0, 6.0)
                resp_base = rng.normal(14.0, 1.5)
                eda_base = rng.normal(2.5, 0.4)
                temp_base = rng.normal(36.8, 0.1)
                acc_std = rng.normal(0.02, 0.005)
            elif label == 2:  # Acute Stress
                hr_base = rng.normal(98.0, 7.0)
                rmssd_base = rng.normal(19.0, 3.0)
                resp_base = rng.normal(23.0, 2.5)
                eda_base = rng.normal(8.0, 1.2)
                temp_base = rng.normal(36.9, 0.15)
                acc_std = rng.normal(0.04, 0.01)
            else:  # Activity
                hr_base = rng.normal(135.0, 10.0)
                rmssd_base = rng.normal(22.0, 4.0)
                resp_base = rng.normal(27.0, 3.0)
                eda_base = rng.normal(11.0, 2.0)
                temp_base = rng.normal(37.5, 0.2)
                acc_std = rng.normal(0.45, 0.08)

            for col in self.feature_columns:
                low = col.lower()
                if "hr_mean" in low:
                    row[col] = hr_base
                elif "hr_std" in low:
                    row[col] = abs(rng.normal(6.0, 1.0))
                elif "hrv_rmssd" in low:
                    row[col] = rmssd_base
                elif "hrv_sdnn" in low:
                    row[col] = rmssd_base * 1.2
                elif "resp_rate" in low:
                    row[col] = resp_base
                elif "eda_mean" in low:
                    row[col] = eda_base
                elif "temp_mean" in low:
                    row[col] = temp_base
                elif "acc" in low and "std" in low:
                    row[col] = acc_std
                elif "acc" in low and "mean" in low:
                    row[col] = 0.95
                else:
                    row[col] = rng.normal(0.0, 1.0)

            rows.append(row)

        X_synth = pd.DataFrame(rows)
        y_synth = pd.Series(labels, name="label")
        return X_synth, y_synth

    def benchmark_model(
        self,
        model_name: str,
        model: Any,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        is_unsupervised: bool = False
    ) -> Dict[str, Any]:
        """Profile latency, memory, throughput, and metrics for a single model."""
        if model is None:
            return {"error": f"Model {model_name} not available"}

        proc = psutil.Process(os.getpid())
        gc.collect()
        mem_before_mb = proc.memory_info().rss / (1024.0 * 1024.0)

        # Single-window streaming latency profiling (100 repetitions)
        latencies_ms: List[float] = []
        n_eval = min(len(X), 100)
        single_windows = [X.iloc[i:i+1] for i in range(n_eval)]

        for w in single_windows:
            t0 = time.perf_counter()
            _ = model.predict(w)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

        # Batch throughput profiling
        t_batch_0 = time.perf_counter()
        preds = model.predict(X)
        t_batch_1 = time.perf_counter()
        batch_duration_sec = max(1e-5, t_batch_1 - t_batch_0)
        throughput_windows_sec = len(X) / batch_duration_sec

        mem_after_mb = proc.memory_info().rss / (1024.0 * 1024.0)
        mem_delta_mb = max(0.0, mem_after_mb - mem_before_mb)

        result: Dict[str, Any] = {
            "model_name": model_name,
            "sample_count": len(X),
            "feature_count": X.shape[1],
            "latency_ms": {
                "mean": round(float(np.mean(latencies_ms)), 3),
                "median": round(float(np.median(latencies_ms)), 3),
                "p95": round(float(np.percentile(latencies_ms, 95)), 3),
                "min": round(float(np.min(latencies_ms)), 3),
                "max": round(float(np.max(latencies_ms)), 3)
            },
            "throughput_windows_per_sec": round(throughput_windows_sec, 1),
            "memory_footprint_mb": round(mem_delta_mb, 2)
        }

        if not is_unsupervised and y is not None:
            # Map predictions if needed
            result["metrics"] = {
                "accuracy": round(float(accuracy_score(y, preds)), 4),
                "f1_macro": round(float(f1_score(y, preds, average="macro", zero_division=0)), 4),
                "f1_weighted": round(float(f1_score(y, preds, average="weighted", zero_division=0)), 4),
                "precision_macro": round(float(precision_score(y, preds, average="macro", zero_division=0)), 4),
                "recall_macro": round(float(recall_score(y, preds, average="macro", zero_division=0)), 4)
            }
        elif is_unsupervised:
            # Isolation Forest anomaly percentage (-1 is outlier, 1 is inlier)
            outlier_ratio = float(np.mean(preds == -1))
            result["metrics"] = {
                "anomaly_detection_rate": round(outlier_ratio, 4),
                "inlier_count": int(np.sum(preds == 1)),
                "outlier_count": int(np.sum(preds == -1))
            }

        return result

    def run_full_ml_benchmark(self) -> Dict[str, Any]:
        """Execute full comparative benchmark on real WESAD vs synthetic simulator datasets."""
        # Step 0: Ensure strict space radiation isolation
        self.verify_radiation_isolation()

        X_real, y_real = self.load_real_wesad_data()
        X_synth, y_synth = self.generate_synthetic_benchmark_dataset(n_windows=len(X_real))

        results: Dict[str, Any] = {
            "benchmark_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "radiation_isolated": True,
            "feature_count": len(self.feature_columns),
            "dataset_sizes": {
                "real_wesad_windows": len(X_real),
                "synthetic_simulator_windows": len(X_synth)
            },
            "real_wesad_benchmark": {
                "random_forest": self.benchmark_model("RandomForest", self.rf_model, X_real, y_real),
                "hist_gradient_boosting": self.benchmark_model("HistGradientBoosting", self.hgb_model, X_real, y_real),
                "isolation_forest": self.benchmark_model("IsolationForest", self.iso_model, X_real, is_unsupervised=True)
            },
            "synthetic_simulator_benchmark": {
                "random_forest": self.benchmark_model("RandomForest", self.rf_model, X_synth, y_synth),
                "hist_gradient_boosting": self.benchmark_model("HistGradientBoosting", self.hgb_model, X_synth, y_synth),
                "isolation_forest": self.benchmark_model("IsolationForest", self.iso_model, X_synth, is_unsupervised=True)
            }
        }
        return results
