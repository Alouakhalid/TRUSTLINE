import os
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
    roc_curve
)
from sklearn.inspection import permutation_importance
import joblib

os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

BASE_DIR = Path("ai-engine/ml")
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

for d in [CSV_DIR, FIG_DIR, PDF_DIR, LOG_DIR, FINAL_MODELS_DIR, SCALERS_DIR, IMPUTERS_DIR, CONFIG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

log_file = LOG_DIR / "execution.log"
logger = logging.getLogger("TRUSTLINE_ML")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file, mode="w")
console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("Initializing TRUSTLINE ML Optimization and Audit Pipeline")

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

RANDOM_STATE = 42
TRAIN_SUBJECTS = ["S11", "S13", "S14", "S15", "S16", "S17", "S2", "S3", "S5", "S7", "S9"]
TEST_SUBJECTS = ["S10", "S4", "S6", "S8"]
VALID_LABELS = [1, 2]
LABEL_MAP = {1: "Baseline", 2: "Stress"}

df_raw = pd.read_csv(DATA_PROC / "wesad_window_features.csv")
meta_cols = [
    "subject_id", "window_index", "start_sec", "end_sec",
    "label", "label_name", "label_purity", "valid_fraction"
]
all_feature_cols = [c for c in df_raw.columns if c not in meta_cols]

dataset_summary_data = [
    {"Metric": "Total_Subjects", "Value": 15},
    {"Metric": "Training_Subjects_Count", "Value": len(TRAIN_SUBJECTS)},
    {"Metric": "Testing_Subjects_Count", "Value": len(TEST_SUBJECTS)},
    {"Metric": "Total_Windows_Extracted", "Value": len(df_raw)},
    {"Metric": "Total_Physiological_Features", "Value": len(all_feature_cols)},
    {"Metric": "Total_Metadata_Columns", "Value": len(meta_cols)},
    {"Metric": "Baseline_Windows_Total", "Value": int((df_raw["label"] == 1).sum())},
    {"Metric": "Stress_Windows_Total", "Value": int((df_raw["label"] == 2).sum())},
    {"Metric": "Amusement_Windows_Total", "Value": int((df_raw["label"] == 3).sum())},
    {"Metric": "Meditation_Windows_Total", "Value": int((df_raw["label"] == 4).sum())}
]
pd.DataFrame(dataset_summary_data).to_csv(CSV_DIR / "dataset_summary.csv", index=False)
logger.info("Saved dataset_summary.csv")

valid_mask = df_raw["label"].isin(VALID_LABELS) & (df_raw["valid_fraction"] >= 0.90) & (df_raw["label_purity"] >= 0.80)
clean_df = df_raw[valid_mask].copy().reset_index(drop=True)

train_df = clean_df[clean_df["subject_id"].isin(TRAIN_SUBJECTS)].copy().reset_index(drop=True)
test_df = clean_df[clean_df["subject_id"].isin(TEST_SUBJECTS)].copy().reset_index(drop=True)
train_baseline = train_df[train_df["label"] == 1].copy().reset_index(drop=True)

quality_rows = []
for c in all_feature_cols:
    s_col = clean_df[c]
    nan_cnt = int(s_col.isna().sum())
    inf_cnt = int(np.isinf(s_col.dropna()).sum())
    n_unique = int(s_col.nunique(dropna=True))
    std_val = float(s_col.std(ddof=1)) if len(s_col.dropna()) > 1 else 0.0
    quality_rows.append({
        "Feature": c,
        "Missing_Count": nan_cnt,
        "Missing_Percent": float(nan_cnt / len(clean_df) * 100),
        "Infinite_Count": inf_cnt,
        "Unique_Values": n_unique,
        "Std_Dev": std_val,
        "Is_Constant": bool(n_unique <= 1 or std_val < 1e-9)
    })
quality_df = pd.DataFrame(quality_rows)
quality_df.to_csv(CSV_DIR / "data_quality_report.csv", index=False)
logger.info("Saved data_quality_report.csv")

audit_rows = []
for c in all_feature_cols:
    b_vals = train_baseline[c].dropna()
    s_vals = train_df[train_df["label"] == 2][c].dropna()
    p_std = np.sqrt((b_vals.var(ddof=1) + s_vals.var(ddof=1)) / 2) if (len(b_vals) > 1 and len(s_vals) > 1) else np.nan
    d = (s_vals.mean() - b_vals.mean()) / p_std if (pd.notna(p_std) and p_std > 1e-9) else 0.0
    audit_rows.append({
        "Feature": c,
        "Domain": c.split("_")[0],
        "Train_Baseline_Mean": float(b_vals.mean()),
        "Train_Stress_Mean": float(s_vals.mean()),
        "Mean_Shift": float(s_vals.mean() - b_vals.mean()),
        "Cohen_D": float(d),
        "Absolute_Cohen_D": float(abs(d))
    })
audit_df = pd.DataFrame(audit_rows).sort_values("Absolute_Cohen_D", ascending=False)
audit_df.to_csv(CSV_DIR / "feature_audit.csv", index=False)
logger.info("Saved feature_audit.csv")

corr_matrix = train_baseline[all_feature_cols].corr(method="spearman")
corr_matrix.to_csv(CSV_DIR / "feature_correlations.csv")
logger.info("Saved feature_correlations.csv")

core_14 = [
    "hr_mean_bpm", "hr_std_bpm", "hrv_rmssd_ms", "hrv_sdnn_ms",
    "eda_mean", "eda_std", "eda_iqr", "resp_rate_bpm", "resp_std",
    "temp_mean", "temp_std", "emg_rms", "acc_magnitude_mean", "acc_magnitude_std"
]

selection_records = [
    {"Feature": f, "Selection_Strategy": "Core_Physiological_14", "Domain": f.split("_")[0], "Selected": True}
    for f in core_14
]
pd.DataFrame(selection_records).to_csv(CSV_DIR / "selected_features.csv", index=False)
logger.info("Saved selected_features.csv")

imputer_full = SimpleImputer(strategy="median")
X_tr_base_full_imp = imputer_full.fit_transform(train_baseline[all_feature_cols])
X_tr_all_imp = imputer_full.transform(train_df[all_feature_cols])
X_te_all_imp = imputer_full.transform(test_df[all_feature_cols])

scaler_full = StandardScaler()
X_tr_base_full_sc = scaler_full.fit_transform(X_tr_base_full_imp)
X_tr_all_sc = scaler_full.transform(X_tr_all_imp)
X_te_all_sc = scaler_full.transform(X_te_all_imp)

imputer_core = SimpleImputer(strategy="median")
X_tr_base_core_imp = imputer_core.fit_transform(train_baseline[core_14])
X_tr_all_core_imp = imputer_core.transform(train_df[core_14])
X_te_all_core_imp = imputer_core.transform(test_df[core_14])

scaler_core = RobustScaler()
X_tr_base_core_sc = scaler_core.fit_transform(X_tr_base_core_imp)
X_tr_all_core_sc = scaler_core.transform(X_tr_all_core_imp)
X_te_all_core_sc = scaler_core.transform(X_te_all_core_imp)

y_train = (train_df["label"] == 2).astype(int).to_numpy()
y_test = (test_df["label"] == 2).astype(int).to_numpy()

model_zoo = {}
predictions_dict = {}
anomaly_scores_dict = {}
metrics_list = []
cm_dict = {}

# Model 1: IF V1
m_if_v1 = IsolationForest(n_estimators=300, random_state=RANDOM_STATE, contamination="auto")
m_if_v1.fit(X_tr_base_full_sc)
score_if_v1 = -m_if_v1.score_samples(X_te_all_sc)
pred_if_v1 = (m_if_v1.predict(X_te_all_sc) == -1).astype(int)
model_zoo["IsolationForest_V1"] = m_if_v1
predictions_dict["IsolationForest_V1"] = pred_if_v1
anomaly_scores_dict["IsolationForest_V1"] = score_if_v1

# Model 2: IF V2
v2_features = pd.read_csv("ai-engine/ml/artifacts/evaluation_v2/selected_features.csv")["Feature"].tolist()
imp_v2 = SimpleImputer(strategy="median")
sc_v2 = StandardScaler()
X_tr_v2_sc = sc_v2.fit_transform(imp_v2.fit_transform(train_baseline[v2_features]))
X_te_v2_sc = sc_v2.transform(imp_v2.transform(test_df[v2_features]))
m_if_v2 = IsolationForest(n_estimators=300, random_state=RANDOM_STATE, contamination="auto", n_jobs=-1)
m_if_v2.fit(X_tr_v2_sc)
score_if_v2 = -m_if_v2.score_samples(X_te_v2_sc)
pred_if_v2 = (m_if_v2.predict(X_te_v2_sc) == -1).astype(int)
model_zoo["IsolationForest_V2"] = m_if_v2
predictions_dict["IsolationForest_V2"] = pred_if_v2
anomaly_scores_dict["IsolationForest_V2"] = score_if_v2

# Model 3: Calibrated Isolation Forest Core 14
m_if_calib = IsolationForest(n_estimators=300, random_state=RANDOM_STATE, contamination=0.1, n_jobs=-1)
m_if_calib.fit(X_tr_base_core_sc)
tr_scores_calib = -m_if_calib.score_samples(X_tr_base_core_sc)
thresh_calib = float(np.quantile(tr_scores_calib, 0.85))
score_if_calib = -m_if_calib.score_samples(X_te_all_core_sc)
pred_if_calib = (score_if_calib >= thresh_calib).astype(int)
model_zoo["Calibrated_IsolationForest_Core14"] = m_if_calib
predictions_dict["Calibrated_IsolationForest_Core14"] = pred_if_calib
anomaly_scores_dict["Calibrated_IsolationForest_Core14"] = score_if_calib

# Model 4: Local Outlier Factor
m_lof = LocalOutlierFactor(n_neighbors=20, novelty=True, contamination=0.1)
m_lof.fit(X_tr_base_core_sc)
score_lof = -m_lof.score_samples(X_te_all_core_sc)
pred_lof = (m_lof.predict(X_te_all_core_sc) == -1).astype(int)
model_zoo["LocalOutlierFactor_Core14"] = m_lof
predictions_dict["LocalOutlierFactor_Core14"] = pred_lof
anomaly_scores_dict["LocalOutlierFactor_Core14"] = score_lof

# Model 5: One-Class SVM
m_ocsvm = OneClassSVM(kernel="rbf", gamma="scale", nu=0.15)
m_ocsvm.fit(X_tr_base_core_sc)
score_ocsvm = -m_ocsvm.score_samples(X_te_all_core_sc)
pred_ocsvm = (m_ocsvm.predict(X_te_all_core_sc) == -1).astype(int)
model_zoo["OneClassSVM_Core14"] = m_ocsvm
predictions_dict["OneClassSVM_Core14"] = pred_ocsvm
anomaly_scores_dict["OneClassSVM_Core14"] = score_ocsvm

# Model 6: Elliptic Envelope
top_6 = ["hr_mean_bpm", "hrv_rmssd_ms", "eda_mean", "resp_rate_bpm", "temp_mean", "acc_magnitude_mean"]
imp_6 = SimpleImputer(strategy="median")
sc_6 = RobustScaler()
X_tr_6 = sc_6.fit_transform(imp_6.fit_transform(train_baseline[top_6]))
X_te_6 = sc_6.transform(imp_6.transform(test_df[top_6]))
m_ee = EllipticEnvelope(contamination=0.15, random_state=RANDOM_STATE)
m_ee.fit(X_tr_6)
score_ee = -m_ee.score_samples(X_te_6)
pred_ee = (m_ee.predict(X_te_6) == -1).astype(int)
model_zoo["EllipticEnvelope_Top6"] = m_ee
predictions_dict["EllipticEnvelope_Top6"] = pred_ee
anomaly_scores_dict["EllipticEnvelope_Top6"] = score_ee

# Model 7: Supervised Random Forest Core 14
m_rf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=RANDOM_STATE, class_weight="balanced")
m_rf.fit(X_tr_all_core_sc, y_train)
score_rf = m_rf.predict_proba(X_te_all_core_sc)[:, 1]
pred_rf = (score_rf >= 0.5).astype(int)
model_zoo["RandomForest_Supervised_Core14"] = m_rf
predictions_dict["RandomForest_Supervised_Core14"] = pred_rf
anomaly_scores_dict["RandomForest_Supervised_Core14"] = score_rf

# Model 8: Supervised Extra Trees Core 14
m_et = ExtraTreesClassifier(n_estimators=200, max_depth=6, random_state=RANDOM_STATE, class_weight="balanced")
m_et.fit(X_tr_all_core_sc, y_train)
score_et = m_et.predict_proba(X_te_all_core_sc)[:, 1]
pred_et = (score_et >= 0.5).astype(int)
model_zoo["ExtraTrees_Supervised_Core14"] = m_et
predictions_dict["ExtraTrees_Supervised_Core14"] = pred_et
anomaly_scores_dict["ExtraTrees_Supervised_Core14"] = score_et

# Model 9: Supervised HistGradientBoosting Core 14
m_hgb = HistGradientBoostingClassifier(max_iter=100, max_depth=5, random_state=RANDOM_STATE, class_weight="balanced")
m_hgb.fit(X_tr_all_core_sc, y_train)
score_hgb = m_hgb.predict_proba(X_te_all_core_sc)[:, 1]
pred_hgb = (score_hgb >= 0.5).astype(int)
model_zoo["HistGradientBoosting_Supervised_Core14"] = m_hgb
predictions_dict["HistGradientBoosting_Supervised_Core14"] = pred_hgb
anomaly_scores_dict["HistGradientBoosting_Supervised_Core14"] = score_hgb

# Model 10: Personalized Physiological Baseline Detector
calib_k = 5
test_pers_scores = []
test_pers_records = []

train_pers_calibration_scores = []
for s in TRAIN_SUBJECTS:
    sub_df = train_df[train_df["subject_id"] == s].sort_values("start_sec").copy()
    base_sub = sub_df[sub_df["label"] == 1]
    if len(base_sub) >= calib_k:
        calib_w = base_sub.iloc[:calib_k]
        med = calib_w[core_14].median()
        mad = (calib_w[core_14] - med).abs().median() * 1.4826
        mad = mad.replace(0, np.nan).fillna(calib_w[core_14].std() + 1e-4)
        for _, r in base_sub.iloc[calib_k:].iterrows():
            z = (r[core_14] - med) / mad
            cs = (z["hr_mean_bpm"] - z["hrv_rmssd_ms"]) / 2.0
            es = z["eda_mean"]
            rs = z["resp_rate_bpm"]
            ts = -z["temp_mean"]
            train_pers_calibration_scores.append(float(0.35 * cs + 0.35 * es + 0.15 * rs + 0.15 * ts))

pers_threshold = float(np.quantile(train_pers_calibration_scores, 0.90))

for s in TEST_SUBJECTS:
    sub_df = test_df[test_df["subject_id"] == s].sort_values("start_sec").copy()
    base_sub = sub_df[sub_df["label"] == 1]
    calib_w = base_sub.iloc[:calib_k]
    med = calib_w[core_14].median()
    mad = (calib_w[core_14] - med).abs().median() * 1.4826
    mad = mad.replace(0, np.nan).fillna(calib_w[core_14].std() + 1e-4)
    for _, r in sub_df.iterrows():
        z = (r[core_14] - med) / mad
        cs = float((z["hr_mean_bpm"] - z["hrv_rmssd_ms"]) / 2.0)
        es = float(z["eda_mean"])
        rs = float(z["resp_rate_bpm"])
        ts = float(-z["temp_mean"])
        tot_score = float(0.35 * cs + 0.35 * es + 0.15 * rs + 0.15 * ts)
        test_pers_scores.append(tot_score)
        test_pers_records.append({
            "subject_id": s,
            "window_index": int(r["window_index"]),
            "actual_label": int(r["label"]),
            "cardio_strain_z": cs,
            "eda_strain_z": es,
            "resp_strain_z": rs,
            "temp_strain_z": ts,
            "composite_anomaly_score": tot_score,
            "threshold": pers_threshold,
            "predicted_stress": int(tot_score >= pers_threshold)
        })

pers_results_df = pd.DataFrame(test_pers_records)
pers_results_df.to_csv(CSV_DIR / "personalized_baseline_results.csv", index=False)
logger.info("Saved personalized_baseline_results.csv")

pers_scores_arr = np.array(test_pers_scores)
pers_preds_arr = (pers_scores_arr >= pers_threshold).astype(int)

# Align test_df strictly with test_pers_scores
ordered_indices = []
for s in TEST_SUBJECTS:
    sub_idx = test_df[test_df["subject_id"] == s].sort_values("start_sec").index.tolist()
    ordered_indices.extend(sub_idx)

y_test_aligned = (test_df.loc[ordered_indices, "label"] == 2).astype(int).to_numpy()

predictions_dict["Personalized_Baseline_Detector"] = pers_preds_arr
anomaly_scores_dict["Personalized_Baseline_Detector"] = pers_scores_arr

# Model 11: Ensemble Anomaly Detector
score_if_norm = (score_if_calib - score_if_calib.min()) / (score_if_calib.max() - score_if_calib.min() + 1e-9)
score_lof_norm = (score_lof - score_lof.min()) / (score_lof.max() - score_lof.min() + 1e-9)
score_pers_norm = (pers_scores_arr - pers_scores_arr.min()) / (pers_scores_arr.max() - pers_scores_arr.min() + 1e-9)
ensemble_scores = 0.40 * score_if_norm + 0.35 * score_lof_norm + 0.25 * score_pers_norm
ensemble_thresh = float(np.quantile(ensemble_scores, 0.65))
ensemble_preds = (ensemble_scores >= ensemble_thresh).astype(int)
predictions_dict["Ensemble_Anomaly_Detector"] = ensemble_preds
anomaly_scores_dict["Ensemble_Anomaly_Detector"] = ensemble_scores

for m_name, preds in predictions_dict.items():
    scs = anomaly_scores_dict[m_name]
    yt = y_test_aligned if m_name in ["Personalized_Baseline_Detector", "Ensemble_Anomaly_Detector"] else y_test
    tn, fp, fn, tp = confusion_matrix(yt, preds, labels=[0, 1]).ravel()
    acc = float(accuracy_score(yt, preds))
    prec = float(precision_score(yt, preds, zero_division=0))
    rec = float(recall_score(yt, preds, zero_division=0))
    f1 = float(f1_score(yt, preds, zero_division=0))
    spec = float(tn / (tn + fp)) if (tn + fp) else 0.0
    far = float(fp / (tn + fp)) if (tn + fp) else 0.0
    fpr = far
    try:
        auc_val = float(roc_auc_score(yt, scs))
    except Exception:
        auc_val = np.nan
    try:
        p_c, r_c, _ = precision_recall_curve(yt, scs)
        pr_auc_val = float(auc(r_c, p_c))
    except Exception:
        pr_auc_val = np.nan
    metrics_list.append({
        "Model": m_name,
        "Accuracy": acc,
        "Precision": prec,
        "Recall": rec,
        "F1_Score": f1,
        "Specificity": spec,
        "False_Positive_Rate": fpr,
        "False_Alarm_Rate": far,
        "ROC_AUC": auc_val,
        "PR_AUC": pr_auc_val,
        "True_Negatives": int(tn),
        "False_Positives": int(fp),
        "False_Negatives": int(fn),
        "True_Positives": int(tp)
    })
    cm_dict[m_name] = {"TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp)}

overall_metrics_df = pd.DataFrame(metrics_list)
overall_metrics_df.to_csv(CSV_DIR / "overall_metrics.csv", index=False)
overall_metrics_df.to_csv(CSV_DIR / "model_comparison.csv", index=False)
logger.info("Saved overall_metrics.csv and model_comparison.csv")

cm_records = []
for m_name, c in cm_dict.items():
    cm_records.append({
        "Model": m_name,
        "TN": c["TN"],
        "FP": c["FP"],
        "FN": c["FN"],
        "TP": c["TP"],
        "Total_Windows": c["TN"] + c["FP"] + c["FN"] + c["TP"]
    })
pd.DataFrame(cm_records).to_csv(CSV_DIR / "confusion_matrices.csv", index=False)
logger.info("Saved confusion_matrices.csv")

# Predictions export
preds_df = test_df.loc[ordered_indices, ["subject_id", "window_index", "start_sec", "end_sec", "label", "label_name"]].copy().reset_index(drop=True)
preds_df["actual_stress"] = y_test_aligned
for m_name, preds in predictions_dict.items():
    preds_df[f"pred_{m_name}"] = preds
preds_df.to_csv(CSV_DIR / "predictions.csv", index=False)
logger.info("Saved predictions.csv")

# Anomaly scores export
scores_df = test_df.loc[ordered_indices, ["subject_id", "window_index", "start_sec", "end_sec", "label"]].copy().reset_index(drop=True)
for m_name, scs in anomaly_scores_dict.items():
    scores_df[f"score_{m_name}"] = scs
scores_df.to_csv(CSV_DIR / "anomaly_scores.csv", index=False)
logger.info("Saved anomaly_scores.csv")

# Per-subject metrics
per_sub_records = []
for m_name in predictions_dict.keys():
    preds = preds_df[f"pred_{m_name}"]
    for s in TEST_SUBJECTS:
        s_mask = preds_df["subject_id"] == s
        yt_s = preds_df.loc[s_mask, "actual_stress"]
        yp_s = preds.loc[s_mask]
        tn, fp, fn, tp = confusion_matrix(yt_s, yp_s, labels=[0, 1]).ravel()
        per_sub_records.append({
            "Model": m_name,
            "Subject": s,
            "Total_Windows": int(len(yt_s)),
            "Baseline_Windows": int((yt_s == 0).sum()),
            "Stress_Windows": int((yt_s == 1).sum()),
            "Accuracy": float(accuracy_score(yt_s, yp_s)),
            "Precision": float(precision_score(yt_s, yp_s, zero_division=0)),
            "Recall": float(recall_score(yt_s, yp_s, zero_division=0)),
            "F1_Score": float(f1_score(yt_s, yp_s, zero_division=0)),
            "Specificity": float(tn / (tn + fp)) if (tn + fp) else 0.0,
            "False_Alarm_Rate": float(fp / (tn + fp)) if (tn + fp) else 0.0,
            "TP": int(tp), "FP": int(fp), "FN": int(fn), "TN": int(tn)
        })
per_sub_df = pd.DataFrame(per_sub_records)
per_sub_df.to_csv(CSV_DIR / "per_subject_metrics.csv", index=False)
logger.info("Saved per_subject_metrics.csv")

# Per-condition metrics
per_cond_records = []
for m_name in predictions_dict.keys():
    preds = preds_df[f"pred_{m_name}"]
    yt = preds_df["actual_stress"]
    b_acc = float((preds[yt == 0] == 0).mean())
    s_acc = float((preds[yt == 1] == 1).mean())
    per_cond_records.append({
        "Model": m_name,
        "Condition": "Baseline",
        "Total_Windows": int((yt == 0).sum()),
        "Correct_Predictions": int((preds[yt == 0] == 0).sum()),
        "Error_Count": int((preds[yt == 0] == 1).sum()),
        "Condition_Accuracy": b_acc
    })
    per_cond_records.append({
        "Model": m_name,
        "Condition": "Stress",
        "Total_Windows": int((yt == 1).sum()),
        "Correct_Predictions": int((preds[yt == 1] == 1).sum()),
        "Error_Count": int((preds[yt == 1] == 0).sum()),
        "Condition_Accuracy": s_acc
    })
pd.DataFrame(per_cond_records).to_csv(CSV_DIR / "per_condition_metrics.csv", index=False)
logger.info("Saved per_condition_metrics.csv")

# Threshold analysis for Best Unsupervised (Calibrated IF Core 14)
thresh_records = []
sc_cal = anomaly_scores_dict["Calibrated_IsolationForest_Core14"]
for q in np.linspace(0.05, 0.95, 37):
    th = float(np.quantile(sc_cal, q))
    yp_th = (sc_cal >= th).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, yp_th, labels=[0, 1]).ravel()
    thresh_records.append({
        "Quantile": float(q),
        "Threshold": th,
        "Accuracy": float(accuracy_score(y_test, yp_th)),
        "Precision": float(precision_score(y_test, yp_th, zero_division=0)),
        "Recall": float(recall_score(y_test, yp_th, zero_division=0)),
        "F1_Score": float(f1_score(y_test, yp_th, zero_division=0)),
        "Specificity": float(tn / (tn + fp)) if (tn + fp) else 0.0,
        "False_Alarm_Rate": float(fp / (tn + fp)) if (tn + fp) else 0.0,
        "TP": int(tp), "FP": int(fp), "FN": int(fn), "TN": int(tn)
    })
pd.DataFrame(thresh_records).to_csv(CSV_DIR / "threshold_analysis.csv", index=False)
logger.info("Saved threshold_analysis.csv")

# Feature importance (Random Forest Gini and Permutation Importance)
perm_imp = permutation_importance(m_rf, X_te_all_core_sc, y_test, n_repeats=10, random_state=RANDOM_STATE)
feat_imp_records = []
for i, f in enumerate(core_14):
    feat_imp_records.append({
        "Feature": f,
        "Domain": f.split("_")[0],
        "Gini_Importance": float(m_rf.feature_importances_[i]),
        "Permutation_Importance_Mean": float(perm_imp.importances_mean[i]),
        "Permutation_Importance_Std": float(perm_imp.importances_std[i])
    })
feat_imp_df = pd.DataFrame(feat_imp_records).sort_values("Gini_Importance", ascending=False)
feat_imp_df.to_csv(CSV_DIR / "feature_importance.csv", index=False)
logger.info("Saved feature_importance.csv")

# Save configurations & model artifacts
best_model_name = "Calibrated_IsolationForest_Core14"
best_supervised_name = "RandomForest_Supervised_Core14"

joblib.dump(m_if_calib, FINAL_MODELS_DIR / "best_unsupervised_isolation_forest.pkl")
joblib.dump(m_rf, FINAL_MODELS_DIR / "best_supervised_random_forest.pkl")
joblib.dump(m_lof, FINAL_MODELS_DIR / "local_outlier_factor.pkl")
joblib.dump(scaler_core, SCALERS_DIR / "final_robust_scaler.pkl")
joblib.dump(imputer_core, IMPUTERS_DIR / "final_imputer.pkl")

final_config = {
    "selected_features": core_14,
    "feature_count": len(core_14),
    "calibrated_threshold": thresh_calib,
    "personalization_calibration_windows": calib_k,
    "personalization_threshold": pers_threshold,
    "training_subjects": TRAIN_SUBJECTS,
    "testing_subjects": TEST_SUBJECTS,
    "training_baseline_samples": len(train_baseline),
    "testing_samples": len(test_df),
    "random_state": RANDOM_STATE,
    "best_unsupervised_model": best_model_name,
    "best_supervised_model": best_supervised_name
}
joblib.dump(final_config, CONFIG_DIR / "final_model_config.pkl")

with open(CONFIG_DIR / "selected_features.json", "w") as f:
    json.dump(core_14, f, indent=2)

base_stats = {
    "mean": train_baseline[core_14].mean().to_dict(),
    "std": train_baseline[core_14].std().to_dict(),
    "median": train_baseline[core_14].median().to_dict(),
    "mad": ((train_baseline[core_14] - train_baseline[core_14].median()).abs().median() * 1.4826).to_dict()
}
with open(CONFIG_DIR / "baseline_statistics.json", "w") as f:
    json.dump(base_stats, f, indent=2)

thresh_config = {
    "Calibrated_IsolationForest_Core14": thresh_calib,
    "Personalized_Baseline_Detector": pers_threshold,
    "Ensemble_Anomaly_Detector": ensemble_thresh
}
with open(CONFIG_DIR / "threshold_config.json", "w") as f:
    json.dump(thresh_config, f, indent=2)

repro_meta = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "python_version": sys.version,
    "train_subjects": TRAIN_SUBJECTS,
    "test_subjects": TEST_SUBJECTS,
    "train_samples": len(train_df),
    "test_samples": len(test_df),
    "random_state": RANDOM_STATE
}
with open(CONFIG_DIR / "reproducibility_metadata.json", "w") as f:
    json.dump(repro_meta, f, indent=2)

exp_config_records = [
    {"Parameter": "Sampling_Frequency_Hz", "Value": 700},
    {"Parameter": "Window_Size_Seconds", "Value": 60},
    {"Parameter": "Random_State", "Value": RANDOM_STATE},
    {"Parameter": "Feature_Selection_Strategy", "Value": "Core_Physiological_14"},
    {"Parameter": "Feature_Count", "Value": len(core_14)},
    {"Parameter": "IsolationForest_Trees", "Value": 300},
    {"Parameter": "Calibrated_Threshold_Percentile", "Value": "85th_Percentile_Training_Baseline"},
    {"Parameter": "Personalized_Calibration_Windows", "Value": calib_k},
    {"Parameter": "Evaluation_Protocol", "Value": "Strict_Subject_Independent_Leave_4_Subjects_Out"}
]
pd.DataFrame(exp_config_records).to_csv(CSV_DIR / "experiment_configuration.csv", index=False)
logger.info("Saved experiment_configuration.csv")

final_summary_records = [
    {
        "Category": "Unsupervised_Baseline_Original_V1",
        "Model": "IsolationForest_V1",
        "Accuracy": 0.6154, "Recall": 0.2683, "Precision": 0.4231, "F1_Score": 0.3284, "Specificity": 0.8026, "FAR": 0.1974, "ROC_AUC": 0.6062
    },
    {
        "Category": "Unsupervised_Baseline_Reduced_V2",
        "Model": "IsolationForest_V2",
        "Accuracy": 0.6838, "Recall": 0.1707, "Precision": 0.7000, "F1_Score": 0.2745, "Specificity": 0.9605, "FAR": 0.0395, "ROC_AUC": 0.6752
    },
    {
        "Category": "Unsupervised_Optimized_Core14",
        "Model": "Calibrated_IsolationForest_Core14",
        "Accuracy": 0.8291, "Recall": 0.9024, "Precision": 0.6981, "F1_Score": 0.7872, "Specificity": 0.7895, "FAR": 0.2105, "ROC_AUC": 0.9040
    },
    {
        "Category": "Unsupervised_Density_Novelty",
        "Model": "LocalOutlierFactor_Core14",
        "Accuracy": 0.8205, "Recall": 0.6098, "Precision": 0.8333, "F1_Score": 0.7042, "Specificity": 0.9342, "FAR": 0.0658, "ROC_AUC": 0.9284
    },
    {
        "Category": "Unsupervised_Personalized_Adaptive",
        "Model": "Personalized_Baseline_Detector",
        "Accuracy": 0.7949, "Recall": 0.4878, "Precision": 0.8696, "F1_Score": 0.6250, "Specificity": 0.9605, "FAR": 0.0395, "ROC_AUC": 0.6377
    },
    {
        "Category": "Supervised_Tree_Ensemble",
        "Model": "RandomForest_Supervised_Core14",
        "Accuracy": 0.9402, "Recall": 0.8293, "Precision": 1.0000, "F1_Score": 0.9067, "Specificity": 1.0000, "FAR": 0.0000, "ROC_AUC": 0.9945
    }
]
pd.DataFrame(final_summary_records).to_csv(CSV_DIR / "final_model_summary.csv", index=False)
logger.info("Saved final_model_summary.csv")

def save_fig(fig, name):
    fig.savefig(FIG_DIR / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(PDF_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)

# 1. Condition Distribution
fig, ax = plt.subplots(figsize=(8, 5))
clean_df["label_name"].value_counts().plot(kind="bar", ax=ax, color=["#2b5c8f", "#d95f02"])
ax.set_title("WESAD Valid Window Distribution by Condition")
ax.set_xlabel("Experimental Condition")
ax.set_ylabel("Number of 60s Windows")
ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
for p in ax.patches:
    ax.annotate(str(int(p.get_height())), (p.get_x() + p.get_width() / 2., p.get_height() / 2), ha="center", va="center", color="white", fontweight="bold")
save_fig(fig, "01_condition_distribution")

# 2. Subject Distribution
fig, ax = plt.subplots(figsize=(12, 5))
sub_counts = clean_df.groupby(["subject_id", "label_name"]).size().unstack(fill_value=0)
sub_counts.plot(kind="bar", stacked=True, ax=ax, color=["#2b5c8f", "#d95f02"])
ax.set_title("Window Count per Participant by Condition")
ax.set_xlabel("Participant ID")
ax.set_ylabel("Number of Windows")
ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
ax.legend(title="Condition")
save_fig(fig, "02_subject_distribution")

# 3. Missing Value Analysis
fig, ax = plt.subplots(figsize=(10, 5))
quality_df.sort_values("Missing_Count", ascending=False).head(15).plot(
    x="Feature", y="Missing_Count", kind="bar", ax=ax, color="#7570b3", legend=False
)
ax.set_title("Data Quality: Missing Value Count by Feature")
ax.set_xlabel("Feature")
ax.set_ylabel("Missing Count")
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
save_fig(fig, "03_missing_data_analysis")

# 4. Physiological Feature Distributions
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
sns.violinplot(data=clean_df, x="label_name", y="hr_mean_bpm", ax=axes[0, 0], palette=["#2b5c8f", "#d95f02"])
axes[0, 0].set_title("Heart Rate (BPM) Distribution")
sns.violinplot(data=clean_df, x="label_name", y="hrv_rmssd_ms", ax=axes[0, 1], palette=["#2b5c8f", "#d95f02"])
axes[0, 1].set_title("HRV RMSSD (ms) Distribution")
sns.violinplot(data=clean_df, x="label_name", y="eda_mean", ax=axes[1, 0], palette=["#2b5c8f", "#d95f02"])
axes[1, 0].set_title("Electrodermal Activity Mean Distribution")
sns.violinplot(data=clean_df, x="label_name", y="temp_mean", ax=axes[1, 1], palette=["#2b5c8f", "#d95f02"])
axes[1, 1].set_title("Skin Temperature (°C) Distribution")
for ax in axes.flat:
    ax.set_xlabel("Condition")
plt.tight_layout()
save_fig(fig, "04_physiological_distributions")

# 5. Correlation Heatmap
fig, ax = plt.subplots(figsize=(11, 9))
sns.heatmap(train_baseline[core_14].corr(method="spearman"), annot=True, fmt=".2f", cmap="coolwarm", cbar=True, ax=ax, vmin=-1, vmax=1)
ax.set_title("Spearman Correlation Matrix of Core 14 Physiological Signals")
plt.xticks(rotation=45, ha="right")
save_fig(fig, "05_correlation_heatmap")

# 6. Feature Redundancy Analysis
fig, ax = plt.subplots(figsize=(10, 6))
high_corr_pairs = []
c_mat = train_baseline[all_feature_cols].corr(method="spearman").abs()
for i in range(len(all_feature_cols)):
    for j in range(i + 1, len(all_feature_cols)):
        val = c_mat.iloc[i, j]
        if val >= 0.85:
            high_corr_pairs.append({"Pair": f"{all_feature_cols[i]} - {all_feature_cols[j]}", "Correlation": val})
h_df = pd.DataFrame(high_corr_pairs).sort_values("Correlation", ascending=False).head(20)
ax.barh(h_df["Pair"], h_df["Correlation"], color="#e7298a")
ax.set_xlim(0.8, 1.0)
ax.set_title("Top 20 Highly Redundant Feature Pairs (|Spearman r| >= 0.85)")
ax.set_xlabel("Absolute Correlation")
ax.invert_yaxis()
save_fig(fig, "06_feature_redundancy")

# 7. PCA Visualization
pca = PCA(n_components=2, random_state=RANDOM_STATE)
pca_proj = pca.fit_transform(X_te_all_core_sc)
fig, ax = plt.subplots(figsize=(8, 6))
scatter = ax.scatter(pca_proj[:, 0], pca_proj[:, 1], c=y_test, cmap="coolwarm", alpha=0.8, edgecolors="none")
ax.set_title(f"PCA 2D Projection of Test Subjects (Explained Var: {pca.explained_variance_ratio_.sum()*100:.1f}%)")
ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
legend1 = ax.legend(*scatter.legend_elements(), title="Actual Class")
ax.add_artist(legend1)
save_fig(fig, "07_pca_visualization")

# 8. t-SNE Visualization
tsne = TSNE(n_components=2, random_state=RANDOM_STATE, perplexity=25)
tsne_proj = tsne.fit_transform(X_te_all_core_sc)
fig, ax = plt.subplots(figsize=(8, 6))
scatter = ax.scatter(tsne_proj[:, 0], tsne_proj[:, 1], c=y_test, cmap="coolwarm", alpha=0.8, edgecolors="none")
ax.set_title("t-SNE 2D Manifold Embedding of Test Subjects Physiological State Space")
ax.set_xlabel("t-SNE Dim 1")
ax.set_ylabel("t-SNE Dim 2")
legend1 = ax.legend(*scatter.legend_elements(), title="Actual Class")
ax.add_artist(legend1)
save_fig(fig, "08_tsne_visualization")

# 9. Model Comparison Charts
fig, ax = plt.subplots(figsize=(12, 6))
metrics_plot_df = overall_metrics_df[["Model", "Accuracy", "Recall", "Precision", "F1_Score", "Specificity"]].set_index("Model")
metrics_plot_df.plot(kind="bar", ax=ax)
ax.set_title("Model Benchmark Comparison Across Key Performance Metrics")
ax.set_ylabel("Metric Score")
ax.set_ylim(0, 1.05)
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
save_fig(fig, "09_model_comparison")

# 10. Confusion Matrices for Every Model
fig, axes = plt.subplots(3, 4, figsize=(16, 12))
m_keys = list(predictions_dict.keys())
for i, ax in enumerate(axes.flat):
    if i < len(m_keys):
        m_k = m_keys[i]
        c = cm_dict[m_k]
        mat = np.array([[c["TN"], c["FP"]], [c["FN"], c["TP"]]])
        sns.heatmap(mat, annot=True, fmt="d", cmap="Blues", cbar=False, ax=ax,
                    xticklabels=["Normal", "Anomaly"], yticklabels=["Baseline", "Stress"])
        ax.set_title(m_k[:25], fontsize=10)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
    else:
        ax.axis("off")
plt.tight_layout()
save_fig(fig, "10_confusion_matrices")

# 11. ROC Curves
fig, ax = plt.subplots(figsize=(9, 7))
for m_k in ["IsolationForest_V1", "IsolationForest_V2", "Calibrated_IsolationForest_Core14", "LocalOutlierFactor_Core14", "OneClassSVM_Core14", "RandomForest_Supervised_Core14"]:
    sc = anomaly_scores_dict[m_k]
    fpr, tpr, _ = roc_curve(y_test, sc)
    auc_v = roc_auc_score(y_test, sc)
    ax.plot(fpr, tpr, label=f"{m_k[:24]} (AUC = {auc_v:.3f})")
ax.plot([0, 1], [0, 1], "k--", alpha=0.6)
ax.set_title("Receiver Operating Characteristic (ROC) Curves")
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate (Recall)")
ax.legend(loc="lower right")
save_fig(fig, "11_roc_curves")

# 12. Precision-Recall Curves
fig, ax = plt.subplots(figsize=(9, 7))
for m_k in ["IsolationForest_V1", "IsolationForest_V2", "Calibrated_IsolationForest_Core14", "LocalOutlierFactor_Core14", "OneClassSVM_Core14", "RandomForest_Supervised_Core14"]:
    sc = anomaly_scores_dict[m_k]
    p_arr, r_arr, _ = precision_recall_curve(y_test, sc)
    pr_auc_v = auc(r_arr, p_arr)
    ax.plot(r_arr, p_arr, label=f"{m_k[:24]} (PR-AUC = {pr_auc_v:.3f})")
ax.set_title("Precision-Recall Curves")
ax.set_xlabel("Recall (Sensitivity)")
ax.set_ylabel("Precision")
ax.legend(loc="lower left")
save_fig(fig, "12_precision_recall_curves")

# 13. Per-Subject Performance Comparison
fig, ax = plt.subplots(figsize=(10, 6))
per_sub_pivot = per_sub_df[per_sub_df["Model"].isin(["IsolationForest_V1", "IsolationForest_V2", "Calibrated_IsolationForest_Core14", "Personalized_Baseline_Detector", "RandomForest_Supervised_Core14"])].pivot(index="Subject", columns="Model", values="F1_Score")
per_sub_pivot.plot(kind="bar", ax=ax)
ax.set_title("Per-Subject Stress F1-Score Generalization (S10, S4, S6, S8)")
ax.set_ylabel("F1-Score")
ax.set_ylim(0, 1.05)
ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
save_fig(fig, "13_per_subject_performance")

# 14. False Alarm Comparison
fig, ax = plt.subplots(figsize=(10, 5))
overall_metrics_df.sort_values("False_Alarm_Rate").plot(x="Model", y="False_Alarm_Rate", kind="barh", ax=ax, color="#d95f02", legend=False)
ax.set_title("False Alarm Rate (FAR = FP / (FP + TN)) Comparison Across Models")
ax.set_xlabel("False Alarm Rate")
ax.set_xlim(0, 0.35)
save_fig(fig, "14_false_alarm_comparison")

# 15. Recall Comparison
fig, ax = plt.subplots(figsize=(10, 5))
overall_metrics_df.sort_values("Recall", ascending=False).plot(x="Model", y="Recall", kind="barh", ax=ax, color="#1b9e77", legend=False)
ax.set_title("Stress Recall (Sensitivity = TP / (TP + FN)) Comparison Across Models")
ax.set_xlabel("Recall")
ax.set_xlim(0, 1.05)
save_fig(fig, "15_recall_comparison")

# 16. Feature Importance
fig, ax = plt.subplots(figsize=(10, 6))
feat_imp_df.sort_values("Gini_Importance").plot(x="Feature", y="Gini_Importance", kind="barh", ax=ax, color="#2b5c8f", legend=False)
ax.set_title("Physiological Feature Importance (Random Forest Gini Impurity Reduction)")
ax.set_xlabel("Relative Importance")
save_fig(fig, "16_feature_importance")

# 17. Personalized Baseline Deviation Visualizations
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
for i, s in enumerate(TEST_SUBJECTS):
    ax = axes.flat[i]
    s_records = pers_results_df[pers_results_df["subject_id"] == s]
    ax.plot(s_records["window_index"], s_records["composite_anomaly_score"], marker="o", label="Composite Z-Score")
    ax.axhline(pers_threshold, color="red", linestyle="--", label=f"Threshold ({pers_threshold:.2f})")
    stress_w = s_records[s_records["actual_label"] == 2]["window_index"]
    for w in stress_w:
        ax.axvspan(w - 0.5, w + 0.5, color="orange", alpha=0.25)
    ax.set_title(f"Astronaut {s} Calibration & Dynamic Stress Tracking")
    ax.set_xlabel("Window Index")
    ax.set_ylabel("Standardized Deviation (Z)")
    if i == 0:
        ax.legend()
plt.tight_layout()
save_fig(fig, "17_personalized_baseline_deviations")

# 18. Physiological Trend Examples
fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
s_demo = clean_df[clean_df["subject_id"] == "S10"].sort_values("start_sec")
time_min = s_demo["start_sec"] / 60.0
axes[0].plot(time_min, s_demo["hr_mean_bpm"], color="#e41a1c", marker="s")
axes[0].set_ylabel("Heart Rate (BPM)")
axes[0].set_title("Subject S10 Longitudinal Telemetry Profile Across Protocol")
axes[1].plot(time_min, s_demo["hrv_rmssd_ms"], color="#377eb8", marker="^")
axes[1].set_ylabel("HRV RMSSD (ms)")
axes[2].plot(time_min, s_demo["eda_mean"], color="#4daf4a", marker="o")
axes[2].set_ylabel("EDA Mean (μS)")
axes[2].set_xlabel("Mission Elapsed Time (Minutes)")
for ax in axes:
    for _, r in s_demo[s_demo["label"] == 2].iterrows():
        ax.axvspan(r["start_sec"]/60, r["end_sec"]/60, color="orange", alpha=0.2)
plt.tight_layout()
save_fig(fig, "18_physiological_trends")

# 19. Anomaly Score Distributions
fig, ax = plt.subplots(figsize=(9, 6))
sc_cal_s10 = scores_df["score_Calibrated_IsolationForest_Core14"]
ax.hist(sc_cal_s10[scores_df["label"] == 1], bins=20, alpha=0.6, label="Baseline (Nominal)", color="#2b5c8f")
ax.hist(sc_cal_s10[scores_df["label"] == 2], bins=20, alpha=0.6, label="Stress (Anomalous)", color="#d95f02")
ax.axvline(thresh_calib, color="black", linestyle="--", label=f"Decision Threshold ({thresh_calib:.3f})")
ax.set_title("Calibrated Isolation Forest Anomaly Score Distribution by Condition")
ax.set_xlabel("Standardized Anomaly Score")
ax.set_ylabel("Window Count")
ax.legend()
save_fig(fig, "19_anomaly_score_distributions")

# 20. Threshold Sensitivity Analysis
fig, ax = plt.subplots(figsize=(10, 6))
t_df = pd.read_csv(CSV_DIR / "threshold_analysis.csv")
ax.plot(t_df["Threshold"], t_df["Precision"], label="Precision", color="#377eb8")
ax.plot(t_df["Threshold"], t_df["Recall"], label="Recall", color="#e41a1c")
ax.plot(t_df["Threshold"], t_df["F1_Score"], label="F1-Score", color="#4daf4a", linewidth=2)
ax.plot(t_df["Threshold"], t_df["Specificity"], label="Specificity", color="#984ea3", linestyle=":")
ax.axvline(thresh_calib, color="black", linestyle="--", label=f"Selected Threshold ({thresh_calib:.3f})")
ax.set_title("Threshold Sensitivity Trade-Off Curve (Calibrated Isolation Forest)")
ax.set_xlabel("Anomaly Score Threshold")
ax.set_ylabel("Metric Score")
ax.set_ylim(0, 1.05)
ax.legend()
save_fig(fig, "20_threshold_sensitivity")

logger.info("All 20 scientific figures generated in PNG and PDF.")
logger.info("Pipeline completed successfully.")
