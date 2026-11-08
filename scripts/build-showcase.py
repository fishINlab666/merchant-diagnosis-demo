"""Publish the product showcase and generated merchant reports."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(root / 'tools/check_product_copy.py'), '--root', str(root)],
               check=True)
destination = root / 'dist'
if destination.is_symlink():
    raise RuntimeError('dist must not be a symlink')
if destination.exists():
    shutil.rmtree(destination)
destination.mkdir()
shutil.copytree(root / 'public', destination, dirs_exist_ok=True)
shutil.copy2(root / 'index.html', destination / 'index.html')
print('Static showcase copied to dist/')
