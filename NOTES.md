# Notas de trabajo

## Estado actual

Fases 1 a 3 de la v0.1 terminadas (plan `docs/plans/001-v0.1-mvp.md`). La app abre una ventana al estilo MoneyMatter: barra lateral con navegación y cuentas con sus saldos, barra superior con "Agregar transacción" (todavía sin acción) y tema claro/oscuro que sigue al sistema. Las páginas son provisorias (`PlaceholderPage`). 114 tests en verde. Sigue la fase 4: página de Cuentas.

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
- **2026-11-05 — Categorías predeterminadas dentro de `001_initial.sql`.** Se cargan con INSERT en la migración inicial en lugar de un `seed.py`, para que se creen una sola vez y en la misma transacción que el esquema.
- **2026-11-05 — Servicios con "borradores".** `TransactionDraft` y `TransferDraft` agrupan lo que el usuario completa en un formulario, para no pasar siete parámetros sueltos. Los repositorios nunca hacen commit: cada servicio envuelve su operación en `Database.transaction()`, así una transferencia nunca queda guardada a medias.
- **2026-11-05 — Reglas de transferencias.** Entre cuentas de la misma moneda, el monto que entra es igual al que sale. Entre ARS y USD, el usuario indica los dos montos. Borrar una pata borra la transferencia completa. Las cuentas archivadas no aceptan transacciones nuevas.
- **2026-11-05 — Íconos propios en lugar de Lucide.** Íconos de línea simples dibujados para Nodus (`ui/icons/`), sin depender de descargas ni de otra licencia. Se colorean según el tema reemplazando `currentColor`.
- **2026-11-05 — Tema con tokens.** Una sola hoja de estilos (`ui/theme/stylesheet.qss`) con nombres de color (`$accent`, `$text`…) que `ThemeManager` completa con la paleta clara u oscura. También se ajusta la `QPalette`, para que los widgets que la hoja no cubre respeten el tema. Se usa el estilo Fusion, que aplica las hojas de estilo igual en todos los sistemas.
- **2026-11-05 — `EventBus` para refrescar pantallas.** Quien guarda un cambio emite una señal (`accounts_changed`, `transactions_changed`…) y cada pantalla que muestra esos datos se actualiza sola.
- **2026-11-05 — Entorno con venv + pip y gráficos con QtCharts.** venv viene con Python 3.11.9 y QtCharts está incluido en PySide6, así que no suman dependencias.

## Preguntas abiertas

- Tipografía: por ahora Segoe UI (la del sistema); evaluar incluir Inter, como MoneyMatter.
- Las capturas en modo sin ventana necesitan `QT_QPA_FONTDIR` en Windows para encontrar las fuentes (ya está en `scripts/screenshot.py` y en `tests/conftest.py`).
- Licencia del proyecto.

## Registro de sesiones

### 2026-11-05
Lectura de la especificación y del repo de referencia. Definidas las reglas de trabajo y creada la base del repo. Revisados el modelo de datos, las categorías y las pantallas de MoneyMatter; escrito el plan 001 con multimoneda ARS/USD y categorías de gasto/ingreso. Fases 1 a 3 implementadas y verificadas (tests, ruff, capturas revisadas y app abierta contra una carpeta de prueba).
