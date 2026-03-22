"""
database/init_db.py
-------------------
Run this file ONCE to set up the entire database.

Creates 3 tables:
  1. slots    — all 36 parking slots (16 car + 20 bike)
  2. vehicles — every vehicle detected by entry camera
  3. sessions — every parking session (entry to exit)

HOW TO RUN:
  python database/init_db.py
"""

import sqlite3
import os

# ── Path setup ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'parking.db')


def get_connection():
    """
    Open and return a connection to parking.db.
    row_factory lets you access columns by name: row['slot_number']
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn):
    """Create all 3 tables if they don't exist yet."""
    cursor = conn.cursor()

    # ── TABLE 1: slots ──
    # Stores every physical parking slot in the lot.
    # Status changes when a vehicle arrives or leaves.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS slots (
            slot_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number  TEXT    NOT NULL UNIQUE,
            vehicle_type TEXT    NOT NULL CHECK(vehicle_type IN ('car', 'bike')),
            position     TEXT    NOT NULL CHECK(position    IN ('top', 'bot')),
            status       TEXT    NOT NULL DEFAULT 'free'
                                 CHECK(status IN ('free', 'occ'))
        )
    ''')

    # ── TABLE 2: vehicles ──
    # One row per unique vehicle ever detected by the entry camera.
    # vehicle_number = number plate read by EasyOCR
    # vehicle_type   = 'car' or 'bike' detected by OpenCV
    # first_seen     = timestamp of first ever detection
    # entry_image    = file path of the camera frame that detected it
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_number TEXT    NOT NULL UNIQUE,
            vehicle_type   TEXT    NOT NULL CHECK(vehicle_type IN ('car', 'bike')),
            first_seen     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            entry_image    TEXT
        )
    ''')

    # ── TABLE 3: sessions ──
    # One row per parking visit (entry to exit).
    # A vehicle can have many sessions over time (many visits).
    # A slot can have many sessions over time (many cars parked there).
    # entry_time      = auto-filled when entry camera detects vehicle
    # exit_time       = auto-filled when exit camera detects same plate
    # duration_minutes= calculated as exit_time - entry_time
    # exit_image      = file path of exit camera frame
    # status: 'active'    = vehicle currently parked
    #         'completed' = vehicle exited, slot freed
    #         'flagged'   = stayed too long (future feature)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_id          INTEGER NOT NULL,
            vehicle_id       INTEGER NOT NULL,
            entry_time       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            exit_time        TEXT,
            duration_minutes INTEGER,
            exit_image       TEXT,
            status           TEXT    NOT NULL DEFAULT 'active'
                                     CHECK(status IN ('active', 'completed', 'flagged')),
            FOREIGN KEY (slot_id)   REFERENCES slots(slot_id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
        )
    ''')

    conn.commit()
    print("[OK] All 3 tables created.")


def seed_slots(conn):
    """
    Insert 36 default slots only if the table is empty.

    Layout:
      Car zone  — C1–C8  (top row) + C9–C16  (bottom row) = 16 slots
      Bike zone — B1–B10 (top row) + B11–B20 (bottom row) = 20 slots
    """
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM slots')
    if cursor.fetchone()[0] > 0:
        print("[SKIP] Slots already exist. Skipping seed.")
        return

    slots = []

    # Car slots — top row
    for i in range(1, 9):
        slots.append((f'C{i}', 'car', 'top', 'free'))

    # Car slots — bottom row
    for i in range(9, 17):
        slots.append((f'C{i}', 'car', 'bot', 'free'))

    # Bike slots — top row
    for i in range(1, 11):
        slots.append((f'B{i}', 'bike', 'top', 'free'))

    # Bike slots — bottom row
    for i in range(11, 21):
        slots.append((f'B{i}', 'bike', 'bot', 'free'))

    cursor.executemany(
        'INSERT INTO slots (slot_number, vehicle_type, position, status) VALUES (?,?,?,?)',
        slots
    )
    conn.commit()
    print(f"[OK] {len(slots)} slots inserted.")
    print("      Car  : C1–C16  (16 slots)")
    print("      Bike : B1–B20  (20 slots)")


def main():
    print("=" * 45)
    print("  ParkSmart — Database Initializer")
    print("=" * 45)
    print(f"  DB path : {DB_PATH}")
    print()

    conn = get_connection()
    create_tables(conn)
    seed_slots(conn)
    conn.close()

    print()
    print("[DONE] Database ready. Run: python app.py")
    print("=" * 45)


if __name__ == '__main__':
    main()