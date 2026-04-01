"""Fix mojibake in dashboard.py."""

import sys

path = sys.argv[1] if len(sys.argv) > 1 else "app/dashboard.py"

with open(path, encoding="utf-8") as f:
    text = f.read()

text = text.lstrip("\ufeff")

fixes = [
    ("VersiÃ³n", "Versión"),
    ("raÃ\xadz", "raíz"),
    ("mÃ³dulos", "módulos"),
    ("SesiÃ³n", "Sesión"),
    ("sesiÃ³n", "sesión"),
    ("AnÃ¡lisis", "Análisis"),
    ("anÃ¡lisis", "análisis"),
    ("TelemetrÃ\xada", "Telemetría"),
    ("telemetrÃ\xada", "telemetría"),
    ("encontrÃ³", "encontró"),
    ("analÃ\xadticos", "analíticos"),
    ("validaciÃ³n", "validación"),
    ("degradaciÃ³n", "degradación"),
    ("comparaciÃ³n", "comparación"),
    ("ComparaciÃ³n", "Comparación"),
    ("GrÃ¡ficos", "Gráficos"),
    ("grÃ¡ficos", "gráficos"),
    ("estÃ¡", "está"),
    ("NeumÃ¡ticos", "Neumáticos"),
    ("NeumÃ¡tico", "Neumático"),
    ("EvoluciÃ³n", "Evolución"),
    ("evoluciÃ³n", "evolución"),
    ("MÃ©tricas", "Métricas"),
    ("\u00e2\u20ac\u201c", "\u2014"),  # â€" (left quote variant) -> —
    ("\u00e2\u20ac\u201d", "\u2014"),  # â€" (right quote variant) -> —
    ("\u00e2\u0153\u2026", "\u2705"),  # âœ… -> ✅
    ("\u00e2\u009d\u0152", "\u274c"),  # â❌ -> ❌
    ("TÂº", "T\u00ba"),
]

count = 0
for bad, good in fixes:
    if bad in text:
        text = text.replace(bad, good)
        count += 1

with open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)

print(f"Fixed {count} patterns in {path}")

remaining = [
    (i + 1, line)
    for i, line in enumerate(text.split("\n"))
    if any(0x80 <= ord(c) <= 0x24F for c in line)
]
if remaining:
    print("Remaining non-ascii:")
    for n, l in remaining:
        print(f"  {n}: {l!r}")
else:
    print("Clean - no more mojibake")
