"""
ml_model/analytics.py
----------------------
Three ML models trained on parking session data.

  Model 1 — Peak hour predictor
    Input  : hour (0-23), day_of_week (0-6), is_weekend
    Output : predicted occupancy level (low / medium / high)
    Use    : dashboard widget, "Expected busy hours today"

  Model 2 — Duration estimator
    Input  : vehicle_type, hour, day_of_week, is_weekend
    Output : predicted stay in minutes
    Use    : display "Expected stay: ~2h" at entry

  Model 3 — Anomaly detector
    Input  : actual duration vs expected for that vehicle type + hour
    Output : True if vehicle has overstayed (anomaly)
    Use    : flag sessions on dashboard after threshold

All models use scikit-learn (no GPU needed).
Models are trained once and cached in memory on first call.

INSTALL:
  pip install scikit-learn pandas numpy

USAGE:
  from ml_model.analytics import (
      get_peak_prediction,
      get_duration_estimate,
      get_anomaly_flags,
      get_hourly_heatmap,
  )
"""

import os
import csv
import pickle
import random
from datetime import datetime

# ── lazy imports (so Flask starts fast) ──
_sklearn_loaded = False
_pd = None
_np = None
RandomForestClassifier = None
RandomForestRegressor  = None
IsolationForest        = None
LabelEncoder           = None

def _load_sklearn():
    global _sklearn_loaded, _pd, _np
    global RandomForestClassifier, RandomForestRegressor
    global IsolationForest, LabelEncoder
    if _sklearn_loaded:
        return
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier as RFC
    from sklearn.ensemble import RandomForestRegressor  as RFR
    from sklearn.ensemble import IsolationForest        as IF
    from sklearn.preprocessing import LabelEncoder      as LE
    _pd                    = pd
    _np                    = np
    RandomForestClassifier = RFC
    RandomForestRegressor  = RFR
    IsolationForest        = IF
    LabelEncoder           = LE
    _sklearn_loaded        = True


# ── Paths ──
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH  = os.path.join(BASE_DIR, 'database', 'parking_data.csv')
MODEL_DIR  = os.path.join(BASE_DIR, 'database', 'models')

# ── In-memory model cache ──
_models = {}


# ═══════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════

def _load_csv():
    """Load parking_data.csv into a list of dicts."""
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}\n"
            "Run: python ml_model/generate_data.py"
        )
    with open(DATA_PATH, newline='') as f:
        return list(csv.DictReader(f))


def _to_df(rows):
    """Convert list of dicts to a pandas DataFrame with correct dtypes."""
    _load_sklearn()
    df = _pd.DataFrame(rows)
    int_cols = [
        'hour', 'minute', 'day_of_week', 'is_weekend',
        'is_morning_rush', 'is_lunch', 'is_evening_rush',
        'month', 'day', 'vehicle_type_num', 'duration_minutes'
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = _pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    return df


# ═══════════════════════════════════════════════
#  MODEL 1 — PEAK HOUR PREDICTOR
#  Classifies each hour as low / medium / high occupancy
# ═══════════════════════════════════════════════

def _label_occupancy(count, low_thresh=10, high_thresh=25):
    """Convert arrival count → occupancy label."""
    if count <= low_thresh:
        return 'low'
    elif count <= high_thresh:
        return 'medium'
    else:
        return 'high'


def _train_peak_model(df):
    """
    Aggregate data by (day_of_week, hour) → arrival count → label.
    Train a Random Forest to predict label from (hour, day_of_week, is_weekend).
    """
    _load_sklearn()

    # Count arrivals per (day_of_week, hour) combination
    grouped = (
        df.groupby(['day_of_week', 'hour'])
          .size()
          .reset_index(name='count')
    )
    grouped['is_weekend'] = (grouped['day_of_week'] >= 5).astype(int)
    grouped['label']      = grouped['count'].apply(_label_occupancy)

    X = grouped[['hour', 'day_of_week', 'is_weekend']].values
    y = grouped['label'].values

    le  = LabelEncoder()
    y_e = le.fit_transform(y)

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y_e)

    return {'clf': clf, 'le': le}


def get_peak_prediction(hour=None, day_of_week=None):
    """
    Predict occupancy level for a given hour and day.

    Args:
      hour        (int): 0-23. Defaults to current hour.
      day_of_week (int): 0=Mon … 6=Sun. Defaults to today.

    Returns dict:
      {
        'hour':       18,
        'day_name':   'Monday',
        'level':      'high',          # low / medium / high
        'confidence': 0.87,            # model confidence 0-1
        'message':    'Peak hours expected. Lot likely full.'
      }
    """
    now = datetime.now()
    if hour        is None: hour        = now.hour
    if day_of_week is None: day_of_week = now.weekday()

    is_weekend = 1 if day_of_week >= 5 else 0

    model = _get_model('peak')
    clf   = model['clf']
    le    = model['le']

    X    = [[hour, day_of_week, is_weekend]]
    pred = clf.predict(X)[0]
    prob = clf.predict_proba(X)[0].max()

    level    = le.inverse_transform([pred])[0]
    day_name = ['Monday','Tuesday','Wednesday','Thursday',
                'Friday','Saturday','Sunday'][day_of_week]

    messages = {
        'low':    'Quiet period. Plenty of slots available.',
        'medium': 'Moderate traffic. Some slots available.',
        'high':   'Peak hours expected. Lot may fill up soon.',
    }

    return {
        'hour':       hour,
        'day_name':   day_name,
        'level':      level,
        'confidence': round(float(prob), 2),
        'message':    messages[level],
    }


def get_hourly_heatmap(day_of_week=None):
    """
    Return predicted occupancy level for every hour of a given day.
    Used to draw the heatmap chart on the dashboard.

    Returns list of 24 dicts: [{ hour, level, confidence }, ...]
    """
    now = datetime.now()
    if day_of_week is None:
        day_of_week = now.weekday()

    return [
        get_peak_prediction(hour=h, day_of_week=day_of_week)
        for h in range(24)
    ]


# ═══════════════════════════════════════════════
#  MODEL 2 — DURATION ESTIMATOR
#  Predicts how long a vehicle will stay
# ═══════════════════════════════════════════════

def _train_duration_model(df):
    """
    Train a Random Forest regressor to predict stay duration.
    Features: vehicle_type_num, hour, day_of_week, is_weekend,
              is_morning_rush, is_lunch, is_evening_rush
    Target:   duration_minutes
    """
    _load_sklearn()

    features = [
        'vehicle_type_num', 'hour', 'day_of_week', 'is_weekend',
        'is_morning_rush', 'is_lunch', 'is_evening_rush'
    ]

    df_clean = df[features + ['duration_minutes']].dropna()
    X = df_clean[features].values
    y = df_clean['duration_minutes'].values

    reg = RandomForestRegressor(n_estimators=100, random_state=42)
    reg.fit(X, y)

    return {'reg': reg, 'features': features}


def get_duration_estimate(vehicle_type, hour=None, day_of_week=None):
    """
    Predict how long a vehicle is likely to stay.

    Args:
      vehicle_type (str): 'car' or 'bike'
      hour         (int): 0-23. Defaults to current hour.
      day_of_week  (int): 0-6. Defaults to today.

    Returns dict:
      {
        'vehicle_type':     'car',
        'predicted_minutes': 142,
        'predicted_str':    '2h 22m',
        'range_str':        '1h 30m – 3h 00m',
        'confidence_note':  'Based on 90 days of parking data'
      }
    """
    now = datetime.now()
    if hour        is None: hour        = now.hour
    if day_of_week is None: day_of_week = now.weekday()

    is_weekend      = 1 if day_of_week >= 5 else 0
    is_morning_rush = 1 if 7  <= hour <= 9  else 0
    is_lunch        = 1 if 12 <= hour <= 13 else 0
    is_evening_rush = 1 if 17 <= hour <= 19 else 0
    vtype_num       = 0 if vehicle_type == 'car' else 1

    model = _get_model('duration')
    reg   = model['reg']

    X    = [[vtype_num, hour, day_of_week, is_weekend,
             is_morning_rush, is_lunch, is_evening_rush]]
    pred = int(reg.predict(X)[0])
    pred = max(5, pred)

    # Rough confidence interval (±30%)
    low  = max(5, int(pred * 0.70))
    high = int(pred * 1.30)

    def fmt(minutes):
        h, m = divmod(minutes, 60)
        return f'{h}h {m:02d}m' if h > 0 else f'{m}m'

    return {
        'vehicle_type':      vehicle_type,
        'predicted_minutes': pred,
        'predicted_str':     fmt(pred),
        'range_str':         f'{fmt(low)} – {fmt(high)}',
        'confidence_note':   'Based on 90 days of parking data',
    }


# ═══════════════════════════════════════════════
#  MODEL 3 — ANOMALY DETECTOR
#  Flags vehicles that have overstayed
# ═══════════════════════════════════════════════

def _train_anomaly_model(df):
    """
    Train an Isolation Forest on [vehicle_type_num, hour, duration_minutes].
    Isolation Forest learns what 'normal' looks like and flags outliers.
    """
    _load_sklearn()

    features = ['vehicle_type_num', 'hour', 'duration_minutes']
    df_clean = df[features].dropna()
    X        = df_clean.values

    iso = IsolationForest(
        contamination = 0.05,   # expect ~5% anomalies
        random_state  = 42,
        n_estimators  = 100,
    )
    iso.fit(X)

    return {'iso': iso}


def get_anomaly_flags(active_sessions):
    """
    Check currently active sessions for anomalies (unusually long stays).

    Args:
      active_sessions: list of session dicts from get_active_sessions()
                       Each must have: vehicle_type, entry_time

    Returns list of dicts — one per session, with added fields:
      {
        ...original session fields...,
        'duration_so_far':  245,      # minutes parked so far
        'is_anomaly':       True,     # True = overstayed
        'anomaly_score':    -0.18,    # more negative = more anomalous
        'anomaly_label':    'Overstayed — check vehicle'
      }
    """
    if not active_sessions:
        return []

    _load_sklearn()
    model = _get_model('anomaly')
    iso   = model['iso']
    now   = datetime.now()

    results = []
    for session in active_sessions:
        try:
            entry_dt  = datetime.strptime(session['entry_time'], '%Y-%m-%d %H:%M:%S')
        except (ValueError, KeyError):
            entry_dt  = now

        duration_so_far = int((now - entry_dt).total_seconds() / 60)
        hour            = entry_dt.hour
        vtype_num       = 0 if session.get('vehicle_type') == 'car' else 1

        X     = [[vtype_num, hour, duration_so_far]]
        score = float(iso.score_samples(X)[0])   # more negative = more outlier
        pred  = iso.predict(X)[0]                 # -1 = anomaly, 1 = normal

        is_anomaly = (pred == -1)
        label      = 'Overstayed — check vehicle' if is_anomaly else 'Normal'

        results.append({
            **session,
            'duration_so_far': duration_so_far,
            'is_anomaly':      is_anomaly,
            'anomaly_score':   round(score, 3),
            'anomaly_label':   label,
        })

    return results


# ═══════════════════════════════════════════════
#  MODEL CACHE + TRAINING ORCHESTRATOR
# ═══════════════════════════════════════════════

def _get_model(name):
    """
    Return a trained model by name ('peak', 'duration', 'anomaly').
    Trains on first call, then caches in memory.
    Also persists to disk as a pickle so subsequent app restarts are faster.
    """
    global _models

    if name in _models:
        return _models[name]

    # Try loading from disk first
    os.makedirs(MODEL_DIR, exist_ok=True)
    pkl_path = os.path.join(MODEL_DIR, f'{name}_model.pkl')

    if os.path.exists(pkl_path):
        with open(pkl_path, 'rb') as f:
            _models[name] = pickle.load(f)
        print(f"[ANALYTICS] Loaded {name} model from disk.")
        return _models[name]

    # Train from scratch
    print(f"[ANALYTICS] Training {name} model...")
    rows = _load_csv()
    df   = _to_df(rows)

    if name == 'peak':
        model = _train_peak_model(df)
    elif name == 'duration':
        model = _train_duration_model(df)
    elif name == 'anomaly':
        model = _train_anomaly_model(df)
    else:
        raise ValueError(f"Unknown model: {name}")

    # Save to disk
    with open(pkl_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"[ANALYTICS] {name} model trained and saved.")

    _models[name] = model
    return model


def train_all():
    """
    Pre-train all models. Call this once after generating data,
    or add it to your app startup.

    Usage:
      python -c "from ml_model.analytics import train_all; train_all()"
    """
    for name in ('peak', 'duration', 'anomaly'):
        _get_model(name)
    print("[ANALYTICS] All models ready.")


# ═══════════════════════════════════════════════
#  QUICK TEST (run directly)
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    print("Training all models...\n")
    train_all()

    print("\n── Peak prediction (Monday 8am) ──")
    print(get_peak_prediction(hour=8, day_of_week=0))

    print("\n── Peak prediction (Sunday 3pm) ──")
    print(get_peak_prediction(hour=15, day_of_week=6))

    print("\n── Duration estimate (car, 8am) ──")
    print(get_duration_estimate('car', hour=8, day_of_week=1))

    print("\n── Duration estimate (bike, 12pm) ──")
    print(get_duration_estimate('bike', hour=12, day_of_week=3))

    print("\n── Anomaly detection (mock sessions) ──")
    mock_sessions = [
        {'vehicle_number': 'UP80AB1234', 'vehicle_type': 'car',
         'entry_time': '2024-01-15 08:00:00', 'slot_number': 'C1'},
        {'vehicle_number': 'UP80XY9999', 'vehicle_type': 'bike',
         'entry_time': '2024-01-15 06:00:00', 'slot_number': 'B1'},   # anomaly
    ]
    for r in get_anomaly_flags(mock_sessions):
        print(f"  {r['vehicle_number']} — {r['duration_so_far']}min — anomaly={r['is_anomaly']}")