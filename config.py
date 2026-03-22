"""
config.py
---------
All configuration settings for ParkSmart.
Change values here — never hardcode them inside app.py or routes.

To use in app:
  app.config.from_object(Config)
  app.config['SECRET_KEY']
"""

import os

class Config:
    # ── Flask ──
    # Secret key is required for flash messages (session-based)
    # Change this to any long random string before sharing/deploying
    SECRET_KEY = os.environ.get('SECRET_KEY', 'parksmart_dev_secret_2024')

    # Debug mode — True shows detailed errors in browser
    # Set to False before deploying to production
    DEBUG = True

    # Server host and port
    HOST = '0.0.0.0'   # 0.0.0.0 = accessible on local network
    PORT = 5000

    # ── Database ──
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH  = os.path.join(BASE_DIR, 'database', 'parking.db')

    # ── File uploads ──
    UPLOAD_FOLDER   = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

    # ── Parking lot layout ──
    # Total slots (used for validation)
    TOTAL_CAR_SLOTS  = 16   # C1–C16
    TOTAL_BIKE_SLOTS = 20   # B1–B20
    TOTAL_SLOTS      = TOTAL_CAR_SLOTS + TOTAL_BIKE_SLOTS  # 36

    # ── Auto-refresh interval (milliseconds) ──
    # How often the lot map refreshes in the browser
    REFRESH_INTERVAL = 30000  # 30 seconds