# Resumen Estadístico de Correcciones Ortotipográficas — Umineko Project

Este documento resume las estadísticas cuantitativas y cualitativas de la revisión ortotipográfica y técnica final realizada sobre los 182 catálogos JSON de la traducción española de Umineko Project.

## 1. Métricas Globales del Corpus

- **Catálogos de traducción revisados**: 182 (104 historias episódicas, 8 omakes, 70 catálogos de cadenas y UI)
- **Bloques estructurales verificados**: 11
- **Entradas totales analizadas**: 68.651
- **Campos de texto evaluados**: 200.014 (131.363 segmentos de diálogo + 66.562 vistas previas + 2.089 cadenas de sistema)
- **Catálogos modificados**: 136
- **Catálogos sin modificaciones**: 46
- **Correcciones totales aplicadas**: 563
  - Correcciones iniciales de alta confianza: 489
  - Resoluciones de prioridad media contextual: 7
  - Normalizaciones de dobles espacios innecesarios: 67
- **Casos de prioridad baja / variantes artísticas protegidas**: 100% conservados (stutters expresivos, formato puzzle de Beatrice en Ep7 Ch2)

## 2. Desglose por Categoría de Corrección

| Categoría | Cantidad | % del Total | Ejemplos Representativos |
|---|---:|---:|---|
| `TILDE` | 368 | 65,4% | `también`, `después`, `aquí`, `había`, `fácil`, `déjame`, `construido`, `casi`, `fe`, `vi`, `desafío`, `incluido` |
| `ESPACIADO` | 74 | 13,1% | Normalización de dobles espacios innecesarios tras puntuación, dobles espacios intervocálicos, espacios ante coma |
| `ERRATA` | 70 | 12,4% | `extremadamente`, `construir`, `descansando`, `arrepentimiento`, `milagro`, `oportunidad`, `resurrección` |
| `SECUENCIA DUPLICADA` | 18 | 3,2% | `que que` → `que`, `en en` → `en`, `de de` → `de`, `solo solo` → `solo`, duplicación de `que` entre etiquetas ruby |
| `NOMBRE PROPIO` | 16 | 2,8% | `Battler` (de `Batlter`/`Batller`), `Ushiromiya` (de `Ushromiya`), `George` (de `Geoge`), `Halloween` |
| `ORTOGRAFÍA` | 12 | 2,1% | `cabeza` (de `caveza`), `resurrección` (de `resurreción`), `perfección` (de `perfeción`), `acercarse` |
| `CONCORDANCIA / CONTEXTO` | 5 | 0,9% | `han juntado` (de `han juntando`), `está entrenando` (de `alguien lo entrenando`) |

## 3. Estado de Verificación y Round-Trip

1. **Validación de Schema y Formato**: `PASS` (`tools.esfile validate translation/` -> 0 errores, 0 modified untracked).
2. **Validación de Linter y Reglas**: `PASS` (`tools.translation_lint validate translation/` -> 0 errores).
3. **Suite Completa de Pruebas**: `PASS` (`python3 -m unittest discover -s tests` -> 31/31 pruebas aprobadas).
4. **Compilación de Contenedor ONS2**: `PASS` (`tools.esfile build` -> 4.576.804 bytes, SHA-256: `ffb56fe2ba8e0d70494dc1bafd241ca840904da7358e9d9b1168012c2f65f8e7`).
5. **Determinismo Bit a Bit**: `PASS` (Dos compilaciones sucesivas producen el mismo SHA-256).
6. **Reextracción y Comparación Semántica**: `PASS` (`diff_targets` -> `Plaintext identical: True`, `Semantically identical: True`, 0 drift, 0 saltos de marcadores).
7. **Preservación del Archivo Original**: `PASS` (`es.file` preservado intacto con SHA-256 `0c00c9cf156b6429e01e6f1d26a6ae655329ef8301b6719a1742834b524300e1`).
