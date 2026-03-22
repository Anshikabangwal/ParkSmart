"""
routes/parking.py
-----------------
All URL routes for ParkSmart.

URL MAP:
  GET  /              → index()     Parking lot map
  GET  /dashboard     → dashboard() Attendant dashboard
  GET  /camera        → camera()    Camera simulation page
  POST /entry         → entry()     Entry gate — image upload OR simulation
  POST /exit          → exit()      Exit gate  — image upload OR simulation
  POST /release       → release()   Manual release from dashboard
  GET  /api/slots     → api_slots() JSON slot data for auto-refresh
"""

import os
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, jsonify
)
from datetime import datetime
from models.db import (
    get_all_slots,
    get_slot_counts,
    get_slot_by_id,
    get_active_sessions,
    get_all_sessions,
    close_session,
)
from ml_model.camera import (
    process_entry,
    process_exit,
    simulate_entry,
    simulate_exit,
)

# ── Blueprint ──
parking_bp = Blueprint('parking', __name__)

# ── Upload folder ──
# Uploaded camera images are saved here temporarily
UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static', 'uploads'
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def allowed_file(filename):
    """Check if uploaded file has an allowed image extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file, prefix='img'):
    """
    Save an uploaded image to static/uploads/ with a timestamp name.
    Returns the saved file path or None if save failed.
    """
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None

    ext       = file.filename.rsplit('.', 1)[1].lower()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename  = f'{prefix}_{timestamp}.{ext}'
    filepath  = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return filepath


# ════════════════════════════════════════
#  HOME — Parking Lot Map
#  URL: GET /
# ════════════════════════════════════════
@parking_bp.route('/')
def index():
    """
    Main page — shows the visual parking lot map.
    Splits slots into 4 groups for the template.
    """
    all_slots = get_all_slots()
    counts    = get_slot_counts()

    slots_car_top  = [s for s in all_slots if s['vehicle_type'] == 'car'  and s['position'] == 'top']
    slots_car_bot  = [s for s in all_slots if s['vehicle_type'] == 'car'  and s['position'] == 'bot']
    slots_bike_top = [s for s in all_slots if s['vehicle_type'] == 'bike' and s['position'] == 'top']
    slots_bike_bot = [s for s in all_slots if s['vehicle_type'] == 'bike' and s['position'] == 'bot']

    return render_template(
        'index.html',
        slots_car_top  = slots_car_top,
        slots_car_bot  = slots_car_bot,
        slots_bike_top = slots_bike_top,
        slots_bike_bot = slots_bike_bot,
        total_slots     = counts['total'],
        available_slots = counts['free'],
        occupied_slots  = counts['occ'],
        reserved_slots  = 0,
        current_year    = datetime.now().year,
    )


# ════════════════════════════════════════
#  CAMERA PAGE
#  URL: GET /camera
# ════════════════════════════════════════
@parking_bp.route('/camera')
def camera():
    """
    Camera simulation page.
    Attendant uploads an image here to simulate entry or exit.
    Renders: templates/camera.html
    """
    counts = get_slot_counts()
    return render_template(
        'camera.html',
        total_slots     = counts['total'],
        available_slots = counts['free'],
        occupied_slots  = counts['occ'],
        current_year    = datetime.now().year,
    )


# ════════════════════════════════════════
#  ENTRY GATE
#  URL: POST /entry
# ════════════════════════════════════════
@parking_bp.route('/entry', methods=['POST'])
def entry():
    """
    Handles vehicle entry — two modes:

    MODE 1 — Image upload (real camera simulation):
      Form sends: image file
      Pipeline:   detect type → read plate → assign slot → create session

    MODE 2 — Manual simulation (no image, for testing):
      Form sends: vehicle_number + vehicle_type (text fields)
      Pipeline:   skips OCR/detection → directly assigns slot

    Mode is decided by checking if an image file was uploaded.
    After processing, redirects to /camera with flash message.
    """
    image_file     = request.files.get('image')
    vehicle_number = request.form.get('vehicle_number', '').strip()
    vehicle_type   = request.form.get('vehicle_type', 'car').strip()

    # ── MODE 1: Image uploaded ──
    if image_file and image_file.filename != '':
        image_path = save_uploaded_image(image_file, prefix='entry')

        if not image_path:
            flash('Invalid image file. Use JPG or PNG.', 'error')
            return redirect(url_for('parking.camera'))

        result = process_entry(image_path)

    # ── MODE 2: Manual simulation ──
    elif vehicle_number:
        if vehicle_type not in ('car', 'bike'):
            flash('Vehicle type must be car or bike.', 'error')
            return redirect(url_for('parking.camera'))

        result = simulate_entry(vehicle_number, vehicle_type)

    else:
        flash('Please upload an image or enter a vehicle number.', 'error')
        return redirect(url_for('parking.camera'))

    # ── Flash result ──
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')

    return redirect(url_for('parking.camera'))


# ════════════════════════════════════════
#  EXIT GATE
#  URL: POST /exit
# ════════════════════════════════════════
@parking_bp.route('/exit', methods=['POST'])
def exit_gate():
    """
    Handles vehicle exit — two modes:

    MODE 1 — Image upload:
      OCR reads the plate → finds active session → closes it

    MODE 2 — Manual simulation:
      Vehicle number typed in → finds session → closes it

    After processing, redirects to /camera with flash message
    showing slot number and duration parked.
    """
    image_file     = request.files.get('image')
    vehicle_number = request.form.get('vehicle_number', '').strip()

    # ── MODE 1: Image uploaded ──
    if image_file and image_file.filename != '':
        image_path = save_uploaded_image(image_file, prefix='exit')

        if not image_path:
            flash('Invalid image file. Use JPG or PNG.', 'error')
            return redirect(url_for('parking.camera'))

        result = process_exit(image_path)

    # ── MODE 2: Manual simulation ──
    elif vehicle_number:
        result = simulate_exit(vehicle_number)

    else:
        flash('Please upload an image or enter a vehicle number.', 'error')
        return redirect(url_for('parking.camera'))

    # ── Flash result ──
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')

    return redirect(url_for('parking.camera'))


# ════════════════════════════════════════
#  DASHBOARD
#  URL: GET /dashboard
# ════════════════════════════════════════
@parking_bp.route('/dashboard')
def dashboard():
    """
    Attendant dashboard showing:
      - Currently active sessions (vehicles parked right now)
      - Full session history
    Renders: templates/dashboard.html
    """
    active_sessions = get_active_sessions()
    all_sessions    = get_all_sessions()
    counts          = get_slot_counts()

    return render_template(
        'dashboard.html',
        active_sessions = active_sessions,
        all_sessions    = all_sessions,
        total_slots     = counts['total'],
        available_slots = counts['free'],
        occupied_slots  = counts['occ'],
        current_year    = datetime.now().year,
    )


# ════════════════════════════════════════
#  MANUAL RELEASE
#  URL: POST /release
# ════════════════════════════════════════
@parking_bp.route('/release', methods=['POST'])
def release():
    """
    Manually release a slot from the dashboard.
    Used when a vehicle exits without triggering exit camera.

    Form field: vehicle_number
    """
    vehicle_number = request.form.get('vehicle_number', '').strip()

    if not vehicle_number:
        flash('Vehicle number is required.', 'error')
        return redirect(url_for('parking.dashboard'))

    result = simulate_exit(vehicle_number)

    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')

    return redirect(url_for('parking.dashboard'))


# ════════════════════════════════════════
#  SLOTS API — JSON
#  URL: GET /api/slots
# ════════════════════════════════════════
@parking_bp.route('/api/slots')
def api_slots():
    """
    Returns live slot data as JSON.
    Used by index.html to auto-refresh the map every 30s
    without reloading the full page.

    Response:
    {
      "total": 36, "free": 28, "occ": 8,
      "slots": [ { slot_id, slot_number, status, ... }, ... ]
    }
    """
    counts    = get_slot_counts()
    all_slots = get_all_slots()

    return jsonify({
        'total': counts['total'],
        'free':  counts['free'],
        'occ':   counts['occ'],
        'slots': all_slots,
    })