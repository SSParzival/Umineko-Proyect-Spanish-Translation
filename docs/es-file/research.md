# Investigación Técnica del Recurso `es.file` en Umineko Project

## 1. Propósito y Alcance

Este documento registra la investigación empírica e ingeniería inversa realizadas sobre el archivo `es.file` presente en la instalación local de **Umineko Project**, con el objetivo de determinar sin suposiciones previas:

1. Su formato binario real y las transformaciones criptográficas/de compresión aplicadas.
2. El modo exacto en que el motor **ONScripter-RU** (`onscripter-new.exe`) valida, decodifica y ejecuta dicho archivo.
3. La estructura interna del guion decodificado y la jerarquía real de los textos traducibles al español.
4. Las herramientas oficiales y comunitarias relacionadas y el motivo exacto de las diferencias binarias entre implementaciones de `zlib`.

---

## 2. Fuentes y Evidencia Consultada

### 2.1 Evidencia local analizada directamente
| Archivo | Tamaño (bytes) | SHA-256 | Rol identificado |
|---|---:|---|---|
| `es.file` | 4,577,201 | `0c00c9cf156b6429e01e6f1d26a6ae655329ef8301b6719a1742834b524300e1` | Contenedor `ONS2` del guion localizado al español (`UminekoPS3ficationEs`, v8.2b). |
| `en.file` | 4,458,165 | `a9dfd16c4f1b657e539f1aa9e9d11fdfb95a5d7ecee7fb125da1c78081d59777` | Contenedor `ONS2` del guion en inglés (`UminekoPS3ficationEn`). |
| `ru.file` | 5,078,604 | `a6c71091e391f44f88c3fbf44aa7828a7079043b0d958af165f8b2337e57e6c7` | Contenedor `ONS2` del guion en ruso (`UminekoPS3ficationRu`). |
| `wh.file` | 4,377,294 | `7f88e597441d6353c330ec0d777302fc81689e2e42ed621ed55b5e771c32dd82` | Contenedor `ONS2` del guion en inglés Witch Hunt (`UminekoPS3ficationWh`). |
| `chiru.file` | 926,166 | `00e799033d41e44d34b2f7bd66b2e73040e59004c7b9aa1d4d34359befcae314` | Registro INI en texto plano (`[picture]`) cargado mediante `loadreg "chiru.file"`. |
| `ons.cfg` | 104 | `d4675ef767c4412c6438cb78ff5aa01b529c2d6b66f9cb638d8c8011cd5843a3` | Configuración de arranque del motor (`game-script=es.file`). |
| `onscripter-new.exe` | 15,558,656 | — | Binario PE32+ x86-64 de ONScripter-RU utilizado para desensamblado estático. |

### 2.2 Repositorios y herramientas públicas contrastadas
1. **`umineko-project/onscripter-ru`**: Motor personalizado derivado de ONScripter por Umineko Project (licenciado bajo GPLv2 / BSD 3-Clause).
2. **`umineko-project/umineko-scripting`**: Repositorio de scripts y herramientas de empaquetado de Umineko Project (`update-manager/update-manager.php`, estructura de directorios `story/ep1..ep8`, `omake`, `script`).
3. **UniversoWTC (`UminekoPS3ficationEs`)**: Equipo responsable de la traducción al español de Umineko Project (acreditado dentro del propio bloque `*credits_base` de `es.file`).
4. **`VictoriqueMoe/umineko_quote_finder`**: Herramienta comunitaria que consume contenedores `.file` (`ONS2`) para indexación de citas.

---

## 3. Hipótesis y Experimentos Empíricos

### Hipótesis 1: Naturaleza del contenedor `.file`
* **Observación inicial**: `chiru.file` es texto ASCII plano (`[picture]`), mientras que `es.file`, `en.file`, `ru.file` y `wh.file` son reportados por `file(1)` como `data` binaria, comenzando todos con los bytes `4f 4e 53 32` (`"ONS2"`).
* **Conclusión**: La extensión `.file` NO define un formato único en Umineko Project. `chiru.file` es un archivo de registro INI plano leído por `loadreg`, mientras que los scripts de idioma usan el contenedor binario `ONS2`.

### Hipótesis 2: Estructura del encabezado `ONS2`
* **Experimento**: Se analizaron los primeros 16 bytes de los cuatro archivos de idioma:
  * `es.file` (tamaño total `4,577,201`): `4f4e5332` (`"ONS2"`), `a1d74500` (`4,577,185` LE), `26722b01` (`19,624,486` LE), `6e000000` (`0x6e = 110 = 'n'` LE).
  * `en.file` (tamaño total `4,458,165`): `4f4e5332` (`"ONS2"`), `a5064400` (`4,458,149` LE), `eea32001` (`18,916,334` LE), `6e000000` (`0x6e` LE).
  * `ru.file` (tamaño total `5,078,604`): `4f4e5332` (`"ONS2"`), `3c7e4d00` (`5,078,588` LE), `a3746301` (`23,295,139` LE), `6e000000` (`0x6e` LE).
  * `wh.file` (tamaño total `4,377,294`): `4f4e5332` (`"ONS2"`), `beca4200` (`4,377,278` LE), `f0841c01` (`18,646,256` LE), `6e000000` (`0x6e` LE).
* **Resultado verificado**: En los cuatro archivos, el campo en offset `0x04` es exactamente `file_size - 16`.

### Hipótesis 3: Algoritmo exacto de decodificación en `onscripter-new.exe`
* **Experimento**: Se desensambló la sección `.text` de `onscripter-new.exe` en torno a las referencias a la constante `0x32534e4f` (`"ONS2"`), localizadas en:
  1. `0x1400a3d2d`: Escaneo y validación rápida de archivos `.file` disponibles.
  2. `0x140115560` (`ScriptHandler::readScript`): Cargador principal del script del juego.
* **Hallazgos verificados en el código máquina (`0x140115722..0x1401159ea`)**:
  1. Verifica que `[rbp+0x00] == 0x32534e4f` (`"ONS2"`) y `[rbp+0x0c] == 0x6e`.
  2. Verifica que `0x10 <= comp_size <= 0x10000000` y `0x10 <= uncomp_size <= 0x10000000`.
  3. Carga la dirección `rdi = 0x140bb6640` (offset de archivo `0xbb4840` en `.rdata`), que contiene una tabla de sustitución biyectiva `T` de 256 bytes (permutación de `0x00..0xff`).
  4. **Primera pasada de desofuscación (`0x140115900`)**: Para cada byte `b` del bloque comprimido (`offset 0x10`, longitud `comp_size`):
     $$\text{comp}[i] = T[\text{raw}[i] \oplus \text{0x86}] \oplus \text{0x23}$$
  5. **Descompresión ZLIB (`0x1401159a2`)**: Invoca `uncompress` (de `zlib 1.3.2`) sobre el flujo desofuscado (cuyos primeros dos bytes en `es.file` son `78 9c`, cabecera estándar RFC 1950), produciendo exactamente `19,624,486` bytes.
  6. **Segunda pasada de desofuscación (`0x1401159c0`)**: Para cada byte `b` del flujo descomprimido:
     $$\text{plain}[i] = T[\text{decomp}[i] \oplus \text{0x45}] \oplus \text{0x71}$$
  7. **Validación semántica del script (`0x140116ab4..0x140116b5d`)**: El motor busca dentro de los primeros 256 bytes la directiva `;gameid UminekoPS3fication`.

### Hipótesis 4: Reproducibilidad bit a bit de la compresión ZLIB
* **Experimento**: Al comprimir el flujo pre-segunda-capa con el módulo `zlib` de Python del sistema (enlazado contra `zlib-ng 1.3.1.zlib-ng` en Arch Linux), `zlib.compress(data, 6)` produjo `4,627,736` bytes en lugar de `4,577,185` bytes.
* **Investigación adicional**: Se probó `deflateInit2_` de `zlib` clásico (`1.3.1`, Jean-loup Gailly / Mark Adler) variando `level` (`1..9`) y `memLevel` (`8..9`):
  * Con `level=6, wbits=15, memLevel=9` (los parámetros exactos que utiliza `gzcompress($data, 6)` de PHP en `update-manager.php`), `zlib` clásico regeneró exactamente los `4,577,185` bytes de `es.file`, produciendo un archivo reconstruido con **SHA-256 idéntico bit a bit** (`0c00c9cf156b6429e01e6f1d26a6ae655329ef8301b6719a1742834b524300e1`).
  * Por su parte, `en.file`, `ru.file` y `wh.file` coincidieron bit a bit con `level=6, wbits=15, memLevel=8` en `zlib` clásico.
* **Decisión de diseño**:
  * Almacenar en `manifest.json` los parámetros ZLIB detectados (`zlib_level: 6`, `zlib_wbits: 15`, `zlib_mem_level: 9`).
  * En el compilador (`tools.esfile`), utilizar `zlib` clásico (`deflateInit2` con `memLevel=9`) cuando esté disponible en el entorno para garantizar **igualdad binaria exacta (SHA-256)**, con fallback automático y transparente al `zlib.compressobj(level=6, wbits=15, memLevel=9)` de la biblioteca estándar de Python si el sistema operativo solo dispone de `zlib-ng`, garantizando en todos los casos **equivalencia funcional total** en el motor.

---

## 4. Hallazgos sobre la Estructura Interna del Guion (`es.file`)

El flujo decodificado de `es.file` consta de `19,624,486` bytes en codificación **UTF-8** válida (`585,051` líneas al dividir por `\n`, sin bytes `NUL`).

### 4.1 Saltos de línea mixtos (`CRLF` vs `LF`)
El script presenta `585,050` saltos `\n`, de los cuales `518,487` van precedidos por `\r` (`CRLF`). Se identificaron exactamente `337` transiciones entre `LF` y `CRLF`. Cada capítulo (`*umi1_op`, `*umi1_1`, etc.) proviene de un archivo fuente con terminadores `CRLF` cuya última línea carecía de `\r\n` final antes de ser concatenada con `\n` por el empaquetador.
* **Decisión**: Preservar el terminador exacto (`\r\n` vs `\n`) de cada línea para garantizar reconstrucción sin pérdidas.

### 4.2 Jerarquía real y conteo de entradas traducibles
1. **Capítulos de historia y Omake (`story/ep1..ep8`, `story/omake`)**:
   * `172` capítulos (`163` capítulos principales/teatime/ura_teatime en episodios 1–8 y `9` capítulos en `omake`).
   * `66,562` comandos de diálogo `d` / `d2` en episodios y omake (más `14` en la vista previa de fuentes `*load_font_preference`, totalizando `66,576` comandos `d` / `d2`).
   * De los `66,576` comandos `d` / `d2`, `66,571` están precedidos inmediatamente por una etiqueta `*` única (`*d1`..`*d67510`, `*dhidden1`, `*o1_1`..`*o9_...`, `*goa_1e`..`*kak_10e`), y solo `5` líneas en `*chiru_trailer` / `*omake_chiru_menu` carecen de etiqueta `*` propia.
   * Las `69,950` etiquetas `*` del archivo son **100% únicas globalmente** (0 duplicados).
2. **Definiciones de alias de texto (`stralias` en `*define` y `*bt_def`)**:
   * Total de declaraciones `stralias`: `3,671`.
   * Rutas de archivos gráficos/subtítulos y coordenadas de reloj: `2,120`.
   * Textos localizados (`tips_*`, `r_tips_*`, `grim_*`, `r_grim*`, `chars_*`, `name_*`, `save_*`, `scenario_*`, `date_scenario_*`, `set_*`, `ep8_*`, `trophy_text_*`, `verify_*`, `verification_*`, etc.): `1,551` entradas.
3. **Títulos de pistas musicales (`*bgm_locale_title` y `*bgm_title_language`)**:
   *Asignaciones `mov $BGM_Title,"..."` para los títulos en español y tabla multiidioma.
4. **Cadenas de interfaz, créditos y sistema (`*define`, `*credits_base`, `*o3_start`, `*chiru_trailer`, `*omake_chiru_menu`, `*turu_pettann`, `*teatime_4`)**:
   * Títulos de ventana (`caption`, `versionstr`), créditos (`add $Free1,"..."`), entrada manual de historial (`setlog`), y sprites de texto (`lsp` / `lsph` con prefijo `:s`).

### 4.3 Anomalías preexistentes detectadas en `es.file`
El análisis exhaustivo reveló tres tipos de particularidades en el archivo `es.file` original que un parser ingenuo rompería:
1. **12 líneas `d`/`d2` con número impar de acentos graves (`` ` ``)**: Causadas por erratas tipográficas en la traducción original (doble backtick `` `` `` antes de `[@]` o un backtick extra antes de `...` o `"` en las líneas `35501`, `41228`, `54149`, `103938`, `113336`, `216309`, `225711`, `340322`, `340356`, `358578`, `540645` y `542814`). Sin embargo, al segmentar por secuencias de etiquetas `[...]`, el 100% de los segmentos de texto en las `66,576` líneas empiezan y terminan con `` ` ``.
2. **2 entradas `stralias` multilínea**: `chars_3_hid_2` (líneas `545028–545029`) y `chars_bernquiz_mar_1` (líneas `545382–545383`) contienen un salto de línea literal `\n` dentro de las comillas dobles en lugar de `{n}`.
3. **6 declaraciones `stralias` sin coma separadora**: `clock_scenario_6_10` a `clock_scenario_6_15` (líneas `546044–546049`).

Nuestra herramienta preserva de forma exacta estas construcciones para que el round-trip sin ediciones sea bit a bit idéntico, y las reporta explícitamente como advertencias en los comandos `inspect`, `extract` y `validate`.

---

## 5. Alternativas Descartadas

1. **Extraer `es.file` como un único archivo `.txt` plano de 19.6 MB**: Descartado porque incumple la organización estructurada por episodios/escenas, expone todo el código del motor (coordenadas, lógica condicional, subrutinas) al traductor y facilita romper marcadores `[lv ...]` o etiquetas `*d`.
2. **Generar un único JSON monolítico o 68,000 archivos individuales**: Descartado por ser incómodo para edición humana y control de versiones; se optó por `172` archivos de capítulo bajo `story/ep1..ep8/` y `story/omake/` más catálogos temáticos bajo `strings/`.
3. **Normalizar saltos de línea (`CRLF` → `LF`) o corregir automáticamente las 12 erratas de backticks durante la extracción**: Descartado porque violaría la preservación editorial estricta e impediría alcanzar la igualdad binaria (`SHA-256`) en la prueba de round-trip.

---

## 6. Derechos, Licencias y Exclusión en Git

* El motor **ONScripter-RU** se distribuye bajo **GNU GPLv2** (con código propio de Umineko Project también disponible bajo **BSD 3-Clause**).
* Los guiones narrativos, voces, gráficos y textos traducidos son propiedad intelectual de **07th Expansion**, **Alchemist**, **Umineko Project** y **UniversoWTC**.
* Por consiguiente, `.gitignore` bloquea estrictamente `*.file`, `*.exe`, `*.dll`, `game.hash`, las carpetas de recursos (`backgrounds/`, `graphics/`, `sound/`, `sprites/`, `video/`, `fonts/`, `legacy/`) y los directorios de extracción (`translation*/`). El repositorio solo versiona el código de la herramienta (`tools/esfile`), esquemas (`schemas/`), pruebas con fixtures sintéticas propias (`tests/`) y documentación técnica (`docs/`).
