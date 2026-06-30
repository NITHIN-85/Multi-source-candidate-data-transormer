from src.parser import extract_text_from_pdf, parse_resume

pdf_path = "data/Mallikarjunn_Resumee.pdf"
print("=" * 60)
print("Testing PDF extraction...")
print("=" * 60)

# Test 1: Extract raw text
text = extract_text_from_pdf(pdf_path)
print(f"\n1. Raw extracted text length: {len(text)}")
print(f"   First 500 chars:\n{text[:500]}")
print(f"   Total lines: {len(text.split(chr(10)))}")

# Test 2: Parse resume
print("\n" + "=" * 60)
print("Testing full resume parsing...")
print("=" * 60)
result = parse_resume(pdf_path)
if result:
    print(f"\nParsed successfully!")
    print(f"Full name: {result.get('full_name')}")
    print(f"Emails: {result.get('emails')}")
    print(f"Phones: {result.get('phones')}")
    print(f"Skills: {result.get('skills')}")
    print(f"Experience: {result.get('experience')}")
    print(f"Education: {result.get('education')}")
    print(f"Source: {result.get('source')}")
else:
    print("ERROR: parse_resume returned None!")
