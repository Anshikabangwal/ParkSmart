"""
ml_model/camera.py
------------------
Main camera pipeline for ParkSmart.
Connects OCR (plate reading) + prediction (vehicle type) + database.

Two main functions:
  process_entry(image_path) → called when entry camera captures a vehicle
  process_exit(image_path)  → called when exit camera captures a vehicle

Both return a result dict that routes/parking.py uses to respond to the user.

Flow:
  ENTRY:
    image → detect vehicle type → read plate → check if already parked
    → find best free slot → create session → mark slot occupied
    → return result

  EXIT:
    image → read plate → find active session
    → close session → calculate duration → free slot
    → return result
"""

import os
from ml_model.predict import detect_vehicle_type
from ml_model.ocr     import read_plate_from_image
from models.db        import (
    get_or_create_vehicle,
    get_best_free_slot,
    create_session,
    close_session,
    is_vehicle_parked,
)


def process_entry(image_path):
    """
    Full entry pipeline — called when a vehicle arrives at entry gate.

    Args:
      image_path (str): path to the uploaded/captured image

    Returns a dict:
      On success:
        {
          'success':      True,
          'vehicle_number': 'UP80AB1234',
          'vehicle_type': 'car',
          'slot_number':  'C3',
          'slot_id':      3,
          'session_id':   7,
          'message':      'Vehicle UP80AB1234 assigned to slot C3'
        }
      On failure:
        {
          'success': False,
          'message': reason for failure
        }
    """
    print(f"\n[ENTRY] Processing image: {image_path}")

    # ── Step 1: Detect vehicle type ──
    vehicle_type = detect_vehicle_type(image_path)
    if vehicle_type == 'unknown':
        return {
            'success': False,
            'message': 'Could not detect vehicle type from image.'
        }
    print(f"[ENTRY] Vehicle type: {vehicle_type}")

    # ── Step 2: Read number plate ──
    vehicle_number = read_plate_from_image(image_path)
    if not vehicle_number:
        return {
            'success': False,
            'message': 'Could not read number plate from image. Please try again.'
        }
    print(f"[ENTRY] Plate: {vehicle_number}")

    # ── Step 3: Check if vehicle is already parked ──
    existing = is_vehicle_parked(vehicle_number)
    if existing:
        return {
            'success': False,
            'message': f'Vehicle {vehicle_number} is already parked at slot {existing["slot_number"]}.'
        }

    # ── Step 4: Find the best available slot ──
    slot = get_best_free_slot(vehicle_type)
    if not slot:
        return {
            'success': False,
            'message': f'No free slots available for {vehicle_type}. Parking lot is full!'
        }
    print(f"[ENTRY] Assigned slot: {slot['slot_number']}")

    # ── Step 5: Get or create vehicle record ──
    vehicle = get_or_create_vehicle(
        vehicle_number = vehicle_number,
        vehicle_type   = vehicle_type,
        entry_image    = image_path
    )

    # ── Step 6: Create session (marks slot as occupied) ──
    session_id = create_session(
        slot_id    = slot['slot_id'],
        vehicle_id = vehicle['vehicle_id']
    )

    if not session_id:
        return {
            'success': False,
            'message': f'Slot {slot["slot_number"]} was just taken. Please retry.'
        }

    print(f"[ENTRY] Session {session_id} created. Slot {slot['slot_number']} is now occupied.")

    return {
        'success':        True,
        'vehicle_number': vehicle_number,
        'vehicle_type':   vehicle_type,
        'slot_number':    slot['slot_number'],
        'slot_id':        slot['slot_id'],
        'session_id':     session_id,
        'message':        f'Vehicle {vehicle_number} assigned to slot {slot["slot_number"]}'
    }


def process_exit(image_path):
    """
    Full exit pipeline — called when a vehicle leaves at exit gate.

    Args:
      image_path (str): path to the uploaded/captured image

    Returns a dict:
      On success:
        {
          'success':          True,
          'vehicle_number':   'UP80AB1234',
          'slot_number':      'C3',
          'entry_time':       '2024-03-21 10:30:00',
          'exit_time':        '2024-03-21 12:45:00',
          'duration_minutes': 135,
          'message':          'Vehicle UP80AB1234 exited. Slot C3 is now free.'
        }
      On failure:
        {
          'success': False,
          'message': reason for failure
        }
    """
    print(f"\n[EXIT] Processing image: {image_path}")

    # ── Step 1: Read number plate ──
    vehicle_number = read_plate_from_image(image_path)
    if not vehicle_number:
        return {
            'success': False,
            'message': 'Could not read number plate from image. Please try again.'
        }
    print(f"[EXIT] Plate: {vehicle_number}")

    # ── Step 2: Close the active session ──
    result = close_session(
        vehicle_number = vehicle_number,
        exit_image     = image_path
    )

    if not result:
        return {
            'success': False,
            'message': f'No active parking session found for vehicle {vehicle_number}.'
        }

    duration_minutes = result['duration_minutes']
    hours   = duration_minutes // 60
    minutes = duration_minutes %  60

    duration_str = f'{hours}h {minutes}m' if hours > 0 else f'{minutes}m'

    print(f"[EXIT] Session closed. Slot {result['slot_number']} is now free.")
    print(f"[EXIT] Duration: {duration_str}")

    return {
        'success':          True,
        'vehicle_number':   vehicle_number,
        'slot_number':      result['slot_number'],
        'entry_time':       result['entry_time'],
        'exit_time':        result['exit_time'],
        'duration_minutes': duration_minutes,
        'duration_str':     duration_str,
        'message':          f'Vehicle {vehicle_number} exited. Slot {result["slot_number"]} is now free. Duration: {duration_str}'
    }


def simulate_entry(vehicle_number, vehicle_type):
    """
    Simulate entry WITHOUT an image — for testing purposes.
    Skips OCR and detection, uses provided values directly.

    Args:
      vehicle_number (str): e.g. 'UP80AB1234'
      vehicle_type   (str): 'car' or 'bike'

    Returns same dict as process_entry()

    Called by: /entry route when simulation mode is on.
    """
    print(f"\n[SIM-ENTRY] vehicle={vehicle_number}  type={vehicle_type}")

    # Check if already parked
    existing = is_vehicle_parked(vehicle_number)
    if existing:
        return {
            'success': False,
            'message': f'Vehicle {vehicle_number} is already parked at slot {existing["slot_number"]}.'
        }

    # Find best free slot
    slot = get_best_free_slot(vehicle_type)
    if not slot:
        return {
            'success': False,
            'message': f'No free {vehicle_type} slots available.'
        }

    # Get or create vehicle
    vehicle = get_or_create_vehicle(
        vehicle_number = vehicle_number,
        vehicle_type   = vehicle_type,
        entry_image    = None
    )

    # Create session
    session_id = create_session(
        slot_id    = slot['slot_id'],
        vehicle_id = vehicle['vehicle_id']
    )

    if not session_id:
        return {
            'success': False,
            'message': f'Slot {slot["slot_number"]} was just taken. Retry.'
        }

    return {
        'success':        True,
        'vehicle_number': vehicle_number,
        'vehicle_type':   vehicle_type,
        'slot_number':    slot['slot_number'],
        'slot_id':        slot['slot_id'],
        'session_id':     session_id,
        'message':        f'Vehicle {vehicle_number} assigned to slot {slot["slot_number"]}'
    }


def simulate_exit(vehicle_number):
    """
    Simulate exit WITHOUT an image — for testing purposes.
    Skips OCR, uses provided vehicle number directly.

    Args:
      vehicle_number (str): e.g. 'UP80AB1234'

    Returns same dict as process_exit()

    Called by: /exit route when simulation mode is on.
    """
    print(f"\n[SIM-EXIT] vehicle={vehicle_number}")

    result = close_session(
        vehicle_number = vehicle_number,
        exit_image     = None
    )

    if not result:
        return {
            'success': False,
            'message': f'No active session found for {vehicle_number}.'
        }

    duration_minutes = result['duration_minutes']
    hours   = duration_minutes // 60
    minutes = duration_minutes %  60
    duration_str = f'{hours}h {minutes}m' if hours > 0 else f'{minutes}m'

    return {
        'success':          True,
        'vehicle_number':   vehicle_number,
        'slot_number':      result['slot_number'],
        'entry_time':       result['entry_time'],
        'exit_time':        result['exit_time'],
        'duration_minutes': duration_minutes,
        'duration_str':     duration_str,
        'message':          f'Vehicle {vehicle_number} exited. Slot {result["slot_number"]} free. Duration: {duration_str}'
    }