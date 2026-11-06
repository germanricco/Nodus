# Contribuir a Nodus

Gracias por el interés. Las ideas y los reportes de errores son bienvenidos en [Issues](https://github.com/germanricco/Nodus/issues): si encontraste un problema, cuenta qué hiciste, qué esperabas y qué pasó, con la versión de Nodus (está en Ajustes). Esta guía explica cómo ejecutar Nodus desde el código, cómo está organizado y cómo se publica una versión.

## Preparar el entorno

Hace falta **Python 3.11**. En Windows, conviene instalarlo desde [python.org](https://www.python.org/downloads/) y no desde la Microsoft Store: esa versión guarda los archivos de `AppData` en una carpeta privada, donde el Explorador no los encuentra. Desde una terminal, en la carpeta del proyecto:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # en Linux o macOS: .venv/bin/python
.venv/Scripts/python -m nodus
```

Para probar sin tocar tus datos reales, define la variable de entorno `NODUS_DATA_DIR` con otra carpeta antes de abrirlo; Nodus crea ahí su base de datos y sus copias de seguridad.

## Comandos de uso diario

```bash
.venv/Scripts/python -m pytest                       # tests
.venv/Scripts/python -m ruff check .                 # lint
.venv/Scripts/python -m ruff format .                # formato
.venv/Scripts/python scripts/screenshot.py --demo    # capturas de cada pantalla, claras y oscuras
```

Las capturas se generan sobre una base temporal con datos de demostración (`scripts/demo_data.py`), así que muestran todas las pantallas con contenido sin tocar ningún dato real. Después de cambiar la interfaz, conviene generarlas y revisarlas en los dos temas.

## Cómo está organizado el código

El paquete `src/nodus/` está en capas que solo dependen hacia abajo:

- `models`: el dominio puro (dinero, cuentas, períodos, presupuestos), sin Qt ni SQL.
- `database`: la conexión a SQLite, las migraciones y los repositorios que traducen filas a modelos.
- `services`: las reglas de negocio, como saldos, validaciones o qué vence.
- `ui`: ventanas, páginas, diálogos y tema. La interfaz nunca ejecuta SQL ni calcula saldos.

Los tests en `tests/` siguen la misma estructura. Algunas reglas que conviene conocer:

- **Dinero:** los montos se guardan en centavos enteros, nunca en números de punto flotante, que acumulan errores de redondeo.
- **Migraciones:** el esquema vive en `src/nodus/database/migrations/NNN_nombre.sql` y se aplica con `PRAGMA user_version`. Una migración publicada nunca se edita, porque las bases de los usuarios ya la aplicaron: cada cambio va en un archivo nuevo con el número siguiente.
- **Idiomas:** el código, los identificadores y los mensajes de commit van en inglés; los textos que ve el usuario, en español.
- **Estilo:** PEP 8 y type hints en todo código nuevo, con un docstring breve en cada módulo, clase y método público.

## Compilar el instalador

```bash
.venv/Scripts/python -m pip install -e ".[build]"
.venv/Scripts/python scripts/build.py
```

El script congela la aplicación con PyInstaller en `dist/Nodus/` y, si encuentra [Inno Setup 6](https://jrsoftware.org/isinfo.php), genera `dist/Nodus-Setup-<versión>.exe`. Para probar el instalador sin tocar tus datos, ábrelo con `NODUS_DATA_DIR` definida.

## Publicar una versión

1. Subir `nodus.__version__` en `src/nodus/__init__.py` y actualizar el README (en inglés y en español).
2. Crear una etiqueta anotada cuyo mensaje sean las notas del release: `git tag -a vX.Y.Z -F notas.md`.
3. Subir el commit y la etiqueta. El flujo `.github/workflows/release.yml` comprueba que la etiqueta coincida con la versión, corre los tests, compila el instalador y crea el release con él.

Para probar la compilación sin publicar nada, en GitHub: Actions → Release → Run workflow, que deja el instalador como artefacto de la ejecución.
