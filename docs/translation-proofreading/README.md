# Flujo de Revisión Ortotipográfica — Traducción Española de Umineko Project

Este directorio documenta el sistema automatizado, profesional y reproducible de control de calidad ortotipográfico, detección de erratas y preservación estructural para la localización al español de Umineko Project (`translation/`, originado en `es.file`).

## 1. Propósito y Alcance

El objetivo del proyecto es garantizar que el español de los 182 catálogos JSON de traducción sea formalmente correcto, natural y editorialmente cuidado según las normas de la RAE/ASALE y las convenciones del universo narrativo de *Umineko When They Cry*, sin alterar la estructura técnica requerida por el motor ONScripter-RU para reconstruir el archivo binario `es.file`.

### Campos Editables vs. Campos Protegidos

| Tipo de Campo | Ejemplos | Política de Edición |
|---|---|---|
| **Editable (Diálogos)** | `segments[i].text` | Modificable fuera de etiquetas inline `{...}`. Se sincronizan `text` y listas `inline_tags`. |
| **Editable (Cadenas)** | `text` en `stralias`, `bgm_title`, `credits_line`, `caption` | Modificable fuera de etiquetas inline `{...}`. |
| **Protegido (Estructural)** | `id`, `kind`, `line_number`, `line_span`, `line_ending`, `markers` | **Estrictamente intocable**. |
| **Protegido (Técnico)** | `command_prefix`, `command_suffix`, `sprite_prefix`, `voice_files` | **Estrictamente intocable**. |
| **Protegido (Bloques)** | `blocks/*.json` | Scripts estructurales no editables. |

## 2. Herramientas del Sistema (`tools.translation_lint`)

El paquete de herramientas se invoca mediante CLI estándar de Python:

```bash
# Escanear catálogos y reportar hallazgos sin modificar archivos
python3 -m tools.translation_lint scan translation/

# Generar reportes formales (JSONL y Markdown)
python3 -m tools.translation_lint report translation/ --output-dir reports/

# Validar integridad estructural, schema y etiquetas
python3 -m tools.translation_lint validate translation/

# Aplicar correcciones lingüísticas de confianza alta
python3 -m tools.translation_lint apply translation/ --reports-dir reports/
```

## 3. Diccionario y Guía de Estilo

- **Diccionario de términos aceptados**: [`translation/config/accepted-words.txt`](file:///home/ssparzival/Games/Umineko%20Proyect/translation/config/accepted-words.txt). Incluye nombres propios canónicos, dialecto de Hideyoshi (`to's`, `pensa'o`, `na'`, `'tá`), honoríficos japoneses y onomatopeyas.
- **Guía de estilo**: [`translation/config/style-guide.md`](file:///home/ssparzival/Games/Umineko%20Proyect/translation/config/style-guide.md) y [`docs/translation-proofreading/style-guide.md`](file:///home/ssparzival/Games/Umineko%20Proyect/docs/translation-proofreading/style-guide.md).

## 4. Auditoría y Trazabilidad

Cada corrección aplicada y cada hallazgo ambiguo queda registrado en:
- [`reports/translation-corrections.jsonl`](file:///home/ssparzival/Games/Umineko%20Proyect/reports/translation-corrections.jsonl): Registro detallado por entrada, campo, valor anterior y posterior.
- [`reports/translation-corrections.md`](file:///home/ssparzival/Games/Umineko%20Proyect/reports/translation-corrections.md): Resumen ejecutivo por categoría y archivo.
- [`reports/translation-human-review.md`](file:///home/ssparzival/Games/Umineko%20Proyect/reports/translation-human-review.md): Casos de confianza media y baja reservados para decisión editorial.

## 5. Verificación de Round-Trip

El ciclo completo de reconstrucción y reextracción garantiza 100% de identidad semántica:

$$\text{translation/} \xrightarrow{\text{build}} \text{es.rebuilt.file} \xrightarrow{\text{extract}} \text{reextracted/} \xrightarrow{\text{diff}} 0 \text{ diferencias}$$
