from pathlib import Path
import sys
from pypdf import PdfReader

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'artifacts' / 'main-report.pdf'
pages = len(PdfReader(path).pages)
print(f'Print page count: {pages}')
if pages != 1:
    raise SystemExit(f'Expected one A4 page, got {pages}')
