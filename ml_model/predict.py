"""
ml_model/predict.py
-------------------
Detects vehicle type (car or bike) from an image using OpenCV.

We use a simple but effective approach:
  - Detect the vehicle's bounding box using background subtraction or contours
  - Calculate the aspect ratio (width / height) of the detected object
  - Cars are wider and taller → larger area, wider bounding box
  - Bikes are narrower → smaller area, taller aspect ratio

No deep learning model needed for this basic classification.
For better accuracy later, you can swap this with a YOLOv5 model.

INSTALL:
  pip install opencv-python numpy pillow
"""

import cv2
import numpy as np
import os


def load_image(image_path):
    """
    Load an image from file path.
    Returns a numpy array (BGR) or None if file not found.
    """
    if not os.path.exists(image_path):
        print(f"[PREDICT] Image not found: {image_path}")
        return None

    img = cv2.imread(image_path)
    if img is None:
        print(f"[PREDICT] Could not read image: {image_path}")
        return None

    return img


def preprocess(image):
    """
    Prepare image for analysis:
      1. Convert to grayscale (removes colour noise)
      2. Apply Gaussian blur (smooths edges)
      3. Apply threshold (makes vehicle stand out as white on black)

    Returns the thresholded binary image.
    """
    gray      = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred   = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY)
    return thresh


def get_largest_contour(thresh_image):
    """
    Find contours in the thresholded image.
    Return the largest contour — assumed to be the vehicle.

    Contours are outlines of shapes found in the image.
    The vehicle is the biggest shape, so we take the largest contour.
    """
    contours, _ = cv2.findContours(
        thresh_image,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return None

    # Pick the largest contour by area
    largest = max(contours, key=cv2.contourArea)
    return largest


def classify_by_aspect_ratio(contour, image_shape):
    """
    Classify vehicle as 'car' or 'bike' based on bounding box shape.

    How it works:
      - Get the bounding rectangle of the largest contour
      - Calculate aspect_ratio = width / height
      - Calculate area_ratio   = bounding_box_area / total_image_area

      Cars:
        aspect_ratio > 1.2  (wider than tall)
        area_ratio   > 0.15 (takes up significant portion of image)

      Bikes:
        aspect_ratio <= 1.2 (narrower, more upright)
        area_ratio   <= 0.15 (smaller footprint)

    Returns 'car' or 'bike'
    """
    x, y, w, h = cv2.boundingRect(contour)

    aspect_ratio = w / h if h > 0 else 1.0
    area         = w * h
    image_area   = image_shape[0] * image_shape[1]
    area_ratio   = area / image_area if image_area > 0 else 0.0

    print(f"[PREDICT] aspect_ratio={aspect_ratio:.2f}  area_ratio={area_ratio:.2f}")

    # Classification rules
    if aspect_ratio > 1.2 and area_ratio > 0.10:
        return 'car'
    else:
        return 'bike'


def detect_vehicle_type(image_path):
    """
    Main function — detect vehicle type from an image file.

    Args:
      image_path (str): path to uploaded image

    Returns:
      'car'  — if a car/SUV/van detected
      'bike' — if a motorbike/scooter detected
      'unknown' — if detection fails

    Called by: ml_model/camera.py entry pipeline
    """
    image = load_image(image_path)
    if image is None:
        return 'unknown'

    thresh   = preprocess(image)
    contour  = get_largest_contour(thresh)

    if contour is None:
        print("[PREDICT] No contour found. Defaulting to 'car'.")
        return 'car'

    vehicle_type = classify_by_aspect_ratio(contour, image.shape)
    print(f"[PREDICT] Vehicle type: {vehicle_type}")
    return vehicle_type


def detect_vehicle_type_from_array(image_array):
    """
    Detect vehicle type from a numpy array (e.g. OpenCV video frame).

    Args:
      image_array: numpy BGR array from cv2.VideoCapture

    Returns:
      'car', 'bike', or 'unknown'

    Called by: live video processing pipeline (future feature)
    """
    if image_array is None:
        return 'unknown'

    thresh  = preprocess(image_array)
    contour = get_largest_contour(thresh)

    if contour is None:
        return 'car'

    vehicle_type = classify_by_aspect_ratio(contour, image_array.shape)
    return vehicle_type


def draw_detection(image_path, output_path=None):
    """
    Draw bounding box and label on the image for visual debugging.
    Saves annotated image to output_path (or overwrites input if not given).

    Useful for testing: lets you see what OpenCV detected.

    Args:
      image_path  (str): input image path
      output_path (str): where to save annotated image (optional)

    Returns:
      vehicle_type (str)
    """
    image = load_image(image_path)
    if image is None:
        return 'unknown'

    thresh   = preprocess(image)
    contour  = get_largest_contour(thresh)

    if contour is None:
        return 'car'

    vehicle_type = classify_by_aspect_ratio(contour, image.shape)

    # Draw bounding box
    x, y, w, h = cv2.boundingRect(contour)
    colour      = (0, 200, 100) if vehicle_type == 'car' else (0, 140, 255)
    cv2.rectangle(image, (x, y), (x + w, y + h), colour, 2)
    cv2.putText(
        image,
        vehicle_type.upper(),
        (x, y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        colour,
        2
    )

    save_path = output_path or image_path
    cv2.imwrite(save_path, image)
    print(f"[PREDICT] Annotated image saved: {save_path}")

    return vehicle_type