"""
ml_model/generate_data.py
--------------------------
Generates a realistic synthetic parking dataset and saves it to
database/parking_data.csv

Patterns baked in (mirrors a real Indian parking lot):
  - Morning rush   07:00–09:30  (heavy car traffic)
  - Lunch peak     12:00–13:30  (mixed)
  - Evening rush   17:00–19:30  (heaviest)
  - Night quiet    22:00–06:00  (near zero)
  - Weekends       more bikes, shorter stays, later start
  - Cars stay longer on average than bikes
  - Repeat visitors (some plates appear many times)

Run this file directly to generate the CSV:
  python ml_model/generate_data.py
"""

import random
import os
import csv
from datetime import datetime, timedelta

# ── Reproducibility ──
random.seed(42)

# ── Output path ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(BASE_DIR, 'database', 'parking_data.csv')


# ─────────────────────────────────────────
#  SYNTHETIC PLATE POOL
#  A mix of regulars (seen often) + one-timers
# ─────────────────────────────────────────

def make_plate(prefix='UP80'):
    letters = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ', k=2))
    digits  = str(random.randint(1000, 9999))
    return f"{prefix}{letters}{digits}"

# 40 regular visitors (appear frequently)
REGULARS = [make_plate() for _ in range(40)]

# 200 one-time / occasional visitors
OCCASIONALS = [make_plate() for _ in range(200)]

# Vehicle type per plate (fixed — a car owner stays a car owner)
PLATE_TYPE = {}
for p in REGULARS:
    PLATE_TYPE[p] = random.choices(['car', 'bike'], weights=[0.65, 0.35])[0]
for p in OCCASIONALS:
    PLATE_TYPE[p] = random.choices(['car', 'bike'], weights=[0.55, 0.45])[0]


# ─────────────────────────────────────────
#  HOUR WEIGHT TABLE
#  probability distribution across 24 hours
#  sum doesn't need to be 1 — we normalise
# ─────────────────────────────────────────

HOUR_WEIGHTS_WEEKDAY = [
    0.1,  # 00
    0.05, # 01
    0.02, # 02
    0.02, # 03
    0.02, # 04
    0.05, # 05
    0.3,  # 06
    0.9,  # 07  ← morning rush starts
    1.8,  # 08
    1.5,  # 09
    0.9,  # 10
    0.7,  # 11
    1.3,  # 12  ← lunch peak
    1.2,  # 13
    0.8,  # 14
    0.7,  # 15
    0.9,  # 16
    2.0,  # 17  ← evening rush
    2.2,  # 18  ← peak
    1.5,  # 19
    0.9,  # 20
    0.5,  # 21
    0.3,  # 22
    0.15, # 23
]

HOUR_WEIGHTS_WEEKEND = [
    0.1,  # 00
    0.05, # 01
    0.02, # 02
    0.02, # 03
    0.02, # 04
    0.03, # 05
    0.1,  # 06
    0.3,  # 07
    0.6,  # 08
    0.9,  # 09  ← weekend starts later
    1.2,  # 10
    1.1,  # 11
    1.5,  # 12  ← lunch
    1.4,  # 13
    1.3,  # 14
    1.2,  # 15
    1.4,  # 16
    1.8,  # 17  ← evening
    1.9,  # 18
    1.6,  # 19
    1.2,  # 20
    0.8,  # 21
    0.5,  # 22
    0.2,  # 23
]

def _normalise(weights):
    total = sum(weights)
    return [w / total for w in weights]

WD_NORM = _normalise(HOUR_WEIGHTS_WEEKDAY)
WE_NORM = _normalise(HOUR_WEIGHTS_WEEKEND)


# ─────────────────────────────────────────
#  DURATION MODEL
#  Returns stay duration in minutes
#  based on vehicle type, hour, and weekday
# ─────────────────────────────────────────

def sample_duration(vehicle_type, hour, is_weekend):
    """
    Cars stay longer. Bikes are quick.
    Morning commuters stay all day. Lunch visitors 30-90 min.
    """
    if vehicle_type == 'car':
        if 7 <= hour <= 9:                     # morning commute
            base = random.gauss(360, 60)       # ~6 hours
        elif 12 <= hour <= 13:                 # lunch
            base = random.gauss(60, 20)
        elif 17 <= hour <= 19:                 # evening
            base = random.gauss(90, 30)
        else:
            base = random.gauss(120, 40)
    else:  # bike
        if 7 <= hour <= 9:
            base = random.gauss(240, 60)       # bikes leave earlier
        elif 12 <= hour <= 13:
            base = random.gauss(45, 15)
        else:
            base = random.gauss(75, 25)

    if is_weekend:
        base *= random.uniform(0.7, 1.1)       # shorter on weekends

    return max(5, int(base))                   # minimum 5 minutes


# ─────────────────────────────────────────
#  SLOT ASSIGNMENT MODEL
#  Mirrors get_best_free_slot() in db.py
# ─────────────────────────────────────────

CAR_SLOTS  = [f'C{i}' for i in range(1, 17)]   # C1-C16
BIKE_slots = [f'B{i}' for i in range(1, 21)]   # B1-B20

def assign_slot(vehicle_type, occupied_slots):
    pool = CAR_SLOTS if vehicle_type == 'car' else BIKE_slots
    free = [s for s in pool if s not in occupied_slots]
    return free[0] if free else None             # lowest free slot


# ─────────────────────────────────────────
#  MAIN GENERATOR
# ─────────────────────────────────────────

def generate_dataset(n_days=90, output_path=OUT_PATH):
    """
    Generate n_days worth of synthetic parking sessions.

    Returns:
      list of dicts (also written to CSV)

    Each row has:
      session_id, vehicle_number, vehicle_type, slot_number,
      entry_time, exit_time, duration_minutes, status,
      hour, day_of_week, is_weekend, is_morning_rush,
      is_lunch, is_evening_rush, month, day
    """
    print(f"[GEN] Generating {n_days} days of synthetic data...")

    sessions   = []
    session_id = 1
    start_date = datetime(2024, 1, 1)

    for day_offset in range(n_days):
        current_date = start_date + timedelta(days=day_offset)
        weekday      = current_date.weekday()   # 0=Mon, 6=Sun
        is_weekend   = weekday >= 5

        # How many arrivals today?
        if is_weekend:
            n_arrivals = random.randint(25, 60)
        else:
            n_arrivals = random.randint(40, 90)

        hour_weights = WE_NORM if is_weekend else WD_NORM

        # Pick arrival hours for the day
        hours = random.choices(range(24), weights=hour_weights, k=n_arrivals)
        hours.sort()

        occupied = {}   # slot → exit_datetime (to avoid double-booking)

        for hour in hours:
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            entry_dt = current_date.replace(hour=hour, minute=minute, second=second)

            # Pick a plate (70% regular, 30% occasional)
            if random.random() < 0.70:
                plate = random.choice(REGULARS)
            else:
                plate = random.choice(OCCASIONALS)

            vehicle_type = PLATE_TYPE[plate]

            # Free up slots whose exit time has passed
            occupied = {
                slot: exit_t
                for slot, exit_t in occupied.items()
                if exit_t > entry_dt
            }

            slot = assign_slot(vehicle_type, set(occupied.keys()))
            if not slot:
                continue   # lot full — skip this arrival

            duration = sample_duration(vehicle_type, hour, is_weekend)
            exit_dt  = entry_dt + timedelta(minutes=duration)

            occupied[slot] = exit_dt

            # Derived features (these are what the ML models train on)
            is_morning_rush = 1 if 7 <= hour <= 9  else 0
            is_lunch        = 1 if 12 <= hour <= 13 else 0
            is_evening_rush = 1 if 17 <= hour <= 19 else 0

            sessions.append({
                'session_id':       session_id,
                'vehicle_number':   plate,
                'vehicle_type':     vehicle_type,
                'slot_number':      slot,
                'entry_time':       entry_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'exit_time':        exit_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'duration_minutes': duration,
                'status':           'completed',

                # ── Feature columns for ML ──
                'hour':             hour,
                'minute':           minute,
                'day_of_week':      weekday,
                'is_weekend':       int(is_weekend),
                'is_morning_rush':  is_morning_rush,
                'is_lunch':         is_lunch,
                'is_evening_rush':  is_evening_rush,
                'month':            current_date.month,
                'day':              current_date.day,
                'vehicle_type_num': 0 if vehicle_type == 'car' else 1,
            })

            session_id += 1

    # ── Write CSV ──
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = list(sessions[0].keys())

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sessions)

    print(f"[GEN] Done. {len(sessions)} sessions written to: {output_path}")
    return sessions


# ─────────────────────────────────────────
#  QUICK STATS (run directly to verify)
# ─────────────────────────────────────────

if __name__ == '__main__':
    data = generate_dataset(n_days=90)

    # Print a quick summary
    cars  = sum(1 for r in data if r['vehicle_type'] == 'car')
    bikes = sum(1 for r in data if r['vehicle_type'] == 'bike')
    avg_d = sum(r['duration_minutes'] for r in data) / len(data)

    print(f"\n── Dataset summary ──")
    print(f"  Total sessions : {len(data)}")
    print(f"  Cars           : {cars}  ({cars*100//len(data)}%)")
    print(f"  Bikes          : {bikes} ({bikes*100//len(data)}%)")
    print(f"  Avg duration   : {avg_d:.1f} min")
    print(f"  Unique plates  : {len(set(r['vehicle_number'] for r in data))}")