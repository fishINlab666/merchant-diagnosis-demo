"""Publish the product showcase and generated merchant reports."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
# Historical reports remain byte-for-byte archives; gate current product surfaces.
surfaces = ['public/reports/audience-chain.html',
            'public/reports/audience-chain-v183.html',
            'public/reports/single-v183.html',
            'public/reports/api-chain-v183.html']
subprocess.run([sys.executable, str(root / 'tools/check_product_copy.py'), '--root', str(root),
                *[item for surface in surfaces for item in ('--file', surface)],
                '--file', 'tools/recording-console.html',
                '--file', '.agents/skills/merchant-diagnosis/assets/boss-report.js'],
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
