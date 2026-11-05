import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import (
    IsolationForest, RandomForestClassifier, ExtraTreesClassifier,
    HistGradientBoostingClassifier
)
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM
from sklearn.covariance import EllipticEnvelope
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)

df = pd.read_csv("ai-engine/ml/data/processed/wesad_window_features.csv")
meta_cols = [
    "subject_id", "window_index", "start_sec", "end_sec",
    "label", "label_name", "label_purity", "valid_fraction"
]
train_subjects = ["S11", "S13", "S14", "S15", "S16", "S17", "S2", "S3", "S5", "S7", "S9"]
test_subjects = ["S10", "S4", "S6", "S8"]

valid_mask = df["label"].isin([1, 2]) & (df["valid_fraction"] >= 0.90) & (df["label_purity"] >= 0.80)
clean_df = df[valid_mask].copy()

all_feature_cols = [c for c in clean_df.columns if c not in meta_cols]

train_df = clean_df[clean_df["subject_id"].isin(train_subjects)].copy()
test_df = clean_df[clean_df["subject_id"].isin(test_subjects)].copy()

train_baseline = train_df[train_df["label"] == 1].copy()

y_test = (test_df["label"] == 2).astype(int).to_numpy()
y_train = (train_df["label"] == 2).astype(int).to_numpy()

# 1. Feature sets
# Full set
imputer_full = SimpleImputer(strategy="median")
X_train_full = imputer_full.fit_transform(train_baseline[all_feature_cols])
X_test_full = imputer_full.transform(test_df[all_feature_cols])
scaler_full = StandardScaler()
X_train_full_scaled = scaler_full.fit_transform(X_train_full)
X_test_full_scaled = scaler_full.transform(X_test_full)

# Core physiological 14 features
core_14 = [
    "hr_mean_bpm", "hr_std_bpm", "hrv_rmssd_ms", "hrv_sdnn_ms",
    "eda_mean", "eda_std", "eda_iqr", "resp_rate_bpm", "resp_std",
    "temp_mean", "temp_std", "emg_rms", "acc_magnitude_mean", "acc_magnitude_std"
]
imputer_core = SimpleImputer(strategy="median")
X_train_core = imputer_core.fit_transform(train_baseline[core_14])
X_test_core = imputer_core.transform(test_df[core_14])
scaler_core = RobustScaler()
X_train_core_scaled = scaler_core.fit_transform(X_train_core)
X_test_core_scaled = scaler_core.transform(X_test_core)

# Model definitions and runs
results = []

def record_metrics(name, y_true, y_pred, scores=None, extra=""):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    spec = tn / (tn + fp) if (tn + fp) else 0
    far = fp / (tn + fp) if (tn + fp) else 0
    auc = roc_auc_score(y_true, scores) if scores is not None and len(np.unique(y_true)) > 1 else np.nan
    results.append({
        "Model": name, "Features": extra,
        "Accuracy": acc, "Precision": prec, "Recall": rec, "F1": f1,
        "Specificity": spec, "FAR": far, "ROC_AUC": auc,
        "TN": tn, "FP": fp, "FN": fn, "TP": tp
    })

# Model 1: IF V1 (Original)
if_v1 = IsolationForest(n_estimators=300, random_state=42, contamination="auto")
if_v1.fit(X_train_full_scaled)
scores_v1 = -if_v1.score_samples(X_test_full_scaled)
pred_v1 = (if_v1.predict(X_test_full_scaled) == -1).astype(int)
record_metrics("IsolationForest_V1_Full", y_test, pred_v1, scores_v1, "99 features")

# Model 2: IF V2 (69 features reproduction)
v2_feats = pd.read_csv("ai-engine/ml/artifacts/evaluation_v2/selected_features.csv")["Feature"].tolist()
imputer_v2 = SimpleImputer(strategy="median")
X_tr_v2 = imputer_v2.fit_transform(train_baseline[v2_feats])
X_te_v2 = imputer_v2.transform(test_df[v2_feats])
scaler_v2 = StandardScaler()
X_tr_v2_sc = scaler_v2.fit_transform(X_tr_v2)
X_te_v2_sc = scaler_v2.transform(X_te_v2)
if_v2 = IsolationForest(n_estimators=300, random_state=42, contamination="auto", n_jobs=-1)
if_v2.fit(X_tr_v2_sc)
scores_v2 = -if_v2.score_samples(X_te_v2_sc)
pred_v2 = (if_v2.predict(X_te_v2_sc) == -1).astype(int)
record_metrics("IsolationForest_V2_Reduced", y_test, pred_v2, scores_v2, "69 features")

# Model 3: IF Core 14 Features (Tuned contamination)
# On training baseline, 90th percentile threshold
if_core = IsolationForest(n_estimators=300, random_state=42, contamination=0.1, n_jobs=-1)
if_core.fit(X_train_core_scaled)
scores_core = -if_core.score_samples(X_test_core_scaled)
train_scores = -if_core.score_samples(X_train_core_scaled)
thresh_core = np.quantile(train_scores, 0.85)
pred_core = (scores_core >= thresh_core).astype(int)
record_metrics("IsolationForest_Core14_Calibrated", y_test, pred_core, scores_core, "14 core features")

# Model 4: One-Class SVM
oc_svm = OneClassSVM(kernel="rbf", gamma="scale", nu=0.15)
oc_svm.fit(X_train_core_scaled)
scores_svm = -oc_svm.score_samples(X_test_core_scaled)
pred_svm = (oc_svm.predict(X_test_core_scaled) == -1).astype(int)
record_metrics("OneClassSVM_Core14", y_test, pred_svm, scores_svm, "14 core features")

# Model 5: Local Outlier Factor (Novelty=True)
lof = LocalOutlierFactor(n_neighbors=20, novelty=True, contamination=0.1)
lof.fit(X_train_core_scaled)
scores_lof = -lof.score_samples(X_test_core_scaled)
pred_lof = (lof.predict(X_test_core_scaled) == -1).astype(int)
record_metrics("LocalOutlierFactor_Core14", y_test, pred_lof, scores_lof, "14 core features")

# Model 6: Elliptic Envelope (Mahalanobis distance on top 6 orthogonal features)
top_6 = ["hr_mean_bpm", "hrv_rmssd_ms", "eda_mean", "resp_rate_bpm", "temp_mean", "acc_magnitude_mean"]
X_tr_6 = imputer_core.fit_transform(train_baseline[top_6])
X_te_6 = imputer_core.transform(test_df[top_6])
X_tr_6_sc = scaler_core.fit_transform(X_tr_6)
X_te_6_sc = scaler_core.transform(X_te_6)
ee = EllipticEnvelope(contamination=0.15, random_state=42)
ee.fit(X_tr_6_sc)
scores_ee = -ee.score_samples(X_te_6_sc)
pred_ee = (ee.predict(X_te_6_sc) == -1).astype(int)
record_metrics("EllipticEnvelope_Top6", y_test, pred_ee, scores_ee, "6 core features")

# Model 7: Supervised Random Forest (Trained on train subjects only)
X_tr_all = imputer_full.fit_transform(train_df[all_feature_cols])
X_te_all = imputer_full.transform(test_df[all_feature_cols])
rf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, class_weight="balanced")
rf.fit(X_tr_all, y_train)
prob_rf = rf.predict_proba(X_te_all)[:, 1]
pred_rf = (prob_rf >= 0.5).astype(int)
record_metrics("RandomForest_Supervised_Full", y_test, pred_rf, prob_rf, "99 features")

# Model 8: Supervised Extra Trees
et = ExtraTreesClassifier(n_estimators=200, max_depth=6, random_state=42, class_weight="balanced")
et.fit(X_tr_all, y_train)
prob_et = et.predict_proba(X_te_all)[:, 1]
pred_et = (prob_et >= 0.5).astype(int)
record_metrics("ExtraTrees_Supervised_Full", y_test, pred_et, prob_et, "99 features")

# Model 9: Supervised HistGradientBoosting
hgb = HistGradientBoostingClassifier(max_iter=100, max_depth=5, random_state=42, class_weight="balanced")
hgb.fit(X_tr_all, y_train)
prob_hgb = hgb.predict_proba(X_te_all)[:, 1]
pred_hgb = (prob_hgb >= 0.5).astype(int)
record_metrics("HistGradientBoosting_Supervised", y_test, pred_hgb, prob_hgb, "99 features")

# Model 10: Personalized Physiological Baseline Anomaly Detection
# For each test subject, calibrate using their first K baseline windows (e.g. K=5)
# Score each test window using robust Z-score across autonomic features
calib_k = 5
pers_scores = []
pers_preds = []

# Key physiological markers with expected physiological direction:
# HR increase (+), HRV RMSSD decrease (-), EDA mean increase (+), Resp rate increase (+), Temp decrease (-)
for s in test_subjects:
    sub_df = test_df[test_df["subject_id"] == s].sort_values("start_sec").copy()
    base_sub = sub_df[sub_df["label"] == 1]
    calib_windows = base_sub.iloc[:calib_k]
    
    # Compute median and MAD on calibration windows
    med = calib_windows[core_14].median()
    mad = (calib_windows[core_14] - med).abs().median() * 1.4826
    mad = mad.replace(0, np.nan).fillna(calib_windows[core_14].std() + 1e-4)
    
    for idx, row in sub_df.iterrows():
        # Robust z-scores
        z = (row[core_14] - med) / mad
        # Autonomic stress deviation score:
        # Cardio strain: higher HR, lower HRV
        cardio_score = (z["hr_mean_bpm"] - z["hrv_rmssd_ms"]) / 2.0
        # EDA strain: higher skin conductance
        eda_score = z["eda_mean"]
        # Resp strain: higher resp rate
        resp_score = z["resp_rate_bpm"]
        # Temp strain: lower skin temp
        temp_score = -z["temp_mean"]
        
        # Combined anomaly score (weighted physiological deviation)
        total_score = float(0.35 * cardio_score + 0.35 * eda_score + 0.15 * resp_score + 0.15 * temp_score)
        pers_scores.append(total_score)

pers_scores = np.array(pers_scores)
# Threshold calibrated on training subjects using same calibration procedure!
train_pers_scores = []
for s in train_subjects:
    sub_df = train_df[train_df["subject_id"] == s].sort_values("start_sec").copy()
    base_sub = sub_df[sub_df["label"] == 1]
    if len(base_sub) >= calib_k:
        calib_windows = base_sub.iloc[:calib_k]
        med = calib_windows[core_14].median()
        mad = (calib_windows[core_14] - med).abs().median() * 1.4826
        mad = mad.replace(0, np.nan).fillna(calib_windows[core_14].std() + 1e-4)
        for idx, row in base_sub.iloc[calib_k:].iterrows():
            z = (row[core_14] - med) / mad
            cs = (z["hr_mean_bpm"] - z["hrv_rmssd_ms"]) / 2.0
            es = z["eda_mean"]
            rs = z["resp_rate_bpm"]
            ts = -z["temp_mean"]
            train_pers_scores.append(float(0.35 * cs + 0.35 * es + 0.15 * rs + 0.15 * ts))

train_pers_threshold = np.quantile(train_pers_scores, 0.90) if train_pers_scores else 2.0
pers_preds = (pers_scores >= train_pers_threshold).astype(int)

# Align y_test correctly by subject and start_sec
aligned_y_test = []
for s in test_subjects:
    sub_df = test_df[test_df["subject_id"] == s].sort_values("start_sec")
    aligned_y_test.extend((sub_df["label"] == 2).astype(int).tolist())
aligned_y_test = np.array(aligned_y_test)

record_metrics("Personalized_Baseline_Detector", aligned_y_test, pers_preds, pers_scores, "Adaptive Z-score")

res_df = pd.DataFrame(results)
print(res_df.to_string(index=False))
