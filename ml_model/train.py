"""Training Script for ApaarAnomalyClassifier using Scikit-Learn.

Follows ML Best Practices:
1. Strict featurization ordering (train/test split before fitting).
2. Missing value handling.
3. Stratified K-fold / validation splits.
4. Comprehensive metrics: Precision, Recall, F1-Score, ROC-AUC, and Confusion Matrix.
5. Model serialization with Joblib.

NOTE: As per project guidelines, this script does NOT train on dummy data.
It awaits user-provided labeled dataset.
"""

import argparse
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

# Add parent directory to path so ml_model can be imported directly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ml_model.anomaly_model import ApaarAnomalyClassifier
from ml_model.feature_extractor import FEATURE_NAMES, GroundTruthComparator


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train Scikit-Learn Random Forest Anomaly Model for APAAR Data Integrity."
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Path to training CSV file (must include target label column: 'is_anomaly' or 'label').",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=os.path.join(BASE_DIR, "database", "ground_truth.db"),
        help="Path to SQLite ground truth database.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(BASE_DIR, "ml_model", "saved_models", "rf_anomaly_model.joblib"),
        help="Output path for the serialized Random Forest model.",
    )
    parser.add_argument(
        "--n_estimators",
        type=int,
        default=100,
        help="Number of decision trees in Random Forest.",
    )
    parser.add_argument(
        "--max_depth",
        type=int,
        default=12,
        help="Maximum depth of trees.",
    )
    parser.add_argument(
        "--test_size",
        type=float,
        default=0.2,
        help="Fraction of data reserved for validation (default 0.20).",
    )
    return parser.parse_args()


def train_pipeline(data_path: str, db_path: str, output_path: str, n_estimators: int, max_depth: int, test_size: float):
    print("=" * 70)
    print("APAAR Random Forest Anomaly Model — Training Pipeline")
    print("=" * 70)

    if not os.path.exists(data_path):
        print(f"[Error] Training dataset not found at: {data_path}")
        sys.exit(1)

    print(f"Loading training data from: {data_path}")
    df = pd.read_csv(data_path)
    print(f"Dataset shape: {df.shape[0]} rows, {df.shape[1]} columns")

    # Detect target label column
    target_col = None
    for candidate in ["is_anomaly", "label", "target", "anomaly", "is_fraud"]:
        if candidate in df.columns:
            target_col = candidate
            break

    if target_col is None:
        print("[Error] Could not find target column. Expected 'is_anomaly', 'label', or 'anomaly' (0=valid, 1=anomaly).")
        sys.exit(1)

    # Check if dataset already contains extracted comparison features or raw records
    has_features = all(feat in df.columns for feat in FEATURE_NAMES)

    if has_features:
        print("[Info] Dataset already contains pre-computed comparison features.")
        X = df[FEATURE_NAMES]
    else:
        print("[Info] Extracting comparison features against Ground Truth SQLite DB...")
        comparator = GroundTruthComparator(db_path)
        X, _, _ = comparator.extract_features_dataframe(df)

    y = df[target_col].astype(int)

    # Handle missing / null values in feature matrix (ML Best Practices)
    null_counts = X.isnull().sum()
    if null_counts.sum() > 0:
        print("[Data Cleaning] Missing values detected in features:")
        print(null_counts[null_counts > 0])
        print("Imputing numeric features with median/zero defaults...")
        X = X.fillna(0.0)

    print(f"\nClass Distribution:\n - Authentic (0): {(y == 0).sum()} ({((y == 0).sum()/len(y))*100:.1f}%)")
    print(f" - Anomaly (1):   {(y == 1).sum()} ({((y == 1).sum()/len(y))*100:.1f}%)")

    # ML Best Practice: Train/Test Split BEFORE model fitting
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

    print(f"\nSplit sizes: Train={len(X_train)}, Test={len(X_test)}")
    print(f"Fitting Scikit-Learn RandomForestClassifier (n_estimators={n_estimators}, max_depth={max_depth})...")

    clf = ApaarAnomalyClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42
    )
    clf.fit(X_train, y_train)

    # Evaluate on held-out test split
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    print("\n" + "=" * 70)
    print("Test Set Evaluation Metrics:")
    print("=" * 70)
    print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"Recall:    {recall_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"F1-Score:  {f1_score(y_test, y_pred, zero_division=0):.4f}")
    try:
        print(f"ROC-AUC:   {roc_auc_score(y_test, y_proba):.4f}")
    except ValueError:
        pass

    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Authentic", "Anomaly"], zero_division=0))

    print("\nTop Feature Importances (Gini importance):")
    for feat, imp in list(clf.get_feature_importances().items())[:8]:
        print(f"  • {feat:<30}: {imp:.4f}")

    # Serialize trained model
    clf.save(output_path)
    print(f"\n[Success] Trained model saved ready for inference at: {output_path}")


def main():
    args = parse_args()

    if args.data is None:
        print("=" * 70)
        print("APAAR Random Forest Anomaly Model Architecture Ready")
        print("=" * 70)
        print("Model is configured and waiting for user-provided training data.")
        print("Dummy data training is disabled per instructions.\n")
        print("To train once you have downloaded or prepared your dataset, run:")
        print("  .venv\\Scripts\\python ml_model/train.py --data path/to/your_dataset.csv\n")
        print("Expected training CSV columns:")
        print("  • apaar_id, aadhar_number, date_of_birth, last_successful_degree, current_semester")
        print("  • university_name (e.g. University of Mumbai), institution_name (e.g. College of Engg)")
        print("  • is_anomaly (0 = Authentic, 1 = Fraud/Anomaly)")
        print("  • (Optional) full_name, course_name")
        print("=" * 70)
        return

    train_pipeline(
        data_path=args.data,
        db_path=args.db,
        output_path=args.output,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        test_size=args.test_size,
    )


if __name__ == "__main__":
    main()
