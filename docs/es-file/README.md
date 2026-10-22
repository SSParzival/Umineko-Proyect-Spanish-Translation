# Toolkit de Ingeniería Inversa y Localización para `es.file` (`ONS2`)

## 1. Resumen Técnico

`es.file` es el archivo contenedor principal del script localizado en español para **Umineko Project** (motor **ONScripter-RU**). Empaqueta un único script monolítico en **UTF-8** (`19,624,486` bytes, `585,050` líneas físicas) dentro de un contenedor binario propietario denominado **`ONS2`** (`4,577,201` bytes) que aplica:

1. **Ofuscación interna** mediante una tabla de sustitución biyectiva `T` de 256 bytes y máscaras XOR (`0x45`, `0x71`).
2. **Compresión ZLIB** (`RFC 1950`, `level=6`, `wbits=15`, `memLevel=9`, checksum `Adler-32`).
3. **Ofuscación externa** mediante la misma tabla `T` y máscaras XOR (`0x86`, `0x23`), precedida por un encabezado binario de 16 bytes en **little-endian** (`magic="ONS2"`, `comp_size`, `uncomp_size`, `key_flag=0x6e`).

El paquete Python `tools.esfile` implementa un flujo **100% determinista, reversible y libre de pérdida** (`es.file → translation/ → es.file`) capaz de reconstruir el archivo original con **igualdad binaria exacta (`SHA-256` idéntico bit a bit)**.

---

## 2. Documentación del Directorio

* [`research.md`](research.md): Evidencia empírica del desensamblado de `onscripter-new.exe` (`ScriptHandler::readScript`), tabla de sustitución y análisis comparativo entre `es.file`, `en.file`, `ru.file` y `wh.file`.
* [`format.md`](format.md): Especificación técnica completa del formato binario `ONS2`, ecuaciones de codificación/decodificación y gramática del script ONScripter-RU.
* [`editing-guide.md`](editing-guide.md): Guía práctica para traductores y editores (qué archivos y campos editar, preservación de marcadores `[...]` y etiquetas `{...}`, validación y pruebas en el juego).

---

## 3. Comandos Disponibles (`python -m tools.esfile`)

### 3.1 Inspección (`inspect`)
Muestra el tipo de contenedor, metadatos del script, tamaños, ratio de compresión, checksums (`SHA-256` y `Adler-32`), conteo de catálogos/entradas y advertencias del archivo fuente sin volcar el texto completo:

```bash
python3 -m tools.esfile inspect es.file --verbose
python3 -m tools.esfile inspect es.file --json
```

### 3.2 Extracción estructurada (`extract`)
Desofusca, descomprime y analiza `es.file`, generando catálogos JSON editables organizados por episodio/capítulo y categoría de cadenas, bloques estructurales y un manifiesto con sumas `SHA-256`:

```bash
python3 -m tools.esfile extract es.file --output translation/
```

Opciones:
* `--output <dir>` / `-o <dir>`: Directorio de salida.
* `--force` / `-f`: Permite sobrescribir un directorio de salida no vacío.
* `--keep-raw`: Guarda además una copia íntegra del script UTF-8 decodificado en `translation/raw/decoded_script.txt`.
* `--report <ruta>`: Escribe una copia adicional del reporte de extracción JSON.
* `--verbose` / `-v`: Muestra el detalle de advertencias preexistentes en el script original.

### 3.3 Validación (`validate`)
Verifica la integridad estructural, sintáctica y semántica de un directorio extraído antes de compilar:

```bash
python3 -m tools.esfile validate translation/ --strict --verbose
```

Detecta:
* Archivos faltantes o adicionales no registrados en `manifest.json`.
* IDs duplicados, desconocidos, huérfanos o fuera de orden.
* Marcadores `[...]` alterados o corchetes `[` / `]` infiltrados dentro de segmentos de diálogo.
* Etiquetas en línea `{...}` desbalanceadas o eliminadas (`--strict`).
* Comillas dobles `"` o acentos graves `` ` `` no escapados introducidos por error.
* Saltos de línea literales `\n` en lugar de `{n}`.
* Entradas vaciadas accidentalmente o caracteres incompatibles con UTF-8.
* Alteración accidental de bloques estructurales (`blocks/*.json`).

### 3.4 Compilación (`build`)
Reconstruye un archivo binario `.file` (`ONS2`) a partir del directorio editable validando previamente todas las entradas y recalculando `uncomp_size`, el flujo ZLIB (`Adler-32`) y `comp_size`:

```bash
python3 -m tools.esfile build translation/ es.rebuilt.file --verbose
```

> **Seguridad**: Nunca sobrescribe un archivo de salida existente a menos que se indique explícitamente `--force`.

### 3.5 Comparación semántica y binaria (`diff`)
Compara dos archivos `.file` o dos directorios de traducción extraídos e informa diferencias binarias esperadas/inesperadas, entradas agregadas, eliminadas o modificadas, cambios de metadatos, marcadores u orden:

```bash
python3 -m tools.esfile diff es.file es.rebuilt.file --verbose
python3 -m tools.esfile diff translation-a/ translation-b/ --report diff.json
```

---

## 4. Estructura Generada (`translation/`)

```text
translation/
├── manifest.json                 # Metadatos del contenedor ONS2, inventario y SHA-256
├── report.json                   # Reporte detallado de extracción y advertencias
├── story/
│   ├── ep1/                      # 19 capítulos del Episodio 1 (umi1_op, umi1_1..16, teatime_1, ura_teatime_1)
│   ├── ep2/                      # 21 capítulos del Episodio 2
│   ├── ep3/                      # 21 capítulos del Episodio 3
│   ├── ep4/                      # 22 capítulos del Episodio 4
│   ├── ep5/                      # 18 capítulos del Episodio 5
│   ├── ep6/                      # 21 capítulos del Episodio 6
│   ├── ep7/                      # 21 capítulos del Episodio 7
│   ├── ep8/                      # 19 capítulos del Episodio 8
│   └── omake/                    # 9 capítulos de Omake y contenido extra
├── strings/
│   ├── define_system.json        # Títulos de ventana (caption) y mensajes de verificación (*define)
│   ├── credits.json              # Líneas de créditos (*credits_base)
│   ├── tips_titles.json          # Títulos de Tips en menú (r_tips_*)
│   ├── tips_texts.json           # Textos completos de Tips (tips_*)
│   ├── grimoire_texts.json       # Títulos y explicaciones del Grimorio (r_grim*, grim_*)
│   ├── characters.json           # Perfiles y nombres de personajes (chars_*, name_*)
│   ├── menu_and_ui.json          # Capítulos, reloj, guardado/carga y ajustes
│   ├── ep8_mystery.json          # Acertijos y juego de Bernkastel del EP8 (ep8_*, quiz_*)
│   ├── trophies.json             # Títulos y descripciones de trofeos (trophy_text_*)
│   ├── font_preview.json         # Líneas de prueba en selector de fuentes (*goa_*, *kak_*)
│   └── bgm_titles.json           # Títulos de pistas musicales en español (*bgm_locale_title)
└── blocks/
    ├── 00_define_and_start.json  # Código estructural no traducible de *define y *start
    ├── 01_story_ep1.json .. 08_story_ep8.json
    ├── 09_story_omake.json
    └── 10_post_story.json        # Lógica de menús, galerías, música y sistema
```

---

## 5. Solución de Problemas y Limitaciones Conocidas

1. **Diferencia de tamaño comprimido en distribuciones con `zlib-ng`**:
   * `es.file` fue compilado originalmente con `zlib 1.3.1` clásico (`memLevel=9`). En sistemas donde Python enlaza con `zlib-ng`, `tools.esfile.codec` localiza dinámicamente `libz.so.1.3.1` clásico si está disponible en el sistema (o mediante la variable de entorno `ESFILE_LIBZ_PATH=/ruta/a/libz.so.1.3.1`) para garantizar igualdad binaria bit a bit (`SHA-256` idéntico). Si solo existe `zlib-ng`, el archivo generado es 100% válido y funcionalmente idéntico para `onscripter-new.exe` (`plaintext_sha256` idéntico).
2. **Anomalías preexistentes en `es.file`**:
   * El archivo `es.file` original contiene `12` líneas de diálogo con un acento grave `` ` `` extra por errata tipográfica, `14` líneas con llaves `{`/`}` desbalanceadas de origen, `2` entradas `stralias` con salto de línea físico embebido, `6` entradas `stralias` sin coma separadora y `2` entradas `stralias` con comillas dobles ASCII internas. Todas ellas se preservan de forma exacta para garantizar el round-trip sin pérdida y se reportan como advertencias (`warnings`).
