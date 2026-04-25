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
"""
routes/parking.py
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

def _get_analytics():
    try:
        from ml_model.analytics import (
            get_peak_prediction,
            get_duration_estimate,
            get_anomaly_flags,
            get_hourly_heatmap,
        )
        return get_peak_prediction, get_duration_estimate, get_anomaly_flags, get_hourly_heatmap
    except Exception as e:
        print(f"[ROUTES] ML analytics unavailable: {e}")
        return None, None, None, None

parking_bp = Blueprint('parking', __name__)

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static', 'uploads'
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_image(file, prefix='img'):
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

@parking_bp.route('/')
def index():
    all_slots = get_all_slots()
    counts    = get_slot_counts()
    slots_car_top  = [s for s in all_slots if s['vehicle_type'] == 'car'  and s['position'] == 'top']
    slots_car_bot  = [s for s in all_slots if s['vehicle_type'] == 'car'  and s['position'] == 'bot']
    slots_bike_top = [s for s in all_slots if s['vehicle_type'] == 'bike' and s['position'] == 'top']
    slots_bike_bot = [s for s in all_slots if s['vehicle_type'] == 'bike' and s['position'] == 'bot']
    return render_template(
        'index.html',
        slots_car_top=slots_car_top, slots_car_bot=slots_car_bot,
        slots_bike_top=slots_bike_top, slots_bike_bot=slots_bike_bot,
        total_slots=counts['total'], available_slots=counts['free'],
        occupied_slots=counts['occ'], reserved_slots=0,
        current_year=datetime.now().year,
    )

@parking_bp.route('/camera')
def camera():
    counts = get_slot_counts()
    return render_template(
        'camera.html',
        total_slots=counts['total'], available_slots=counts['free'],
        occupied_slots=counts['occ'], current_year=datetime.now().year,
    )

@parking_bp.route('/entry', methods=['POST'])
def entry():
    image_file     = request.files.get('image')
    vehicle_number = request.form.get('vehicle_number', '').strip()
    vehicle_type   = request.form.get('vehicle_type', 'car').strip()

    if image_file and image_file.filename != '':
        image_path = save_uploaded_image(image_file, prefix='entry')
        if not image_path:
            flash('Invalid image file. Use JPG or PNG.', 'error')
            return redirect(url_for('parking.camera'))
        result = process_entry(image_path)
    elif vehicle_number:
        if vehicle_type not in ('car', 'bike'):
            flash('Vehicle type must be car or bike.', 'error')
            return redirect(url_for('parking.camera'))
        result = simulate_entry(vehicle_number, vehicle_type)
    else:
        flash('Please upload an image or enter a vehicle number.', 'error')
        return redirect(url_for('parking.camera'))

    if result['success']:
        _, get_duration_estimate, _, _ = _get_analytics()
        if get_duration_estimate:
            try:
                vtype = result.get('vehicle_type', vehicle_type)
                est   = get_duration_estimate(vtype)
                result['message'] += f'  |  Expected stay: {est["predicted_str"]}'
            except Exception:
                pass
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')

    return redirect(url_for('parking.camera'))

@parking_bp.route('/exit', methods=['POST'])
def exit_gate():
    image_file     = request.files.get('image')
    vehicle_number = request.form.get('vehicle_number', '').strip()

    if image_file and image_file.filename != '':
        image_path = save_uploaded_image(image_file, prefix='exit')
        if not image_path:
            flash('Invalid image file. Use JPG or PNG.', 'error')
            return redirect(url_for('parking.camera'))
        result = process_exit(image_path)
    elif vehicle_number:
        result = simulate_exit(vehicle_number)
    else:
        flash('Please upload an image or enter a vehicle number.', 'error')
        return redirect(url_for('parking.camera'))

    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')

    return redirect(url_for('parking.camera'))

@parking_bp.route('/dashboard')
def dashboard():
    active_sessions = get_active_sessions()
    all_sessions    = get_all_sessions()
    counts          = get_slot_counts()

    get_peak_prediction, _, get_anomaly_flags, get_hourly_heatmap = _get_analytics()

    flagged_sessions = active_sessions
    if get_anomaly_flags:
        try:
            flagged_sessions = get_anomaly_flags(active_sessions)
        except Exception as e:
            print(f"[DASHBOARD] Anomaly detection error: {e}")

    peak_now = None
    if get_peak_prediction:
        try:
            peak_now = get_peak_prediction()
        except Exception as e:
            print(f"[DASHBOARD] Peak prediction error: {e}")

    heatmap_js = []
    if get_hourly_heatmap:
        try:
            heatmap_js = [
                {'hour': h['hour'], 'level': h['level'], 'confidence': h['confidence']}
                for h in get_hourly_heatmap()
            ]
        except Exception as e:
            print(f"[DASHBOARD] Heatmap error: {e}")

    return render_template(
        'dashboard.html',
        active_sessions=flagged_sessions,
        all_sessions=all_sessions,
        total_slots=counts['total'],
        available_slots=counts['free'],
        occupied_slots=counts['occ'],
        peak_now=peak_now,
        heatmap_js=heatmap_js,
        current_year=datetime.now().year,
    )

@parking_bp.route('/release', methods=['POST'])
def release():
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

@parking_bp.route('/api/slots')
def api_slots():
    counts    = get_slot_counts()
    all_slots = get_all_slots()
    return jsonify({
        'total': counts['total'],
        'free':  counts['free'],
        'occ':   counts['occ'],
        'slots': all_slots,
    })