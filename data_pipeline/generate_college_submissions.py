"""College Submissions Dataset Generator & Separate Database Ingestion.

Creates 3 realistic college admission upload datasets (around 520 records each):
1. Sardar Patel Institute of Technology (SPIT) - University of Mumbai
2. Veermata Jijabai Technological Institute (VJTI) - University of Mumbai
3. College of Engineering Pune (COEP Tech) - Savitribai Phule Pune University

Stores these student submissions in an ISOLATED database:
  database/college_submissions.db (separate from ground_truth.db)

Injects rich, realistic anomaly patterns across the datasets:
- Inter-dataset duplicate admissions (VJTI students appearing in SPIT)
- Cross-university duplicate admissions (SPIT/VJTI students appearing in COEP)
- Aadhaar identity theft / swapped credentials
- Malformed / truncated APAAR IDs (10-11 digits)
- Prerequisite degree anomalies (claiming 10th standard for B.Tech)
- Unverified semester leaps in 1st year admissions
- DOB discrepancies / typos
- Unregistered phantom students
"""

import os
import random
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GT_DB_PATH = os.path.join(BASE_DIR, "database", "ground_truth.db")
COLLEGE_DB_PATH = os.path.join(BASE_DIR, "database", "college_submissions.db")
DATA_DIR = os.path.join(BASE_DIR, "data")

SPIT_CSV = os.path.join(DATA_DIR, "submissions_spit_2025.csv")
VJTI_CSV = os.path.join(DATA_DIR, "submissions_vjti_2025.csv")
COEP_CSV = os.path.join(DATA_DIR, "submissions_coep_2025.csv")


def init_college_submissions_db():
    """Initializes the isolated college submissions SQLite database."""
    print(f"Initializing separate college submissions DB at: {COLLEGE_DB_PATH}")
    conn = sqlite3.connect(COLLEGE_DB_PATH)
    cursor = conn.cursor()

    cursor.executescript(
        """
        DROP TABLE IF EXISTS college_submitted_students;
        DROP TABLE IF EXISTS submission_batches_meta;

        CREATE TABLE submission_batches_meta (
            batch_id TEXT PRIMARY KEY,
            college_name TEXT NOT NULL,
            university_name TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            total_records INTEGER,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE college_submitted_students (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            college_name TEXT NOT NULL,
            university_name TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            apaar_id TEXT,
            aadhar_number TEXT,
            full_name TEXT,
            date_of_birth TEXT,
            gender TEXT,
            course_name TEXT,
            last_successful_degree TEXT,
            current_semester INTEGER,
            is_anomaly INTEGER NOT NULL DEFAULT 0,
            anomaly_types TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES submission_batches_meta(batch_id)
        );

        CREATE INDEX idx_sub_college ON college_submitted_students (college_name);
        CREATE INDEX idx_sub_apaar ON college_submitted_students (apaar_id);
        CREATE INDEX idx_sub_aadhar ON college_submitted_students (aadhar_number);
        CREATE INDEX idx_sub_anomaly ON college_submitted_students (is_anomaly);
        """
    )
    conn.commit()
    conn.close()


def generate_college_submissions():
    random.seed(101)
    init_college_submissions_db()

    # Load authentic students from Ground Truth database
    print("Loading base student identities from ground_truth.db ...")
    conn_gt = sqlite3.connect(GT_DB_PATH)
    gt_df = pd.read_sql_query("SELECT * FROM ground_truth_students", conn_gt)
    conn_gt.close()

    print(f"Loaded {len(gt_df)} master records from Ground Truth.")

    # Partition pools for colleges:
    # SPIT pool: 400 clean
    # VJTI pool: 400 clean
    # COEP pool: 400 clean
    pool_spit = gt_df.iloc[0:400].copy()
    pool_vjti = gt_df.iloc[400:800].copy()
    pool_coep = gt_df.iloc[800:1200].copy()

    # Swapping reference pool
    pool_other = gt_df.iloc[1200:2000].copy()

    records_spit = []
    records_vjti = []
    records_coep = []

    # -------------------------------------------------------------
    # 1. Populate SPIT Base Records (~360 Clean)
    # -------------------------------------------------------------
    for _, row in pool_spit.iloc[0:360].iterrows():
        records_spit.append({
            "college_name": "Sardar Patel Institute of Technology (SPIT)",
            "university_name": "University of Mumbai",
            "academic_year": "2025-26",
            "apaar_id": row["apaar_id"],
            "aadhar_number": row["aadhar_number"],
            "full_name": row["full_name"],
            "date_of_birth": row["date_of_birth"],
            "gender": row["gender"],
            "course_name": row["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 0,
            "anomaly_types": "CLEAN_AUTHENTIC",
        })

    # -------------------------------------------------------------
    # 2. Populate VJTI Base Records (~360 Clean)
    # -------------------------------------------------------------
    for _, row in pool_vjti.iloc[0:360].iterrows():
        records_vjti.append({
            "college_name": "Veermata Jijabai Technological Institute (VJTI)",
            "university_name": "University of Mumbai",
            "academic_year": "2025-26",
            "apaar_id": row["apaar_id"],
            "aadhar_number": row["aadhar_number"],
            "full_name": row["full_name"],
            "date_of_birth": row["date_of_birth"],
            "gender": row["gender"],
            "course_name": row["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 0,
            "anomaly_types": "CLEAN_AUTHENTIC",
        })

    # -------------------------------------------------------------
    # 3. Populate COEP Base Records (~360 Clean)
    # -------------------------------------------------------------
    for _, row in pool_coep.iloc[0:360].iterrows():
        records_coep.append({
            "college_name": "College of Engineering Pune (COEP Tech)",
            "university_name": "Savitribai Phule Pune University",
            "academic_year": "2025-26",
            "apaar_id": row["apaar_id"],
            "aadhar_number": row["aadhar_number"],
            "full_name": row["full_name"],
            "date_of_birth": row["date_of_birth"],
            "gender": row["gender"],
            "course_name": row["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 0,
            "anomaly_types": "CLEAN_AUTHENTIC",
        })

    # =============================================================
    # ANOMALY GENERATION ACROSS DATASETS
    # =============================================================

    # Anomaly Type A: Intra-University Cross-College Duplicates (SPIT & VJTI Conflict)
    # 45 students from VJTI's legitimate pool are ALSO submitted by SPIT!
    print("Injecting Intra-University duplicate admissions (SPIT vs VJTI)...")
    spit_vjti_conflicts = pool_vjti.iloc[360:400].copy()
    for _, row in spit_vjti_conflicts.iterrows():
        # Clean in VJTI
        records_vjti.append({
            "college_name": "Veermata Jijabai Technological Institute (VJTI)",
            "university_name": "University of Mumbai",
            "academic_year": "2025-26",
            "apaar_id": row["apaar_id"],
            "aadhar_number": row["aadhar_number"],
            "full_name": row["full_name"],
            "date_of_birth": row["date_of_birth"],
            "gender": row["gender"],
            "course_name": row["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 0,
            "anomaly_types": "CLEAN_IN_PRIMARY_COLLEGE",
        })
        # Duplicate anomalous claim in SPIT!
        records_spit.append({
            "college_name": "Sardar Patel Institute of Technology (SPIT)",
            "university_name": "University of Mumbai",
            "academic_year": "2025-26",
            "apaar_id": row["apaar_id"],
            "aadhar_number": row["aadhar_number"],
            "full_name": row["full_name"],
            "date_of_birth": row["date_of_birth"],
            "gender": row["gender"],
            "course_name": "B.Tech - Computer Engineering",
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 1,
            "anomaly_types": "INTRA_UNIVERSITY_CROSS_COLLEGE_DUAL_ENROLLMENT (Also admitted at VJTI)",
        })

    # Anomaly Type B: Cross-University Duplicate Admissions (COEP vs Mumbai Colleges)
    # 35 students from SPIT are ALSO submitted by COEP under Pune University!
    print("Injecting Cross-University duplicate admissions (COEP vs Mumbai University)...")
    coep_mumbai_conflicts = pool_spit.iloc[360:395].copy()
    for _, row in coep_mumbai_conflicts.iterrows():
        # Anomalous dual enrollment in COEP
        records_coep.append({
            "college_name": "College of Engineering Pune (COEP Tech)",
            "university_name": "Savitribai Phule Pune University",
            "academic_year": "2025-26",
            "apaar_id": row["apaar_id"],
            "aadhar_number": row["aadhar_number"],
            "full_name": row["full_name"],
            "date_of_birth": row["date_of_birth"],
            "gender": row["gender"],
            "course_name": "B.Tech - Artificial Intelligence & Data Science",
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 1,
            "anomaly_types": "CROSS_UNIVERSITY_DUAL_ENROLLMENT (Also enrolled in Mumbai University - SPIT)",
        })

    # Anomaly Type C: Swapped Aadhaar Identity / Stolen Identity
    print("Injecting Aadhaar identity mismatch anomalies...")
    swap_candidates = pool_other.iloc[0:90].copy()
    for i in range(30):
        # In SPIT
        r = swap_candidates.iloc[i]
        victim = pool_other.iloc[i + 50]
        records_spit.append({
            "college_name": "Sardar Patel Institute of Technology (SPIT)",
            "university_name": "University of Mumbai",
            "academic_year": "2025-26",
            "apaar_id": r["apaar_id"],
            "aadhar_number": victim["aadhar_number"],  # Swapped Aadhaar!
            "full_name": r["full_name"],
            "date_of_birth": r["date_of_birth"],
            "gender": r["gender"],
            "course_name": r["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 1,
            "anomaly_types": "AADHAAR_APAAR_LINK_MISMATCH",
        })

    for i in range(30, 60):
        # In VJTI
        r = swap_candidates.iloc[i]
        victim = pool_other.iloc[i + 20]
        records_vjti.append({
            "college_name": "Veermata Jijabai Technological Institute (VJTI)",
            "university_name": "University of Mumbai",
            "academic_year": "2025-26",
            "apaar_id": r["apaar_id"],
            "aadhar_number": victim["aadhar_number"],  # Swapped Aadhaar!
            "full_name": r["full_name"],
            "date_of_birth": r["date_of_birth"],
            "gender": r["gender"],
            "course_name": r["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 1,
            "anomaly_types": "AADHAAR_APAAR_LINK_MISMATCH",
        })

    for i in range(60, 90):
        # In COEP
        r = swap_candidates.iloc[i]
        victim = pool_other.iloc[i - 40]
        records_coep.append({
            "college_name": "College of Engineering Pune (COEP Tech)",
            "university_name": "Savitribai Phule Pune University",
            "academic_year": "2025-26",
            "apaar_id": r["apaar_id"],
            "aadhar_number": victim["aadhar_number"],  # Swapped Aadhaar!
            "full_name": r["full_name"],
            "date_of_birth": r["date_of_birth"],
            "gender": r["gender"],
            "course_name": r["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 1,
            "anomaly_types": "AADHAAR_APAAR_LINK_MISMATCH",
        })

    # Anomaly Type D: Malformed / Truncated APAAR IDs (e.g. 10 or 11 digits)
    print("Injecting malformed/incomplete APAAR IDs...")
    malformed_candidates = pool_other.iloc[90:165].copy()
    for i, (_, r) in enumerate(malformed_candidates.iterrows()):
        short_apaar = r["apaar_id"][:random.choice([10, 11])]  # Truncated
        target_list = records_spit if i < 25 else (records_vjti if i < 50 else records_coep)
        coll = (
            "Sardar Patel Institute of Technology (SPIT)"
            if i < 25
            else (
                "Veermata Jijabai Technological Institute (VJTI)"
                if i < 50
                else "College of Engineering Pune (COEP Tech)"
            )
        )
        uni = "University of Mumbai" if i < 50 else "Savitribai Phule Pune University"
        target_list.append({
            "college_name": coll,
            "university_name": uni,
            "academic_year": "2025-26",
            "apaar_id": short_apaar,
            "aadhar_number": r["aadhar_number"],
            "full_name": r["full_name"],
            "date_of_birth": r["date_of_birth"],
            "gender": r["gender"],
            "course_name": r["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 1,
            "anomaly_types": f"INCOMPLETE_APAAR_DIGITS_{len(short_apaar)}_CHARS",
        })

    # Anomaly Type E: Semester Leaps in 1st Year Admission
    print("Injecting semester leap anomalies...")
    sem_leap_candidates = pool_other.iloc[165:240].copy()
    for i, (_, r) in enumerate(sem_leap_candidates.iterrows()):
        leap_sem = random.choice([3, 4, 5, 6, 7])
        target_list = records_spit if i < 25 else (records_vjti if i < 50 else records_coep)
        coll = (
            "Sardar Patel Institute of Technology (SPIT)"
            if i < 25
            else (
                "Veermata Jijabai Technological Institute (VJTI)"
                if i < 50
                else "College of Engineering Pune (COEP Tech)"
            )
        )
        uni = "University of Mumbai" if i < 50 else "Savitribai Phule Pune University"
        target_list.append({
            "college_name": coll,
            "university_name": uni,
            "academic_year": "2025-26",
            "apaar_id": r["apaar_id"],
            "aadhar_number": r["aadhar_number"],
            "full_name": r["full_name"],
            "date_of_birth": r["date_of_birth"],
            "gender": r["gender"],
            "course_name": r["course_name"],
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": leap_sem,
            "is_anomaly": 1,
            "anomaly_types": f"SEMESTER_LEAP_ANOMALY_+{leap_sem-1}",
        })

    # Anomaly Type F: Invalid Prerequisite Degree (Claiming 10th standard for B.Tech)
    print("Injecting invalid degree progression anomalies...")
    degree_candidates = pool_other.iloc[240:315].copy()
    for i, (_, r) in enumerate(degree_candidates.iterrows()):
        target_list = records_spit if i < 25 else (records_vjti if i < 50 else records_coep)
        coll = (
            "Sardar Patel Institute of Technology (SPIT)"
            if i < 25
            else (
                "Veermata Jijabai Technological Institute (VJTI)"
                if i < 50
                else "College of Engineering Pune (COEP Tech)"
            )
        )
        uni = "University of Mumbai" if i < 50 else "Savitribai Phule Pune University"
        target_list.append({
            "college_name": coll,
            "university_name": uni,
            "academic_year": "2025-26",
            "apaar_id": r["apaar_id"],
            "aadhar_number": r["aadhar_number"],
            "full_name": r["full_name"],
            "date_of_birth": r["date_of_birth"],
            "gender": r["gender"],
            "course_name": r["course_name"],
            "last_successful_degree": "10th Standard / SSC",  # Invalid!
            "current_semester": 1,
            "is_anomaly": 1,
            "anomaly_types": "INVALID_DEGREE_PROGRESSION (Claiming 10th std without 12th/Diploma)",
        })

    # Anomaly Type G: Unregistered / Phantom Students (Not in Ground Truth)
    print("Injecting unregistered phantom students...")
    for i in range(60):
        target_list = records_spit if i < 20 else (records_vjti if i < 40 else records_coep)
        coll = (
            "Sardar Patel Institute of Technology (SPIT)"
            if i < 20
            else (
                "Veermata Jijabai Technological Institute (VJTI)"
                if i < 40
                else "College of Engineering Pune (COEP Tech)"
            )
        )
        uni = "University of Mumbai" if i < 40 else "Savitribai Phule Pune University"
        target_list.append({
            "college_name": coll,
            "university_name": uni,
            "academic_year": "2025-26",
            "apaar_id": f"9999{90000000 + i}",  # Phantom APAAR
            "aadhar_number": f"9999{80000000 + i}",  # Phantom Aadhaar
            "full_name": f"Phantom Student {i+1}",
            "date_of_birth": "2007-06-15",
            "gender": "Male" if i % 2 == 0 else "Female",
            "course_name": "B.Tech - Computer Engineering",
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": 1,
            "is_anomaly": 1,
            "anomaly_types": "RECORD_NOT_IN_GROUND_TRUTH",
        })

    # Shuffle datasets for realistic ordering
    random.shuffle(records_spit)
    random.shuffle(records_vjti)
    random.shuffle(records_coep)

    df_spit = pd.DataFrame(records_spit)
    df_vjti = pd.DataFrame(records_vjti)
    df_coep = pd.DataFrame(records_coep)

    df_spit.to_csv(SPIT_CSV, index=False)
    df_vjti.to_csv(VJTI_CSV, index=False)
    df_coep.to_csv(COEP_CSV, index=False)

    print("\n" + "=" * 70)
    print("College Submissions Generated:")
    print(f" 1. SPIT  : {len(df_spit)} rows ({df_spit['is_anomaly'].sum()} anomalies, {len(df_spit)-df_spit['is_anomaly'].sum()} clean)")
    print(f" 2. VJTI  : {len(df_vjti)} rows ({df_vjti['is_anomaly'].sum()} anomalies, {len(df_vjti)-df_vjti['is_anomaly'].sum()} clean)")
    print(f" 3. COEP  : {len(df_coep)} rows ({df_coep['is_anomaly'].sum()} anomalies, {len(df_coep)-df_coep['is_anomaly'].sum()} clean)")
    print("=" * 70)

    # Store into separate database (college_submissions.db)
    print(f"\nStoring into separate isolated database: {COLLEGE_DB_PATH} ...")
    conn_col = sqlite3.connect(COLLEGE_DB_PATH)
    cursor = conn_col.cursor()

    batches = [
        ("BATCH-SPIT-2025", "Sardar Patel Institute of Technology (SPIT)", "University of Mumbai", "2025-26", df_spit),
        ("BATCH-VJTI-2025", "Veermata Jijabai Technological Institute (VJTI)", "University of Mumbai", "2025-26", df_vjti),
        ("BATCH-COEP-2025", "College of Engineering Pune (COEP Tech)", "Savitribai Phule Pune University", "2025-26", df_coep),
    ]

    for b_id, c_name, u_name, ay, b_df in batches:
        cursor.execute(
            """
            INSERT INTO submission_batches_meta (batch_id, college_name, university_name, academic_year, total_records)
            VALUES (?, ?, ?, ?, ?)
            """,
            (b_id, c_name, u_name, ay, len(b_df)),
        )

        rows_data = [
            (
                b_id,
                r["college_name"],
                r["university_name"],
                r["academic_year"],
                r["apaar_id"],
                r["aadhar_number"],
                r["full_name"],
                r["date_of_birth"],
                r["gender"],
                r["course_name"],
                r["last_successful_degree"],
                int(r["current_semester"]),
                int(r["is_anomaly"]),
                r["anomaly_types"],
            )
            for _, r in b_df.iterrows()
        ]

        cursor.executemany(
            """
            INSERT INTO college_submitted_students (
                batch_id, college_name, university_name, academic_year,
                apaar_id, aadhar_number, full_name, date_of_birth, gender,
                course_name, last_successful_degree, current_semester,
                is_anomaly, anomaly_types
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_data,
        )

    conn_col.commit()
    cursor.execute("SELECT COUNT(*) FROM college_submitted_students;")
    total_in_db = cursor.fetchone()[0]
    conn_col.close()

    print(f"Successfully recorded {total_in_db} submissions in college_submissions.db.")
    print("The whole truth in ground_truth.db remains completely untouched and pristine!")


if __name__ == "__main__":
    generate_college_submissions()
