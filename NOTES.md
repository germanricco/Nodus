# Notas de trabajo

## Estado actual

v0.1 terminada (plan `docs/plans/001-v0.1-mvp.md`, versión `0.1.0`): Dashboard, Cuentas, Transacciones, Categorías y Ajustes, con 197 tests en verde (incluida la prueba de punta a punta) y el README completo (las capturas se suman en una versión posterior). La prueba con datos reales dio lugar a la v0.1.1 (plan `002`, arreglos de interfaz, borrar cuentas y la ruta de datos con el Python de la Store). Después viene la v0.2 (ejecutable, GitHub Actions y aviso de actualizaciones), con su plan `003`.

Desde la v0.1.0, el esquema ya no se cambia editando `001_initial.sql`: cada cambio va en una migración nueva.

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
- **2026-11-05 — Montos como se escriben en Argentina.** `parse_amount` toma la coma como separador decimal y el punto como separador de miles ("1.234,56"). Un punto solo seguido de uno o dos dígitos se toma como decimal ("12.50"), porque mucha gente lo escribe así.
- **2026-11-05 — Patrimonio sin cuentas archivadas.** `NetWorthService` suma solo las cuentas activas. Si hace falta convertir y no hay cotización, muestra "Sin cotización" en lugar de un número inventado.
- **2026-11-05 — Errores dentro del diálogo.** `FormDialog` muestra el mensaje de error en el propio diálogo y lo deja abierto, para que el usuario corrija sin volver a escribir todo.
- **2026-11-05 — Orden alfabético en Python, no en SQLite.** `name_sort_key` ignora mayúsculas y tildes; la intercalación NOCASE de SQLite solo pliega ASCII y mandaba al final los nombres que empiezan con tilde ("Árbol").
- **2026-11-05 — Confirmar antes de borrar.** `confirm()` deja "Cancelar" como botón por defecto, y el aviso dice cuántas transacciones pasan a «Otros».
- **2026-11-05 — Una transferencia, una fila.** En las listas, las dos patas de una transferencia se muestran como un solo movimiento ("Banco → Ahorro", "$ 243.100 → US$ 200"), aunque el filtro por cuenta devuelva una sola pata. Lo arma `TransactionListBuilder` (`ui/transaction_list.py`), que también usará el dashboard.
- **2026-11-05 — Transacciones por mes.** La página de Transacciones filtra por mes con un selector ‹ mes › en lugar de un rango libre de fechas: cubre el uso habitual con menos controles. El rango libre queda en el backlog.
- **2026-11-05 — Al editar, una transferencia sigue siendo transferencia.** Un gasto puede pasar a ingreso y viceversa, pero no a transferencia ni al revés, porque se guardan distinto. Para cambiarlo se borra y se vuelve a cargar.
- **2026-11-05 — Imágenes en la hoja de estilos.** `ThemeManager` completa también `$icons`, la carpeta de íconos del paquete, para que la hoja cargue la flecha de las listas desplegables (`chevron-down.svg`, en un gris que sirve en ambos temas).
- **2026-11-05 — Preferencias dentro de la base del usuario.** El tema se guarda en la tabla `settings` (`SettingsService`), así viaja con los datos si el archivo se copia a otra computadora. Un valor desconocido vuelve a "Según el sistema".
- **2026-11-05 — Capturas del README más adelante.** La v0.1 es usable pero la interfaz todavía va a cambiar; las imágenes se suman al README (en `docs/images/`) en una versión posterior, para no cargar el historial de git con capturas que quedan viejas enseguida. La carpeta `screenshots/` sigue ignorada (es para revisar la interfaz).
- **2026-11-05 — Entorno con venv + pip.** venv viene con Python 3.11.9, así que no suma dependencias.
- **2026-11-05 — Gráficos dibujados con QPainter.** El anillo de gastos y la barra de flujo (`ui/widgets/charts.py`) se pintan a mano en lugar de usar QtCharts: son pocas líneas, toman los colores del tema directamente y permiten el total en el centro del anillo. QtCharts queda como opción para gráficos más complejos (evolución del saldo).
- **2026-11-05 — Flujo del mes en pesos.** `DashboardService` suma ingresos y gastos convirtiendo los movimientos en dólares con la cotización de su día. Los que no tienen cotización se dejan fuera y el dashboard lo avisa, en lugar de mostrar un total equivocado. Las transferencias no cuentan como ingreso ni gasto, y los gastos se agrupan por categoría principal.
- **2026-11-05 — Licencia MIT.** El proyecto es open source y al autor solo le importa que se cite el repositorio: MIT lo exige a través del aviso de copyright (que incluye la URL) sin más restricciones. Es compatible con PySide6 (LGPL) también al empaquetar con PyInstaller.
- **2026-11-05 — Dashboard con layout fijo.** No se implementa el botón de MoneyMatter para cambiar el tamaño de las tarjetas: para un uso personal no aporta y complica la interfaz.
- **2026-11-05 — Dashboard limpio.** Debe mostrar solo lo que importa a simple vista. De las 9 tarjetas de MoneyMatter se toman las importantes. Quedan fuera Progreso FIRE, utilización de crédito y tasa de impuestos promedio, y la lista de seguimiento de categorías se reconsidera junto con Presupuestos.
- **2026-11-05 — Próximos pagos en el dashboard, en versión compacta.** Mostrará solo los cobros recurrentes de los próximos 14 días y los vencidos, y se oculta si no hay suscripciones. MoneyMatter la trae en su layout por defecto (`subscriptions-overview`) porque es la única tarjeta que mira hacia adelante («qué me va a salir de la cuenta pronto»). Además, una app de escritorio no puede avisar mientras está cerrada, así que el dashboard, lo primero que se ve al abrirla, es el aviso más confiable. Las notificaciones complementan la tarjeta, no la reemplazan.
- **2026-11-05 — Selector de período con seis opciones rápidas.** Mes actual, últimos 3, 6 y 12 meses, este año y año anterior, sin rango libre, para mantener la interfaz simple.

- **2026-11-05 — Borrar una cuenta borra sus transferencias completas.** Dejar la pata de la otra cuenta la convertiría en un ingreso o gasto suelto que nunca existió. El aviso lo explica y sugiere archivar para conservar el historial.
- **2026-11-05 — Python de python.org, no de la Microsoft Store.** El de la Store desvía lo que se escribe en `AppData` a una carpeta privada de su paquete: el Explorador no ve los datos y el ejecutable de la v0.2 no los encontraría. `visible_path` muestra la ruta real en Ajustes por si alguien lo usa igual.
- **2026-11-05 — Listas desplegables debajo del control.** Fusion abre la lista encima del control, alineada con el ítem actual; `combobox-popup: 0` la abre siempre debajo, como en la web.

## Preguntas abiertas

- Tipografía: por ahora Segoe UI (la del sistema); evaluar incluir Inter, como MoneyMatter.
- Las capturas en modo sin ventana necesitan `QT_QPA_FONTDIR` en Windows para encontrar las fuentes (ya está en `scripts/screenshot.py` y en `tests/conftest.py`).

## Registro de sesiones

### 2026-11-05
Lectura de la especificación y del repo de referencia. Definidas las reglas de trabajo y creada la base del repo. Revisados el modelo de datos, las categorías y las pantallas de MoneyMatter; escrito el plan 001 con multimoneda ARS/USD y categorías de gasto/ingreso. Fases 1 a 9 implementadas y verificadas; v0.1 cerrada (tests, ruff, capturas revisadas y app abierta contra una carpeta de prueba).
