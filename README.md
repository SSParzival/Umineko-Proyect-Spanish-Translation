# Umineko Project — Toolkit de Localización para `es.file` (`ONS2`)

Herramienta profesional de ingeniería inversa, extracción estructurada, validación, compilación determinista y comparación semántica/binaria para el contenedor de script `es.file` (`ONS2`) utilizado por **Umineko Project** (motor **ONScripter-RU**).

---

## Características Principales

* **Reversibilidad bit a bit (Lossless Round-Trip)**: Extraer `es.file` y reconstruirlo sin modificaciones produce un archivo binariamente idéntico (`SHA-256 == 0c00c9cf156b6429e01e6f1d26a6ae655329ef8301b6719a1742834b524300e1`).
* **Organización modular amigable para traducción**: Divide las `68,651` entradas traducibles del script monolítico (`585,050` líneas) en `182` catálogos JSON organizados por episodio/capítulo (`story/ep1..8/*.json`, `story/omake/*.json`) y categoría de interfaz (`strings/*.json`), separando por completo el código estructural no traducible en `blocks/*.json`.
* **Protección de sincronización y comandos**: Separa explícitamente los marcadores de control y voz (`[lv ...]`, `[@]`, `[\]`, `[|]`, `[#][*]`) de los segmentos de texto editables (`segments[i].text`) y valida el balance de etiquetas en línea (`{n}`, `{c:FF0000:...}`, `{f:5:...}`, `{p:...}`).
* **Seguridad y determinismo**: Sin dependencias externas fuera de la biblioteca estándar de Python (`>= 3.10`), con protección estricta contra *path traversal*, colisiones de mayúsculas/minúsculas, enlaces simbólicos y sobrescritura accidental.

---

## Inicio Rápido

```bash
# 1. Inspeccionar el contenedor binario es.file
python3 -m tools.esfile inspect es.file --verbose

# 2. Extraer el contenido editable a una estructura de carpetas
python3 -m tools.esfile extract es.file --output translation/

# 3. Validar la estructura extraída y las modificaciones realizadas
python3 -m tools.esfile validate translation/ --strict --verbose

# 4. Reconstruir un nuevo archivo .file
python3 -m tools.esfile build translation/ es.rebuilt.file --verbose

# 5. Comparar semántica y binariamente dos archivos .file o dos carpetas
python3 -m tools.esfile diff es.file es.rebuilt.file --verbose

# 6. Ejecutar la suite completa de pruebas automatizadas (unitarias, fuzzing y round-trip)
python3 -m unittest discover -s tests -v
```

---

## Estructura del Repositorio

* [`tools/esfile/`](tools/esfile/): Implementación del paquete CLI (`codec.py`, `models.py`, `parser.py`, `extractor.py`, `inspector.py`, `validator.py`, `builder.py`, `differ.py`, `cli.py`).
* [`tests/`](tests/): Suite de pruebas unitarias, integración, seguridad de rutas, fuzzing y round-trip sobre `es.file`.
* [`docs/es-file/`](docs/es-file/):
  * [`README.md`](docs/es-file/README.md): Manual técnico y referencia de comandos CLI.
  * [`research.md`](docs/es-file/research.md): Informe de ingeniería inversa del binario `onscripter-new.exe` y contenedores `.file`.
  * [`format.md`](docs/es-file/format.md): Especificación formal del formato `ONS2` y gramática ONScripter-RU.
  * [`editing-guide.md`](docs/es-file/editing-guide.md): Guía detallada para traductores y protocolo de prueba en el juego.
* [`schemas/`](schemas/): Esquemas JSON (`manifest.schema.json` y `translation-catalog.schema.json`).
* [`examples/`](examples/): Ejemplo ilustrativo de manifiesto (`manifest.example.json`).
