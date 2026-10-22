# Registro de Hallazgos para Revisión Humana — Umineko Project

Este informe documenta los casos detectados que presentan ambigüedad estilística, sintáctica,
narrativa o dependencias de glosa ruby bilingüe que **NO** deben modificarse automáticamente,
a fin de preservar la fidelidad a la voz narrativa, idiolectos y coherencia técnica.

## Casos Registrados para Decisión Humana

| Archivo | ID Entrada | Personaje | Categoría | Confianza | Fragmento / Detalle | Criterio / Decisión Recomendada |
|---|---|---|---|---|---|---|
| `story/ep8/teatime_8.json` | `ep8.teatime_8.d67746` | `battler` | `POSIBLE ERROR CONTEXTUAL` | `MEDIA` | `... Me apuesto algo a que alguien lo entrenando infernalmente.` | Posible omisión de verbo auxiliar ('está' / 'estuvo' o 'entrenó'). Se requiere decisión editorial humana para no alterar el ritmo del diálogo. |
| `story/ep7/umi7_4.json` | `ep7.umi7_4.d51677` | `narrator` | `POSIBLE ERROR DE EXTRACCIÓN` | `MEDIA` | `{ruby:even though it's nothing more than:aunque ahora no sea más que} {ruby:an unusable scrap heap now.:que un montón de chatarra inservible.}` | Duplicación de 'que' debida a la división de etiquetas ruby entre el texto inglés y español. No se altera automáticamente para no desalinear la glosa. |
| `story/ep6/umi6_16.json` | `ep6.umi6_16.d49232` | `battler` | `NO MODIFICAR` | `BAJA` | `Deten... te...` | Tartamudeo e interrupción deliberada de 'Detente... te...'. La palabra completa es llana sin tilde ('detente'); la fragmentación es idiolecto expresivo. |
| `story/ep6/umi6_16.json` | `ep6.umi6_16.d49256` | `battler` | `NO MODIFICAR` | `BAJA` | `deten... te...` | Tartamudeo e interrupción deliberada de 'detente... te...'. Idiolecto expresivo protegido. |
| `story/ep8/umi8_16.json` | `ep8.umi8_16.d65167` | `battler` | `NO MODIFICAR` | `BAJA` | `¡¡D-Deten—!!` | Tartamudeo/interrupción abrupta de '¡¡Detente—!!'. Expresión truncada protegida. |

## Recomendación Editorial

- **Preservar idiolectos y stutters**: Los tartamudeos y frases fragmentadas (`Deten... te...`, `¡¡D-Deten—!!`) reflejan shock o vacilación emocional y no deben ser 'corregidos' a formas gramaticales formales.
- **Preservar glosas ruby bilingües**: Cuando una división de tags ruby inglesa genera una repetición aparente en español (`más que} {ruby:...:que un`), unificarlas rompería la correspondencia con el texto superior en pantalla.
