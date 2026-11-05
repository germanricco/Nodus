# Notas de trabajo

## Estado actual

Base de trabajo lista: `.gitignore`, `CLAUDE.md`, `NOTES.md`, `TASKS.md`, `README.md` y la plantilla de planes. Todavía no hay código. Lo siguiente es el plan `docs/plans/001` para la v0.1 (MVP usable).

## Decisiones

- **2026-11-05 — Commits.** Claude propone el mensaje y hace commit solo con aprobación del usuario; nunca push. Así el usuario controla el historial y cada commit queda como punto de control.
- **2026-11-05 — Idioma.** Código, identificadores y commits en inglés; documentación, planes, tareas e interfaz en español. El código en inglés es el estándar del ecosistema; el usuario trabaja en español.
- **2026-11-05 — Planes y tareas.** Un plan por versión o funcionalidad en `docs/plans/`, backlog en `TASKS.md`, memoria y decisiones en `NOTES.md`.
- **2026-11-05 — Referencias fuera del repo.** `referencias/` está en `.gitignore`: es un clon con su propio git y licencia AGPL, solo para consulta.
- **2026-11-05 — Estrategia por versiones.** Primero una v0.1 chica y estable para probar, después funciones por incrementos. MoneyMatter es la referencia de funciones e interfaz.

## Preguntas abiertas

- Librería de interfaz: QFluentWidgets (widgets) o QML.
- Librería de gráficos para el dashboard.
- Formato del dinero en la base (centavos en INTEGER o `Decimal` como texto).
- Gestor de entorno: venv + pip (disponible hoy) o uv (no instalado).
- Licencia del proyecto.

## Registro de sesiones

### 2026-11-05
Lectura de la especificación y del repo de referencia. Definidas las reglas de trabajo y creada la base del repo.
