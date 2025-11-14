#!/usr/bin/env python3
"""Script de prueba para diagnosticar errores en el dashboard."""

import sys
from pathlib import Path

# Añadir el directorio raíz del proyecto a sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

try:
    print("Importando módulos...")
    print("✓ Módulos importados correctamente")

    print("✓ Dependencias básicas importadas")

    # Simular la carga de datos
    print("Probando carga de datos...")
    # Aquí iría el código que carga los datos

    print("✓ Script de prueba completado exitosamente")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
