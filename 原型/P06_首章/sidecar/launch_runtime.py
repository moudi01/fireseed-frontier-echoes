"""Run the packaged protocol with a per-process diagnostic file."""

import os
from pathlib import Path
from runpy import run_path
import sys


diagnostic = Path(sys.argv.pop(1))
try:
    sys.stderr = diagnostic.open('x', encoding='utf-8', buffering=1)
except OSError:
    # Diagnostics cannot block the game or fill the unused Windows stderr pipe.
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')
run_path(str(Path(__file__).with_name('protocol_service.py')), run_name='__main__')
