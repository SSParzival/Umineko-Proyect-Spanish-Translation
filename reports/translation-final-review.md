# Informe Final de Control de Calidad Lingüístico, Ortotipográfico y Técnico — Umineko Project

Este documento constituye la memoria técnica de cierre de la revisión lingüística, ortotipográfica, contextual y técnica realizada sobre los 182 catálogos estructurados de la traducción al español de Umineko Project, extraídos de `es.file`.

---

## 1. Resumen Ejecutivo de la Revisión de Cierre

- **Alcance del proyecto**: 182 catálogos editables (104 historias principales de los Episodios 1 a 8, 8 omakes / tés y 70 catálogos de interfaz y cadenas auxiliares).
- **Entradas totales revisadas**: 68.651 entradas (200.014 campos de texto, sumando segmentos de diálogo y cadenas de sistema).
- **Correcciones totales consolidadas**: **563**
  - **Fase 1 (Alta confianza)**: 489 correcciones ortotipográficas objetivas (tildes, erratas obvias, secuencias duplicadas, nombres propios).
  - **Fase 2 (Prioridad media contextual)**: 7 correcciones verificadas caso por caso contra guion en inglés y audio japonés (`REV-001` a `REV-007`).
  - **Fase 3 (Normalización de dobles espacios)**: 67 correcciones focalizadas en suprimir dobles espacios innecesarios fuera de etiquetas, cumpliendo con la directiva explícita del usuario.
- **Expresiones protegidas / Prioridad baja**: 100% conservadas (tartamudeos de Battler en Ep6/Ep8, espaciado artístico del teléfono/puzzle de Beatrice en Ep7 Ch2).
- **Estado de validación**: `VALID` (0 errores en esquema, 0 etiquetas desbalanceadas, 0 discrepancias de hash en `manifest.json`).
- **Estado de pruebas unitarias**: 31 de 31 pruebas aprobadas (`OK`).
- **Integridad del archivo original**: `es.file` conservado 100% intacto (`SHA-256: 0c00c9cf156b6429e01e6f1d26a6ae655329ef8301b6719a1742834b524300e1`).
- **Archivo recompilado final**: `es.reviewed.file` generado determinísticamente (`SHA-256: ffb56fe2ba8e0d70494dc1bafd241ca840904da7358e9d9b1168012c2f65f8e7`).
- **Round-trip inverso**: `diff_targets(translation, reextracted)` arrojó `Plaintext identical: True`, `Semantically identical: True`, 0 drift.

---

## 2. Verificación de Correcciones de Prioridad Alta

Se comprobó que las 489 correcciones iniciales de prioridad alta aplicadas en los Episodios 1 a 8 y cadenas auxiliares no presentaron regresiones sintácticas ni afectaron las etiquetas de control del motor PONScripter:

1. **Acentuación ortográfica**: Se restituyeron tildes en adverbios y pronombres interrogativos/exclamativos, formas verbales con hiato (`teníamos`, `había`) y agudas terminadas en vocal/n/s (`también`, `después`, `aquí`).
2. **Erratas léxicas**: Se subsanaron omisiones o trasposiciones evidentes de caracteres (`extremadamente`, `descansando`, `arrepentimiento`, `milagro`).
3. **Consonantes geminadas**: Se normalizaron simplificaciones indebidas (`resurreción` $\to$ `resurrección`, `perfeción` $\to$ `perfección`).
4. **Secuencias duplicadas**: Se eliminaron duplicaciones tipográficas accidentales de partículas (`que que`, `en en`, `de de`, `solo solo`).
5. **Nombres propios de canon**: Se homogeneizó la grafía de nombres como `Battler` (corrigiendo `Batlter`/`Batller`), `Ushiromiya` (`Ushromiya`), `George` (`Geoge`) y festividades (`Halloween`).

---

## 3. Resolución Definitiva de Hallazgos de Prioridad Media

Cada uno de los 7 casos ambiguos de prioridad media fue investigado con acceso a su contexto oracional amplio, guion comparado y audio original, registrándose en `translation/config/review-decisions.jsonl`:

| ID | Catálogo y Entrada | Hablante | Antes | Después | Justificación Técnica y Lingüística |
|---|---|---|---|---|---|
| `REV-001` | `story/ep8/teatime_8.json`<br>`ep8.teatime_8.d67746` | Bernkastel | `... Me apuesto algo a que alguien lo entrenando infernalmente.` | `... Me apuesto algo a que alguien lo está entrenando infernalmente.` | Restitución del auxiliar *está* en perífrasis continua, cotejado con *"I'll bet he has a hellish coach"* y audio japonés. |
| `REV-002` | `story/ep7/umi7_4.json`<br>`ep7.umi7_4.d51677` | Narrador | `{ruby:...:aunque ahora no sea más que} {ruby:...:que un montón de chatarra inservible.}` | `{ruby:...:aunque ahora no sea más que} {ruby:...:un montón de chatarra inservible.}` | Supresión de duplicación de *que* al inicio de la segunda glosa ruby contigua, evitando repetición visual en pantalla. |
| `REV-003` | `story/ep6/umi6_18.json`<br>`ep6.umi6_18.d50079` | Dlanor | `Espero con ansias su {f:5:desafio}.` | `Espero con ansias su {f:5:desafío}.` | Tilde de hiato en sustantivo llano *desafío* dentro de etiqueta `{f:5:...}`. |
| `REV-004` | `story/ep6/umi6_18.json`<br>`ep6.umi6_18.d50324` | Erika | `{p:1:Siendo más específicos, no tuvo opotunidad de escapar...}` | `{p:1:Siendo más específicos, no tuvo oportunidad de escapar...}` | Subsanación de omisión de *r* en *oportunidad* dentro de etiqueta `{p:1:...}`. |
| `REV-005` | `story/ep6/umi6_18.json`<br>`ep6.umi6_18.d50428` | Ronove | `aprobación para la {f:5:ressurrección}!!` | `aprobación para la {f:5:resurrección}!!` | Eliminación de doble *s* errónea en *resurrección* dentro de etiqueta `{f:5:...}`. |
| `REV-006` | `story/ep7/umi7_11.json`<br>`ep7.umi7_11.d53813` | Yasu | `{i:¡Hurra , ya estoy en casa!}` | `{i:¡Hurra, ya estoy en casa!}` | Supresión de espacio tipográfico espurio antes de coma en etiqueta en cursiva. |
| `REV-007` | `story/ep7/umi7_5.json`<br>`ep7.umi7_5.d51852` | Italiano | `Yamamoto incluído,` | `Yamamoto incluido,` | Supresión de tilde impropia en participio con diptongo `-uido` en glosa ruby. |

---

## 4. Confirmación de Hallazgos de Prioridad Baja y Expresiones Protegidas

En estricta observancia del principio conservador:
- Los tartamudeos dramáticos de Battler (`"D-De-Deten... te..."` en `ep6.umi6_16.d49232`, `"N-No... deten... te..."` en `ep6.umi6_16.d49256` y `"¡¡D-Deten—!!"` en `ep8.umi8_16.d65167`) se confirmaron como idiolectos expresivos intencionales y se mantuvieron intactos.
- Las formas coloquiales y adaptaciones fonéticas justificadas por el registro de los personajes se conservaron sin alteraciones.

---

## 5. Auditoría Exhaustiva y Normalización de Dobles Espacios

Siguiendo la instrucción directa del usuario (*"En cuanto a los dobles espacios, la mayoría del tiempo NO SON NECESARIOS, piensa que solo cuando el contexto de verdad lo amerita, so haz última revisión enfocada en eso del doble espacio"*):

1. **Análisis empírico del corpus**:
   - Se identificaron exactamente **70 instancias** con dobles espacios en segmentos de diálogo y textos de cadenas.
2. **Casos preservados por contexto y diseño artístico (3 instancias)**:
   - `story/ep7/umi7_2.json` (`ep7.umi7_2.d51163`): `"{f:5:Yo... no  p u e d o  llamarlo. ¿Aun así  q uie r e  que lo  haga}?..."` (llamada telefónica espectral de Beatrice con letras separadas).
   - `story/ep7/umi7_2.json` (`ep7.umi7_2.d51165`): `"{f:5:Si  us ted  ins iste... yo lo  puedo  ll amar  especi  almente para  usted,  pero}..."` (continuación de la transmisión entrecortada).
   - `story/ep7/umi7_2.json` (`ep7.umi7_2.d51167`): `'"' + " "*60 + '."'` (pausa dramática de 60 espacios previa al punto final).
3. **Casos normalizados a espacio simple (67 instancias)**:
   - **24 segmentos con doble espacio inicial**: El motor PONScripter utiliza un espacio simple al inicio del segmento posterior a una pausa de clic (`@`). 59.563 segmentos utilizaban 1 espacio, mientras que 24 contenían erróneamente 2 espacios (`  pero...` $\to$ ` pero...`). Se normalizaron a 1 espacio.
   - **7 segmentos con doble espacio final**: En `ep8/umi8_14.json` se suprimieron espacios residuales al final de línea (`Era una mujer.  ` $\to$ `Era una mujer.`).
   - **33 dobles espacios internos**: Espacios duplicados tras puntos suspensivos o entre palabras (`resistir...  no` $\to$ `resistir... no`, `arrestando al  culpable` $\to$ `arrestando al culpable`, `cara del viejo  bastardo` $\to$ `cara del viejo bastardo`).
   - **3 dobles espacios en cadenas de sistema**: En `strings/characters.json` (`Lucifer  ({p:4:...})` $\to$ `Lucifer ({p:4:...})`) y `strings/trophies.json` (`Regalo de Kinzo:  Mango` $\to$ `Regalo de Kinzo: Mango`).

---

## 6. Validación de Estructura, Esquema y Hashes

Tras la aplicación de los cambios:
- Se ejecutó `python3 -m tools.translation_lint normalize-spaces --dry-run translation/`, certificando que **0 dobles espacios innecesarios** quedan pendientes.
- Se actualizaron los hashes SHA-256 de los 41 catálogos modificados en `translation/manifest.json`.
- Se ejecutó `python3 -m tools.esfile validate translation/`, arrojando:
  ```
  Validation VALID: translation (182 catalogs, 11 blocks, 68,651 entries, 0 errors, 28 warnings, 0 modified catalogs).
  ```

---

## 7. Reconstrucción, Determinismo y Round-Trip Inverso

La compilación y verificación técnica arrojó los siguientes resultados:

1. **Compilación estricta**:
   ```bash
   python3 -m tools.esfile build translation/ es.reviewed.file --force --strict
   ```
   Generó `es.reviewed.file` con un tamaño de 4.576.804 bytes.
2. **Determinismo bit a bit**:
   Dos compilaciones sucesivas e independientes produjeron sumas SHA-256 idénticas (`ffb56fe2ba8e0d70494dc1bafd241ca840904da7358e9d9b1168012c2f65f8e7`).
3. **Prueba de reextracción y equivalencia semántica**:
   Se extrajo `es.reviewed.file` en un directorio temporal y se ejecutó `diff_targets`:
   - `Plaintext identical`: **True**
   - `Semantically identical`: **True**
   - `Added entries`: **0**
   - `Removed entries`: **0**
   - `Modified entries`: **0**
   - `Altered command markers`: **0**
   - `Altered structural blocks`: **0**

---

## 8. Matriz de Checksums y Archivos

| Archivo | Tamaño (bytes) | SHA-256 | Estado |
|---|---:|---|---|
| `es.file` (Original) | 4.577.201 | `0c00c9cf156b6429e01e6f1d26a6ae655329ef8301b6719a1742834b524300e1` | Intacto / Preservado |
| `es.reviewed.file` (Revisado) | 4.576.804 | `ffb56fe2ba8e0d70494dc1bafd241ca840904da7358e9d9b1168012c2f65f8e7` | Compilado y validado |
| `translation/manifest.json` | 38.647 | `bf741364d930263f338d1502faae3d5e2e4ef166a4bc2c3fe091c68f2fe963d3` | Actualizado y sincronizado |

---

## 9. Estructura de Commits Git

La totalidad de los avances quedó organizada en una secuencia limpia de commits:

- `68726c5`: `fix: resolve medium priority translation review findings`
- `7221d12`: `fix: normalize unnecessary double spaces across Spanish translation`
- `a50a8f0`: `test: preserve verified translation forms and conventions`
- `027dee7`: `test: validate the final Spanish translation build`
- `[HEAD]`: `docs: record the final Spanish translation review`
