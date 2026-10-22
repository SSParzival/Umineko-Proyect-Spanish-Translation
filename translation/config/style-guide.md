# Guía de Estilo Ortotipográfico — Traducción Española de Umineko Project

Esta guía documenta las convenciones editoriales, lingüísticas y técnicas seguidas durante la revisión ortotipográfica de los catálogos JSON en `translation/`.

## 1. Principio Rector: Edición Conservadora y Preservación de Voz

1. **Corrección objetiva sin reescritura**: Solo se corrigen errores ortográficos, erratas tipográficas, omisiones o excesos de tildes inequívocos, palabras duplicadas por accidente, palabras fusionadas erróneamente (`apunto de` → `a punto de`, `Apesar` → `A pesar`), concordancias gramaticales rotas (`han juntando` → `han juntado`, `Este vía` → `Esta vía`) y erratas en nombres propios canónicos (`Batlter` → `Battler`, `Ushromiya` → `Ushiromiya`).
2. **Respeto a los idiolectos y registros**:
   - **Hideyoshi Ushiromiya**: Se conserva íntegramente su habla coloquial con elisiones marcadas por apóstrofo (`to's`, `pensa'o`, `na'`, `pa'`, `'tá`, `rápi'o`, `búsque'as`) que adaptan su dialecto de Kansai.
   - **Maria Ushiromiya**: Se conservan sus interjecciones (`uu`, `uu-uu`), infantilismos y repeticiones expresivas.
   - **Beatrice, Ronove, Virgilia, Dlanor**: Se conserva el registro solemne, arcaizante o inquisitorial, incluidas mayúsculas enfáticas de conceptos mágicos (`Verdad Roja`, `Verdad Azul`, `Fragmento`, `Tierra Dorada`, `Magia`, `Bruja`).
   - **Alargamientos vocálicos y consonánticos**: Se preservan en gritos, llantos y risas (`Battleer`, `Bwattleer`, `verdaaaad`, `kihihihi`, `ahahaha`, `pu ku ku`).

## 2. Acentuación y Tildes (Norma RAE / ASALE)

1. **Monosílabos**: Los monosílabos verbales y nominales no llevan tilde salvo en los casos de tilde diacrítica:
   - Se corrigen *fé* → `fe`, *ví* → `vi`, *dí* → `di`, *fuí* → `fui`, *dió* → `dio`, *vió* → `vio`.
2. **Hiatos y diptongos**:
   - Los participios e infinitivos terminados en `-uido`, `-uida`, `-uir` contienen diptongo ortográfico y no llevan tilde (*construído* → `construido`, *incluído* → `incluido`, *huír* → `huir`, *destruído* → `destruido`, *fluída* → `fluida`, *guíadas* → `guiadas`).
   - El verbo *rehusar* lleva tilde en las formas rizotónicas por hiato con *h* intercalada (`rehúso`, `rehúsas`, `rehúsa`, `rehúsan`, `rehúsen`).
3. **Palabras llanas, agudas y esdrújulas**:
   - Palabras llanas terminadas en `-n` o `-s` no llevan tilde salvo hiato: se corrigen *crímen* → `crimen`, *órden* → `orden` (singular), *márgen* → `margen`, *jóven* → `joven`, *casí* → `casi`.
   - En plural pasan a ser esdrújulas y llevan tilde: `órdenes`, `jóvenes`, `márgenes`, `crímenes`.
   - Verbos con pronombres enclíticos siguen las reglas generales de acentuación (`déjame`, `díganme`, `escúchame`, `pregúntale`, `acéptalo`, `comiéndose`, `dándole`, `viéndola`, `ensártenlas`, `muéstrenlas`, `mantenlo`).
4. **Tilde diacrítica en interrogativos y relativos**:
   - Llevan tilde los interrogativos/exclamativos directos e indirectos (`qué`, `quién`, `cómo`, `cuándo`, `cuánto`, `dónde`).
   - No llevan tilde los pronombres relativos y conjunciones átonas (`la cual`, `los cuales`, `un lugar donde dormir`, `primos, quienes habían...`, `Cuando madure...`).

## 3. Nombres Propios y Terminología Canónica

| Forma Canónica | Erratas Corregidas | Notas |
|---|---|---|
| `Battler` | `Batlter`, `Batller` | Se conserva `Battleer` / `Bwattleer` en gritos expresivos. |
| `Ushiromiya` | `Ushromiya` | Apellido familiar. |
| `George` | `Geoge` | Nieto mayor. |
| `Krauss` | `Kraus` | Primer hijo de Kinzo. |
| `Natsuhi` | `Nastuhi` | Esposa de Krauss. |
| `Shannon` | `Sannon` | Sirvienta de la familia. |
| `Kumasawa` | `Kumsawa` | Sirvienta veterana. |
| `Okonogi` | `Okonagi` | Ejecutivo del Grupo Ushiromiya. |
| `Niijima` | `Nijima` | Isla vecina a Rokkenjima. |
| `Mariage Sorcière` | `Marriage Sorcière` | Alianza de brujas de Beatrice y Maria (francés canónico). |
| `Lucifer` | `Lúcifer` | Hermana mayor de las Siete Estacas del Purgatorio. |
| `Satán‐nee` | `Satan‐nee` | Hermana entre las Siete Estacas (con tilde aguda en español). |
| `Halloween` | `Hallowen`, `hallowen` | Festividad en inglés con mayúscula inicial. |
| `Siete Estacas` | `Sietes Estacas` | Concordancia de numeral cardinal (`Siete`). |

## 4. Puntuación, Espaciado y Etiquetas Técnicas

1. **Espaciado**: No debe existir espacio antes de coma (`,`), punto (`.`), punto y coma (`;`) ni dos puntos (`:`).
2. **Guiones en honoríficos**: La traducción original emplea tanto el guion ASCII (`-`, `U+002D`) como el guion Unicode (`‐`, `U+2010`) en sufijos como `-san`, `‐sama`, `-ojousama`. Se preserva el carácter exacto de cada línea para evitar diffs innecesarios en el binario reconstruido.
3. **Etiquetas inline de ONScripter-RU**:
   - Queda estrictamente prohibido alterar las etiquetas `{n}`, `{c:...}`, `{f:...}`, `{p:...}`, `{i:...}`, `{e:...}`, `{a:...}`, `{y:...}`, `{0}`, `{-}` o los marcadores entre corchetes `[lv ...]`, `[@]`, `[!]`, `[\]`, `[w...]`.
   - Toda corrección en un diálogo (`segments[i]["text"]`) debe actualizar automáticamente la vista previa `entry["text"]` y las listas `inline_tags`.
