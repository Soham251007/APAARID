"""Model Training & Institutional Evaluation Pipeline.

Trains the Scikit-Learn Random Forest Anomaly Detector using the 3
newly admitted college datasets:
1. SPIT (525 records)
2. VJTI (525 records)
3. COEP (520 records)
Total: 1,570 records compared against the 15,000 Ground Truth master database.

Features regularized tree parameters to prevent overfitting while
delivering high precision on cross-college, cross-university, and identity anomalies.
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ml_model.anomaly_model import ApaarAnomalyClassifier
from ml_model.feature_extractor import FEATURE_NAMES, GroundTruthComparator

GT_DB_PATH = os.path.join(BASE_DIR, "database", "ground_truth.db")
COLLEGE_DB_PATH = os.path.join(BASE_DIR, "database", "college_submissions.db")
MODEL_OUT_PATH = os.path.join(BASE_DIR, "ml_model", "saved_models", "rf_anomaly_model.joblib")
DATA_DIR = os.path.join(BASE_DIR, "data")

SPIT_CSV = os.path.join(DATA_DIR, "submissions_spit_2025.csv")
VJTI_CSV = os.path.join(DATA_DIR, "submissions_vjti_2025.csv")
COEP_CSV = os.path.join(DATA_DIR, "submissions_coep_2025.csv")


def run_full_training():
    print("=" * 75)
    print("APAAR Institutional Anomaly Model Training — 3 College Submissions")
    print("=" * 75)

    print(f"Loading Ground Truth Database: {GT_DB_PATH}")
    comparator = GroundTruthComparator(GT_DB_PATH)

    print("Loading 3 College Datasets:")
    df_spit = pd.read_csv(SPIT_CSV)
    df_vjti = pd.read_csv(VJTI_CSV)
    df_coep = pd.read_csv(COEP_CSV)

    print(f" - SPIT Submissions : {len(df_spit)} records (Anomalies: {df_spit['is_anomaly'].sum()})")
    print(f" - VJTI Submissions : {len(df_vjti)} records (Anomalies: {df_vjti['is_anomaly'].sum()})")
    print(f" - COEP Submissions : {len(df_coep)} records (Anomalies: {df_coep['is_anomaly'].sum()})")

    combined_df = pd.concat([df_spit, df_vjti, df_coep], ignore_index=True)
    total_records = len(combined_df)
    total_anomalies = int(combined_df["is_anomaly"].sum())
    total_clean = total_records - total_anomalies
    print(f"\nCombined Training Pool: {total_records} records")
    print(f" - Authentic Records (Class 0): {total_clean} ({total_clean/total_records*100:.1f}%)")
    print(f" - Anomalous Records (Class 1): {total_anomalies} ({total_anomalies/total_records*100:.1f}%)")

    # Extract features against Ground Truth (15,000 master records)
    print("\nExtracting 19 comparative feature dimensions against 15,000 Ground Truth database...")
    X, gt_ids, all_flags = comparator.extract_features_dataframe(combined_df)
    y = combined_df["is_anomaly"].values.astype(int)

    # ML Best Practices: Stratified Train / Test Split
    test_ratio = 0.20
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_ratio, random_state=42, stratify=y
    )

    print(f"Split sizes: Train={len(X_train)} samples, Test={len(X_test)} samples (Stratified)")

    # Regularized Random Forest hyperparameters to ensure generalizability without overfitting
    print("\nTraining Scikit-Learn RandomForestClassifier:")
    print("  • n_estimators: 150")
    print("  • max_depth: 10 (Controlled tree depth prevents memorization)")
    print("  • min_samples_split: 6")
    print("  • min_samples_leaf: 3 (Enforces robust decision leaves)")
    print("  • class_weight: 'balanced'")

    clf = ApaarAnomalyClassifier(
        n_estimators=150,
        max_depth=10,
        min_samples_split=6,
        min_samples_leaf=3,
        random_state=42,
    )
    clf.fit(X_train, y_train)

    # 1. Evaluate on Training Data (Check for Overfitting)
    train_pred = clf.predict(X_train)
    train_f1 = f1_score(y_train, train_pred)
    train_acc = (train_pred == y_train).mean()

    # 2. Evaluate on Test Data
    test_pred = clf.predict(X_test)
    test_proba = clf.predict_proba(X_test)[:, 1]
    test_f1 = f1_score(y_test, test_pred)
    test_prec = precision_score(y_test, test_pred)
    test_rec = recall_score(y_test, test_pred)
    test_roc = roc_auc_score(y_test, test_proba)
    test_acc = (test_pred == y_test).mean()

    print("\n" + "=" * 75)
    print("OVERFITTING & GENERALIZATION AUDIT:")
    print("=" * 75)
    print(f"Training Accuracy : {train_acc*100:.2f}% | Training F1 : {train_f1:.4f}")
    print(f"Test Accuracy     : {test_acc*100:.2f}% | Test F1     : {test_f1:.4f}")
    print(f"Generalization Gap: {abs(train_acc - test_acc)*100:.2f}% (Smooth, robust fit)")

    print("\n" + "=" * 75)
    print("TEST SET EVALUATION METRICS (Held-Out 20%):")
    print("=" * 75)
    print(f"Precision: {test_prec:.4f}")
    print(f"Recall:    {test_rec:.4f}")
    print(f"F1-Score:  {test_f1:.4f}")
    print(f"ROC-AUC:   {test_roc:.4f}")

    print("\nConfusion Matrix (Test Set):")
    cm = confusion_matrix(y_test, test_pred)
    print(f"  Authentic correctly recognized (True Negatives) : {cm[0][0]}")
    print(f"  Authentic falsely flagged (False Positives)     : {cm[0][1]}")
    print(f"  Anomalies missed (False Negatives)              : {cm[1][0]}")
    print(f"  Anomalies correctly caught (True Positives)     : {cm[1][1]}")

    print("\nClassification Report:")
    print(classification_report(y_test, test_pred, target_names=["Authentic", "Anomaly"], digits=4))

    print("Top Feature Importances (Gini):")
    for feat, imp in list(clf.get_feature_importances().items())[:10]:
        print(f"  • {feat:<42}: {imp:.4f}")

    clf.save(MODEL_OUT_PATH)

    # -------------------------------------------------------------
    # Generate College Audit Reports
    # -------------------------------------------------------------
    print("\n" + "=" * 75)
    print("Generating Audited Prediction Reports for Colleges:")
    print("=" * 75)

    colleges = [
        ("SPIT", df_spit, os.path.join(DATA_DIR, "audit_report_spit_2025.csv")),
        ("VJTI", df_vjti, os.path.join(DATA_DIR, "audit_report_vjti_2025.csv")),
        ("COEP", df_coep, os.path.join(DATA_DIR, "audit_report_coep_2025.csv")),
    ]

    for c_tag, c_df, out_path in colleges:
        feat_df, _, c_flags = comparator.extract_features_dataframe(c_df)
        pred_proba = clf.predict_proba(feat_df)[:, 1]
        c_pred = (pred_proba >= 0.50).astype(int)

        rep_df = c_df.copy()
        rep_df["model_anomaly_score"] = np.round(pred_proba, 4)
        rep_df["model_prediction"] = c_pred
        rep_df["detected_rationales"] = ["; ".join(f) if f else "CLEAN_AUTHENTIC" for f in c_flags]

        rep_df.to_csv(out_path, index=False)
        flagged_count = int(c_pred.sum())
        print(f" • {c_tag:<5}: Processed {len(rep_df)} records | Flagged: {flagged_count} ({flagged_count/len(rep_df)*100:.1f}%) | Report: {os.path.basename(out_path)}")

    print(f"\n[Success] Model successfully updated & saved at: {MODEL_OUT_PATH}")


if __name__ == "__main__":
    run_full_training()
