"""
ml_model/ocr.py
---------------
Reads vehicle number plates from images using EasyOCR.

EasyOCR works fully offline after first run.
First run downloads ~100MB language models automatically.

INSTALL:
  pip install easyocr pillow

HOW IT WORKS:
  1. Load image (from file path or numpy array)
  2. EasyOCR scans the image for text
  3. We clean the result — remove spaces, uppercase
  4. Return the most likely plate number
"""

import re
import os

# EasyOCR is imported lazily (only when needed)
# so Flask starts fast even if OCR is not used immediately
_reader = None


def get_reader():
    """
    Load EasyOCR reader once and reuse it.
    Loading takes ~3 seconds on first call.
    After that it is cached in _reader.
    """
    global _reader
    if _reader is None:
        import easyocr
        # 'en' = English language model
        # gpu=False → use CPU (safe default, works on all machines)
        _reader = easyocr.Reader(['en'], gpu=False)
        print("[OCR] EasyOCR reader loaded.")
    return _reader


def clean_plate(text):
    """
    Clean raw OCR text into a standard plate format.

    Raw OCR output is messy: 'UP- 80 A B12 34' or 'up80ab1234'
    We want: 'UP80AB1234'

    Steps:
      1. Uppercase everything
      2. Remove all non-alphanumeric characters (spaces, dashes, dots)
      3. Return cleaned string
    """
    text = text.upper()
    text = re.sub(r'[^A-Z0-9]', '', text)
    return text


def is_valid_plate(text):
    """
    Basic check: is this string a plausible Indian number plate?

    Indian plates are typically 8–10 characters.
    Examples: UP80AB1234, MH12DE1433, DL3CAF0001

    We accept anything 6–12 chars after cleaning.
    Returns True or False.
    """
    return 6 <= len(text) <= 12


def read_plate_from_image(image_path):
    """
    Main function — read number plate from an image file.

    Args:
      image_path (str): path to the uploaded image file

    Returns:
      plate_number (str) if a valid plate is found  e.g. 'UP80AB1234'
      None                if no valid plate detected

    How it picks the best result:
      EasyOCR returns multiple text boxes with confidence scores.
      We take the one with highest confidence that passes is_valid_plate().
    """
    if not os.path.exists(image_path):
        print(f"[OCR] Image not found: {image_path}")
        return None

    reader  = get_reader()
    results = reader.readtext(image_path)
    # results = [ ([bbox], text, confidence), ... ]

    best_plate      = None
    best_confidence = 0.0

    for (bbox, text, confidence) in results:
        cleaned = clean_plate(text)

        if is_valid_plate(cleaned) and confidence > best_confidence:
            best_plate      = cleaned
            best_confidence = confidence

    if best_plate:
        print(f"[OCR] Plate detected: {best_plate} (confidence: {best_confidence:.2f})")
    else:
        print("[OCR] No valid plate found in image.")

    return best_plate


def read_plate_from_array(image_array):
    """
    Read number plate from a numpy array (e.g. OpenCV frame).
    Used when processing live video frames.

    Args:
      image_array: numpy array (BGR format from cv2.imread)

    Returns:
      plate_number (str) or None
    """
    reader  = get_reader()
    results = reader.readtext(image_array)

    best_plate      = None
    best_confidence = 0.0

    for (bbox, text, confidence) in results:
        cleaned = clean_plate(text)
        if is_valid_plate(cleaned) and confidence > best_confidence:
            best_plate      = cleaned
            best_confidence = confidence

    if best_plate:
        print(f"[OCR] Plate detected: {best_plate} (confidence: {best_confidence:.2f})")
    else:
        print("[OCR] No valid plate found in frame.")

    return best_plate