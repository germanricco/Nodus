# Notas de trabajo

## Estado actual

Base de trabajo commiteada (`8456e41`). Plan de la v0.1 escrito en `docs/plans/001-v0.1-mvp.md`, pendiente de revisión del usuario. Todavía no hay código; lo siguiente es la fase 1 (entorno y cimientos).

## Decisiones

- **2026-11-05 — Commits.** Claude propone el mensaje y hace commit solo con aprobación del usuario; nunca push. Así el usuario controla el historial y cada commit queda como punto de control.
- **2026-11-05 — Idioma.** Código, identificadores y commits en inglés; documentación, planes, tareas e interfaz en español. El código en inglés es el estándar del ecosistema; el usuario trabaja en español.
- **2026-11-05 — Planes y tareas.** Un plan por versión o funcionalidad en `docs/plans/`, backlog en `TASKS.md`, memoria y decisiones en `NOTES.md`.
- **2026-11-05 — Referencias fuera del repo.** `referencias/` está en `.gitignore`: es un clon con su propio git y licencia AGPL, solo para consulta.
- **2026-11-05 — Estrategia por versiones.** Primero una v0.1 chica y estable para probar, después funciones por incrementos. MoneyMatter es la referencia de funciones e interfaz.
- **2026-11-05 — Interfaz con Qt Widgets y un tema QSS propio.** Permite imitar el aspecto de MoneyMatter, mantiene todo en Python orientado a objetos y evita la GPL de QFluentWidgets.
- **2026-11-05 — Categorías del usuario, separadas en gastos e ingresos.** Set predeterminado corto: gastos (Supermercado y comida, Vivienda, Servicios, Transporte, Salud, Educación, Proyectos, Ocio, Ropa, Otros) e ingresos (Sueldo, Trabajo freelance, Reembolsos, Otros). Cada usuario agrega las suyas. `Category.kind` reutiliza `TransactionType`. Hay una "Otros" de sistema por tipo. La tabla admite subcategorías opcionales (`parent_id`) para no tener que migrar después. Se descartó el set de unas 80 categorías de MoneyMatter por ser demasiado grande.
- **2026-11-05 — Multimoneda ARS/USD desde la v0.1.** El usuario hoy maneja en Excel cuentas en pesos y en dólares, y ve el patrimonio en ambas monedas. Cada cuenta tiene su moneda y las transferencias entre monedas guardan los dos montos, como en MoneyMatter.
- **2026-11-05 — Cotización manual con historial.** La cotización que importa en Argentina (MEP, blue) no es la oficial, y la carga manual funciona sin internet. La automática (DolarApi) queda para después.
- **2026-11-05 — Dinero en centavos (INTEGER) y saldos calculados.** Como en MoneyMatter: sin errores de redondeo, y los saldos nunca quedan desincronizados.
- **2026-11-05 — Entorno con venv + pip y gráficos con QtCharts.** venv viene con Python 3.11.9 y QtCharts está incluido en PySide6, así que no suman dependencias.

## Preguntas abiertas

- Tipografía: la del sistema (Segoe UI) o incluir Inter, como MoneyMatter.
- Licencia del proyecto.

## Registro de sesiones

### 2026-11-05
Lectura de la especificación y del repo de referencia. Definidas las reglas de trabajo y creada la base del repo. Revisados el modelo de datos, las categorías y las pantallas de MoneyMatter; escrito el plan 001 con multimoneda ARS/USD.
