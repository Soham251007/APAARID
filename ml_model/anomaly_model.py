"""Random Forest Anomaly Detection Model for APAAR Student Data.

Built with Scikit-Learn to compare inputted student records against
the master Ground Truth database and detect fraudulent entries, identity
mismatches, and academic inconsistencies.
"""

import os
from typing import Any, Dict, List, Optional
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError

from .feature_extractor import FEATURE_NAMES


class ApaarAnomalyClassifier:
    """Scikit-Learn Random Forest Classifier tailored for APAAR Academic & Identity

    Anomaly Detection.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: Optional[int] = 12,
        min_samples_split: int = 4,
        min_samples_leaf: int = 2,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state

        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=self.min_samples_split,
            min_samples_leaf=self.min_samples_leaf,
            class_weight="balanced",  # Critical for anomaly/fraud detection where anomalies are rare
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.feature_names = FEATURE_NAMES
        self.is_trained = False

    def fit(
        self,
        X: Any,
        y: Any,
        sample_weight: Optional[np.ndarray] = None,
    ) -> "ApaarAnomalyClassifier":
        """Trains the Random Forest model on feature matrix X and target y.

        y = 0: Valid/Authentic Record
        y = 1: Anomalous/Fraudulent Record
        """
        if isinstance(X, pd.DataFrame):
            X_mat = X[self.feature_names].values
        else:
            X_mat = np.array(X)

        y_vec = np.array(y).astype(int)

        self.model.fit(X_mat, y_vec, sample_weight=sample_weight)
        self.is_trained = True
        return self

    def predict(self, X: Any) -> np.ndarray:
        """Predict binary classification (0 = Normal, 1 = Anomaly)."""
        if not self.is_trained:
            raise NotFittedError(
                "ApaarAnomalyClassifier is not yet trained. "
                "Please provide a training dataset and call .fit() before running inference."
            )
        if isinstance(X, pd.DataFrame):
            X_mat = X[self.feature_names].values
        else:
            X_mat = np.array(X)
        return self.model.predict(X_mat)

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict anomaly probabilities [P(normal), P(anomaly)]."""
        if not self.is_trained:
            raise NotFittedError(
                "ApaarAnomalyClassifier is not yet trained. "
                "Please provide a training dataset and call .fit() before running inference."
            )
        if isinstance(X, pd.DataFrame):
            X_mat = X[self.feature_names].values
        else:
            X_mat = np.array(X)
        return self.model.predict_proba(X_mat)

    def get_feature_importances(self) -> Dict[str, float]:
        """Return dictionary of feature names and their Gini importance scores."""
        if not self.is_trained:
            raise NotFittedError("Model must be trained before accessing feature importances.")
        importances = self.model.feature_importances_
        sorted_pairs = sorted(
            zip(self.feature_names, importances), key=lambda x: x[1], reverse=True
        )
        return {name: float(round(imp, 4)) for name, imp in sorted_pairs}

    def explain_record(
        self, features_dict: Dict[str, float], anomaly_prob: float
    ) -> List[str]:
        """Provides an interpretable, human-readable rationale for why a record was flagged."""
        reasons = []

        if features_dict.get("apaar_exists_in_gt", 0.0) == 0.0:
            reasons.append("Unregistered APAAR ID (not present in ground truth)")

        if features_dict.get("aadhar_exists_in_gt", 0.0) == 0.0:
            reasons.append("Aadhaar number not found in master records")

        if features_dict.get("apaar_aadhar_link_match", 0.0) == 0.0:
            reasons.append("APAAR and Aadhaar pair discrepancy (paired with different identity)")

        dob_diff = features_dict.get("dob_diff_days", 0.0)
        if dob_diff > 0:
            reasons.append(f"Date of birth mismatch ({int(dob_diff)} days variance)")

        if features_dict.get("degree_progression_valid", 1.0) == 0.0:
            reasons.append("Invalid degree progression (claimed lower/inconsistent prior degree)")

        sem_diff = features_dict.get("current_semester_diff", 0.0)
        if sem_diff > 2.0:
            reasons.append(f"Unverified semester jump (+{int(sem_diff)} terms ahead)")
        elif sem_diff < 0.0:
            reasons.append(f"Semester regression anomaly ({int(sem_diff)} terms)")

        if features_dict.get("cross_university_duplicate", 0.0) == 1.0:
            reasons.append("Cross-University Dual Enrollment: Student is actively enrolled at another university")

        if features_dict.get("intra_university_cross_college_duplicate", 0.0) == 1.0:
            reasons.append("Intra-University Dual Enrollment: Student is concurrently registered at another college under the same university")

        if features_dict.get("intra_college_multi_course_duplicate", 0.0) == 1.0:
            reasons.append("Concurrent Course Conflict: Multiple active enrollments detected at the same college")

        if features_dict.get("active_enrollment_count", 1.0) > 1.0:
            reasons.append(f"Multiple active admissions detected ({int(features_dict.get('active_enrollment_count', 1))} active institutions/records)")

        if features_dict.get("apaar_length_valid", 1.0) == 0.0:
            reasons.append("Malformed APAAR Identifier: ID does not have required 12 digits")

        name_sim = features_dict.get("name_similarity_score", 1.0)
        if name_sim < 0.70:
            reasons.append(f"Substantial name mismatch (similarity: {name_sim*100:.1f}%)")

        return reasons

    def save(self, filepath: str) -> None:
        """Serializes the trained Scikit-Learn model to disk."""
        if not self.is_trained:
            raise NotFittedError("Cannot save an untrained model.")
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "feature_names": self.feature_names,
                "params": {
                    "n_estimators": self.n_estimators,
                    "max_depth": self.max_depth,
                    "min_samples_split": self.min_samples_split,
                    "min_samples_leaf": self.min_samples_leaf,
                    "random_state": self.random_state,
                },
            },
            filepath,
        )
        print(f"Model successfully saved to: {filepath}")

    @classmethod
    def load(cls, filepath: str) -> "ApaarAnomalyClassifier":
        """Loads a serialized Scikit-Learn Random Forest model."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"No saved model found at {filepath}")
        data = joblib.load(filepath)
        instance = cls(**data.get("params", {}))
        instance.model = data["model"]
        instance.feature_names = data.get("feature_names", FEATURE_NAMES)
        instance.is_trained = True
        return instance
