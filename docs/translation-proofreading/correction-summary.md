# Resumen Estadístico de Correcciones Ortotipográficas — Umineko Project

Este documento resume las estadísticas cuantitativas y cualitativas de la revisión ortotipográfica realizada sobre los 182 catálogos JSON de la traducción española de Umineko Project.

## 1. Métricas Globales del Corpus

- **Catálogos de traducción revisados**: 182 (104 historias episódicas, 8 omakes, 70 catálogos de cadenas y UI)
- **Bloques estructurales verificados**: 11
- **Entradas totales analizadas**: 68.651
- **Campos de texto evaluados**: 200.014 (131.363 segmentos de diálogo + 66.562 vistas previas + 2.089 cadenas de sistema)
- **Catálogos modificados**: 130
- **Catálogos sin modificaciones**: 52
- **Correcciones totales de confianza ALTA aplicadas**: 489
- **Hallazgos ambiguos documentados para decisión humana**: 5

## 2. Desglose por Categoría de Corrección

| Categoría | Cantidad | % del Total | Ejemplos Representativos |
|---|---:|---:|---|
| `TILDE` | 366 | 74,8% | `también`, `después`, `aquí`, `había`, `fácil`, `déjame`, `construido`, `casi`, `fe`, `vi` |
| `ERRATA` | 67 | 13,7% | `extremadamente`, `construir`, `descansando`, `arrepentimiento`, `milagro`, `entender` |
| `SECUENCIA DUPLICADA` | 17 | 3,5% | `que que` → `que`, `en en` → `en`, `de de` → `de`, `solo solo` → `solo`, `una una` → `una` |
| `NOMBRE PROPIO` | 16 | 3,3% | `Battler` (de `Batlter`/`Batller`), `Ushiromiya` (de `Ushromiya`), `George` (de `Geoge`), `Halloween` |
| `ORTOGRAFÍA` | 12 | 2,5% | `cabeza` (de `caveza`), `resurrección` (de `resurreción`), `perfección` (de `perfeción`), `acercarse` |
| `ESPACIADO` | 6 | 1,2% | `¡Hurra, ya`, `cascabel, ¿cierto?`, `a pesar de que`, `a punto de` |
| `CONCORDANCIA` | 5 | 1,0% | `han juntado` (de `han juntando`), `haber pensado` (de `haber pensando`), `Esta vía` (de `Este vía`) |

## 3. Estado de Verificación y Round-Trip

1. **Validación de Schema y Formato**: `PASS` (`tools.esfile validate translation/` -> 0 errores).
2. **Validación de Linter y Reglas**: `PASS` (`tools.translation_lint validate translation/` -> 0 errores).
3. **Compilación de Contenedor ONS2**: `PASS` (`tools.esfile build` -> 4.576.879 bytes, SHA-256 verificado).
4. **Reextracción y Comparación Semántica**: `PASS` (`diff_targets` -> `Plaintext identical: True`, `Semantically identical: True`, 0 drift).
