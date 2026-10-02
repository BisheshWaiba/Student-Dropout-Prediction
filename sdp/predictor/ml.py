"""Loads the trained scikit-learn pipeline + metadata exported by the notebook."""
import csv
import json
from functools import lru_cache

import joblib
import pandas as pd
from django.conf import settings


class ModelNotReady(Exception):
    """Raised when the model files are missing or cannot be loaded."""


def _dir():
    return settings.ML_MODEL_DIR


@lru_cache(maxsize=1)
def load_artifacts():
    model_path = _dir() / "student_model.pkl"
    meta_path = _dir() / "model_meta.json"
    missing = [p.name for p in (model_path, meta_path) if not p.exists()]
    if missing:
        raise ModelNotReady(
            "Missing file(s) in the ml_model/ folder: " + ", ".join(missing) +
            ". Copy them from the notebook's model/ output folder.")
    try:
        model = joblib.load(model_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:  # e.g. scikit-learn version mismatch
        raise ModelNotReady(
            f"Could not load the model ({exc.__class__.__name__}: {exc}). "
            "This usually means scikit-learn here is a different version than the one "
            "used for training. Install the same version.") from exc
    return model, meta


def get_meta():
    return load_artifacts()[1]


def load_comparison():
    """Optional model_comparison.csv from the notebook (used on the Model Info page)."""
    path = _dir() / "model_comparison.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "feature_set": r.get("Feature set", ""),
                "model": r.get("Model", ""),
                "cv_f1": r.get("CV macro-F1", ""),
                "test_acc": r.get("Test accuracy", ""),
                "test_f1": r.get("Test macro-F1", ""),
            })
    return rows


def risk_level(p_dropout):
    if p_dropout >= 0.50:
        return "High"
    if p_dropout >= 0.25:
        return "Moderate"
    return "Low"


def predict(values):
    """values: dict {feature_name: number}. Returns dict with label + probabilities."""
    model, meta = load_artifacts()
    names = [f["name"] for f in meta["features"]]
    frame = pd.DataFrame([{n: float(values[n]) for n in names}])[names]
    proba = model.predict_proba(frame)[0]
    classes = meta["class_names"]
    probs = {c: float(p) for c, p in zip(classes, proba)}
    label = max(probs, key=probs.get)
    return {"label": label, "probs": probs}
