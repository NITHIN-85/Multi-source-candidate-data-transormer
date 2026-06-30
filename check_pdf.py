import pypdf

pdf_path = 'data/Mallikarjunn_Resumee.pdf'
r = pypdf.PdfReader(pdf_path)
print(f'Total pages: {len(r.pages)}')
for i, page in enumerate(r.pages):
    text = page.extract_text()
    print(f'\nPage {i+1} text length: {len(text)}')
    print(f'First 200 chars: {text[:200]}')
