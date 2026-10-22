"""Spanish orthotypographic linter, validator, and automated correction toolkit for Umineko Project."""

from __future__ import annotations

__version__ = "1.0.0"

CATEGORIES = (
    "ORTOGRAFÍA",
    "TILDE",
    "ERRATA",
    "PUNTUACIÓN",
    "ESPACIADO",
    "MAYÚSCULAS",
    "CONCORDANCIA",
    "CODIFICACIÓN",
    "TÉRMINO INCONSISTENTE",
    "NOMBRE PROPIO",
    "SECUENCIA DUPLICADA",
    "POSIBLE ERROR DE EXTRACCIÓN",
    "POSIBLE ERROR CONTEXTUAL",
    "CAMBIO ESTILÍSTICO PROPUESTO",
    "REQUIERE REVISIÓN HUMANA",
    "NO MODIFICAR",
)

CONFIDENCE_LEVELS = ("ALTA", "MEDIA", "BAJA")
NON_AUTO_APPLY_CATEGORIES = frozenset(
    {
        "POSIBLE ERROR CONTEXTUAL",
        "CAMBIO ESTILÍSTICO PROPUESTO",
        "POSIBLE ERROR DE EXTRACCIÓN",
        "REQUIERE REVISIÓN HUMANA",
        "NO MODIFICAR",
    }
)
