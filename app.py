"""
app.py
------
Main entry point for ParkSmart Smart Parking System.

HOW TO RUN:
  1. python database/init_db.py   (only once)
  2. python app.py

Then open browser:
  http://localhost:5000           → Parking lot map
  http://localhost:5000/camera    → Camera gate simulation
  http://localhost:5000/dashboard → Attendant dashboard
  http://localhost:5000/api/slots → Live JSON data
"""

from flask import Flask
from config import Config
from routes.parking import parking_bp


def create_app():
    """
    Application factory — creates and configures the Flask app.
    Keeps everything clean and testable.
    """
    app = Flask(__name__)

    # Load config from config.py
    app.config.from_object(Config)

    # Register all routes from routes/parking.py
    app.register_blueprint(parking_bp)

    return app


# ── Create app instance ──
app = create_app()


if __name__ == '__main__':
    print("=" * 48)
    print("  ParkSmart — Smart Parking System")
    print("=" * 48)
    print("  Lot Map   : http://localhost:5000/")
    print("  Camera    : http://localhost:5000/camera")
    print("  Dashboard : http://localhost:5000/dashboard")
    print("  API       : http://localhost:5000/api/slots")
    print("=" * 48)

    app.run(
        debug=app.config['DEBUG'],
        host=app.config['HOST'],
        port=app.config['PORT'],
    )