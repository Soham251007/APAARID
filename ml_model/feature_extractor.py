"""Feature extraction module for APAAR Identity & Academic Anomaly Detection.

Compares inputted student records (from CSV uploads) against the
authoritative SQLite Ground Truth database to generate numerical feature
vectors for the Scikit-Learn Random Forest Classifier.

Specialized capabilities include:
1. Detecting cross-university dual enrollment (student enrolled at another university).
2. Detecting intra-university dual enrollment (student enrolled in another college under the same university).
3. Detecting intra-college duplicate course enrollment.
4. Detecting batch-level multi-institution duplicate submissions.
"""

from datetime import datetime
import difflib
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# Standard academic degree hierarchy rank for progression validation
DEGREE_HIERARCHY: Dict[str, int] = {
    "10TH": 1,
    "SSC": 1,
    "MATRIC": 1,
    "12TH": 2,
    "HSC": 2,
    "INTERMEDIATE": 2,
    "DIPLOMA": 2,
    "POLYTECHNIC": 2,
    "BACHELORS": 3,
    "B.TECH": 3,
    "B.E.": 3,
    "B.SC": 3,
    "BCA": 3,
    "B.COM": 3,
    "B.A.": 3,
    "MASTERS": 4,
    "M.TECH": 4,
    "M.E.": 4,
    "M.SC": 4,
    "MCA": 4,
    "MBA": 4,
    "PHD": 5,
    "DOCTORATE": 5,
}

FEATURE_NAMES: List[str] = [
    "apaar_exists_in_gt",
    "aadhar_exists_in_gt",
    "apaar_aadhar_link_match",
    "dob_exact_match",
    "dob_diff_days",
    "last_degree_exact_match",
    "degree_progression_valid",
    "degree_level_gap",
    "current_semester_diff",
    "is_semester_leap",
    "is_semester_regression",
    "name_similarity_score",
    "institution_match",
    "course_match",
    "cross_university_duplicate",
    "intra_university_cross_college_duplicate",
    "intra_college_multi_course_duplicate",
    "active_enrollment_count",
    "apaar_length_valid",
]


def normalize_str(val: Any) -> str:
    """Strip, upper-case, and standardize whitespace for comparison."""
    if val is None or pd.isna(val):
        return ""
    return " ".join(str(val).strip().upper().split())


def get_degree_rank(degree_str: str) -> int:
    """Return numeric rank of a degree based on keyword mapping."""
    norm = normalize_str(degree_str)
    for key, rank in DEGREE_HIERARCHY.items():
        if key in norm:
            return rank
    return 0


def calculate_date_diff_days(d1: str, d2: str) -> int:
    """Calculate absolute difference in days between two date strings."""
    date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]
    dt1 = None
    dt2 = None

    for fmt in date_formats:
        if dt1 is None and d1:
            try:
                dt1 = datetime.strptime(d1.strip(), fmt)
            except ValueError:
                pass
        if dt2 is None and d2:
            try:
                dt2 = datetime.strptime(d2.strip(), fmt)
            except ValueError:
                pass

    if dt1 and dt2:
        return abs((dt1 - dt2).days)
    return 9999 if (d1 or d2) else 0


class GroundTruthComparator:
    """Compares input records with the SQLite ground truth database

    to construct ML feature vectors, specifically evaluating dual/cross
    enrollments across universities and colleges.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_ground_truth_match(
        self,
        cursor: sqlite3.Cursor,
        apaar_id: str,
        aadhar_number: str,
        full_name: str,
        dob: str,
    ) -> Optional[sqlite3.Row]:
        """Find the matching ground truth record using primary or composite keys."""
        norm_apaar = normalize_str(apaar_id)
        norm_aadhar = normalize_str(aadhar_number)

        # 1. Direct APAAR lookup
        if norm_apaar:
            cursor.execute(
                "SELECT * FROM ground_truth_students WHERE UPPER(apaar_id) = ? LIMIT 1",
                (norm_apaar,),
            )
            row = cursor.fetchone()
            if row:
                return row

        # 2. Direct Aadhaar lookup
        if norm_aadhar:
            cursor.execute(
                "SELECT * FROM ground_truth_students WHERE aadhar_number = ? LIMIT 1",
                (norm_aadhar,),
            )
            row = cursor.fetchone()
            if row:
                return row

        # 3. Composite fallback: Name + DOB
        if full_name and dob:
            cursor.execute(
                """
                SELECT * FROM ground_truth_students
                WHERE UPPER(full_name) = ? AND date_of_birth = ?
                LIMIT 1
                """,
                (normalize_str(full_name), dob.strip()),
            )
            row = cursor.fetchone()
            if row:
                return row

        return None

    def analyze_enrollment_conflicts(
        self,
        cursor: sqlite3.Cursor,
        aadhar_number: str,
        apaar_id: str,
        in_uni: str,
        in_inst: str,
        in_course: str,
    ) -> Tuple[float, float, float, float, List[str]]:
        """Analyzes active enrollment conflicts across universities and colleges.

        Returns:
            (cross_uni_dup, intra_uni_cross_coll_dup, intra_coll_course_dup, total_active_count, conflict_flags)
        """
        norm_aadhar = normalize_str(aadhar_number)
        norm_apaar = normalize_str(apaar_id)
        norm_in_uni = normalize_str(in_uni)
        norm_in_inst = normalize_str(in_inst)
        norm_in_course = normalize_str(in_course)

        if not norm_aadhar and not norm_apaar:
            return 0.0, 0.0, 0.0, 0.0, []

        cursor.execute(
            """
            SELECT university_name, institution_name, course_name
            FROM ground_truth_students
            WHERE (aadhar_number = ? OR UPPER(apaar_id) = ?)
              AND is_active = 1
            """,
            (norm_aadhar, norm_apaar),
        )
        active_enrollments = cursor.fetchall()
        total_active_count = float(len(active_enrollments))

        cross_uni_dup = 0.0
        intra_uni_cross_coll_dup = 0.0
        intra_coll_course_dup = 0.0
        flags = []

        for row in active_enrollments:
            gt_uni = normalize_str(row["university_name"])
            gt_inst = normalize_str(row["institution_name"])
            gt_course = normalize_str(row["course_name"])

            # 1. Cross-University Duplicate: Enrolled in a completely different university
            if gt_uni and norm_in_uni and gt_uni != norm_in_uni:
                cross_uni_dup = 1.0
                flags.append(f"DUAL_ENROLLMENT_DIFFERENT_UNIVERSITY (Existing: {gt_uni}, Submitted: {norm_in_uni})")

            # 2. Intra-University Duplicate: Same university, but enrolled in a DIFFERENT college/institution
            elif (
                (gt_uni and norm_in_uni and gt_uni == norm_in_uni)
                or (not gt_uni and not norm_in_uni)
            ) and (gt_inst and norm_in_inst and gt_inst != norm_in_inst):
                intra_uni_cross_coll_dup = 1.0
                flags.append(
                    f"DUAL_ENROLLMENT_SAME_UNIVERSITY_DIFFERENT_COLLEGE (University: {gt_uni or 'State/Affiliating'}, Existing College: {gt_inst}, Submitted College: {norm_in_inst})"
                )

            # 3. Same college, but different course registered concurrently
            elif (
                (gt_inst and norm_in_inst and gt_inst == norm_in_inst)
                and (gt_course and norm_in_course and gt_course != norm_in_course)
            ):
                intra_coll_course_dup = 1.0
                flags.append(f"CONCURRENT_COURSE_ENROLLMENT_SAME_COLLEGE (Existing: {gt_course}, Submitted: {norm_in_course})")

        return cross_uni_dup, intra_uni_cross_coll_dup, intra_coll_course_dup, total_active_count, flags

    def extract_features_single(
        self,
        input_record: Dict[str, Any],
        cursor: sqlite3.Cursor,
        batch_counts: Optional[Dict[str, int]] = None,
    ) -> Tuple[Dict[str, float], Optional[int], List[str]]:
        """Extract comparison feature dictionary between one inputted record and Ground Truth.

        Returns:
            (features_dict, matched_gt_id, detected_flags)
        """
        in_apaar = normalize_str(input_record.get("apaar_id", ""))
        in_aadhar = normalize_str(input_record.get("aadhar_number", ""))
        in_name = normalize_str(
            input_record.get(
                "full_name", input_record.get("name", input_record.get("student_name", ""))
            )
        )
        in_dob = str(input_record.get("date_of_birth", input_record.get("dob", ""))).strip()
        in_uni = normalize_str(
            input_record.get("university_name", input_record.get("university", ""))
        )
        in_inst = normalize_str(
            input_record.get(
                "institution_name", input_record.get("institution", input_record.get("college", ""))
            )
        )
        in_course = normalize_str(
            input_record.get("course_name", input_record.get("course", ""))
        )
        in_degree = normalize_str(
            input_record.get(
                "last_successful_degree",
                input_record.get("last_degree", input_record.get("degree", "")),
            )
        )
        in_sem_val = input_record.get("current_semester", input_record.get("semester", 1))
        try:
            in_sem = int(in_sem_val)
        except (ValueError, TypeError):
            in_sem = 1

        gt_row = self.find_ground_truth_match(
            cursor, in_apaar, in_aadhar, in_name, in_dob
        )

        flags: List[str] = []

        # Analyze Multi-Institution Enrollment Conflicts (against Ground Truth)
        (
            cross_uni_dup,
            intra_uni_dup,
            intra_coll_dup,
            active_count,
            enroll_flags,
        ) = self.analyze_enrollment_conflicts(
            cursor, in_aadhar, in_apaar, in_uni, in_inst, in_course
        )
        flags.extend(enroll_flags)

        # Batch-level duplicate detection (same student appearing multiple times in the upload)
        if batch_counts:
            key_apaar = f"APAAR_{in_apaar}" if in_apaar else ""
            key_aadhar = f"AADHAAR_{in_aadhar}" if in_aadhar else ""
            if (key_apaar and batch_counts.get(key_apaar, 0) > 1) or (
                key_aadhar and batch_counts.get(key_aadhar, 0) > 1
            ):
                flags.append("BATCH_SUBMISSION_DUPLICATE (Student submitted multiple times in same upload)")
                active_count = max(active_count, 2.0)

        # Validate APAAR length format (standard 12 digits)
        apaar_digits = "".join(filter(str.isdigit, in_apaar))
        apaar_len_valid = 1.0 if len(apaar_digits) == 12 else 0.0
        if apaar_len_valid == 0.0:
            flags.append(f"MALFORMED_APAAR_LENGTH_{len(apaar_digits)}_DIGITS (Expected 12)")

        if gt_row is None:
            # Record does NOT exist anywhere in Ground Truth master registry
            flags.append("RECORD_NOT_IN_GROUND_TRUTH")
            features = {
                "apaar_exists_in_gt": 0.0,
                "aadhar_exists_in_gt": 0.0,
                "apaar_aadhar_link_match": 0.0,
                "dob_exact_match": 0.0,
                "dob_diff_days": 9999.0,
                "last_degree_exact_match": 0.0,
                "degree_progression_valid": 0.0,
                "degree_level_gap": 0.0,
                "current_semester_diff": 0.0,
                "is_semester_leap": 0.0,
                "is_semester_regression": 0.0,
                "name_similarity_score": 0.0,
                "institution_match": 0.0,
                "course_match": 0.0,
                "cross_university_duplicate": cross_uni_dup,
                "intra_university_cross_college_duplicate": intra_uni_dup,
                "intra_college_multi_course_duplicate": intra_coll_dup,
                "active_enrollment_count": active_count,
                "apaar_length_valid": apaar_len_valid,
            }
            return features, None, flags

        gt_id = gt_row["id"]
        gt_apaar = normalize_str(gt_row["apaar_id"])
        gt_aadhar = normalize_str(gt_row["aadhar_number"])
        gt_name = normalize_str(gt_row["full_name"])
        gt_dob = str(gt_row["date_of_birth"]).strip()
        gt_degree = normalize_str(gt_row["last_successful_degree"])
        gt_sem = int(gt_row["current_semester"])
        gt_inst = normalize_str(gt_row["institution_name"])
        gt_course = normalize_str(gt_row["course_name"])

        # 1. Identifier pairing checks
        apaar_exists = 1.0 if in_apaar and in_apaar == gt_apaar else 0.0
        aadhar_exists = 1.0 if in_aadhar and in_aadhar == gt_aadhar else 0.0
        apaar_aadhar_match = 1.0 if (apaar_exists == 1.0 and aadhar_exists == 1.0) else 0.0

        if in_apaar and in_apaar == gt_apaar and in_aadhar != gt_aadhar:
            flags.append("AADHAAR_APAAR_PAIRING_MISMATCH")
        elif in_aadhar and in_aadhar == gt_aadhar and in_apaar != gt_apaar:
            flags.append("APAAR_IDENTITY_MISMATCH")

        # 2. Date of birth comparison
        dob_match = 1.0 if in_dob and in_dob == gt_dob else 0.0
        dob_diff_days = float(calculate_date_diff_days(in_dob, gt_dob))
        if dob_diff_days > 0:
            flags.append(f"DOB_DISCREPANCY_{int(dob_diff_days)}_DAYS")

        # 3. Last successful degree & academic progression
        degree_match = (
            1.0
            if in_degree
            and (in_degree == gt_degree or in_degree in gt_degree or gt_degree in in_degree)
            else 0.0
        )
        in_rank = get_degree_rank(in_degree)
        gt_rank = get_degree_rank(gt_degree)
        degree_gap = float(in_rank - gt_rank)

        progression_valid = 1.0
        if in_rank < gt_rank:
            progression_valid = 0.0
            flags.append("REGRESSIVE_DEGREE_CLAIM")
        elif degree_match == 0.0 and in_rank != gt_rank:
            flags.append("DEGREE_MISMATCH")

        # 4. Semester progression
        sem_diff = float(in_sem - gt_sem)
        is_leap = 1.0 if sem_diff > 2.0 else 0.0
        is_regression = 1.0 if sem_diff < 0.0 else 0.0

        if is_leap == 1.0:
            flags.append(f"SEMESTER_LEAP_ANOMALY_+{int(sem_diff)}")
        if is_regression == 1.0:
            flags.append(f"SEMESTER_REGRESSION_ANOMALY_{int(sem_diff)}")

        # 5. Name similarity ratio
        name_sim = float(difflib.SequenceMatcher(None, in_name, gt_name).ratio())
        if name_sim < 0.75:
            flags.append("NAME_SIMILARITY_LOW")

        # 6. Institutional oversight
        inst_match = (
            1.0
            if in_inst
            and (in_inst == gt_inst or in_inst in gt_inst or gt_inst in in_inst)
            else 0.0
        )
        course_match = (
            1.0
            if in_course
            and (in_course == gt_course or in_course in gt_course or gt_course in in_course)
            else 0.0
        )

        features = {
            "apaar_exists_in_gt": apaar_exists,
            "aadhar_exists_in_gt": aadhar_exists,
            "apaar_aadhar_link_match": apaar_aadhar_match,
            "dob_exact_match": dob_match,
            "dob_diff_days": dob_diff_days,
            "last_degree_exact_match": degree_match,
            "degree_progression_valid": progression_valid,
            "degree_level_gap": degree_gap,
            "current_semester_diff": sem_diff,
            "is_semester_leap": is_leap,
            "is_semester_regression": is_regression,
            "name_similarity_score": name_sim,
            "institution_match": inst_match,
            "course_match": course_match,
            "cross_university_duplicate": cross_uni_dup,
            "intra_university_cross_college_duplicate": intra_uni_dup,
            "intra_college_multi_course_duplicate": intra_coll_dup,
            "active_enrollment_count": active_count,
            "apaar_length_valid": apaar_len_valid,
        }

        return features, gt_id, flags

    def extract_features_dataframe(
        self, input_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, List[Optional[int]], List[List[str]]]:
        """Process an entire uploaded CSV DataFrame and return feature DataFrame."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build batch frequency map to detect intra-file duplicate submissions
        batch_counts: Dict[str, int] = {}
        for _, row in input_df.iterrows():
            ap = normalize_str(row.get("apaar_id", ""))
            aa = normalize_str(row.get("aadhar_number", ""))
            if ap:
                batch_counts[f"APAAR_{ap}"] = batch_counts.get(f"APAAR_{ap}", 0) + 1
            if aa:
                batch_counts[f"AADHAAR_{aa}"] = batch_counts.get(f"AADHAAR_{aa}", 0) + 1

        features_list = []
        gt_ids = []
        all_flags = []

        try:
            for _, row in input_df.iterrows():
                row_dict = row.to_dict()
                feat, gt_id, flags = self.extract_features_single(
                    row_dict, cursor, batch_counts=batch_counts
                )
                features_list.append(feat)
                gt_ids.append(gt_id)
                all_flags.append(flags)
        finally:
            conn.close()

        feat_df = pd.DataFrame(features_list)[FEATURE_NAMES]
        return feat_df, gt_ids, all_flags
