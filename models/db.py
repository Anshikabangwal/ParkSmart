"""
models/db.py
------------
All database functions for ParkSmart.
This is the ONLY file that talks to parking.db directly.
Every other file imports from here — never import sqlite3 elsewhere.

Tables handled:
  slots    → get_all_slots(), get_slot_counts(), update_slot_status()
  vehicles → get_or_create_vehicle(), get_vehicle_by_number()
  sessions → create_session(), close_session(), get_active_sessions(), get_all_sessions()
"""

import sqlite3
import os
from datetime import datetime

# ── Database path ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, 'database', 'parking.db')


def get_connection():
    """
    Return a connection to parking.db.
    row_factory = sqlite3.Row lets you use row['column_name'] instead of row[0].
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')  # enforce FK constraints
    return conn


# ════════════════════════════════════════
#  SLOT FUNCTIONS
# ════════════════════════════════════════

def get_all_slots():
    """
    Return all 36 slots as a list of dicts.
    Each dict: { slot_id, slot_number, vehicle_type, position, status }

    Called by: routes index() to render the parking lot map.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT slot_id, slot_number, vehicle_type, position, status
        FROM   slots
        ORDER  BY vehicle_type, position, slot_id
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_slot_by_id(slot_id):
    """
    Return one slot dict by its ID, or None if not found.
    Called by: create_session(), close_session()
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM slots WHERE slot_id = ?', (slot_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_best_free_slot(vehicle_type):
    """
    Find the first available slot for the given vehicle type.
    Returns a slot dict or None if the zone is full.

    Called by: camera pipeline (entry detection) to auto-assign a slot.

    Logic: picks the lowest-numbered free slot in the correct zone.
    e.g. for 'car'  → returns C1 if free, else C2, C3 ...
         for 'bike' → returns B1 if free, else B2, B3 ...
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT slot_id, slot_number, vehicle_type, position, status
        FROM   slots
        WHERE  vehicle_type = ? AND status = 'free'
        ORDER  BY slot_id
        LIMIT  1
    ''', (vehicle_type,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_slot_status(slot_id, new_status):
    """
    Change a slot's status to 'free' or 'occ'.
    Called by: create_session() and close_session()
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE slots SET status = ? WHERE slot_id = ?',
        (new_status, slot_id)
    )
    conn.commit()
    conn.close()


def get_slot_counts():
    """
    Return summary counts as a dict.
    Example: { 'total': 36, 'free': 28, 'occ': 8 }

    Called by: routes index() and dashboard() for the stats bar.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM slots")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM slots WHERE status = 'free'")
    free = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM slots WHERE status = 'occ'")
    occ = cursor.fetchone()[0]

    conn.close()
    return {'total': total, 'free': free, 'occ': occ}


# ════════════════════════════════════════
#  VEHICLE FUNCTIONS
# ════════════════════════════════════════

def get_or_create_vehicle(vehicle_number, vehicle_type, entry_image=None):
    """
    Look up a vehicle by number plate.
    If it exists → return it (repeat visitor).
    If not       → insert a new row and return it (first visit).

    Called by: camera pipeline when entry camera detects a plate.

    Returns a vehicle dict:
      { vehicle_id, vehicle_number, vehicle_type, first_seen, entry_image }
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # Check if vehicle already exists
    cursor.execute(
        'SELECT * FROM vehicles WHERE vehicle_number = ?',
        (vehicle_number.upper(),)
    )
    row = cursor.fetchone()

    if row:
        # Vehicle seen before — return existing record
        conn.close()
        return dict(row)

    # New vehicle — insert it
    cursor.execute('''
        INSERT INTO vehicles (vehicle_number, vehicle_type, first_seen, entry_image)
        VALUES (?, ?, ?, ?)
    ''', (
        vehicle_number.upper(),
        vehicle_type,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        entry_image
    ))
    conn.commit()

    # Return the newly created row
    cursor.execute(
        'SELECT * FROM vehicles WHERE vehicle_number = ?',
        (vehicle_number.upper(),)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_vehicle_by_number(vehicle_number):
    """
    Find a vehicle by its plate number.
    Returns a vehicle dict or None.

    Called by: exit camera pipeline to identify the leaving vehicle.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM vehicles WHERE vehicle_number = ?',
        (vehicle_number.upper(),)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ════════════════════════════════════════
#  SESSION FUNCTIONS
# ════════════════════════════════════════

def create_session(slot_id, vehicle_id):
    """
    Start a new parking session when a vehicle enters:
      1. Insert a new session row with entry_time = now
      2. Mark the slot as occupied

    Returns:
      session_id (int) if successful
      None if slot is already occupied

    Called by: entry camera pipeline after plate is read.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # Verify slot is still free
    cursor.execute(
        'SELECT status FROM slots WHERE slot_id = ?',
        (slot_id,)
    )
    row = cursor.fetchone()
    if not row or row['status'] != 'free':
        conn.close()
        return None

    # Create session
    entry_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO sessions (slot_id, vehicle_id, entry_time, status)
        VALUES (?, ?, ?, 'active')
    ''', (slot_id, vehicle_id, entry_time))

    session_id = cursor.lastrowid

    # Mark slot as occupied
    cursor.execute(
        "UPDATE slots SET status = 'occ' WHERE slot_id = ?",
        (slot_id,)
    )

    conn.commit()
    conn.close()
    return session_id


def close_session(vehicle_number, exit_image=None):
    """
    End a parking session when a vehicle exits:
      1. Find the active session for this vehicle
      2. Set exit_time = now
      3. Calculate duration_minutes
      4. Mark session as 'completed'
      5. Free the slot

    Returns a dict with session summary, or None if no active session found.

    Called by: exit camera pipeline after plate is read.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # Find active session for this vehicle
    cursor.execute('''
        SELECT
            s.session_id,
            s.slot_id,
            s.entry_time,
            v.vehicle_number,
            sl.slot_number
        FROM   sessions s
        JOIN   vehicles v  ON s.vehicle_id  = v.vehicle_id
        JOIN   slots    sl ON s.slot_id     = sl.slot_id
        WHERE  v.vehicle_number = ?
        AND    s.status = 'active'
    ''', (vehicle_number.upper(),))

    session = cursor.fetchone()

    if not session:
        conn.close()
        return None

    # Calculate duration
    exit_time  = datetime.now()
    entry_time = datetime.strptime(session['entry_time'], '%Y-%m-%d %H:%M:%S')
    duration   = int((exit_time - entry_time).total_seconds() / 60)

    exit_time_str = exit_time.strftime('%Y-%m-%d %H:%M:%S')

    # Update session
    cursor.execute('''
        UPDATE sessions
        SET    exit_time        = ?,
               duration_minutes = ?,
               exit_image       = ?,
               status           = 'completed'
        WHERE  session_id = ?
    ''', (exit_time_str, duration, exit_image, session['session_id']))

    # Free the slot
    cursor.execute(
        "UPDATE slots SET status = 'free' WHERE slot_id = ?",
        (session['slot_id'],)
    )

    conn.commit()
    conn.close()

    return {
        'session_id':       session['session_id'],
        'slot_number':      session['slot_number'],
        'vehicle_number':   vehicle_number.upper(),
        'entry_time':       session['entry_time'],
        'exit_time':        exit_time_str,
        'duration_minutes': duration,
    }


def get_active_sessions():
    """
    Return all currently active sessions (vehicles parked right now).
    Each row: { session_id, slot_number, vehicle_number,
                vehicle_type, entry_time, slot_id, vehicle_id }

    Called by: dashboard route to show currently parked vehicles.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            s.session_id,
            sl.slot_number,
            sl.slot_id,
            v.vehicle_number,
            v.vehicle_type,
            v.vehicle_id,
            s.entry_time
        FROM   sessions s
        JOIN   vehicles v  ON s.vehicle_id = v.vehicle_id
        JOIN   slots    sl ON s.slot_id    = sl.slot_id
        WHERE  s.status = 'active'
        ORDER  BY s.entry_time DESC
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_all_sessions():
    """
    Return full session history (all visits ever).
    Each row includes slot, vehicle, times, duration, status.

    Called by: dashboard route for the history table.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            s.session_id,
            sl.slot_number,
            v.vehicle_number,
            v.vehicle_type,
            s.entry_time,
            s.exit_time,
            s.duration_minutes,
            s.status
        FROM   sessions s
        JOIN   vehicles v  ON s.vehicle_id = v.vehicle_id
        JOIN   slots    sl ON s.slot_id    = sl.slot_id
        ORDER  BY s.entry_time DESC
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def is_vehicle_parked(vehicle_number):
    """
    Check if a vehicle is currently parked (has active session).
    Returns the active session dict or None.

    Called by: entry pipeline to prevent double booking same vehicle.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.session_id, sl.slot_number, s.entry_time
        FROM   sessions s
        JOIN   vehicles v  ON s.vehicle_id = v.vehicle_id
        JOIN   slots    sl ON s.slot_id    = sl.slot_id
        WHERE  v.vehicle_number = ?
        AND    s.status = 'active'
    ''', (vehicle_number.upper(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None