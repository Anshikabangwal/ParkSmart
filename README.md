# ParkSmart — Smart Parking System

A camera-based automated parking management system built with Flask, OpenCV, and EasyOCR.

---

## Project Structure

```
ParkSmart/
├── database/
│   ├── __init__.py
│   └── init_db.py        # Creates tables + seeds 36 slots
├── ml_model/
│   ├── __init__.py
│   ├── ocr.py            # EasyOCR number plate reader
│   ├── predict.py        # OpenCV vehicle type detector
│   └── camera.py         # Main entry/exit pipeline
├── models/
│   ├── __init__.py
│   └── db.py             # All database query functions
├── routes/
│   ├── __init__.py
│   └── parking.py        # All Flask URL routes
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   ├── images/
│   └── uploads/          # Camera images saved here at runtime
├── templates/
│   ├── index.html        # Parking lot map
│   ├── dashboard.html    # Attendant dashboard
│   └── camera.html       # Camera gate simulation
├── app.py                # Flask entry point
├── config.py             # All configuration
├── requirements.txt      # Python dependencies
└── README.md
```

---

## Clone the Repository

> You must be added as a collaborator by the repo owner before cloning.
> Accept the invitation email from GitHub first.

```bash
git clone https://github.com/Anshikabangwal/ParkSmart.git
cd ParkSmart
```

---

## Setup Instructions

### 1. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac / Linux
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```
> Note: First run downloads ~200MB EasyOCR language models automatically. This happens only once.

### 3. Initialize database
```bash
python database/init_db.py
```
This creates `database/parking.db` with 36 slots (16 car + 20 bike).

### 4. Run the app
```bash
python app.py
```

---

## Pages

| URL | Page |
|-----|------|
| `http://localhost:5000/` | Parking lot map |
| `http://localhost:5000/camera` | Camera gate simulation |
| `http://localhost:5000/dashboard` | Attendant dashboard |
| `http://localhost:5000/api/slots` | Live JSON slot data |

---

## How It Works

### Automated Flow (with camera image)
1. Upload entry image → OpenCV detects car/bike → EasyOCR reads plate
2. System finds best free slot → creates session → marks slot occupied
3. Upload exit image → EasyOCR reads plate → finds session → calculates duration → frees slot

### Simulation Flow (without camera)
1. Go to `/camera` → use **Manual Input** tab
2. Type vehicle number + select type → click Simulate Entry
3. To exit → type same vehicle number → click Simulate Exit

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `slots` | All 36 parking slots with current status |
| `vehicles` | Every vehicle detected by entry camera |
| `sessions` | Every parking visit (entry time → exit time) |

---

## Important Notes for Collaborators

- `parking.db` is not on GitHub — run `python database/init_db.py` to create it
- `venv/` is not on GitHub — create your own virtual environment
- `static/uploads/` is empty on GitHub — images are saved here at runtime
- EasyOCR models download automatically on first run (~200MB, one time only)

---

## Tech Stack

- **Backend** — Python 3.x + Flask
- **Database** — SQLite
- **Vehicle Detection** — OpenCV
- **Plate Reading** — EasyOCR
- **Frontend** — HTML + CSS + JS (Jinja2 templates)