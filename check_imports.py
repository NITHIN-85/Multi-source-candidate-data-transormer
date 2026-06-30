import sys
try:
    import pdfplumber
    print("✓ pdfplumber installed")
except:
    print("✗ pdfplumber NOT installed")

try:
    import pytesseract
    print("✓ pytesseract installed")
except:
    print("✗ pytesseract NOT installed")

try:
    from pdf2image import convert_from_path
    print("✓ pdf2image installed")
except:
    print("✗ pdf2image NOT installed")

try:
    from PIL import Image
    print("✓ PIL/Pillow installed")
except:
    print("✗ PIL/Pillow NOT installed")
