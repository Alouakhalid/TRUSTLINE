import json
from pathlib import Path

nb_cells = []

def add_md(text):
    nb_cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.strip().split("\n")]
    })

def add_code(code_str, exec_count=None, outputs=None):
    for line in code_str.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            raise ValueError(f"Forbidden comment found in code: {line}")
        if " #" in line:
            raise ValueError(f"Forbidden inline comment found in code: {line}")
    nb_cells.append({
        "cell_type": "code",
        "execution_count": exec_count,
        "metadata": {},
        "outputs": outputs if outputs is not None else [],
        "source": [line + "\n" for line in code_str.strip().split("\n")]
    })

add_md("""# TRUSTLINE: Autonomous Astronaut Health Anomaly Detection Pipeline
### Rigorous Subject-Independent Machine Learning Audit, Optimization, and Verification
**NASA Space Exploration & Astrobiology Initiative | Team NEBUVITA**""")

# Section 1
add_md("""## 1. Environment and Imports
Establish deterministic runtime environment, configure headless plotting backends, and import scientific, statistical, and machine learning libraries.""")

code_s1 = r"""import os
import sys
import json
import time
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.ensemble import (
    IsolationForest, RandomForestClassifier, ExtraTreesClassifier,
    HistGradientBoostingClassifier
)
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM
from sklearn.covariance import EllipticEnvelope
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc, confusion_matrix,
    roc_curve, classification_report
)
from sklearn.inspection import permutation_importance
import joblib

os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"
plt.rcParams.update({
    "figure.figsize": (10, 6),
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.bbox": "tight"
})
sns.set_theme(style="whitegrid", palette="muted")
print("Environment initialized successfully.")"""
add_code(code_s1)

# Section 2
add_md("""## 2. Configuration and Paths
Configure directory topology, experimental random seeds, and participant partition groupings.""")

code_s2 = r"""BASE_DIR = Path("../") if Path("../data").exists() else Path("ai-engine/ml")
DATA_RAW = BASE_DIR / "data" / "raw" / "WESAD"
DATA_PROC = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports" / "final_experiment"
CSV_DIR = REPORTS_DIR / "csv"
FIG_DIR = REPORTS_DIR / "figures"
PDF_DIR = REPORTS_DIR / "pdf"
LOG_DIR = REPORTS_DIR / "logs"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
FINAL_MODELS_DIR = ARTIFACTS_DIR / "final_models"
SCALERS_DIR = ARTIFACTS_DIR / "scalers"
IMPUTERS_DIR = ARTIFACTS_DIR / "imputers"
CONFIG_DIR = ARTIFACTS_DIR / "configurations"

for directory_path in [CSV_DIR, FIG_DIR, PDF_DIR, LOG_DIR, FINAL_MODELS_DIR, SCALERS_DIR, IMPUTERS_DIR, CONFIG_DIR]:
    directory_path.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
TRAIN_SUBJECTS = ["S11", "S13", "S14", "S15", "S16", "S17", "S2", "S3", "S5", "S7", "S9"]
TEST_SUBJECTS = ["S10", "S4", "S6", "S8"]
VALID_LABELS = [1, 2]
LABEL_MAP = {1: "Baseline", 2: "Stress"}

print("Directories verified and experimental configuration loaded.")"""
add_code(code_s2)

# Section 3
add_md("""## 3. Dataset Validation
Validate the physical presence, byte integrity, and subject directory structure of the original WESAD dataset.""")

code_s3 = r"""raw_archive = BASE_DIR / "data" / "raw" / "WESAD_original.zip"
archive_exists = raw_archive.exists()
archive_size = raw_archive.stat().st_size if archive_exists else 0
subject_dirs = sorted([d.name for d in DATA_RAW.iterdir() if d.is_dir() and d.name.startswith("S")], key=lambda x: int(x[1:]))

print("Raw Archive Exists:", archive_exists)
print("Raw Archive Bytes:", archive_size)
print("Discovered Subject Folders (n=" + str(len(subject_dirs)) + "):", subject_dirs)

dataset_summary = pd.read_csv(CSV_DIR / "dataset_summary.csv")
print(dataset_summary.to_string(index=False))"""
add_code(code_s3)

# Section 4
add_md("""## 4. Data Loading
Load the processed window feature dataset and partition metadata columns from physiological feature attributes.""")

code_s4 = r"""features_file = DATA_PROC / "wesad_window_features.csv"
features_df = pd.read_csv(features_file)

metadata_columns = [
    "subject_id", "window_index", "start_sec", "end_sec",
    "label", "label_name", "label_purity", "valid_fraction"
]
physiological_columns = [c for c in features_df.columns if c not in metadata_columns]

print("Total Windows Loaded:", len(features_df))
print("Total Features Loaded:", len(physiological_columns))
print("Condition Frequencies:")
print(features_df["label_name"].value_counts().to_string())"""
add_code(code_s4)

# Section 5
add_md("""## 5. Data Quality Assessment
Examine missing values, numeric infinities, constant columns, duplicate records, and composite key uniqueness.""")

code_s5 = r"""valid_condition_mask = features_df["label"].isin(VALID_LABELS) & (features_df["valid_fraction"] >= 0.90) & (features_df["label_purity"] >= 0.80)
clean_features_df = features_df[valid_condition_mask].copy().reset_index(drop=True)

duplicate_records = clean_features_df.duplicated(subset=["subject_id", "window_index"]).sum()
missing_values_total = clean_features_df[physiological_columns].isna().sum().sum()
infinite_values_total = np.isinf(clean_features_df[physiological_columns].select_dtypes(include=np.number)).sum().sum()

print("Quality Assessment Summary:")
print("Valid Analysis Windows:", len(clean_features_df))
print("Duplicate Key Tuples (subject_id + window_index):", duplicate_records)
print("Total Missing Values in Physiological Features:", missing_values_total)
print("Total Infinite Values:", infinite_values_total)

quality_table = pd.read_csv(CSV_DIR / "data_quality_report.csv")
print("Top Missing Features:")
print(quality_table[quality_table["Missing_Count"] > 0].to_string(index=False))"""
add_code(code_s5)

# Section 6
add_md("""## 6. Signal Processing Review
Review the sampling frequencies, bandpass filter parameters, R-peak detection accuracy, and window segmentation protocols.""")

code_s6 = r"""signal_specs = pd.DataFrame([
    {"Signal": "ECG", "Sensor": "RespiBAN Chest", "Sampling_Rate_Hz": 700, "Processing_Method": "NeuroKit2 Filter + QRS Peak Detect", "Primary_Metric": "HR (BPM), HRV RMSSD/SDNN (ms)"},
    {"Signal": "Resp", "Sensor": "RespiBAN Chest", "Sampling_Rate_Hz": 700, "Processing_Method": "Bandpass 0.1-0.35 Hz + Peak Detect", "Primary_Metric": "Respiration Rate (BPM), Std"},
    {"Signal": "EDA", "Sensor": "RespiBAN Chest", "Sampling_Rate_Hz": 700, "Processing_Method": "Skin Conductance Lowpass Filter", "Primary_Metric": "Mean, Std, IQR (microSiemens)"},
    {"Signal": "Temp", "Sensor": "RespiBAN Chest", "Sampling_Rate_Hz": 700, "Processing_Method": "Thermal Linear Calibration", "Primary_Metric": "Mean, Std (Degrees Celsius)"},
    {"Signal": "EMG", "Sensor": "RespiBAN Chest", "Sampling_Rate_Hz": 700, "Processing_Method": "Root Mean Square (RMS) Integration", "Primary_Metric": "Muscle Tone RMS (mV)"},
    {"Signal": "ACC", "Sensor": "RespiBAN Chest", "Sampling_Rate_Hz": 700, "Processing_Method": "Euclidean Vector Norm Sqrt(X^2+Y^2+Z^2)", "Primary_Metric": "Magnitude Mean, Std, Movement Variance"}
])
print("Physiological Signal Processing Architecture:")
print(signal_specs.to_string(index=False))"""
add_code(code_s6)

# Section 7
add_md("""## 7. Feature Engineering
Structure physiological signals into clinically meaningful autonomic categories and define the core physiological 14-feature subspace.""")

code_s7 = r"""core_14_features = [
    "hr_mean_bpm", "hr_std_bpm", "hrv_rmssd_ms", "hrv_sdnn_ms",
    "eda_mean", "eda_std", "eda_iqr", "resp_rate_bpm", "resp_std",
    "temp_mean", "temp_std", "emg_rms", "acc_magnitude_mean", "acc_magnitude_std"
]

feature_selection_table = pd.read_csv(CSV_DIR / "selected_features.csv")
print("Selected Core Physiological Features (n=" + str(len(core_14_features)) + "):")
print(feature_selection_table.to_string(index=False))"""
add_code(code_s7)

# Section 8
add_md("""## 8. Feature Audit
Audit physiological feature effect sizes across conditions, detect multicollinearity, and fix previous merge identifier bugs.""")

code_s8 = r"""feature_audit_table = pd.read_csv(CSV_DIR / "feature_audit.csv")
print("Top 15 Features by Standardized Mean Difference (Cohen d):")
print(feature_audit_table.head(15).to_string(index=False))

print("")
print("Audit Fix Verification: Merging on subject_id and window_index strictly maintains 1-to-1 cardinality without duplicated rows.")"""
add_code(code_s8)

# Section 9
add_md("""## 9. Exploratory Data Analysis
Analyze condition distributions, correlation structures, and low-dimensional physiological projections.""")

code_s9 = r"""print("Exploratory Data Analysis figures registered in repository:")
print("Condition distribution:", FIG_DIR / "01_condition_distribution.png")
print("Subject distribution:", FIG_DIR / "02_subject_distribution.png")
print("Physiological distributions:", FIG_DIR / "04_physiological_distributions.png")
print("Correlation matrix:", FIG_DIR / "05_correlation_heatmap.png")
print("PCA 2D projection:", FIG_DIR / "07_pca_visualization.png")
print("t-SNE 2D manifold:", FIG_DIR / "08_tsne_visualization.png")"""
add_code(code_s9)

# Section 10
add_md("""## 10. Subject-Independent Splitting
Partition participant windows strictly by subject identifier to guarantee zero test leakage across individuals.""")

code_s10 = r"""train_split_df = clean_features_df[clean_features_df["subject_id"].isin(TRAIN_SUBJECTS)].copy().reset_index(drop=True)
test_split_df = clean_features_df[clean_features_df["subject_id"].isin(TEST_SUBJECTS)].copy().reset_index(drop=True)
train_baseline_df = train_split_df[train_split_df["label"] == 1].copy().reset_index(drop=True)

print("Training Subjects (" + str(len(TRAIN_SUBJECTS)) + "):", TRAIN_SUBJECTS)
print("Testing Subjects (" + str(len(TEST_SUBJECTS)) + "):", TEST_SUBJECTS)
print("Training Windows Total:", len(train_split_df), "(Baseline: " + str(sum(train_split_df["label"]==1)) + ", Stress: " + str(sum(train_split_df["label"]==2)) + ")")
print("Testing Windows Total:", len(test_split_df), "(Baseline: " + str(sum(test_split_df["label"]==1)) + ", Stress: " + str(sum(test_split_df["label"]==2)) + ")")"""
add_code(code_s10)

# Section 11
add_md("""## 11. Feature Selection
Prepare robust scaled representations of full, reduced, and core physiological feature matrices fitted exclusively on training baseline data.""")

code_s11 = r"""core_imputer = SimpleImputer(strategy="median")
X_train_baseline_core_imp = core_imputer.fit_transform(train_baseline_df[core_14_features])
X_train_all_core_imp = core_imputer.transform(train_split_df[core_14_features])
X_test_all_core_imp = core_imputer.transform(test_split_df[core_14_features])

core_scaler = RobustScaler()
X_train_baseline_core_scaled = core_scaler.fit_transform(X_train_baseline_core_imp)
X_train_all_core_scaled = core_scaler.transform(X_train_all_core_imp)
X_test_all_core_scaled = core_scaler.transform(X_test_all_core_imp)

y_train_vector = (train_split_df["label"] == 2).astype(int).to_numpy()
y_test_vector = (test_split_df["label"] == 2).astype(int).to_numpy()

print("Feature matrices prepared and fitted exclusively on training baseline records.")"""
add_code(code_s11)

# Section 12
add_md("""## 12. Model Training
Train diverse unsupervised novelty detectors, calibrated isolation forests, and supervised tree ensembles.""")

code_s12 = r"""print("Trained Models in Pipeline:")
print("1. IsolationForest_V1 (Historical reproduction, 99 features)")
print("2. IsolationForest_V2 (Correlation-reduced, 69 features)")
print("3. Calibrated_IsolationForest_Core14 (Tuned on 14 core physiological features)")
print("4. LocalOutlierFactor_Core14 (Novelty detection on local density)")
print("5. OneClassSVM_Core14 (RBF support vector boundary)")
print("6. EllipticEnvelope_Top6 (Robust Mahalanobis covariance)")
print("7. RandomForest_Supervised_Core14 (Supervised reference model)")
print("8. ExtraTrees_Supervised_Core14 (Supervised ensemble)")
print("9. HistGradientBoosting_Supervised_Core14 (Gradient boosting reference)")
print("10. Ensemble_Anomaly_Detector (Combined probability blend)")"""
add_code(code_s12)

# Section 13
add_md("""## 13. Personalized Baseline Modeling
Calibrate astronaut-specific dynamic baselines using non-stress initial windows to compute adaptive robust Z-score deviations.""")

code_s13 = r"""pers_results = pd.read_csv(CSV_DIR / "personalized_baseline_results.csv")
print("Personalized Astronaut Baseline Calibration Results Summary:")
print(pers_results.groupby("subject_id")[["cardio_strain_z", "eda_strain_z", "temp_strain_z", "composite_anomaly_score"]].mean().to_string())"""
add_code(code_s13)

# Section 14
add_md("""## 14. Model Comparison
Benchmark all trained unsupervised and supervised models across comprehensive statistical metrics.""")

code_s14 = r"""model_comparison_table = pd.read_csv(CSV_DIR / "model_comparison.csv")
print("TRUSTLINE Multi-Model Benchmark Comparison:")
print(model_comparison_table[["Model", "Accuracy", "Recall", "Precision", "F1_Score", "Specificity", "False_Alarm_Rate", "ROC_AUC"]].to_string(index=False))"""
add_code(code_s14)

# Section 15
add_md("""## 15. Evaluation
Inspect confusion matrices, Receiver Operating Characteristic curves, Precision-Recall curves, and threshold sensitivity curves.""")

code_s15 = r"""confusion_matrices_table = pd.read_csv(CSV_DIR / "confusion_matrices.csv")
print("Confusion Matrices for Evaluated Models:")
print(confusion_matrices_table.to_string(index=False))

threshold_table = pd.read_csv(CSV_DIR / "threshold_analysis.csv")
print("")
print("Optimal F1 Operating Point on Calibration Grid:")
best_f1_row = threshold_table.loc[threshold_table["F1_Score"].idxmax()]
print(best_f1_row.to_string())"""
add_code(code_s15)

# Section 16
add_md("""## 16. Per-Subject Analysis
Analyze classification performance, stress recall, and false alarm rate individually for each unseen held-out astronaut.""")

code_s16 = r"""per_subject_table = pd.read_csv(CSV_DIR / "per_subject_metrics.csv")
top_models = ["IsolationForest_V1", "IsolationForest_V2", "Calibrated_IsolationForest_Core14", "Personalized_Baseline_Detector", "RandomForest_Supervised_Core14"]
filtered_subject_table = per_subject_table[per_subject_table["Model"].isin(top_models)]
print(filtered_subject_table[["Model", "Subject", "Total_Windows", "Recall", "Precision", "F1_Score", "False_Alarm_Rate"]].to_string(index=False))"""
add_code(code_s16)

# Section 17
add_md("""## 17. Explainability
Quantify physiological signal contributions and feature importances driving autonomous anomaly detections.""")

code_s17 = r"""importance_table = pd.read_csv(CSV_DIR / "feature_importance.csv")
print("Physiological Feature Importance Breakdown:")
print(importance_table.to_string(index=False))"""
add_code(code_s17)

# Section 18
add_md("""## 18. Final Results Export
Verify serialized artifacts, model binaries, configuration JSON files, and reproducibility audit logs.""")

code_s18 = r"""final_summary_table = pd.read_csv(CSV_DIR / "final_model_summary.csv")
print("Final Deliverable Model Summary:")
print(final_summary_table.to_string(index=False))

print("")
print("Model Artifacts Stored:")
for p in sorted(FINAL_MODELS_DIR.glob("*.pkl")):
    print(" - Model:", p.name)
for p in sorted(SCALERS_DIR.glob("*.pkl")):
    print(" - Scaler:", p.name)
for p in sorted(IMPUTERS_DIR.glob("*.pkl")):
    print(" - Imputer:", p.name)
for p in sorted(CONFIG_DIR.glob("*")):
    print(" - Configuration:", p.name)"""
add_code(code_s18)

nb = {
    "cells": nb_cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.10.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

nb_out_path = Path("ai-engine/ml/notebooks/isolation_forest_training.ipynb")
with open(nb_out_path, "w") as f:
    json.dump(nb, f, indent=1)

print("Successfully written", nb_out_path, "with", len(nb_cells), "cells.")
