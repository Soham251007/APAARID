"""Ground Truth Master Dataset Generator (15,000+ Students).

Generates the authoritative national APAAR registry ("Whole Truth")
and loads it into the primary SQLite database (database/ground_truth.db).

Attributes generated:
- Standard 12-digit unique APAAR ID (Collate nocase, indexed)
- Standard 12-digit unique Aadhaar number (indexed)
- Full legal student name
- Date of birth (ISO YYYY-MM-DD, age 17-23)
- Gender
- University name & Approved Institution
- Course name (B.Tech programs)
- Last successful degree (12th Standard / HSC, Diploma)
- Current semester (1 to 8)
- Admission year & active enrollment status
"""

import datetime
import os
import random
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "ground_truth.db")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "ground_truth_master_15000.csv")

TOTAL_STUDENTS = 15000

# High-fidelity Indian Demographics
FIRST_NAMES_MALE = [
    "Aarav", "Aaditya", "Aayush", "Abhishek", "Aditya", "Akash", "Aman", "Amit",
    "Aniket", "Aniruddh", "Ankit", "Ansh", "Archit", "Arjun", "Armaan", "Aryan",
    "Atharva", "Ayush", "Bhavya", "Chaitanya", "Chinmay", "Darshan", "Dev", "Devansh",
    "Dhruv", "Gaurav", "Harsh", "Harshal", "Hrishikesh", "Ishan", "Jay", "Jayesh",
    "Kabir", "Kaustubh", "Kunal", "Manan", "Manav", "Mayur", "Meet", "Mihir",
    "Nikhil", "Om", "Omkar", "Parth", "Pranav", "Prasad", "Prateek", "Pratham",
    "Rahul", "Rishi", "Rohan", "Rohit", "Sahil", "Samarth", "Sameer", "Sanket",
    "Sarvesh", "Shaunak", "Shivam", "Shlok", "Shreyas", "Siddhant", "Siddhesh",
    "Soham", "Tanmay", "Tejas", "Utkarsh", "Varun", "Vedant", "Vignesh", "Viraj",
    "Vivek", "Yash", "Yuvraj"
]

FIRST_NAMES_FEMALE = [
    "Aadhya", "Aahana", "Aastha", "Akanksha", "Ananya", "Anika", "Anisha", "Ankita",
    "Anushka", "Avani", "Bhakti", "Bhavika", "Chaitali", "Devika", "Disha", "Diya",
    "Divya", "Gauri", "Gayatri", "Isha", "Ishani", "Ishita", "Janhavi", "Jhanvi",
    "Kalyani", "Kashish", "Khushi", "Kiran", "Komal", "Mansi", "Mayuri", "Meera",
    "Mrunal", "Neha", "Nidhi", "Nikita", "Nisha", "Payal", "Pooja", "Prachi",
    "Pranjal", "Prerna", "Priya", "Radhika", "Rhea", "Riddhi", "Riya", "Ruchira",
    "Sakshi", "Samiksha", "Sanika", "Sanjana", "Sara", "Sayali", "Sejal", "Shreya",
    "Shruti", "Siya", "Sneha", "Tanvi", "Tara", "Trisha", "Vaishnavi", "Vidhi"
]

SURNAMES = [
    "Agarwal", "Bapat", "Bhandari", "Bhatia", "Bhosale", "Chavan", "Choudhary",
    "Dalvi", "Damani", "Desai", "Deshmukh", "Gaikwad", "Gandhi", "Ghosh",
    "Gokhale", "Gupta", "Jadhav", "Jain", "Jha", "Joshi", "Kale", "Kamble",
    "Kapoor", "Kapadia", "Karkhanis", "Khan", "Khanna", "Kharat", "Khatri",
    "Korde", "Kothari", "Kulkarni", "Kumar", "Mahajan", "Malhotra", "Mane",
    "Mehta", "Mishra", "Modi", "More", "Mulane", "Mundhada", "Naik", "Nair",
    "Panchal", "Pandey", "Parekh", "Patel", "Patil", "Pawar", "Pillai", "Pradhan",
    "Purohit", "Rane", "Rao", "Raut", "Reddy", "Roy", "Salvi", "Sanghavi",
    "Saraf", "Sawant", "Shah", "Sharma", "Shetty", "Shinde", "Shukla", "Singh",
    "Solanki", "Surve", "Tambe", "Thakur", "Tiwari", "Upadhyay", "Varma", "Verma",
    "Vora", "Wagh", "Yadav"
]

UNIVERSITIES_AND_COLLEGES = [
    {
        "university": "University of Mumbai",
        "colleges": [
            ("K J Somaiya Institute of Technology", "MH-MUM-1042"),
            ("Veermata Jijabai Technological Institute (VJTI)", "MH-MUM-0001"),
            ("Sardar Patel Institute of Technology (SPIT)", "MH-MUM-0002"),
            ("Dwarkadas J. Sanghvi College of Engineering", "MH-MUM-0045"),
            ("Thadomal Shahani Engineering College", "MH-MUM-0098"),
            ("Fr. Conceicao Rodrigues College of Engineering", "MH-MUM-0112"),
            ("Vidyalankar Institute of Technology", "MH-MUM-0210"),
            ("Don Bosco Institute of Technology", "MH-MUM-0315"),
        ],
    },
    {
        "university": "Savitribai Phule Pune University",
        "colleges": [
            ("College of Engineering Pune (COEP Tech)", "MH-PUN-0001"),
            ("Pune Institute of Computer Technology (PICT)", "MH-PUN-0012"),
            ("Vishwakarma Institute of Technology (VIT Pune)", "MH-PUN-0024"),
            ("Maharashtra Institute of Technology (MIT WPU)", "MH-PUN-0045"),
            ("Cummins College of Engineering for Women", "MH-PUN-0060"),
        ],
    },
    {
        "university": "Visvesvaraya Technological University",
        "colleges": [
            ("R.V. College of Engineering", "KA-VTU-0001"),
            ("BMS College of Engineering", "KA-VTU-0002"),
            ("M.S. Ramaiah Institute of Technology", "KA-VTU-0003"),
        ],
    },
    {
        "university": "Dr. A.P.J. Abdul Kalam Technical University",
        "colleges": [
            ("Institute of Engineering and Technology Lucknow", "UP-AKTU-0001"),
            ("JSS Academy of Technical Education Noida", "UP-AKTU-0015"),
            ("Ajay Kumar Garg Engineering College", "UP-AKTU-0028"),
        ],
    },
    {
        "university": "Anna University",
        "colleges": [
            ("College of Engineering Guindy", "TN-AU-0001"),
            ("Madras Institute of Technology", "TN-AU-0002"),
            ("PSG College of Technology", "TN-AU-0003"),
        ],
    },
]

COURSES = [
    "B.Tech - Computer Engineering",
    "B.Tech - Artificial Intelligence & Data Science",
    "B.Tech - Information Technology",
    "B.Tech - Electronics & Telecommunication Engineering",
    "B.Tech - Mechanical Engineering",
    "B.Tech - Electrical Engineering",
    "B.Tech - Civil Engineering",
]


def generate_unique_apaar_numbers(count: int) -> list:
    """Generate deterministic unique 12-digit APAAR numbers."""
    # Standard format: 12 numeric digits (e.g. 186068428480)
    seen = set()
    numbers = []
    base = 100000000000
    for i in range(count):
        # Deterministic unique increment
        num_str = str(base + (i * 58319 + 71) % 899999999999)
        num_str = num_str.zfill(12)
        while num_str in seen:
            base += 1
            num_str = str(base).zfill(12)
        seen.add(num_str)
        numbers.append(num_str)
    return numbers


def generate_unique_aadhar_numbers(count: int) -> list:
    """Generate deterministic unique 12-digit Aadhaar numbers."""
    base_val = 200000000000
    return [str(base_val + i * 17 + 101) for i in range(count)]


def generate_ground_truth():
    print(f"Generating authoritative Ground Truth master registry of {TOTAL_STUDENTS} students...")
    random.seed(42)

    apaar_list = generate_unique_apaar_numbers(TOTAL_STUDENTS)
    aadhar_list = generate_unique_aadhar_numbers(TOTAL_STUDENTS)

    students = []
    start_dob = datetime.date(2003, 1, 1)
    end_dob = datetime.date(2007, 12, 31)
    dob_range_days = (end_dob - start_dob).days

    # Flatten colleges for realistic distribution
    weighted_colleges = []
    for uni_obj in UNIVERSITIES_AND_COLLEGES:
        uni_name = uni_obj["university"]
        for col_name, col_code in uni_obj["colleges"]:
            weighted_colleges.append((uni_name, col_name, col_code))

    for idx in range(TOTAL_STUDENTS):
        is_female = random.random() < 0.35
        gender = "Female" if is_female else "Male"
        first_name = random.choice(FIRST_NAMES_FEMALE if is_female else FIRST_NAMES_MALE)
        middle_name = random.choice(FIRST_NAMES_MALE)
        surname = random.choice(SURNAMES)
        full_name = f"{first_name} {middle_name} {surname}"

        dob_date = start_dob + datetime.timedelta(days=random.randint(0, dob_range_days))
        dob_str = dob_date.strftime("%Y-%m-%d")

        uni_name, col_name, col_code = random.choice(weighted_colleges)
        course = random.choice(COURSES)

        # Semester distribution: Mostly Sem 1-4 for active undergraduate monitoring
        # (Sem 1: 35%, Sem 2: 15%, Sem 3: 20%, Sem 4: 10%, Sem 5: 10%, Sem 6: 5%, Sem 7: 3%, Sem 8: 2%)
        sem_weights = [0.35, 0.15, 0.20, 0.10, 0.10, 0.05, 0.03, 0.02]
        sem = random.choices([1, 2, 3, 4, 5, 6, 7, 8], weights=sem_weights, k=1)[0]

        # Prerequisite degree based on semester:
        # Sem 1-2: 12th Standard / HSC (or Diploma for direct 2nd yr lateral entry)
        if sem <= 2:
            last_degree = "12th Standard / HSC" if random.random() < 0.85 else "Diploma in Engineering"
        elif sem in [3, 4]:
            last_degree = "Diploma in Engineering" if random.random() < 0.40 else "12th Standard / HSC"
        else:
            last_degree = "12th Standard / HSC"

        admission_year = 2026 - ((sem + 1) // 2)

        students.append({
            "id": idx + 1,
            "apaar_id": apaar_list[idx],
            "aadhar_number": aadhar_list[idx],
            "full_name": full_name,
            "date_of_birth": dob_str,
            "gender": gender,
            "university_name": uni_name,
            "institution_code": col_code,
            "institution_name": col_name,
            "course_name": course,
            "last_successful_degree": last_degree,
            "current_semester": sem,
            "admission_year": admission_year,
            "is_active": 1,
        })

    df = pd.DataFrame(students)
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Exported Ground Truth master CSV ({len(df)} rows) to: {OUTPUT_CSV}")

    # Load into SQLite ground_truth.db
    print(f"Populating SQLite database: {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM ground_truth_students;")
    
    # Bulk insert
    records_to_insert = [
        (
            s["apaar_id"],
            s["aadhar_number"],
            s["full_name"],
            s["date_of_birth"],
            s["gender"],
            s["university_name"],
            s["institution_code"],
            s["institution_name"],
            s["course_name"],
            s["last_successful_degree"],
            s["current_semester"],
            s["admission_year"],
            s["is_active"],
        )
        for s in students
    ]

    cursor.executemany(
        """
        INSERT INTO ground_truth_students (
            apaar_id, aadhar_number, full_name, date_of_birth, gender,
            university_name, institution_code, institution_name, course_name,
            last_successful_degree, current_semester, admission_year, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records_to_insert,
    )

    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM ground_truth_students;")
    count = cursor.fetchone()[0]
    conn.close()

    print(f"Successfully loaded {count} student records into ground_truth.db (whole truth).")
    return df


if __name__ == "__main__":
    generate_ground_truth()
