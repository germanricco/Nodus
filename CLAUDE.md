# Nodus

Nodus es una aplicación de escritorio de finanzas personales, local-first: todos los datos del usuario viven en un único archivo SQLite en su computadora, sin servidores, cuentas ni suscripciones. Stack: Python 3.11, PySide6 (Qt) y SQLite; se distribuirá como ejecutable (PyInstaller) publicado por GitHub Actions. La especificación completa está en `docs/especificacion_de_proyecto.md`.

## Al empezar cada sesión

1. Leer `NOTES.md` (sección "Estado actual") y `TASKS.md`.
2. Ejecutar `git log --oneline -10` para ver el trabajo reciente.
3. Si hay un plan activo en `docs/plans/`, abrirlo antes de tocar código.

## Forma de trabajo

- Trabajamos por versiones (v0.1, v0.2…). Cada versión tiene un plan en `docs/plans/NNN-nombre.md` (a partir de `000-plantilla.md`), acordado con el usuario, y se implementa de corrido, tarea por tarea.
- Cada versión termina estable y usable, porque el usuario la prueba antes de seguir creciendo. Lo que no entra en la versión actual va al backlog de `TASKS.md` en lugar de adelantarse.
- Una tarea está hecha solo cuando se verificó (tests o ejecución real de la app), no cuando el código compila.
- Al cerrar una tarea: actualizar `TASKS.md`, `NOTES.md` y la documentación afectada; proponer el mensaje de commit y hacer commit solo si el usuario lo aprueba. Nunca hacer push.
- Si algo falla tras 1-2 intentos de arreglo, parar y explicar el problema al usuario en lugar de encadenar intentos especulativos.

## Convenciones de código

- Programación orientada a objetos: clases con una responsabilidad clara; la lógica de negocio separada de la interfaz y del acceso a la base de datos.
- Identificadores, docstrings y mensajes de commit en inglés. Textos visibles para el usuario, en español.
- PEP 8 y type hints en todo código nuevo.
- Dinero: nunca `float`, porque acumula errores de redondeo. El formato exacto (probablemente centavos en INTEGER, como hace MoneyMatter) se define en el plan del modelo de datos.
- Reutilizar antes de escribir: buscar si ya existe una clase o función que resuelva lo mismo. Si un fragmento de código aparece en más de un lugar, extraerlo de inmediato a un método o función propio.
- Nombres descriptivos, claros y simples.
- Documentar todo, de forma concisa: un docstring breve en cada módulo, clase y método público que explique el propósito y el porqué, sin repetir lo que ya se lee en el código. Comentarios en línea solo donde la lógica no es evidente.
- Los comentarios describen el código actual, no su historia; los cambios se cuentan en los commits.
- Sin sobreingeniería: nada de abstracciones ni configurabilidad para casos hipotéticos que la versión actual no pide. Extraer código repetido sí corresponde siempre.

## Documentación pública

El repositorio vive en GitHub y el README es la primera impresión del proyecto, así que la documentación se cuida tanto como el código.

- Toda tarea que cambie funciones, instalación o uso actualiza `README.md` (y los docs afectados) en el mismo cierre.
- Estilo: lenguaje natural, en párrafos, atractivo y descriptivo. Listas solo cuando los elementos son claramente discretos (requisitos, comandos, pasos de instalación).
- Al cerrar cada versión, revisar el README completo: estado, funciones y capturas cuando haya interfaz.

## Estructura del repositorio

- `src/nodus/`: el paquete de la aplicación, en capas que solo dependen hacia abajo: `ui` → `services` → `database` → `models`. La interfaz nunca ejecuta SQL ni calcula saldos.
  - `app.py`: punto de entrada (`NodusApp`); verifica y migra la base antes de abrir la ventana.
  - `config/`: rutas de datos (`AppPaths`).
  - `models/`: dominio puro, sin Qt ni SQL (`Money`, `Currency`…).
  - `database/`: conexión, migraciones y repositorios.
  - `services/`: reglas de negocio.
  - `ui/`: ventanas, páginas, diálogos y tema.
- `tests/`: espeja la estructura de `src/nodus/`.
- `docs/`: especificación y planes (`docs/plans/`).
- `CLAUDE.md`, `NOTES.md`, `TASKS.md`: reglas, memoria entre sesiones y backlog.
- `referencias/`: repos de referencia clonados; ignorados por git.

## Referencia: MoneyMatter

`referencias/moneymatter` (TypeScript, Vue, PostgreSQL; licencia AGPL) es la guía de funcionalidades, reglas de negocio e interfaz gráfica. Se reimplementa en Python/Qt; no se copia código.

- `README.md`: lista de funciones.
- `packages/docs/public/screenshots/`: capturas claras y oscuras de cada pantalla, la referencia visual principal.
- `packages/frontend/src/pages/`: pantallas (dashboard, accounts, records, budget, settings…).
- `packages/backend/`: reglas de negocio y modelo de datos.

## Comandos

Todo se ejecuta con el Python del entorno virtual `.venv` (Python 3.11). En Git Bash, la ruta es `.venv/Scripts/python`.

- Instalar: `python -m venv .venv` y luego `.venv/Scripts/python -m pip install -e ".[dev]"`
- Abrir la app: `.venv/Scripts/python -m nodus`
- Abrir con datos de prueba: definir `NODUS_DATA_DIR` con una carpeta de prueba antes de abrirla. Usar siempre esta variable al probar, para no tocar los datos reales en `%APPDATA%/Nodus`.
- Tests: `.venv/Scripts/python -m pytest`
- Lint y formato: `.venv/Scripts/python -m ruff check .` y `.venv/Scripts/python -m ruff format .`

## Base de datos y migraciones

El esquema vive en `src/nodus/database/migrations/NNN_nombre.sql` y se aplica con `PRAGMA user_version`. Mientras no se publique la v0.1.0, los cambios de esquema se hacen editando `001_initial.sql`, porque nadie tiene todavía datos que migrar. Después de publicada, cada cambio va en un archivo nuevo con el número siguiente: una migración ya publicada nunca se edita, porque las bases de los usuarios ya la aplicaron.
