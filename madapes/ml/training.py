"""ML training pipeline for signal prediction."""
import json
import logging
import os
from typing import Optional, Tuple

from db import get_connection
from madapes.ml.feature_extractor import extract_features, extract_label, extract_return, FEATURE_NAMES

logger = logging.getLogger(__name__)

MODEL_DIR = "models"
CLASSIFIER_PATH = os.path.join(MODEL_DIR, "signal_classifier.json")
REGRESSOR_PATH = os.path.join(MODEL_DIR, "return_regressor.json")


def _get_training_data() -> Tuple[list, list, list]:
    """Extract features and labels from historical signals.
    Returns (X, y_class, y_return).
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM signals
               WHERE status IN ('win', 'loss')
               AND original_price IS NOT NULL
               AND original_market_cap IS NOT NULL
               ORDER BY original_timestamp"""
        ).fetchall()

    X = []
    y_class = []
    y_return = []

    for row in rows:
        features = extract_features(dict(row))
        label = extract_label(dict(row))
        ret = extract_return(dict(row))

        if features is not None and label is not None:
            X.append(features)
            y_class.append(label)
            y_return.append(ret if ret is not None else 0.0)

    return X, y_class, y_return


def train_classifier() -> Optional[dict]:
    """Train a binary classifier: profitable at 1h?

    Uses scikit-learn if available. Returns metrics dict or None.
    """
    try:
        import numpy as np
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        logger.warning("scikit-learn not installed - ML training disabled")
        return None

    X, y_class, _ = _get_training_data()
    if len(X) < 20:
        logger.info(f"Not enough training data ({len(X)} samples, need 20+)")
        return None

    X_arr = np.array(X)
    y_arr = np.array(y_class)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_arr)

    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )

    # Cross-validation
    scores = cross_val_score(model, X_scaled, y_arr, cv=min(5, len(X) // 4), scoring="accuracy")

    # Train on full data
    model.fit(X_scaled, y_arr)

    # Feature importance
    importances = dict(zip(FEATURE_NAMES, model.feature_importances_.tolist()))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]

    # Save model parameters
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_info = {
        "type": "classifier",
        "accuracy_mean": float(scores.mean()),
        "accuracy_std": float(scores.std()),
        "samples": len(X),
        "top_features": top_features,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
    }

    # Save model using joblib
    try:
        import joblib
        joblib.dump(model, os.path.join(MODEL_DIR, "signal_classifier.pkl"))
        joblib.dump(scaler, os.path.join(MODEL_DIR, "classifier_scaler.pkl"))
    except ImportError:
        pass

    with open(CLASSIFIER_PATH, "w") as f:
        json.dump(model_info, f, indent=2)

    logger.info(
        f"Classifier trained: accuracy={scores.mean():.3f} +/- {scores.std():.3f} "
        f"({len(X)} samples)"
    )
    return model_info


def train_regressor() -> Optional[dict]:
    """Train a regression model: predicted return %.

    Returns metrics dict or None.
    """
    try:
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None

    X, _, y_return = _get_training_data()
    if len(X) < 20:
        return None

    X_arr = np.array(X)
    y_arr = np.array(y_return)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_arr)

    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )

    scores = cross_val_score(model, X_scaled, y_arr, cv=min(5, len(X) // 4), scoring="r2")
    model.fit(X_scaled, y_arr)

    importances = dict(zip(FEATURE_NAMES, model.feature_importances_.tolist()))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]

    os.makedirs(MODEL_DIR, exist_ok=True)
    model_info = {
        "type": "regressor",
        "r2_mean": float(scores.mean()),
        "r2_std": float(scores.std()),
        "samples": len(X),
        "top_features": top_features,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
    }

    try:
        import joblib
        joblib.dump(model, os.path.join(MODEL_DIR, "return_regressor.pkl"))
        joblib.dump(scaler, os.path.join(MODEL_DIR, "regressor_scaler.pkl"))
    except ImportError:
        pass

    with open(REGRESSOR_PATH, "w") as f:
        json.dump(model_info, f, indent=2)

    logger.info(f"Regressor trained: R2={scores.mean():.3f} ({len(X)} samples)")
    return model_info


def predict_signal(signal_data: dict, caller_data=None, multi_caller_count=1) -> Optional[dict]:
    """Predict outcome for a new signal using trained models.

    Returns dict with probability, predicted_return, or None if models not available.
    """
    try:
        import joblib
        import numpy as np
    except ImportError:
        return None

    features = extract_features(signal_data, caller_data, multi_caller_count)
    if features is None:
        return None

    result = {}

    # Classifier prediction
    clf_path = os.path.join(MODEL_DIR, "signal_classifier.pkl")
    clf_scaler_path = os.path.join(MODEL_DIR, "classifier_scaler.pkl")
    if os.path.exists(clf_path) and os.path.exists(clf_scaler_path):
        try:
            clf = joblib.load(clf_path)
            scaler = joblib.load(clf_scaler_path)
            X = scaler.transform(np.array([features]))
            prob = clf.predict_proba(X)[0][1]  # probability of win
            result["win_probability"] = round(float(prob), 3)
        except Exception as e:
            logger.debug(f"Classifier prediction error: {e}")

    # Regressor prediction
    reg_path = os.path.join(MODEL_DIR, "return_regressor.pkl")
    reg_scaler_path = os.path.join(MODEL_DIR, "regressor_scaler.pkl")
    if os.path.exists(reg_path) and os.path.exists(reg_scaler_path):
        try:
            reg = joblib.load(reg_path)
            scaler = joblib.load(reg_scaler_path)
            X = scaler.transform(np.array([features]))
            predicted_return = reg.predict(X)[0]
            result["predicted_return"] = round(float(predicted_return), 2)
        except Exception as e:
            logger.debug(f"Regressor prediction error: {e}")

    return result if result else None
