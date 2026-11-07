"""Publish the Skill's static interview page and generated reports."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
destination = root / 'dist'
if destination.is_symlink():
    raise RuntimeError('dist must not be a symlink')
if destination.exists():
    shutil.rmtree(destination)
destination.mkdir()
shutil.copytree(root / 'public', destination, dirs_exist_ok=True)
shutil.copy2(root / 'index.html', destination / 'index.html')
print('Static showcase copied to dist/')
