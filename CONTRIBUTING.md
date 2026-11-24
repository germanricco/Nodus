# Contribuir a Nodus

Gracias por el interés. Las ideas y los reportes de errores son bienvenidos en [Issues](https://github.com/germanricco/Nodus/issues): si encontraste un problema, cuenta qué hiciste, qué esperabas y qué pasó, con la versión de Nodus (está en Ajustes). Esta guía explica cómo ejecutar Nodus desde el código, cómo está organizado y cómo se publica una versión.

## Preparar el entorno

Hace falta **Python 3.11** en Windows y **Python 3.12** en Linux: la versión de Qt que usa Nodus (PySide6 6.12.0), compilada para Linux, cierra Python con un error al correr sobre 3.11, y con 3.12 no. En Windows, conviene instalarlo desde [python.org](https://www.python.org/downloads/) y no desde la Microsoft Store: esa versión guarda los archivos de `AppData` en una carpeta privada, donde el Explorador no los encuentra. Desde una terminal, en la carpeta del proyecto:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]" -c constraints.txt   # en Linux o macOS: .venv/bin/python
.venv/Scripts/python -m nodus
```

`constraints.txt` fija la versión exacta de todo lo que se instala, Qt y PyInstaller incluidos: es lo mismo que usan la CI y la compilación del instalador, así que un test que pasa en tu máquina pasa allá. Para subir una versión, se cambia ahí y se corren los tests; el archivo dice cómo regenerarlo. La interfaz usa `PySide6-Essentials`, los módulos básicos de Qt, y no el paquete `PySide6` entero.

Para probar sin tocar tus datos reales, define la variable de entorno `NODUS_DATA_DIR` con otra carpeta antes de abrirlo; Nodus crea ahí su base de datos y sus copias de seguridad.

La forma rápida de probar con tus datos de siempre es `scripts/dev.py`. Copia tu base real en `dev-data/` (ignorada por git) y abre Nodus sobre esa copia. La base real se lee en modo solo lectura, así que nunca cambia, aunque el Nodus instalado esté abierto.

```bash
.venv/Scripts/python scripts/dev.py          # copia nueva de los datos reales
.venv/Scripts/python scripts/dev.py --keep   # sigue con la copia anterior y sus cambios
.venv/Scripts/python scripts/dev.py --demo   # empieza de cero con datos de demostración
```

## Comandos de uso diario

```bash
.venv/Scripts/python -m pytest                       # tests
.venv/Scripts/python -m pytest --cov=nodus          # tests, con la cobertura de cada módulo
.venv/Scripts/python -m ruff check .                 # lint
.venv/Scripts/python -m ruff format .                # formato
.venv/Scripts/python scripts/screenshot.py --demo    # capturas de cada pantalla, claras y oscuras (--lang en: en inglés)
.venv/Scripts/python scripts/translations.py extract # suma al catálogo los textos nuevos
.venv/Scripts/python scripts/translations.py check   # qué texto falta traducir o tiene mal un marcador
.venv/Scripts/python scripts/translations.py review  # una página con los textos de cada pantalla en los dos idiomas
```

Las capturas se generan sobre una base temporal con datos de demostración (`scripts/demo_data.py`), así que muestran todas las pantallas con contenido sin tocar ningún dato real. Después de cambiar la interfaz, conviene generarlas y revisarlas en los dos temas. Las que muestran los README viven en `docs/images/`, y las del README en inglés, tomadas con `--lang en`, en `docs/images/en/`; se renuevan al cerrar cada versión.

## Cómo está organizado el código

El paquete `src/nodus/` está en capas que solo dependen hacia abajo:

- `models`: el dominio puro (dinero, cuentas, períodos, presupuestos), sin Qt ni SQL.
- `database`: la conexión a SQLite, las migraciones y los repositorios que traducen filas a modelos.
- `services`: las reglas de negocio, como saldos, validaciones o qué vence.
- `ui`: ventanas, páginas, diálogos y tema. La interfaz nunca ejecuta SQL ni calcula saldos.

Dentro de `services` y de `ui`, cada carpeta agrupa archivos que comparten una regla, que su `__init__.py` dice en una línea. En `services`, los servicios se agrupan por lo que manejan: `accounts`, `transactions`, `classification` (categorías, beneficiarios y etiquetas), `planning` (presupuestos y metas) y `app` (ajustes, avisos, novedades, recorrido y deshacer). `reports` arma cifras combinando otros servicios y nunca toca la base de datos; los ingresos y gastos en pesos se cuentan siempre con `conversion.py`, para que todas las pantallas sumen igual. `external` es la única puerta hacia internet y hacia Windows. En `ui`, `shell` tiene la ventana principal y las partes que existen solo para ella; `text` reúne los textos que se arman para el usuario; `pages/base` tiene las clases de las que parte cada página y las partes que comparten varias; una página nunca importa otra, y lo que se puede hacer sobre un registro desde más de una (editar, borrar, omitir) está en `actions`; y `widgets` tiene piezas reutilizables, ordenadas en `charts`, `inputs` y `tables`, que no conocen las páginas ni los diálogos que las usan.

Los tests en `tests/` siguen la misma estructura. Algunas reglas que conviene conocer:

- **Dinero:** los montos se guardan en centavos enteros, nunca en números de punto flotante, que acumulan errores de redondeo.
- **Registro:** cada módulo anota con `logging.getLogger(__name__)`, y `config/logs.py` lo escribe en `logs/nodus.log`, junto a los datos. Una línea dice qué pasó o qué tipo de error hubo, nunca montos, nombres ni notas, porque el usuario puede mandar el registro al reportar un problema; los mensajes de error pasan por `scrub`, que tapa lo que va entre comillas, los números largos y las rutas. Un error que nada atrapó llega a `ui/error_reporter.py`, que lo anota y lo muestra con «Enviar reporte».
- **Migraciones:** el esquema vive en `src/nodus/database/migrations/NNN_nombre.sql` y se aplica con `PRAGMA user_version`. Una migración publicada nunca se edita, porque las bases de los usuarios ya la aplicaron: cada cambio va en un archivo nuevo con el número siguiente.
- **Tests:** además de los de cada módulo, `tests/test_end_to_end.py` recorre cada área como lo haría una persona: presupuestos, cargos recurrentes, cuotas, reembolsos, metas, grupos de cuentas, deshacer y copias. Lo hace a través de los diálogos y las páginas (`tests/journeys.py`) y termina reabriendo el archivo. Antes de cada `qtbot.addWidget`, `conftest.py` fuerza una recolección de basura, así un objeto que solo sostiene un ciclo de referencias desaparece en el test como desaparecería en la app. Otro test pone un límite al tiempo de arranque con datos de demostración.
- **Idiomas:** el código, los identificadores y los mensajes de commit van en inglés; los textos que ve el usuario se escriben en español, que es el idioma fuente, y se marcan para traducir con `nodus/i18n.py`: `_("Guardar")`, `ngettext("{n} cuota", "{n} cuotas", n).format(n=n)` para los plurales y una frase entera con marcadores con nombre (`_("Vence el {day}").format(day=…)`), nunca pedazos pegados, porque cada idioma ordena distinto. Nunca va un `_()` dentro de un f-string: el extractor no lo ve y el texto queda sin traducir. Los montos, fechas, horas y porcentajes se escriben siempre con `Money.format`, `format_date`, `format_time`, `format_percent` y las demás funciones de `models/language_format.py` y `models/period.py`, que siguen al idioma: en inglés, «$1,234.56», «11/18/2026» y «48%». Un texto se traduce al usarse, nunca al importar el módulo: una tabla de textos guarda `N_("…")` y quien la muestra llama a `_()`. Las traducciones viven en `src/nodus/locale/<idioma>/LC_MESSAGES/nodus.po`; `scripts/translations.py extract` suma los textos nuevos y un test falla mientras alguno no tenga su traducción. El `.mo` que lee la app se compila solo al correr los tests y al compilar (`translations.py compile` lo hace a mano).
- **Interfaz:** cada cosa tiene un solo lugar donde se decide. Los atajos de teclado están en una sola tabla, `ui/shortcuts.py`, de la que salen sus tooltips y la Ayuda; adónde lleva un clic en una fila, en `ui/navigation.py`; las tarjetas se reparten con `CardGrid` y la altura de cada fila de una lista sale de `RowRole`, en `ui/theme/design.py`. Todo botón que solo muestra un ícono lleva un nombre accesible (`setAccessibleName`), para el lector de pantalla, y un test recorre cada página buscando los que no lo tienen.
- **Estilo:** PEP 8 y type hints en todo código nuevo, con un docstring breve en cada módulo, clase y método público.

## Compilar el instalador y el AppImage

```bash
.venv/Scripts/python -m pip install -e ".[build]" -c constraints.txt
.venv/Scripts/python scripts/build.py
```

El script congela la aplicación con PyInstaller en `dist/Nodus/`. En Windows, si encuentra [Inno Setup 6](https://jrsoftware.org/isinfo.php), genera `dist/Nodus-Setup-<versión>.exe`. En Linux arma `dist/Nodus-<versión>-x86_64.AppImage` con `appimagetool`: la primera vez descarga la herramienta y el runtime del AppImage en las versiones fijas que nombra `build.py`, verifica su SHA-256 y los guarda en `build/tools/`. El AppImage no lleva las bibliotecas que cada distribución tiene que poner con su propia versión (las de C y C++, las fuentes y X, que nombra `packaging/appimage-excludelist`, la lista del proyecto AppImage), ni el aspecto GTK de Qt, porque Nodus dibuja su propio tema. Conviene compilarlo en la distribución más vieja que se quiera soportar: un AppImage solo abre donde la glibc es igual o más nueva que la de la máquina que lo armó.

Antes de armar el instalador o el AppImage, el script abre el programa compilado con `--smoke-test`. Esa prueba abre Nodus sobre una carpeta de datos temporal, sin internet y sin tocar el inicio con Windows, revisa lo que PyInstaller podría haber dejado afuera (el plugin de SVG, la traducción de Qt, las novedades, cada página) y sale con un código distinto de 0 si algo falta; en ese caso el script muestra el registro y se detiene. En Linux, la prueba se repite con el AppImage ya armado. Para probar el instalador sin tocar tus datos, ábrelo con `NODUS_DATA_DIR` definida.

Cuando el usuario toca «Actualizar», Nodus descarga el instalador del release (verificando el SHA-256 que publica GitHub para cada archivo adjunto) y lo abre con `/SILENT /SUPPRESSMSGBOXES /NORESTART /RELAUNCH=1` antes de cerrarse. `/RELAUNCH=1` hace que `packaging/nodus.iss` vuelva a abrir Nodus al terminar; sin ese parámetro, una instalación silenciosa deja la aplicación cerrada. Por eso el instalador de cada release tiene que llamarse `Nodus-Setup-<versión>.exe`, como lo genera `scripts/build.py`.

En Linux, el archivo del release es el AppImage mismo, `Nodus-<versión>-x86_64.AppImage`. Nodus lo descarga a la carpeta temporal y verifica su SHA-256. Después lo copia junto al AppImage que está corriendo y lo pone en su lugar en un solo paso, con el mismo nombre, para que la entrada del menú y la del inicio de sesión sigan apuntando a él. Por último, se reinicia sobre el archivo nuevo. El Nodus abierto sigue usando el archivo viejo hasta que se cierra. Si la carpeta no se puede escribir, Nodus lo avisa y ofrece descargarlo desde GitHub.

## Publicar una versión

1. Subir `nodus.__version__` en `src/nodus/__init__.py`, actualizar el README (en inglés y en español) y ponerle la fecha a la sección de la versión en `CHANGELOG.md` y en `CHANGELOG.en.md`.
2. Generar las notas del release a partir de esa sección y crear con ellas una etiqueta anotada:

   ```
   .venv/Scripts/python scripts/release_notes.py X.Y.Z
   git tag -a vX.Y.Z -F notas.md
   ```

   `CHANGELOG.md` es la única fuente de las novedades, escrita para usuarios y en español, y `CHANGELOG.en.md` dice lo mismo en inglés desde la 1.10, con las mismas versiones y los mismos puntos. De ahí salen las notas del release (el mensaje de la etiqueta), el «Qué trae» del aviso de versión nueva y el diálogo de novedades que Nodus muestra una vez al abrir la versión nueva; el programa compilado los lleva adentro. Las notas llevan primero el español y después, tras `<!-- en -->`, el inglés; el aviso de versión nueva y el diálogo de novedades muestran el idioma en que está Nodus.
3. Subir el commit y la etiqueta. El flujo `.github/workflows/release.yml` arma los dos archivos en paralelo. En Windows corre los tests, compila (con la prueba `--smoke-test`), instala el resultado en modo silencioso como lo haría un usuario y vuelve a abrir la copia instalada con `--smoke-test`. En Ubuntu 22.04 corre los tests y arma el AppImage, que también pasa el `--smoke-test`. Se compila en Ubuntu 22.04 porque es la más vieja que ofrece GitHub, y así el AppImage abre en más distribuciones. Solo cuando los dos terminan bien, comprueba que la etiqueta coincida con la versión y crea el release con el instalador y el AppImage. La CI de cada push informa además la cobertura de los tests en la página de la ejecución.

Para probar la compilación sin publicar nada, en GitHub: Actions → Release → Run workflow, que deja el instalador como artefacto de la ejecución.
