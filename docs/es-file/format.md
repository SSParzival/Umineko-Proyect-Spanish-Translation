# Especificación Técnica del Formato `es.file` (`ONS2`)

## 1. Resumen Ejecutivo

El archivo `es.file` utilizado por **Umineko Project** (motor **ONScripter-RU**) es un contenedor binario propietario denominado **`ONS2`**. Envuelve un único flujo de script ONScripter-RU codificado en **UTF-8** mediante una tubería de tres etapas:

1. **Ofuscación interna** del texto plano mediante una tabla de sustitución biyectiva `T` de 256 bytes y máscaras XOR (`0x45`, `0x71`).
2. **Compresión ZLIB** (RFC 1950, DEFLATE con ventana de 32 KB, `level=6`, `memLevel=9`).
3. **Ofuscación externa** del flujo ZLIB mediante la misma tabla `T` y un segundo par de máscaras XOR (`0x86`, `0x23`), precedido por un encabezado binario de 16 bytes en orden **little-endian**.

---

## 2. Layout Binario del Contenedor `ONS2`

| Offset | Tamaño | Tipo | Nombre | Valor en `es.file` | Descripción |
|---:|---:|---|---|---|---|
| `0x00` | 4 B | `char[4]` | `magic` | `"ONS2"` (`4f 4e 53 32`) | Firma mágica del contenedor. |
| `0x04` | 4 B | `uint32_le` | `comp_size` | `4,577,185` (`0x0045d7a1`) | Tamaño en bytes del payload comprimido y ofuscado (`file_size - 16`). Rango válido en motor: `[16, 268435456]`. |
| `0x08` | 4 B | `uint32_le` | `uncomp_size` | `19,624,486` (`0x012b7226`) | Tamaño exacto en bytes del script descomprimido. Rango válido en motor: `[16, 268435456]`. |
| `0x0C` | 4 B | `uint32_le` | `key_flag` | `110` (`0x0000006e`, `'n'`) | Constante de versión/formato exigida por `ScriptHandler::readScript` (`[rbp+0x0c] == 0x6e`). |
| `0x10` | `comp_size` | `uint8[]` | `payload` | `a2 f8 30 22 ...` | Flujo ZLIB ofuscado byte a byte. |

* **Alineación y padding**: No existe padding ni alineación adicional al final del archivo (`16 + comp_size == file_size`).
* **Endianness**: Todos los enteros de 32 bits del encabezado son **little-endian** (`<4sIII` en `struct` de Python).

---

## 3. Algoritmo de Codificación y Decodificación

### 3.1 Tabla de sustitución `T` (256 bytes)
Extraída de `onscripter-new.exe` en VMA `0x140bb6640` (file offset `0xbb4840` en `.rdata`). Es una permutación biyectiva de `{0x00 .. 0xFF}`:

```text
37 6a 09 5e 7a af f5 a4 ba 78 84 58 35 1e 6b 0c
49 c6 c3 44 40 9e 6f 65 e4 f6 fe 22 e2 95 c7 38
f0 1a 82 e0 5b 2a d8 e5 ce 2f 74 25 ec 59 c0 45
4b 64 43 dc b0 b9 30 6d 28 d1 16 bb 66 98 92 90
2c a7 f1 80 c1 d4 8b d6 df 24 2d f7 fb 88 4d 3c
72 f3 db 2b 93 73 ef 85 83 ee c2 8d 5c b2 0b 94
3d a8 3f 1c 4c 6e 03 7b 1d 5a 51 a1 70 41 d0 aa
a0 7e cd d5 15 a9 18 76 c9 7d 7f 0e 3a 99 bf ab
3b 14 3e 9a 04 da 02 fd 63 d9 fa 9f 4e e3 61 be
07 11 a6 1b 19 55 8e 77 0a 47 e6 f8 0d cf d7 33
23 1f bc 62 de 9b 29 53 68 e8 21 b6 34 52 87 cb
08 79 f4 67 69 54 e7 86 ea b4 20 71 01 bd 06 31
00 50 c8 b8 ac 5d 57 7c 89 eb b7 36 8f f2 e1 56
81 4a d2 8c f9 ad 60 a5 42 10 5f 12 b3 ff 4f dd
46 26 a2 17 c5 75 91 27 b5 8a d3 13 2e c4 e9 9d
97 39 32 05 0f ca cc 48 fc ae 96 ed 6c 9c b1 a3
```

Sea $T^{-1}$ la tabla inversa tal que $T^{-1}[T[x]] = x$ para todo $x \in \{0..255\}$.

### 3.2 Proceso de decodificación (`es.file` → UTF-8 script)
1. **Desofuscación externa (`LUT1`)**:
   $$\text{zlib\_bytes}[i] = T[\text{payload}[i] \oplus \text{0x86}] \oplus \text{0x23}$$
2. **Inflado ZLIB**:
   $$\text{decomp} = \text{zlib.decompress}(\text{zlib\_bytes})$$
   Verifica automáticamente el checksum **Adler-32** de 32 bits big-endian al final del flujo ZLIB (`0x00b2ab8f` en `es.file`) y comprueba que `len(decomp) == uncomp_size`.
3. **Desofuscación interna (`LUT2`)**:
   $$\text{plaintext}[i] = T[\text{decomp}[i] \oplus \text{0x45}] \oplus \text{0x71}$$

### 3.3 Proceso de codificación (UTF-8 script → `es.file`)
1. **Ofuscación interna (`INV_LUT2`)**:
   $$\text{decomp}[i] = T^{-1}[\text{plaintext}[i] \oplus \text{0x71}] \oplus \text{0x45}$$
2. **Compresión ZLIB**:
   $$\text{zlib\_bytes} = \text{deflateInit2}(\text{decomp},\ \text{level}=6,\ \text{method}=\text{DEFLATED},\ \text{wbits}=15,\ \text{memLevel}=9,\ \text{strategy}=0)$$
3. **Ofuscación externa (`INV_LUT1`)**:
   $$\text{payload}[i] = T^{-1}[\text{zlib\_bytes}[i] \oplus \text{0x23}] \oplus \text{0x86}$$
4. **Empaquetado de encabezado**:
   $$\text{header} = \text{pack}(\text{"<4sIII"},\ \text{b"ONS2"},\ \text{len}(\text{payload}),\ \text{len}(\text{plaintext}),\ \text{0x6e})$$

---

## 4. Gramática y Estructura Textual del Script Decodificado

### 4.1 Validaciones obligatorias del motor al cargar el script
* **Directiva de identificación**: Dentro de los primeros 256 bytes debe aparecer literalmente `;gameid UminekoPS3fication` (en `es.file`, la línea 2 es `;gameid UminekoPS3ficationEs`).
* **Codificación**: UTF-8 sin BOM, sin bytes `0x00` embebidos, terminado en salto de línea `\n`.

### 4.2 Secciones principales del script
| Rango de líneas (`es.file`) | Etiqueta inicial | Contenido |
|---|---|---|
| `1 .. 3,313` | `*define` | Directivas iniciales (`;mode1920...`, `;gameid`), `numalias`, `stralias` de recursos y verificación del sistema, `versionstr`, `caption`, `preset_define`, `defsub`, `game`. |
| `3,314 .. 3,354` | `*start` | Inicialización global de ventanas, velocidades y variables. |
| `3,355 .. 537,137` | `*umi1_op` .. `*ura_teatime_8` | `163` capítulos de historia principal, fiestas de té (`*teatime_1..8`) y fiestas de té ocultas (`*ura_teatime_1..8`) de los Episodios 1 a 8. |
| `537,138 .. 542,852` | `*o1_0` .. `*o9_0` | `9` capítulos de Omake, minijuegos y tráiler de Chiru. |
| `542,853 .. 543,844` | `*ep1_end` .. `*o4r_59` | Secuencias de cierre de episodios, créditos (`*credits_base`) y tabla de saltos de omake. |
| `543,845 .. 546,805` | `*bt_def` | Catálogo central de `stralias` localizados: títulos y textos de Tips, Grimorio, perfiles de personajes (`chars_*`), nombres (`name_*`), menús de guardado (`save_*`), configuración (`set_*`), misterio del EP8 (`ep8_*`) y trofeos (`trophy_text_*`). |
| `546,806 .. 584,843` | `*bt_ep1_def` .. `*set_window_simple_update` | Lógica de menús, galería CG, música (`*bgm_title_language`), trofeos, configuración, vista previa de fuentes (`*goa_1e`..`*kak_10e`) y acertijos. |
| `584,844 .. 585,051` | `*bgm_locale_title` | Tabla de títulos de pistas BGM traducidos al español (`mov $BGM_Title,"..."`). |

### 4.3 Sintaxis de comandos con contenido traducible
1. **Comandos de diálogo (`d` y `d2`)**:
   ```text
   *d7
   d [lv 0*"19"*"11900003"]`"... Kinzo‐{c:86EF9C:san}.`[gstg 1][@][lv 0*"19"*"11900004"]` Tu cuerpo parece estar en buen estado..."`[\]
   ```
   * Precedidos por el comando de ventana de personaje (`msgwnd_<id>`) y una etiqueta única (`*d<num>`).
   * **Marcadores externos `[...]` (NO traducibles)**:
     * `[lv <canal>*"<carpeta>"*"<id_audio>"]`: Reproducción de voz sincronizada.
     * `[@]`: Pausa de clic dentro del mismo cuadro de texto.
     * `[\]`: Pausa de clic y limpieza del cuadro de texto.
     * `[|]`: Avance automático al finalizar voz/animación.
     * `[#][*]`: Punto de sincronización para `d2` (`wait_on_d` / `d_continue`).
     * `[gstg <n>]`, `[gstt <n>]`, `[gstc ...]`: Desbloqueo de entradas de Grimorio, Tips o Personajes.
     * `[!w<ms>]`, `[ak]`, `[nj]`, `[text_speed_t <n>]`, `[text_fade_t <n>]`: Control de temporización y estilo de ventana.
   * ** Segmentos de texto `` `...` `` (Traducibles)**:
     * Pueden incluir etiquetas de formato en línea `{...}` interpretadas por `ONScripter::executeInlineTextCommand`:
       * `{n}`: Salto de línea dentro del cuadro de texto.
       * `{f:5:Beatrice}`: Cambio de fuente (ej. fuente `5` para nombres mágicos).
       * `{c:86EF9C:san}` / `{c:FF0000:...}`: Color hexadecimal (ej. verdad roja `#FF0000`, verdad azul, verdad dorada, verdad morada).
       * `{p:<id>:...}`: Preset tipográfico.
       * `{i:...}`, `{b:...}`, `{u:...}`: Cursiva, negrita, subrayado.
       * `{a:c:...}`, `{w:<px>:}`, `{fit}`, `{nobr}`: Alineación y ajuste de ancho.
       * `{d:<sz>:...}`, `{e:<pct>:...}`, `{m:<px>:...}`: Tamaño de fuente y espaciado de caracteres.
       * `{h:texto:ruby}` / `{ruby:...}`: Anotaciones furigana/ruby.
       * `{0}`..`{9}`: Pausas breves o separadores de caracteres.

2. **Alias de cadenas (`stralias`)**:
   ```text
   stralias <identificador>,"<prefijo_sprite_opcional><texto_con_etiquetas>"
   ```
   * Cuando el valor define un sprite de texto ONScripter, comienza con `:s;#<ColorHex>[#<ColorHoverHex>]`` (por ejemplo `:s;#C7C7C7#FFFFFF`` o `:s;#FFFFFF``).

3. **Títulos de música (`*bgm_locale_title` / `*bgm_title_language`)**:
   ```text
   if %BGM_Id == <id> mov $BGM_Title,"<título>" : return
   ```

---

## 5. Grado de Certeza

| Componente | Estado | Evidencia |
|---|---|---|
| Encabezado `ONS2` (16 bytes) | **100% Verificado** | Desensamblado de `onscripter-new.exe` (`0x14011572d..0x1401158b8`) y comprobación en `es.file`, `en.file`, `ru.file`, `wh.file`. |
| Tabla de sustitución `T` y máscaras XOR | **100% Verificado** | Extraída de `.rdata` (`0x140bb6640`) y verificada en bucles `0x140115900` y `0x1401159c0`. |
| Compresión ZLIB (`level=6, memLevel=9`) | **100% Verificado** | Reconstrucción bit a bit idéntica (`SHA-256` exacto) frente a `es.file`. |
| Codificación de caracteres (`UTF-8`) | **100% Verificado** | Decodificación estricta de los `19,624,486` bytes sin errores. |
| Bloques opacos o desconocidos en el contenedor | **Ninguno (0 bytes)** | `16 + comp_size == 4,577,201 == len(es.file)`. Todo el código no traducible del script se preserva íntegramente como bloques estructurales. |
