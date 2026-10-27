"""Generate a curated demo CSV dataset for live 3-minute video recording.

Contains:
- 6 Authentic valid students (matching Ground Truth master records).
- 1 Dual-Enrollment Collision (Student active at VJTI concurrently claimed by KJSIT).
- 1 Semester Advancement Leap (Claims Semester 6 during admission).
- 1 Aadhaar / Identity Mismatch (Mismatched Aadhaar number & demographics).
- 1 Prerequisite Qualification Gap (Non-qualifying degree for engineering admission).
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import sqlite3
import pandas as pd
from ml_model.feature_extractor import GroundTruthComparator
from ml_model.anomaly_model import ApaarAnomalyClassifier

DB_PATH = os.path.join(BASE_DIR, "database", "ground_truth.db")
MODEL_PATH = os.path.join(BASE_DIR, "ml_model", "saved_models", "rf_anomaly_model.joblib")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "demo_admission_batch_2026.csv")


def generate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Pick 10 distinct students from KJSIT
    cur.execute(
        """
        SELECT apaar_id, aadhar_number, full_name, date_of_birth, gender, course_name, current_semester
        FROM ground_truth_students
        WHERE institution_name = 'K J Somaiya Institute of Technology'
        ORDER BY id ASC LIMIT 10;
        """
    )
    kjsit_students = cur.fetchall()

    # Pick 1 active student from VJTI for dual claim collision
    cur.execute(
        """
        SELECT apaar_id, aadhar_number, full_name, date_of_birth, gender, course_name, current_semester
        FROM ground_truth_students
        WHERE institution_name LIKE '%VJTI%'
        ORDER BY id DESC LIMIT 1;
        """
    )
    vjti_student = cur.fetchone()
    conn.close()

    records = []

    # 1. Six Authentic Clean Students (Students 0 to 5)
    for r in kjsit_students[:6]:
        records.append({
            "name": r[2],
            "apaar_id": r[0],
            "aadhar_number": r[1],
            "date_of_birth": r[3],
            "gender": r[4],
            "course": r[5],
            "semester": r[6],
            "last_degree": "12th Standard / HSC",
            "college": "K J Somaiya Institute of Technology",
            "audit_type": "CLEAN"
        })

    # 2. Dual Enrollment Collision (VJTI student claimed concurrently by KJSIT)
    records.append({
        "name": vjti_student[2],
        "apaar_id": vjti_student[0],
        "aadhar_number": vjti_student[1],
        "date_of_birth": vjti_student[3],
        "gender": vjti_student[4],
        "course": "B.Tech - Artificial Intelligence & Data Science",
        "semester": 1,
        "last_degree": "12th Standard / HSC",
        "college": "K J Somaiya Institute of Technology",
        "audit_type": "DUAL_ENROLLMENT_COLLISION"
    })

    # 3. Semester Advancement Leap (Student 6: Registered in Sem 1, submitting as Sem 6)
    sem_leap_std = kjsit_students[6]
    records.append({
        "name": sem_leap_std[2],
        "apaar_id": sem_leap_std[0],
        "aadhar_number": sem_leap_std[1],
        "date_of_birth": sem_leap_std[3],
        "gender": sem_leap_std[4],
        "course": sem_leap_std[5],
        "semester": 6,  # Leap to Sem 6
        "last_degree": "12th Standard / HSC",
        "college": "K J Somaiya Institute of Technology",
        "audit_type": "SEMESTER_LEAP_ANOMALY"
    })

    # 4. Aadhaar / Demographic Mismatch (Student 7: Valid APAAR paired with wrong Aadhaar & name)
    mismatch_std = kjsit_students[7]
    records.append({
        "name": "Rohan Vikram Singhania",  # Fake mismatch name
        "apaar_id": mismatch_std[0],
        "aadhar_number": "999988887777",  # Fake Aadhaar
        "date_of_birth": "1997-03-12",     # Mismatched DOB
        "gender": "Male",
        "course": mismatch_std[5],
        "semester": mismatch_std[6],
        "last_degree": "12th Standard / HSC",
        "college": "K J Somaiya Institute of Technology",
        "audit_type": "AADHAAR_IDENTITY_MISMATCH"
    })

    # 5. Prerequisite Qualification Gap (Student 8: Non-accredited qualification)
    deg_gap_std = kjsit_students[8]
    records.append({
        "name": deg_gap_std[2],
        "apaar_id": deg_gap_std[0],
        "aadhar_number": deg_gap_std[1],
        "date_of_birth": deg_gap_std[3],
        "gender": deg_gap_std[4],
        "course": deg_gap_std[5],
        "semester": deg_gap_std[6],
        "last_degree": "Non-Accredited Bridge Course",
        "college": "K J Somaiya Institute of Technology",
        "audit_type": "DEGREE_QUALIFICATION_GAP"
    })

    df = pd.DataFrame(records)
    # Save the demo CSV (without internal audit_type column for realistic college upload)
    upload_df = df.drop(columns=["audit_type"])
    upload_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Generated demo dataset with {len(upload_df)} records at: {OUTPUT_CSV}")

    # Validate with Random Forest comparator
    comparator = GroundTruthComparator(DB_PATH)
    rf_model = ApaarAnomalyClassifier.load(MODEL_PATH)

    ingest_format = upload_df.rename(columns={
        "name": "full_name",
        "course": "course_name",
        "semester": "current_semester",
        "last_degree": "last_successful_degree",
        "college": "college_name",
    })
    ingest_format["university_name"] = "University of Mumbai"
    ingest_format["academic_year"] = "2025-26"

    feat_df, gt_ids, all_flags = comparator.extract_features_dataframe(ingest_format)
    proba = rf_model.predict_proba(feat_df)[:, 1]

    print("\n--- Model Verification Audit ---")
    for idx, (p, f) in enumerate(zip(proba, all_flags)):
        status = "FLAGGED" if p >= 0.50 else "CLEAN"
        print(f"Record {idx+1:02d} [{status}] Conf={p:.2%}: {df.iloc[idx]['name']} ({df.iloc[idx]['audit_type']}) -> {f or ['CLEAN']}")


if __name__ == "__main__":
    generate()
