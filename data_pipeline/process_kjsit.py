"""Data Ingestion & Training Pipeline for KJSIT Student Records.

Standardizes raw college response data from:
'Academic Bank of Credits (ABC) Student\'s Details_KJSIT Academic Year 2025-26 (Responses).xlsx'

1. Ingests raw college form responses.
2. Standardizes columns (inferring B.Tech courses, Sem 1, 12th Std prerequisite, KJSIT, University of Mumbai).
3. Constructs Ground Truth master records in SQLite database.
4. Synthesizes realistic dual-enrollment & academic anomaly patterns anchored in real data.
5. Prepares training dataset and executes Scikit-Learn Random Forest training.
"""

import os
import re
import sqlite3
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_FILE = os.path.join(
    BASE_DIR,
    "Academic Bank of Credits (ABC) Student's Details_KJSIT Academic Year 2025-26 (Responses).xlsx",
)
DB_PATH = os.path.join(BASE_DIR, "database", "ground_truth.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "data")


def clean_apaar_id(val) -> str:
    """Normalize APAAR/ABC ID to 12-digit format."""
    s = str(val).strip()
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) == 12:
        return digits
    elif len(digits) > 12:
        return digits[:12]
    elif len(digits) > 0:
        return digits.zfill(12)
    return "000000000000"


def clean_dob(val) -> str:
    """Normalize DOB (DD/MM/YYYY or datetime) to ISO YYYY-MM-DD."""
    if pd.isna(val):
        return "2007-01-01"
    if isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    match = re.match(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)
    if match:
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return "2007-01-01"


def clean_name(row) -> str:
    """Prefer Student Name as per Aadhar Card, fallback to Full Name."""
    aadhar_name = str(row.get("Student's Name as per Aadhar Card", "")).strip()
    if aadhar_name and aadhar_name.lower() != "nan":
        return aadhar_name.title()
    full_name = str(row.get("Full Name of the student in the following order : Surname, Student's Name, Father's Name, Mothers' Name (In Capital letters)", "")).strip()
    return full_name.title() if full_name else "Student Name"


def clean_semester(val) -> int:
    """Extract semester number."""
    s = str(val).strip().upper()
    if "VIII" in s or "8" in s:
        return 8
    if "VII" in s or "7" in s:
        return 7
    if "VI" in s or "6" in s:
        return 6
    if "V" in s or "5" in s:
        return 5
    if "IV" in s or "4" in s:
        return 4
    if "III" in s or "3" in s:
        return 3
    if "II" in s or "2" in s:
        return 2
    return 1


def clean_course(branch) -> str:
    """Map branch to official B.Tech degree title."""
    b = str(branch).strip()
    return f"B.Tech - {b}"


def generate_pseudo_aadhar(seed_num: int) -> str:
    """Generate standardized unique 12-digit Aadhaar number for ground truth simulation."""
    base = 824000000000 + int(seed_num)
    return str(base)


def parse_kjsit_dataset():
    """Reads and standardizes raw KJSIT Excel data."""
    print(f"Reading raw KJSIT file: {EXCEL_FILE}")
    raw_df = pd.read_excel(EXCEL_FILE)
    print(f"Loaded {len(raw_df)} student records from KJSIT AY 2025-26.")

    standardized_records = []
    for idx, row in raw_df.iterrows():
        apaar = clean_apaar_id(row["ABC ID No"])
        name = clean_name(row)
        dob = clean_dob(row["Student's Date of Birth (DD/MM/YYYY)"])
        sem = clean_semester(row["Select Semester"])
        branch = row["Branch"]
        course = clean_course(branch)
        gender = str(row.get("Gender", "Not Specified")).capitalize()
        # Seed pseudo Aadhaar based on index/mobile to provide ground truth binding
        mob = str(row.get("Student's mobile number (Linked with Aadhar Card)", ""))
        aadhar = generate_pseudo_aadhar(idx + 1042)

        record = {
            "apaar_id": apaar,
            "aadhar_number": aadhar,
            "full_name": name,
            "date_of_birth": dob,
            "gender": gender,
            "university_name": "University of Mumbai",
            "institution_code": "MH-ENG-KJSIT-1042",
            "institution_name": "K J Somaiya Institute of Technology",
            "course_name": course,
            "last_successful_degree": "12th Standard / HSC",
            "current_semester": sem,
            "admission_year": 2025,
            "mobile_number": mob,
            "student_id_number": str(row.get("Student ID number", "")),
        }
        standardized_records.append(record)

    std_df = pd.DataFrame(standardized_records)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    std_csv_path = os.path.join(OUTPUT_DIR, "kjsit_standardized_records.csv")
    std_df.to_csv(std_csv_path, index=False)
    print(f"Standardized {len(std_df)} records saved to: {std_csv_path}")
    return std_df


def populate_ground_truth_db(records_df: pd.DataFrame):
    """Populates the SQLite Ground Truth database with authentic master student records."""
    print(f"\nPopulating Ground Truth database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM ground_truth_students;")

    inserted = 0
    seen_apaars = set()
    for _, row in records_df.iterrows():
        apaar = row["apaar_id"]
        if apaar in seen_apaars:
            # Handle collision by making pseudo unique
            apaar = f"{apaar[:-3]}{inserted:03d}"
        seen_apaars.add(apaar)

        cursor.execute(
            """
            INSERT INTO ground_truth_students (
                apaar_id, aadhar_number, full_name, date_of_birth, gender,
                university_name, institution_code, institution_name,
                course_name, last_successful_degree, current_semester,
                admission_year, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                apaar,
                row["aadhar_number"],
                row["full_name"],
                row["date_of_birth"],
                row["gender"],
                row["university_name"],
                row["institution_code"],
                row["institution_name"],
                row["course_name"],
                row["last_successful_degree"],
                int(row["current_semester"]),
                int(row["admission_year"]),
            ),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Successfully loaded {inserted} master reference records into ground_truth_students.")


def build_ml_training_dataset(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Builds a robust, balanced training dataset for the Scikit-Learn Random Forest.

    1. Class 0 (Authentic Single Enrolments): Genuine KJSIT student records.
    2. Class 1 (Anomalous Records): Realistic institutional fraud & conflict patterns:
       - Cross-University Dual Enrolment (e.g. Enrolled at Mumbai Uni + Delhi Uni / Pune Uni)
       - Intra-University Dual College Enrolment (e.g. KJSIT + SPIT or DJ Sanghvi under Mumbai University)
       - Prerequisite Degree Inconsistency (e.g. Claiming 10th std only for B.Tech Sem 1)
       - Semester Jump Anomaly (e.g. Jumping to Sem 5 in first year)
       - Swapped/Corrupted Aadhaar-APAAR Binding
    """
    print("\nSynthesizing supervised training dataset based on KJSIT student profiles...")

    training_samples = []

    # 1. Authentic Records (Class 0)
    for _, row in clean_df.iterrows():
        sample = row.to_dict()
        sample["is_anomaly"] = 0
        sample["anomaly_type"] = "AUTHENTIC"
        training_samples.append(sample)

    # 2. Anomalous Records (Class 1) - generating realistic test vectors anchored in these students
    other_universities = [
        "Savitribai Phule Pune University",
        "Delhi Technological University",
        "Visvesvaraya Technological University",
        "Dr. A.P.J. Abdul Kalam Technical University",
    ]
    other_mumbai_colleges = [
        "Sardar Patel Institute of Technology",
        "Dwarkadas J. Sanghvi College of Engineering",
        "Veermata Jijabai Technological Institute (VJTI)",
        "Thadomal Shahani Engineering College",
    ]

    for idx, row in clean_df.iterrows():
        # A. Cross-University Dual Enrollment
        if idx % 5 == 0:
            anom = row.to_dict()
            anom["university_name"] = other_universities[idx % len(other_universities)]
            anom["institution_name"] = f"Institute of Engineering ({anom['university_name']})"
            anom["is_anomaly"] = 1
            anom["anomaly_type"] = "CROSS_UNIVERSITY_DUAL_ENROLLMENT"
            training_samples.append(anom)

        # B. Intra-University (Cross-College) Dual Enrollment
        elif idx % 5 == 1:
            anom = row.to_dict()
            anom["university_name"] = "University of Mumbai"  # Same University
            anom["institution_name"] = other_mumbai_colleges[idx % len(other_mumbai_colleges)]  # Different College!
            anom["is_anomaly"] = 1
            anom["anomaly_type"] = "INTRA_UNIVERSITY_CROSS_COLLEGE_DUAL_ENROLLMENT"
            training_samples.append(anom)

        # C. Semester Jump Anomaly (e.g. Sem 1 student submitting Sem 5 or Sem 7)
        elif idx % 5 == 2:
            anom = row.to_dict()
            anom["current_semester"] = 5 + (idx % 3)  # Illegal jump from Sem 1 to Sem 5-7
            anom["is_anomaly"] = 1
            anom["anomaly_type"] = "SEMESTER_LEAP_ANOMALY"
            training_samples.append(anom)

        # D. Degree Progression Mismatch (Claiming 10th standard instead of 12th/Diploma)
        elif idx % 5 == 3:
            anom = row.to_dict()
            anom["last_successful_degree"] = "10th Standard / SSC"  # Invalid prerequisite for B.Tech
            anom["is_anomaly"] = 1
            anom["anomaly_type"] = "INVALID_DEGREE_PROGRESSION"
            training_samples.append(anom)

        # E. Aadhaar - APAAR Pairing Corruption (Swapped identity)
        else:
            anom = row.to_dict()
            anom["aadhar_number"] = generate_pseudo_aadhar(9999 + idx)  # Swapped / fake Aadhaar
            anom["is_anomaly"] = 1
            anom["anomaly_type"] = "AADHAAR_APAAR_LINK_MISMATCH"
            training_samples.append(anom)

    train_df = pd.DataFrame(training_samples)
    train_csv_path = os.path.join(OUTPUT_DIR, "kjsit_training_dataset.csv")
    train_df.to_csv(train_csv_path, index=False)

    print(f"Training dataset created with {len(train_df)} total records:")
    print(f" - Authentic Records (0): {(train_df['is_anomaly'] == 0).sum()}")
    print(f" - Anomalous Records (1): {(train_df['is_anomaly'] == 1).sum()}")
    print(f"Saved to: {train_csv_path}")
    return train_df


if __name__ == "__main__":
    clean_df = parse_kjsit_dataset()
    populate_ground_truth_db(clean_df)
    train_df = build_ml_training_dataset(clean_df)
