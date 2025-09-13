import sys
from pathlib import Path

# Asegura que la raíz del proyecto esté en sys.path durante pytest
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
