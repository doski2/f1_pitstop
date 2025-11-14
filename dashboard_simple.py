"""Dashboard simplificado para diagnóstico."""

import importlib.util
import logging
import sys
from pathlib import Path

# Añadir el directorio raíz del proyecto a sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

try:
    print("Importando modulos...")
    if importlib.util.find_spec("f1m"):
        print("Modulos importados correctamente")
    else:
        raise ImportError("Paquete f1m no encontrado")
except ImportError as e:
    print(f"Error importando modulos: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error inesperado importando modulos: {e}")
    sys.exit(1)

try:
    import streamlit as st

    print("Dependencias basicas importadas")
except Exception as e:
    print(f"Error importando dependencias: {e}")
    sys.exit(1)

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

print("Iniciando aplicación Streamlit...")

st.title("Dashboard F1 Pitstop Strategy - Versión Simplificada")

try:
    st.sidebar.header("Configuración")
    track = st.sidebar.selectbox("Circuito", ["Bahrain"], index=0)
    session = st.sidebar.selectbox(
        "Sesión",
        [
            "Practice 1",
            "Practice 2",
            "Practice 3",
            "Qualifying 1",
            "Qualifying 2",
            "Qualifying 3",
            "Race",
        ],
        index=0,
    )
    driver = st.sidebar.selectbox(
        "Piloto", ["Fernando Alonso", "Lance Stroll"], index=0
    )

    st.info("Dashboard simplificado funcionando correctamente.")
    print("Aplicacion cargada exitosamente")
except Exception as e:
    print(f"Error en la aplicacion: {e}")
    import traceback

    traceback.print_exc()
    st.error(f"Error en la aplicacion: {e}")
    sys.exit(1)
