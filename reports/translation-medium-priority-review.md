# Matriz Final de Resolución de Casos de Prioridad Media — Umineko Project

Este informe documenta la revisión contextual individualizada y la resolución definitiva de todos los casos clasificados previamente como prioridad media en la localización española de Umineko Project.

## Matriz de Casos y Decisiones Editoriales

| ID | Archivo y Entrada | Hablante | Categoría | Problema Original | Decisión | Texto Anterior $\to$ Texto Posterior | Justificación Lingüística y Técnica |
|---|---|---|---|---|---|---|---|
| `MED-001` | `story/ep8/teatime_8.json`<br>`ep8.teatime_8.d67746` | Bernkastel | `CONCORDANCIA / CONTEXTO` | Omisión de verbo auxiliar en perífrasis continua (*alguien lo entrenando*) | **CORREGIR** | `... Me apuesto algo a que alguien lo entrenando infernalmente.`<br>$\to$<br>`... Me apuesto algo a que alguien lo está entrenando infernalmente.` | Restitución del verbo auxiliar omitido `está` en presente continuo, validado con el guion en inglés (*"I'll bet he has a hellish coach"*) y el audio japonés de Bernkastel. |
| `MED-002` | `story/ep7/umi7_4.json`<br>`ep7.umi7_4.d51677` | Narrador | `SECUENCIA DUPLICADA` | Duplicación accidental de *que* entre glosas ruby adyacentes (*más que que un montón*) | **CORREGIR** | `{ruby:...:aunque ahora no sea más que} {ruby:...:que un montón de chatarra inservible.}`<br>$\to$<br>`{ruby:...:aunque ahora no sea más que} {ruby:...:un montón de chatarra inservible.}` | Supresión de la repetición léxica innecesaria al inicio de la segunda glosa ruby, alineando la correspondencia exacta entre *"an unusable scrap heap now."* y *"un montón de chatarra inservible."* sin desajustar el texto en pantalla. |
| `MED-003` | `story/ep6/umi6_18.json`<br>`ep6.umi6_18.d50079` | Dlanor | `TILDE` | Falta de tilde en *desafio* dentro de etiqueta de tamaño `{f:5:...}` | **CORREGIR** | `Espero con ansias su {f:5:desafio}.`<br>$\to$<br>`Espero con ansias su {f:5:desafío}.` | Acentuación obligatoria de hiato en sustantivo llano `desafío`. |
| `MED-004` | `story/ep6/umi6_18.json`<br>`ep6.umi6_18.d50324` | Erika | `ERRATA` | Errata consonántica *opotunidad* dentro de etiqueta `{p:1:...}` | **CORREGIR** | `{p:1:Siendo más específicos, no tuvo opotunidad de escapar...}`<br>$\to$<br>`{p:1:Siendo más específicos, no tuvo oportunidad de escapar...}` | Restitución de consonante `r` omitida en `oportunidad`. |
| `MED-005` | `story/ep6/umi6_18.json`<br>`ep6.umi6_18.d50428` | Ronove | `ERRATA` | Errata tipográfica *ressurrección* dentro de etiqueta `{f:5:...}` | **CORREGIR** | `aprobación para la {f:5:ressurrección}!!`<br>$\to$<br>`aprobación para la {f:5:resurrección}!!` | Eliminación de doble `s` errónea en `resurrección`. |
| `MED-006` | `story/ep7/umi7_11.json`<br>`ep7.umi7_11.d53813` | Yasu | `ESPACIADO` | Espacio indebido antes de coma dentro de etiqueta en cursiva `{i:...}` | **CORREGIR** | `{i:¡Hurra , ya estoy en casa!}`<br>$\to$<br>`{i:¡Hurra, ya estoy en casa!}` | Eliminación de espacio anómalo antes de signo de puntuación. |
| `MED-007` | `story/ep7/umi7_5.json`<br>`ep7.umi7_5.d51852` | Italiano | `TILDE` | Tilde impropia en *incluído* dentro de glosa ruby | **CORREGIR** | `Yamamoto incluído,`<br>$\to$<br>`Yamamoto incluido,` | Supresión de tilde en participio con diptongo ortográfico `-uido`. |

## Estado Final de la Categoría Media

- **Total de casos evaluados**: 7
- **Casos resueltos con corrección**: 7
- **Casos bloqueados o pendientes**: 0 (100% resueltos con justificación técnica y contextual).
