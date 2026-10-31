from pathlib import Path
import sys
import pypdfium2 as pdfium

root = Path(__file__).resolve().parents[1]
pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'artifacts' / 'main-report.pdf'
pdf = pdfium.PdfDocument(pdf_path)
for index, page in enumerate(pdf):
    image = page.render(scale=1.4).to_pil()
    target = pdf_path.parent / f'report-page-{index + 1}.jpg'
    image.save(target, quality=85, optimize=True)
    print(target, target.stat().st_size)
