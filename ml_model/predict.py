"""Inference Pipeline for APAAR Data Integrity & Anomaly Detection.

Compares an incoming student CSV against the SQLite Ground Truth
database using the trained Scikit-Learn Random Forest model, calculates
anomaly probabilities, and records results into the database.
"""

import argparse
import os
import sqlite3
import sys
import uuid
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ml_model.anomaly_model import ApaarAnomalyClassifier
from ml_model.feature_extractor import FEATURE_NAMES, GroundTruthComparator


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Random Forest Anomaly Prediction on an uploaded student CSV."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to inputted student CSV file to verify.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=os.path.join(BASE_DIR, "database", "ground_truth.db"),
        help="Path to SQLite ground truth database.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.path.join(BASE_DIR, "ml_model", "saved_models", "rf_anomaly_model.joblib"),
        help="Path to trained Scikit-Learn Random Forest model file.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.50,
        help="Probability threshold to classify a record as anomalous (default 0.50).",
    )
    parser.add_argument(
        "--output_csv",
        type=str,
        default=None,
        help="Optional path to export flagged anomaly report CSV.",
    )
    return parser.parse_args()


def run_inference(input_csv: str, db_path: str, model_path: str, threshold: float = 0.50, output_csv: str = None):
    print("=" * 70)
    print("APAAR Random Forest Anomaly Prediction & Record Comparison")
    print("=" * 70)

    if not os.path.exists(input_csv):
        print(f"[Error] Input CSV file not found: {input_csv}")
        sys.exit(1)

    if not os.path.exists(model_path):
        print(f"[Error] Trained model not found at {model_path}.")
        print("Please train the model first using: python ml_model/train.py --data <dataset.csv>")
        sys.exit(1)

    # 1. Load model
    print(f"Loading trained Random Forest model: {model_path}")
    clf = ApaarAnomalyClassifier.load(model_path)

    # 2. Load input CSV
    print(f"Reading input records: {input_csv}")
    df = pd.read_csv(input_csv)
    total_records = len(df)
    print(f"Total records in input batch: {total_records}")

    # 3. Extract features via GroundTruthComparator
    print(f"Querying Ground Truth database ({db_path}) & extracting feature vectors...")
    comparator = GroundTruthComparator(db_path)
    X, gt_ids, all_flags = comparator.extract_features_dataframe(df)

    # 4. Predict anomaly probabilities
    proba = clf.predict_proba(X)[:, 1]
    is_anomaly = (proba >= threshold).astype(int)

    # 5. Populate results
    df["anomaly_score"] = np.round(proba, 4)
    df["is_anomaly"] = is_anomaly
    df["matched_ground_truth_id"] = gt_ids
    df["detected_reasons"] = ["; ".join(flags) if flags else "CLEAN" for flags in all_flags]

    anomaly_count = int(is_anomaly.sum())
    clean_count = total_records - anomaly_count
    print("\n" + "=" * 70)
    print(f"Analysis Summary for {os.path.basename(input_csv)}:")
    print(f" - Total Processed: {total_records}")
    print(f" - Clean Records:   {clean_count} ({(clean_count/total_records)*100:.1f}%)")
    print(f" - Flagged Records: {anomaly_count} ({(anomaly_count/total_records)*100:.1f}%)")
    print("=" * 70)

    # 6. Record batch in SQLite
    batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO upload_batches (batch_id, file_name, total_records, anomalies_flagged, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (batch_id, os.path.basename(input_csv), total_records, anomaly_count, "ANALYZED"),
        )

        for idx, row in df.iterrows():
            rec_apaar = str(row.get("apaar_id", ""))
            rec_aadhar = str(row.get("aadhar_number", ""))
            rec_name = str(row.get("full_name", row.get("name", "")))
            rec_dob = str(row.get("date_of_birth", row.get("dob", "")))
            rec_degree = str(row.get("last_successful_degree", ""))
            rec_sem = int(row.get("current_semester", 1)) if str(row.get("current_semester", "")).isdigit() else 1

            rec_uni = str(row.get("university_name", row.get("university", "")))
            rec_inst = str(row.get("institution_name", row.get("institution", row.get("college", ""))))

            cursor.execute(
                """
                INSERT INTO uploaded_student_records
                (batch_id, apaar_id, aadhar_number, full_name, date_of_birth, university_name, institution_name, last_successful_degree, current_semester, raw_row_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (batch_id, rec_apaar, rec_aadhar, rec_name, rec_dob, rec_uni, rec_inst, rec_degree, rec_sem, str(row.to_dict())),
            )
            rec_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO anomaly_detection_results
                (batch_id, record_id, ground_truth_id, match_status, anomaly_score, is_anomaly, detected_anomalies)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    rec_id,
                    gt_ids[idx],
                    "FRAUDULENT" if is_anomaly[idx] else "EXACT_MATCH",
                    float(proba[idx]),
                    int(is_anomaly[idx]),
                    df.at[idx, "detected_reasons"],
                ),
            )

        conn.commit()
        print(f"Results recorded in SQLite batch table under ID: {batch_id}")
    finally:
        conn.close()

    if output_csv:
        df.to_csv(output_csv, index=False)
        print(f"Exported anomaly report to: {output_csv}")

    return df


def main():
    args = parse_args()
    run_inference(
        input_csv=args.input,
        db_path=args.db,
        model_path=args.model,
        threshold=args.threshold,
        output_csv=args.output_csv,
    )


if __name__ == "__main__":
    main()
