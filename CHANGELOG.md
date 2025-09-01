# Changelog

## v1.0.2

Fixes y mejoras:

- **Parser de tiempos de vuelta** robusto (`m:ss.xxx` → segundos) en `strategy.py` → corrige `NaN` de `lap_time_s`.
- **Auto-refresh** limpio en `dashboard.py` (elimina placeholders y sobrescrituras de `st.experimental_rerun`).
- **Separación de distancia total vs horizonte parcial**: la recomendación en vivo usa siempre el total oficial; los planes pueden limitarse a vueltas completadas.
- **Comprobación de combustible** en `enumerate_plans` y en la recomendación en vivo (evita planes inviables por fuel negativo).
- **Elección de compuesto post-pit** basada en tiempo proyectado del tramo restante (no solo intercepto).
- `BASE_DIR` más robusto para ejecución con Streamlit.
- Metadatos extra en modelos guardados: `app_version` y `model_version` (dashboard) y `saved_at` (CLI).

## v1.0.1

Pequeñas mejoras:

- Añadido workflow CI GitHub Actions.
- Limpieza formato README (lint markdown).
- Bump versión en dashboard.

## v1.0.0 (Initial Release)

Primera versión pública con:

- Dashboard Streamlit (laps, stints, temperaturas, desgaste, estrategia, recomendación en vivo)
- Modelos lineales de degradación y carga/guardado de modelos JSON
- Scripts auxiliares: `curate.py` (curación Parquet) y `init_models.py` (modelos iniciales)
- Soporte circuitos iniciales + SaudiArabia
- README ampliado, LICENSE MIT, .gitignore

Pendiente para próximas versiones: métricas de modelo, estrategia avanzada, simulación Safety Car, modelos no lineales.
