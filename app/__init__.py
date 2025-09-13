"""app package initializer.

Make the `app` directory a proper Python package so static analysis
tools (like `mypy`) and imports treat modules under `app` as
`app.<module>` rather than top-level modules that may collide with
files at the repository root (for example `dashboard.py`).

This file intentionally keeps no runtime imports to avoid side-effects
when the package is imported by test runners or type-checkers.
"""

__all__: list[str] = []
