# Guía de Edición de Traducción para `es.file` (Umineko Project)

Esta guía explica cómo editar de forma segura los archivos extraídos de `es.file`, cómo preservar la sincronización de voces y efectos visuales del motor **ONScripter-RU**, cómo validar los cambios y cómo compilar y probar el archivo reconstruido en **Umineko Project**.

---

## 1. Flujo de Trabajo Recomendado

```bash
# 1. Extraer es.file en una carpeta de trabajo
python3 -m tools.esfile extract es.file --output translation/

# 2. Editar los archivos deseados dentro de translation/story/ o translation/strings/

# 3. Validar la integridad de las modificaciones antes de compilar
python3 -m tools.esfile validate translation/ --strict --verbose

# 4. Compilar el nuevo archivo sin sobrescribir el original
python3 -m tools.esfile build translation/ es.rebuilt.file --verbose

# 5. Revisar exactamente qué entradas cambiaron
python3 -m tools.esfile diff es.file es.rebuilt.file --verbose
```

---

## 2. ¿Qué Archivos Se Deben Editar?

### Archivos editables
* `translation/story/ep1/*.json` .. `translation/story/ep8/*.json`: Diálogos y narración de los Episodios 1 a 8 (`umiX_op`, `umiX_1..N`, `teatime_X`, `ura_teatime_X`).
* `translation/story/omake/*.json`: Diálogos de Omake, minijuegos y tráileres (`o1_0`, `o2_0`, `o3_start`, `o4_0`, `chiru_trailer`, `o_chiru_start`, `omake_chiru_menu`, `o8_0`, `o9_0`).
* `translation/strings/*.json`:
  * `define_system.json`: Título de la ventana del juego (`caption`) y textos del verificador de archivos.
  * `credits.json`: Textos de créditos (`*credits_base`).
  * `tips_titles.json` y `tips_texts.json`: Títulos y cuerpos de las pistas (Tips).
  * `grimoire_texts.json`: Entradas del Grimorio de la Bruja.
  * `characters.json`: Nombres y biografías de personajes en el menú.
  * `menu_and_ui.json`: Nombres de capítulos, horas del reloj, textos de guardado/carga y opciones del menú de configuración.
  * `ep8_mystery.json`: Textos del juego de misterio y acertijos de Bernkastel en el Episodio 8.
  * `trophies.json`: Títulos y descripciones de trofeos.
  * `font_preview.json`: Frases de ejemplo en el menú de selección de fuente.
  * `bgm_titles.json`: Títulos traducidos de las pistas musicales (`*bgm_locale_title`).

### Archivos que NO se deben editar manualmente
* `translation/manifest.json`: Contiene los metadatos del contenedor binario `ONS2` y las sumas de verificación `SHA-256`.
* `translation/blocks/*.json`: Contienen el código estructural del motor (transiciones, sprites, efectos de sonido, saltos condicionales y ranuras de inserción). Si se altera un archivo en `blocks/`, `validate` y `build` abortarán con `CHECKSUM_MISMATCH`.

---

## 3. Campos Editables vs. Campos Protegidos

### 3.1 Entradas de diálogo (`"kind": "dialogue"`)
En los archivos de `story/` y en `strings/font_preview.json`, cada línea de diálogo puede estar dividida en varios segmentos sincronizados con clips de voz:

```json
{
  "id": "ep1.umi1_op.d7",
  "kind": "dialogue",
  "line_number": 3551,
  "line_span": 1,
  "line_ending": "LF",
  "chapter": "umi1_op",
  "label": "*d7",
  "speaker": "nan",
  "voice_files": [
    "19/11900003",
    "19/11900004"
  ],
  "command_prefix": "d ",
  "command_suffix": "",
  "sprite_prefix": "",
  "markers": [
    "[lv 0*\"19\"*\"11900003\"]",
    "[gstg 1][@][lv 0*\"19\"*\"11900004\"]",
    "[\\]"
  ],
  "segments": [
    {
      "index": 0,
      "text": "\"... Kinzo‐{c:86EF9C:san}.",
      "inline_tags": [
        "{c:86EF9C:san}"
      ]
    },
    {
      "index": 1,
      "text": " Tu cuerpo parece estar en buen estado...\"",
      "inline_tags": []
    }
  ],
  "text": "\"... Kinzo‐{c:86EF9C:san}.  Tu cuerpo parece estar en buen estado...\"",
  "inline_tags": [
    "{c:86EF9C:san}"
  ],
  "has_stray_backtick": false,
  "has_unbalanced_braces": false,
  "allow_empty": false,
  "status": "translated",
  "notes": ""
}
```

* **QUÉ EDITAR**:
  * Edita **`segments[i].text`** para cada segmento `i`. Ese es el valor autoritativo que el compilador `build` utiliza para reconstruir la línea `d` o `d2`.
  * Opcionalmente puedes actualizar `"status"` (por ejemplo `"reviewed"`) y `"notes"` para control editorial.
* **QUÉ NO TOCAR**:
  * No modifiques `"id"`, `"kind"`, `"line_number"`, `"line_ending"`, `"command_prefix"`, ni la lista `"markers"`.
  * No agregues ni elimines elementos de `"segments"` (la cantidad de segmentos debe coincidir exactamente con `len(markers) - 1` para no desincronizar las voces `[lv ...]`).

### 3.2 Entradas de cadenas (`"kind": "stralias" | "bgm_title" | "credits_line" | "window_caption"`)
En el resto de catálogos dentro de `strings/`, la lista `"segments"` está vacía (`[]`) y el texto editable reside directamente en el campo **`"text"`**:

* **QUÉ EDITAR**:
  * Edita únicamente el campo **`"text"`** (y opcionalmente `"status"` / `"notes"`).
* **QUÉ NO TOCAR**:
  * No modifiques `"sprite_prefix"` (por ejemplo `":s;#C7C7C7#FFFFFF`"`), `"command_prefix"`, `"command_suffix"`, `"id"` ni `"line_number"`.

---

## 4. Reglas de Sintaxis de ONScripter-RU

1. **Prohibido usar acentos graves (`` ` ``) o corchetes (`[`, `]`) dentro del texto de diálogo**:
   * En ONScripter-RU, `` ` `` delimita el inicio y fin de cada segmento de texto y `[...]` delimita comandos externos (`[@]`, `[\]`, `[lv ...]`). Si introduces un `` ` `` o `[` dentro de `segments[i].text`, `validate` y `build` lo rechazarán.
2. **Prohibido usar comillas dobles ASCII (`"`) dentro de `stralias`, `bgm_title`, `credits_line` o `window_caption`**:
   * Esos comandos envuelven la cadena entre comillas dobles (`"..."`). Utiliza comillas tipográficas españolas (`«...»` o `“...”`) dentro del texto.
3. **Saltos de línea**:
   * **Nunca** insertes un salto de línea físico (`Enter` / `\n`) dentro de una cadena JSON. Usa siempre la etiqueta en línea **`{n}`** (o `{n}{n}` para doble salto).
4. **Etiquetas de formato en línea (`{...}`)**:
   * Conserva el balance de llaves `{` y `}`:
     * **`{c:FF0000:texto}`**: Verdad roja (`#FF0000`), verdad azul (`#5299FF`), verdad dorada (`#FFCC00`), verdad morada (`#C559FF`), honoríficos (`#86EF9C`).
     * **`{f:5:Beatrice}`**: Fuente especial (por ejemplo, nombres mágicos).
     * **`{p:<id>:texto}`**: Preset tipográfico de menú, tips o créditos.
     * **`{i:texto}` / `{b:texto}`**: Cursiva / negrita.
     * **`{a:c:texto}` / `{w:700:}` / `{fit}` / `{nobr}`**: Alineación centrada y ajuste de ancho en menús/tips.
     * **`{0}` .. `{9}`**: Pausas de velocidad de texto o separadores de caracteres (ej. `Ki{0}hi{0}hi`).

---

## 5. Protocolo Seguro de Prueba en el Juego (Umineko Project)

Si dispones de una instalación local legítima de **Umineko Project**:

1. **Respaldar el archivo original**:
   ```bash
   cp es.file es.file.backup
   ```
2. **Validar y compilar la versión modificada**:
   ```bash
   python3 -m tools.esfile validate translation/ --strict
   python3 -m tools.esfile build translation/ es.rebuilt.file
   ```
3. **Instalar el archivo reconstruido en una copia o entorno de pruebas**:
   ```bash
   cp es.rebuilt.file es.file
   ```
4. **Lista de verificación dentro del juego**:
   * Iniciar `onscripter-new.exe` (o el ejecutable correspondiente a tu plataforma) y comprobar que no aparece error de carga ni de firma `;gameid`.
   * Verificar el título de la ventana y el menú principal (`Nuevo juego`, `Continuar`, `Guardar/Cargar`, `Tips`, `Grimorio`, `Personajes`, `Galería`, `Música`, `Trofeos`, `Configuración`).
   * Iniciar una escena con diálogo y comprobar:
     * Sincronización de voz (`[lv ...]`) con cada segmento de texto.
     * Pausas de clic (`[@]`) y limpieza de cuadro (`[\]`).
     * Renderizado de caracteres españoles (`á, é, í, ó, ú, ü, ñ, ¿, ¡, «, », —`).
     * Colores de la verdad roja/azul/dorada y fuentes especiales (`{f:5:...}`).
   * Probar guardado y carga de partida.
   * Revisar `stdout.txt` y `stderr.txt` en la carpeta del juego para confirmar ausencia de errores de script.
5. **Restaurar el respaldo cuando sea necesario**:
   ```bash
   cp es.file.backup es.file
   ```
