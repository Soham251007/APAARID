"""Populate AICTE Approved Institutions Directory in ground_truth.db."""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "ground_truth.db")

INSTITUTIONS_DATA = [
    ("K J Somaiya Institute of Technology", "MH-MUM-1042", "University of Mumbai", "Mumbai, Maharashtra", 660, "Autonomous / Private"),
    ("Veermata Jijabai Technological Institute (VJTI)", "MH-MUM-0001", "University of Mumbai", "Mumbai, Maharashtra", 780, "Govt. Aided Autonomous"),
    ("Sardar Patel Institute of Technology (SPIT)", "MH-MUM-0002", "University of Mumbai", "Mumbai, Maharashtra", 600, "Autonomous / Private"),
    ("Dwarkadas J. Sanghvi College of Engineering", "MH-MUM-0045", "University of Mumbai", "Mumbai, Maharashtra", 840, "Autonomous / Private"),
    ("Thadomal Shahani Engineering College", "MH-MUM-0098", "University of Mumbai", "Mumbai, Maharashtra", 720, "Private Aided"),
    ("Fr. Conceicao Rodrigues College of Engineering", "MH-MUM-0112", "University of Mumbai", "Mumbai, Maharashtra", 420, "Private"),
    ("Vidyalankar Institute of Technology", "MH-MUM-0210", "University of Mumbai", "Mumbai, Maharashtra", 720, "Private"),
    ("Don Bosco Institute of Technology", "MH-MUM-0315", "University of Mumbai", "Mumbai, Maharashtra", 480, "Private"),
    ("College of Engineering Pune (COEP Tech)", "MH-PUN-0001", "Savitribai Phule Pune University", "Pune, Maharashtra", 950, "Unitary Public University"),
    ("Pune Institute of Computer Technology (PICT)", "MH-PUN-0012", "Savitribai Phule Pune University", "Pune, Maharashtra", 720, "Private"),
    ("Vishwakarma Institute of Technology (VIT Pune)", "MH-PUN-0024", "Savitribai Phule Pune University", "Pune, Maharashtra", 1100, "Autonomous / Private"),
    ("Maharashtra Institute of Technology (MIT WPU)", "MH-PUN-0045", "Savitribai Phule Pune University", "Pune, Maharashtra", 1200, "State Private University"),
    ("Cummins College of Engineering for Women", "MH-PUN-0060", "Savitribai Phule Pune University", "Pune, Maharashtra", 600, "Autonomous / Private"),
    ("R.V. College of Engineering", "KA-VTU-0001", "Visvesvaraya Technological University", "Bengaluru, Karnataka", 1080, "Autonomous / Private"),
    ("BMS College of Engineering", "KA-VTU-0002", "Visvesvaraya Technological University", "Bengaluru, Karnataka", 1140, "Autonomous / Private"),
    ("M.S. Ramaiah Institute of Technology", "KA-VTU-0003", "Visvesvaraya Technological University", "Bengaluru, Karnataka", 1100, "Autonomous / Private"),
    ("College of Engineering Guindy", "TN-AU-0001", "Anna University", "Chennai, Tamil Nadu", 1250, "University Department"),
    ("Madras Institute of Technology", "TN-AU-0002", "Anna University", "Chennai, Tamil Nadu", 900, "University Department"),
    ("PSG College of Technology", "TN-AU-0003", "Anna University", "Coimbatore, Tamil Nadu", 1020, "Govt. Aided Autonomous"),
    ("Institute of Engineering and Technology Lucknow", "UP-AKTU-0001", "Dr. A.P.J. Abdul Kalam Technical University", "Lucknow, Uttar Pradesh", 780, "Autonomous Govt. Institute"),
    ("JSS Academy of Technical Education Noida", "UP-AKTU-0015", "Dr. A.P.J. Abdul Kalam Technical University", "Noida, Uttar Pradesh", 840, "Private"),
    ("Ajay Kumar Garg Engineering College", "UP-AKTU-0028", "Dr. A.P.J. Abdul Kalam Technical University", "Ghaziabad, Uttar Pradesh", 960, "Private"),
    ("Delhi Technological University (DTU)", "DL-DTU-0001", "Delhi Technological University", "New Delhi, Delhi", 2100, "State Public University"),
    ("Netaji Subhas University of Technology (NSUT)", "DL-NSUT-0001", "NSUT", "New Delhi, Delhi", 1680, "State Public University"),
    ("L.D. College of Engineering", "GJ-GTU-0001", "Gujarat Technological University", "Ahmedabad, Gujarat", 1140, "Government"),
]


def setup_institutions():
    print(f"Setting up AICTE Approved Institutions directory in: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS aicte_approved_institutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_name TEXT UNIQUE NOT NULL,
            institution_code TEXT UNIQUE NOT NULL,
            university_name TEXT NOT NULL,
            city_state TEXT NOT NULL,
            approved_intake INTEGER NOT NULL,
            category TEXT NOT NULL,
            aicte_approval_status TEXT DEFAULT 'Approved - Active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Insert or ignore institutions
    cursor.executemany(
        """
        INSERT OR IGNORE INTO aicte_approved_institutions (
            institution_name, institution_code, university_name, city_state, approved_intake, category
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        INSTITUTIONS_DATA,
    )

    # Also add enrollment_status to ground_truth_students if not present
    try:
        cursor.execute("ALTER TABLE ground_truth_students ADD COLUMN enrollment_status TEXT DEFAULT 'CONFIRMED_ENROLLED';")
    except sqlite3.OperationalError:
        pass  # already exists

    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM aicte_approved_institutions;")
    count = cursor.fetchone()[0]
    conn.close()
    print(f"Successfully configured {count} AICTE Approved Institutions profiles.")


if __name__ == "__main__":
    setup_institutions()
