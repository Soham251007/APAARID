# APAAR-Based Student Data Management and Verification System

An AICTE-compliant academic record integrity portal powered by a Scikit-Learn Random Forest anomaly detection model and persistent SQLite Ground Truth databases.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────────┐
                      │    Modern Vanilla Web UI (HTML5/CSS3)    │
                      │  Institute · University · AICTE Central  │
                      └────────────────────┬─────────────────────┘
                                           │ REST API (JSON)
                                           ▼
                      ┌──────────────────────────────────────────┐
                      │          Flask Backend Server            │
                      │      (Multi-Tier Query & Scoping)        │
                      └─────────────┬──────────────┬─────────────┘
                                    │              │
                   Feature Vector   ▼              ▼  Persistent Storage
        ┌───────────────────────────────┐     ┌────────────────────────────┐
        │  Random Forest Anomaly Engine │     │     SQLite Databases       │
        │  - Aadhaar / ID mismatch      │     │  - ground_truth.db         │
        │  - Semester advancement leaps │     │    (15k master identities) │
        │  - Dual-enrollment collisions │     │  - college_submissions.db  │
        │  - Prerequisite degree gaps   │     │    (1,570 college records) │
        └───────────────────────────────┘     └────────────────────────────┘
```

---

## Key Features

1. **Multi-Tier Administrative Roles:**
   - **Institute Administrator:** Strictly scoped to their selected institution (e.g., K J Somaiya Institute of Technology with 688 enrolled students). Shows only students in that specific college, with dynamic sidebar record count badges.
   - **University Administrator:** Aggregates and monitors all affiliated engineering colleges under that university (e.g., University of Mumbai with 5,450 students across 8 affiliated colleges).
   - **AICTE Central Administrator:** National overview spanning all approved technical universities and institutions.

2. **Machine Learning Anomaly Detection:**
   - Pre-trained Scikit-Learn **Random Forest Classifier** (`ml_model/saved_models/rf_anomaly_model.joblib`).
   - Automatically cross-checks uploaded college admission CSVs/Excels against the Ground Truth master registry.
   - Detects dual-enrollment collisions (same candidate claimed simultaneously by two institutes), semester leaps, qualification prerequisite anomalies, and Aadhaar demographic discrepancies.

3. **Persistent SQLite Master Registries:**
   - `database/ground_truth.db`: Authoritative master database containing 15,000 national student identities, official AICTE approved institutions, and academic history.
   - `database/college_submissions.db`: Tracks incoming institutional admission rosters, quarantined validation queues, and dual-claim conflicts.

4. **Fast Workspace / Profile Switching:**
   - Switch between colleges, universities, and central administrative tiers on the fly using the **`⇄ Switch Role / Institute`** button or the user profile chip without logging out.

5. **Clean Verification Overview:**
   - Verification-focused metrics replacing hardcoded dummy charts.
   - Real-time ML anomaly breakdown cards and scoped recent student admissions.

---

## Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/asmijadhav832-del/APAARID.git
cd APAARID

# Create and activate a virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Running the Server
```bash
python server.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## Project Structure

```
APAARID/
├── server.py                 # Flask REST API server with scoped endpoints
├── requirements.txt          # Python dependencies
├── app.js                    # Dynamic frontend logic & multi-tier state
├── index.html                # Frontend markup with accessible modals
├── styles.css                # Polished design system
├── ml_model/                 # Random forest classifier, training & feature extraction
│   ├── anomaly_model.py      # Random Forest model definition
│   ├── feature_extractor.py  # 10-feature comparison vector generator
│   ├── train.py              # Model training script
│   ├── predict.py            # Inference engine
│   └── saved_models/         # Serialized model (.joblib)
├── database/                 # SQLite databases & schema definitions
│   ├── schema.sql            # Master table schemas
│   ├── ground_truth.db       # Master truth database (15,000 students)
│   ├── college_submissions.db# College admission rosters
│   └── setup_institutions.py # AICTE institution seed script
├── data_pipeline/            # Data generation and standardization pipelines
└── data/                     # CSV datasets, audit reports, and uploads
```

---

## License & Attribution
Developed for the APAAR / AICTE Academic Record Integrity System demo.
