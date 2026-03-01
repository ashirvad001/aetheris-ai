"""
Aetheris — ML Model Service
Trains and loads the ASA Risk Model + Complication Risk Model
Run this once: python -m app.ml.model_service
"""

import numpy as np
import pandas as pd
import pickle
import os
import logging
from pathlib import Path

logger = logging.getLogger("aetheris.ml")

MODELS_DIR = Path("./app/ml/models")
ASA_MODEL_PATH       = MODELS_DIR / "asa_risk_model.pkl"
COMPLICATION_MODEL_PATH = MODELS_DIR / "complication_model.pkl"
SCALER_PATH          = MODELS_DIR / "feature_scaler.pkl"


# ── TRAIN ASA RISK MODEL ───────────────────────────────────────────────────
def train_asa_model(n_samples: int = 8000):
    """
    Train ASA Classification model on synthetic clinical data.
    Based on published research feature importance from MIMIC-IV/NSQIP studies.

    Dataset sources for production:
    - MIMIC-IV: physionet.org/content/mimiciv
    - ACS NSQIP PUF: facs.org/quality-programs/acs-nsqip
    - Kaggle: kaggle.com/datasets/omnamahshivaya/surgical-risk
    """
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report

    logger.info("Generating synthetic training data...")
    np.random.seed(42)
    n = n_samples

    df = pd.DataFrame({
        "age":              np.random.normal(55, 18, n).clip(18, 90),
        "bmi":              np.random.normal(27, 6, n).clip(15, 55),
        "weight_kg":        np.random.normal(75, 18, n).clip(40, 180),
        "systolic_bp":      np.random.normal(125, 22, n).clip(80, 200),
        "diastolic_bp":     np.random.normal(80, 14, n).clip(50, 130),
        "heart_rate":       np.random.normal(78, 16, n).clip(40, 150),
        "temperature":      np.random.normal(36.8, 0.4, n).clip(35.0, 40.0),
        "spo2":             np.random.normal(97.5, 2.0, n).clip(80, 100),
        "resp_rate":        np.random.normal(16, 4, n).clip(8, 35),
        "etco2":            np.random.normal(38, 5, n).clip(20, 60),
        "diabetes":         np.random.binomial(1, 0.15, n).astype(float),
        "hypertension":     np.random.binomial(1, 0.30, n).astype(float),
        "cardiac_hx":       np.random.binomial(1, 0.12, n).astype(float),
        "smoking":          np.random.binomial(1, 0.20, n).astype(float),
        "comorbidity_count": np.random.poisson(1.2, n).clip(0, 8).astype(float),
        "albumin_low":      np.random.binomial(1, 0.10, n).astype(float),
        "hematocrit_low":   np.random.binomial(1, 0.12, n).astype(float),
    })

    # Rule-based ASA label (mirrors clinical ASA definitions)
    def assign_asa(row):
        score = 0
        if row["age"] > 70:              score += 2
        elif row["age"] > 60:            score += 1
        if row["bmi"] > 40:              score += 2
        elif row["bmi"] > 30:            score += 1
        if row["diabetes"]:              score += 1
        if row["hypertension"]:          score += 1
        if row["cardiac_hx"]:            score += 3
        if row["smoking"]:               score += 1
        if row["comorbidity_count"] > 4: score += 2
        elif row["comorbidity_count"] > 2: score += 1
        if row["spo2"] < 92:             score += 3
        elif row["spo2"] < 95:           score += 1
        if row["systolic_bp"] > 160:     score += 1
        if row["albumin_low"]:           score += 1
        if row["hematocrit_low"]:        score += 1
        if score <= 1:   return 1
        elif score <= 3: return 2
        elif score <= 6: return 3
        elif score <= 9: return 4
        else:            return 5

    df["asa_class"] = df.apply(assign_asa, axis=1)

    # Add clinical noise (15% label uncertainty — mirrors real-world inter-rater variability)
    noise_idx = np.random.choice(n, size=int(n * 0.15), replace=False)
    df.loc[noise_idx, "asa_class"] = df.loc[noise_idx, "asa_class"].apply(
        lambda x: min(5, max(1, x + np.random.choice([-1, 1])))
    )

    FEATURES = [
        "age", "bmi", "weight_kg", "systolic_bp", "diastolic_bp",
        "heart_rate", "temperature", "spo2", "resp_rate", "etco2",
        "diabetes", "hypertension", "cardiac_hx", "smoking",
        "comorbidity_count", "albumin_low", "hematocrit_low",
    ]

    X = df[FEATURES]
    y = df["asa_class"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)

    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train_scaled, y_train)

    acc = model.score(X_test_scaled, y_test)
    logger.info(f"ASA Model Accuracy: {acc:.2%}")
    logger.info("\n" + classification_report(y_test, model.predict(X_test_scaled)))

    return model, scaler, FEATURES


# ── TRAIN COMPLICATION RISK MODEL ──────────────────────────────────────────
def train_complication_model(n_samples: int = 6000):
    """
    Multi-output regression for post-op complication risks.
    Predicts: DVT %, Infection %, Pneumonia %, Readmission %
    """
    from sklearn.multioutput import MultiOutputRegressor
    from sklearn.ensemble import RandomForestRegressor

    np.random.seed(99)
    n = n_samples

    df = pd.DataFrame({
        "age":            np.random.normal(55, 18, n).clip(18, 90),
        "bmi":            np.random.normal(27, 6, n).clip(15, 55),
        "surgery_duration_min": np.random.normal(150, 60, n).clip(30, 480),
        "blood_loss_ml":  np.random.normal(300, 200, n).clip(50, 2000),
        "asa_class":      np.random.choice([1,2,3,4], n, p=[0.15,0.40,0.35,0.10]),
        "diabetes":       np.random.binomial(1, 0.15, n).astype(float),
        "hypertension":   np.random.binomial(1, 0.30, n).astype(float),
        "cardiac_hx":     np.random.binomial(1, 0.12, n).astype(float),
        "smoker":         np.random.binomial(1, 0.20, n).astype(float),
        "surgery_type_cardiac":    np.random.binomial(1, 0.15, n).astype(float),
        "surgery_type_orthopedic": np.random.binomial(1, 0.25, n).astype(float),
        "surgery_type_neuro":      np.random.binomial(1, 0.10, n).astype(float),
    })

    # Generate realistic complication risk targets
    base = df["asa_class"] * 3
    df["dvt_risk"]        = (base + df["age"]*0.1 + df["surgery_duration_min"]*0.02
                             + df["cardiac_hx"]*8 + np.random.normal(0,2,n)).clip(1,60)
    df["infection_risk"]  = (base*0.8 + df["diabetes"]*10 + df["blood_loss_ml"]*0.005
                             + df["smoker"]*5 + np.random.normal(0,2,n)).clip(1,50)
    df["pneumonia_risk"]  = (base*1.2 + df["age"]*0.15 + df["smoker"]*12
                             + df["cardiac_hx"]*6 + np.random.normal(0,3,n)).clip(1,60)
    df["readmission_risk"] = (base + df["diabetes"]*8 + df["cardiac_hx"]*10
                              + df["age"]*0.08 + np.random.normal(0,2,n)).clip(1,50)

    FEATURES = [
        "age", "bmi", "surgery_duration_min", "blood_loss_ml", "asa_class",
        "diabetes", "hypertension", "cardiac_hx", "smoker",
        "surgery_type_cardiac", "surgery_type_orthopedic", "surgery_type_neuro",
    ]
    TARGETS = ["dvt_risk", "infection_risk", "pneumonia_risk", "readmission_risk"]

    X = df[FEATURES]
    y = df[TARGETS]

    model = MultiOutputRegressor(
        RandomForestRegressor(n_estimators=100, random_state=42)
    )
    model.fit(X, y)
    logger.info("Complication model trained.")
    return model, FEATURES, TARGETS


# ── SAVE / LOAD ─────────────────────────────────────────────────────────────
def save_models():
    """Train and save all ML models to disk."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Training ASA Risk Model...")
    asa_model, scaler, asa_features = train_asa_model()
    with open(ASA_MODEL_PATH, "wb") as f:
        pickle.dump({"model": asa_model, "features": asa_features}, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    logger.info(f"✅ ASA model saved → {ASA_MODEL_PATH}")

    logger.info("Training Complication Model...")
    comp_model, comp_features, comp_targets = train_complication_model()
    with open(COMPLICATION_MODEL_PATH, "wb") as f:
        pickle.dump({"model": comp_model, "features": comp_features, "targets": comp_targets}, f)
    logger.info(f"✅ Complication model saved → {COMPLICATION_MODEL_PATH}")


def load_asa_model():
    if not ASA_MODEL_PATH.exists():
        logger.warning("ASA model not found — training now...")
        save_models()
    with open(ASA_MODEL_PATH, "rb") as f:
        return pickle.load(f)


def load_complication_model():
    if not COMPLICATION_MODEL_PATH.exists():
        logger.warning("Complication model not found — training now...")
        save_models()
    with open(COMPLICATION_MODEL_PATH, "rb") as f:
        return pickle.load(f)


def load_scaler():
    if not SCALER_PATH.exists():
        save_models()
    with open(SCALER_PATH, "rb") as f:
        return pickle.load(f)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    save_models()
    print("All models saved successfully!")
