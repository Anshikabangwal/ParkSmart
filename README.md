# ParkSmart — Smart Parking Management System

A smart parking management system built using **Flask, OpenCV, EasyOCR, SQLite, and Machine Learning** to automate vehicle entry/exit, parking slot allocation, number plate recognition, and parking analytics.

---

## Features

- Vehicle entry and exit simulation
- Automatic parking slot allocation
- Number plate recognition using OCR
- Vehicle type detection (Car/Bike)
- Parking duration prediction
- Peak hour traffic prediction
- Anomaly/overstay detection
- Live parking dashboard
- Manual simulation mode

---

## Project Structure

```bash
ParkSmart/
│
├── __pycache__/
│
├── database/
│   ├── models/                 # Trained ML models
│   ├── __init__.py
│   ├── init_db.py              # Database initialization
│   ├── parking_data.csv        # Training dataset
│   └── parking.db              # SQLite database
│
├── ml_model/
│   ├── __pycache__/
│   ├── __init__.py
│   ├── analytics.py            # ML model training
│   ├── camera.py               # Camera simulation logic
│   ├── generate_data.py        # Synthetic dataset generator
│   ├── ocr.py                  # Number plate recognition
│   └── predict.py              # Vehicle type prediction
│
├── models/
│   ├── __pycache__/
│   ├── __init__.py
│   └── db.py                   # Database operations
│
├── routes/
│   ├── __pycache__/
│   ├── __init__.py
│   └── parking.py              # Flask routes
│
├── static/
│   ├── css/
│   ├── images/
│   ├── js/
│   └── uploads/                # Uploaded vehicle images
│
├── templates/
│   ├── camera.html
│   ├── dashboard.html
│   └── index.html
│
├── venv/
├── .gitignore
├── app.py                      # Main Flask app
├── config.py                   # Configuration file
├── README.md
└── requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|------|------------|
| Backend | Python, Flask |
| Database | SQLite |
| Computer Vision | OpenCV |
| OCR | EasyOCR |
| Machine Learning | Scikit-learn |
| Frontend | HTML, CSS, JavaScript |

---

## Machine Learning Models Used

### 1. Peak Hour Predictor
Predicts parking occupancy level.

- **Algorithm:** Random Forest Classifier
- **Input:** Hour, day, weekend
- **Output:** Low / Medium / High traffic

---

### 2. Parking Duration Predictor
Estimates how long a vehicle may stay parked.

- **Algorithm:** Random Forest Regressor
- **Input:** Vehicle type, entry hour, weekday/weekend
- **Output:** Predicted parking duration

---

### 3. Anomaly Detector
Detects overstayed or unusual parking sessions.

- **Algorithm:** Isolation Forest
- **Input:** Duration, vehicle type, entry time
- **Output:** Normal / Anomaly

---

## Installation

### Clone Repository
```bash
git clone https://github.com/Anshikabangwal/ParkSmart.git
cd ParkSmart
```

### Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Run Project

### Initialize Database
```bash
python database/init_db.py
```

### Generate Dataset
```bash
python ml_model/generate_data.py
```

### Train Models
```bash
python ml_model/analytics.py
```

### Run Flask App
```bash
python app.py
```

---

## Application Pages

| Route | Description |
|------|-------------|
| `/` | Home page / Parking slots |
| `/camera` | Camera simulation |
| `/dashboard` | Analytics dashboard |

---

## Working Flow

### Entry Process
1. Upload vehicle image or enter manually
2. Detect vehicle type
3. Read number plate
4. Predict duration
5. Assign parking slot

### Exit Process
1. Upload exit image or enter manually
2. Match number plate
3. Calculate duration
4. Free parking slot

---

## Database Tables

### slots
Stores parking slot information.

### vehicles
Stores detected vehicle details.

### sessions
Stores entry and exit sessions.

---

## Future Enhancements

- Real-time CCTV integration
- Payment gateway
- QR-based booking
- Mobile app integration
- Email/SMS alerts

---

## Author

**Anshika Bangwal**

GitHub: https://github.com/Anshikabangwal
