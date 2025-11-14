# Notas de versión v1.2.0

## Nuevas Características

- **Herramientas de Benchmarking de Rendimiento**: Scripts automatizados para validar optimizaciones
  - `benchmark_performance.py`: Pruebas del núcleo del sistema con métricas detalladas
  - `benchmark_dashboard.py`: Simulación del rendimiento del dashboard
  - Documentación completa en `PERFORMANCE_README.md`
- **Optimizaciones de Memoria**: Reducción del 27.1% en uso de memoria para DataFrames
- **Constantes Centralizadas**: Módulo `f1m.constants` para mejor mantenibilidad
- **Memoización Adicional**: Optimización de parsing de tiempos de vuelta
- **Suite de Tests Expandida**: Cobertura completa con 33 tests unitarios

## Mejoras

- Dashboard ampliado a 10 pestañas de análisis estadístico avanzado
- Mejor manejo de errores y verificaciones defensivas
- Carga de datos optimizada con lectura directa desde archivos Parquet
- Sistema de caché exhaustivo para eliminar recálculos
- Imports reorganizados para reducir redundancia

## Optimizaciones de Rendimiento

- **Memoización**: Funciones críticas cacheadas para evitar recálculos
- **Optimización de Memoria**: Conversión automática de tipos de datos eficientes
- **Carga Acelerada**: Procesamiento directo desde datos curados
- **Constantes Centralizadas**: Eliminación de números mágicos hardcodeados

## Mantenimiento

- Reorganización completa del sistema de imports
- Constantes centralizadas en módulo dedicado
- Tests unitarios adicionales para mayor cobertura
- Documentación actualizada y completa
