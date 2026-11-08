# Umineko Project: traducción al español revisada

Versión corregida del guion en español de [Umineko Project](https://umineko-project.org/). Parte de la traducción de [Universo When They Cry](https://universowtc.github.io/) y corrige 563 errores: tildes, erratas, palabras repetidas, nombres mal escritos y espacios de más. No cambia el estilo de la traducción ni la forma de hablar de los personajes.

Todo cabe en un solo archivo, `es.file`, que reemplaza al que instala el parche en español.

## Antes de empezar

Necesitas tener instaladas y funcionando estas dos cosas:

1. **Umineko Project.** Se descarga desde <https://umineko-project.org/en/downloads/>.
2. **El parche en español de Universo When They Cry.** Se descarga desde <https://github.com/UniversoWTC/Umineko-Project-Espa-ol/releases>. Ese parche trae las imágenes, los menús y los subtítulos en español. Este repositorio no los incluye: solo mejora el texto.

Si ya juegas Umineko Project en español, tienes las dos cosas y puedes pasar directo a la instalación.

## Instalación

1. Descarga `es.file` desde la [página de la última versión](https://github.com/SSParzival/Umineko-Proyect-Spanish-Translation/releases/latest). Baja hasta la sección **Assets** y haz clic en `es.file`. No descargues los archivos «Source code»: son el código de este repositorio y no sirven para jugar.
   - También puedes usar el enlace directo: <https://github.com/SSParzival/Umineko-Proyect-Spanish-Translation/releases/latest/download/es.file>
   - Si el navegador avisa que el archivo no se descarga con frecuencia, elige «Conservar» o «Descargar de todos modos».
2. Abre la carpeta donde instalaste Umineko Project. La reconoces porque tiene el programa del juego (`onscripter-ru.exe` en Windows), archivos como `en.file`, `chiru.file` y `game.hash`, y carpetas como `sound`, `sprites` y `graphics`. En esa misma carpeta ya hay un `es.file`, el que dejó el parche en español.
3. Guarda una copia del `es.file` que ya está en la carpeta del juego. Lo más simple es copiarlo al Escritorio. Así puedes volver atrás si algo sale mal.
4. Copia el `es.file` que descargaste (normalmente queda en la carpeta Descargas) y pégalo en la carpeta del juego. Cuando Windows pregunte, elige «Reemplazar el archivo en el destino».
   - El archivo tiene que llamarse exactamente `es.file`. Si el navegador lo guardó como `es (1).file` o algo parecido, cámbiale el nombre antes de pegarlo.
5. Abre el juego. Si aparece en otro idioma, entra en la configuración del juego y cambia el idioma a «Español». Después cierra el juego y vuelve a abrirlo, porque el cambio de idioma se aplica al reiniciar.

En Linux, macOS y Android se hace lo mismo: reemplazar `es.file` en la carpeta donde están los archivos del juego.

Cambiar este archivo no borra tus partidas guardadas.

## Si algo sale mal

- **El juego sigue en inglés.** Revisa el paso 5: el idioma se cambia en la configuración y hay que reiniciar el juego.
- **Faltan imágenes o los menús salen en inglés.** Falta el parche de Universo When They Cry. Instálalo y luego repite los pasos 3 y 4.
- **Reinstalaste o actualizaste el parche de Universo When They Cry.** El parche vuelve a poner su propio `es.file`. Repite los pasos 3 y 4.
- **La verificación de archivos del juego marca `es.file` como modificado.** Es esperable: es un archivo distinto al que trae el parche.
- **Quieres volver a la versión anterior.** Copia el `es.file` que guardaste en el paso 3 de vuelta a la carpeta del juego y reemplaza el que está ahí.

## Qué se corrigió

| Tipo de corrección | Cantidad |
|---|---:|
| Tildes | 368 |
| Espacios de más o mal puestos | 74 |
| Erratas | 69 |
| Palabras repetidas por error | 18 |
| Nombres propios mal escritos | 16 |
| Otras faltas de ortografía | 12 |
| Concordancia (género, número o tiempo verbal) | 6 |
| **Total** | **563** |

Se dejó tal cual, a propósito:

- La forma de hablar de Hideyoshi (`pa'`, `na'`, `'tá`, `pensa'o`).
- Los tartamudeos y alargamientos de voz (`Battleer`, `kihihihi`).
- El texto con espacios del acertijo del teléfono en el episodio 7.
- Los términos propios de la obra (`Verdad Roja`, `Tierra Dorada`) y los honoríficos japoneses.

Las reglas que se siguieron están en [`translation/config/style-guide.md`](translation/config/style-guide.md).

## Para quien quiera editar la traducción

Esta parte es solo para quien quiera cambiar textos y generar su propio `es.file`. Para jugar no hace falta.

El texto está en archivos JSON:

- `translation/story/`: diálogos y narración de los episodios 1 a 8 y de los omake.
- `translation/strings/`: menús, tips, personajes, trofeos, créditos y títulos de música.
- `translation/blocks/`: código del juego. No se edita; si cambia, la compilación se detiene.

En los diálogos se edita `segments[i].text`, sin agregar ni quitar segmentos, porque cada uno va sincronizado con una voz. En `strings/` se edita el campo `text`. Las etiquetas entre llaves (`{c:FF0000:...}`, `{f:5:...}`) deben quedar cerradas.

Se necesita Python 3.10 o superior, sin librerías extra (pytest solo para las pruebas):

```bash
python3 -m tools.esfile validate translation/ --strict   # revisa que todo esté en orden
python3 -m tools.esfile build translation/ out/es.file   # genera el es.file
python3 -m tools.translation_lint scan translation/      # busca faltas de ortografía comunes
python3 -m pytest                                        # corre las pruebas
```

## Créditos

- *Umineko no Naku Koro ni*: 07th Expansion.
- Umineko Project: [umineko-project.org](https://umineko-project.org/).
- Traducción al español: [Universo When They Cry](https://universowtc.github.io/).
- Revisión y correcciones: [SSParzival](https://github.com/SSParzival).

Esta revisión es independiente. No es una versión oficial de Universo When They Cry ni de Umineko Project.
