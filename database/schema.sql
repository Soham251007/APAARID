-- APAAR & Academic Ground Truth Master Database Schema
-- Designed for anomaly detection and comparison with uploaded CSV data via Random Forest

PRAGMA foreign_keys = ON;

-- 1. Ground Truth Master Registry Table (The "Whole Truth" Reference)
CREATE TABLE IF NOT EXISTS ground_truth_students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apaar_id TEXT NOT NULL UNIQUE COLLATE NOCASE,          -- Official 12-digit or standardized APAAR identifier
    aadhar_number TEXT NOT NULL UNIQUE,                    -- 12-digit Aadhaar number
    full_name TEXT,                                        -- Official student legal name
    date_of_birth TEXT NOT NULL,                           -- Date of birth in ISO format (YYYY-MM-DD)
    gender TEXT,                                           -- Gender (Male/Female/Other)
    university_name TEXT,                                  -- Affiliating University (e.g., University of Mumbai, VTU, Anna University)
    institution_code TEXT,                                 -- Approved college/institution code
    institution_name TEXT,                                 -- Approved college/institution name
    course_name TEXT,                                      -- Course / Program of study
    last_successful_degree TEXT NOT NULL,                  -- Highest verified prior degree (e.g., 10th, 12th, Diploma, B.Tech)
    current_semester INTEGER NOT NULL CHECK (current_semester >= 1 AND current_semester <= 12), -- Current enrolled semester
    admission_year INTEGER,                                -- Year of admission into current program
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Fast lookup indexes for ML feature generation and record matching
CREATE INDEX IF NOT EXISTS idx_gt_apaar_id ON ground_truth_students (apaar_id);
CREATE INDEX IF NOT EXISTS idx_gt_aadhar_number ON ground_truth_students (aadhar_number);
CREATE INDEX IF NOT EXISTS idx_gt_dob ON ground_truth_students (date_of_birth);
CREATE INDEX IF NOT EXISTS idx_gt_university ON ground_truth_students (university_name);
CREATE INDEX IF NOT EXISTS idx_gt_institution ON ground_truth_students (institution_name);
CREATE INDEX IF NOT EXISTS idx_gt_semester ON ground_truth_students (current_semester);
CREATE INDEX IF NOT EXISTS idx_gt_degree ON ground_truth_students (last_successful_degree);

-- 2. Uploaded CSV Ingestion Batches Table (Tracks CSV uploads)
CREATE TABLE IF NOT EXISTS upload_batches (
    batch_id TEXT PRIMARY KEY,                             -- Unique batch UUID / reference
    file_name TEXT NOT NULL,                               -- Original CSV file name
    uploaded_by TEXT DEFAULT 'admin',                      -- Uploading user / role
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_records INTEGER DEFAULT 0,
    anomalies_flagged INTEGER DEFAULT 0,
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'ANALYZED', 'FAILED'))
);

-- 3. Staging Table for Uploaded Student Records (Awaiting comparison against ground truth)
CREATE TABLE IF NOT EXISTS uploaded_student_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    apaar_id TEXT,
    aadhar_number TEXT,
    full_name TEXT,
    date_of_birth TEXT,
    university_name TEXT,
    institution_name TEXT,
    course_name TEXT,
    last_successful_degree TEXT,
    current_semester INTEGER,
    raw_row_data TEXT,                                     -- Original JSON/string row representation for auditing
    FOREIGN KEY (batch_id) REFERENCES upload_batches(batch_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_uploaded_batch ON uploaded_student_records (batch_id);
CREATE INDEX IF NOT EXISTS idx_uploaded_apaar ON uploaded_student_records (apaar_id);
CREATE INDEX IF NOT EXISTS idx_uploaded_aadhar ON uploaded_student_records (aadhar_number);
CREATE INDEX IF NOT EXISTS idx_uploaded_uni ON uploaded_student_records (university_name);
CREATE INDEX IF NOT EXISTS idx_uploaded_inst ON uploaded_student_records (institution_name);

-- 4. Anomaly Detection Results Table (Produced by Random Forest & Rule Engines)
CREATE TABLE IF NOT EXISTS anomaly_detection_results (
    anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    record_id INTEGER NOT NULL,                            -- Refers to uploaded_student_records
    ground_truth_id INTEGER,                               -- Refers to ground_truth_students if matched
    match_status TEXT NOT NULL CHECK (match_status IN ('EXACT_MATCH', 'PARTIAL_MATCH', 'UNMATCHED_NEW', 'FRAUDULENT')),
    anomaly_score REAL DEFAULT 0.0,                        -- Probability score from Random Forest (0.0 to 1.0)
    is_anomaly INTEGER NOT NULL DEFAULT 0 CHECK (is_anomaly IN (0, 1)),
    detected_anomalies TEXT,                               -- JSON array or summary: e.g. ["DUPLICATE_ENROLLMENT_SAME_UNIVERSITY_DIFFERENT_COLLEGE"]
    rf_feature_vector TEXT,                                -- JSON serialized feature vector passed to Random Forest model
    reviewer_verdict TEXT DEFAULT 'UNREVIEWED' CHECK (reviewer_verdict IN ('UNREVIEWED', 'CONFIRMED_ANOMALY', 'FALSE_POSITIVE', 'RESOLVED')),
    reviewer_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES upload_batches(batch_id) ON DELETE CASCADE,
    FOREIGN KEY (record_id) REFERENCES uploaded_student_records(record_id) ON DELETE CASCADE,
    FOREIGN KEY (ground_truth_id) REFERENCES ground_truth_students(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_anomalies_batch ON anomaly_detection_results (batch_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_is_anomaly ON anomaly_detection_results (is_anomaly);
CREATE INDEX IF NOT EXISTS idx_anomalies_score ON anomaly_detection_results (anomaly_score);
