"""Shim de compatibilidad: delega `python init_models.py` a `app.init_models`.

El repositorio usa `app/init_models.py` como implementación canónica.
Este archivo mantiene compatibilidad con llamadas desde la raíz.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any


def main(argv: list[str] | None = None) -> Any:
    # Importar el módulo canónico y delegar al entrypoint `main`
    mod = importlib.import_module("app.init_models")
    if hasattr(mod, "main"):
        # Si el módulo espera parsear sys.argv internamente, dejamos que lo haga.
        if argv is None:
            return mod.main()
        # Inyectar temporalmente argv si se pasa
        old_argv = sys.argv
        try:
            sys.argv = [old_argv[0]] + list(argv)
            return mod.main()
        finally:
            sys.argv = old_argv
    # Si no hay main(), intentar ejecutar como script
    if getattr(mod, "__file__", None):
        mod_file = mod.__file__  # type: ignore[assignment]
        # mod.__file__ puede ser None en paquetes virtuales; comprobamos antes
        if mod_file is not None:
            with open(mod_file, "rb") as f:
                code = compile(f.read(), mod_file, "exec")
                ns: dict[str, object] = {"__name__": "__main__"}
                exec(code, ns)
                return None
    raise RuntimeError("Modulo 'app.init_models' no tiene entrypoint 'main'")


if __name__ == "__main__":
    sys.exit(main() or 0)
