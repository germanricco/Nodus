# Tareas

## v0.0 — Base de trabajo

- [x] `.gitignore`, `CLAUDE.md`, `NOTES.md`, `TASKS.md`, `README.md` y plantilla de planes

## v0.1 — MVP usable

Plan: `docs/plans/001-v0.1-mvp.md`. Se usa desde el código fuente.

- [x] 1. Entorno y cimientos: venv, `pyproject.toml`, ventana vacía, `Database` con migraciones, `Money`
- [x] 2. Dominio y datos: modelos, repositorios, categorías por defecto, servicios (cuentas, categorías, transacciones y transferencias, cotizaciones)
- [x] 3. Interfaz base: tema claro/oscuro, ventana con barra lateral, `EventBus`, script de capturas
- [x] 4. Cuentas (ARS y USD)
- [x] 5. Categorías de gasto y de ingreso: set predeterminado corto, alta, edición y borrado por el usuario
- [x] 6. Transacciones: tabla con filtros, Gasto/Ingreso/Transferencia
- [x] 7. Ajustes: tema, cotización manual con historial, ubicación de los datos
- [x] 8. Dashboard: patrimonio ARS/USD, flujo del mes, gastos por categoría, últimas transacciones
- [x] 9. Cierre: prueba de punta a punta, README completo, etiqueta `v0.1.0`

## v0.1.1 — Arreglos tras la prueba con datos reales

Plan: `docs/plans/002-v0.1.1-arreglos.md`.

- [x] Cuentas: poder eliminar una cuenta, con confirmación que avise cuántas transacciones se borran con ella
- [x] Ajustes: el segmento «Según el sistema» del tema se ve con el texto recortado al estar seleccionado
- [x] Ajustes: «Abrir carpeta» de la ubicación de los datos muestra un error de que no está disponible. Causa: el `.venv` usa el Python de la Microsoft Store, que desvía lo que se escribe en `AppData\Roaming` a `AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\Roaming\Nodus`, y el Explorador no ve ese desvío. Arreglo: recrear el `.venv` con Python de python.org y mover el archivo de datos a la ruta real (antes de la v0.2, porque el ejecutable no tendrá el desvío y no encontraría los datos); detectar la Store y mostrar o abrir la ruta real; indicar en el README que se instale Python desde python.org
- [x] Ajustes: en el calendario de la fecha de la cotización, los días de dos dígitos se ven como «...»
- [x] Ajustes: en el calendario, la flecha del menú del mes queda pegada al texto
- [x] Transacciones: las listas desplegables de los filtros (cuenta, categoría, tipo) no siempre se abren hacia abajo y alineadas con el control
- [x] Transacciones: botón «Limpiar filtros»

## v0.2 — Distribución

- [ ] Ejecutable con PyInstaller y logo incrustado
- [ ] GitHub Actions: compilar y publicar en Releases al crear una versión
- [ ] Aviso de nueva versión consultando la API de GitHub

## Más adelante (de MoneyMatter, a priorizar)

- [ ] Presupuestos
- [ ] Importación CSV
- [ ] Exportación y backup
- [ ] Cotización automática (DolarApi: oficial, MEP, blue)
- [ ] Más monedas además de ARS y USD
- [ ] Filtro de transacciones por rango libre de fechas
- [ ] Recordar la última cuenta usada en el diálogo de transacción
- [ ] Reembolsos vinculados al gasto original (gasto neto)
- [ ] Beneficiarios (payees)
- [ ] Grupos de cuentas
- [ ] Divisiones de transacciones (splits)
- [ ] Etiquetas
- [ ] Metas de ahorro
- [ ] Capturas en el README (en `docs/images/`), cuando la interfaz esté más asentada

### Dashboard y análisis (observaciones tras probar la v0.1)

- [ ] Selector de período del dashboard: al hacer clic en el mes, un menú con selección rápida (Mes actual, Últimos 3 meses, Últimos 6 meses, Últimos 12 meses, Este año, Año anterior), sin rango libre
- [ ] Barra superior: botones de notificaciones y de configuración arriba a la derecha, en la fila de «Agregar transacción» (las notificaciones pueden empezar con el aviso de nueva versión de la v0.2)
- [ ] Más tarjetas del dashboard, simplificadas respecto de MoneyMatter: tendencia de saldo, flujo de caja en el tiempo y tendencia de gastos por categoría
- [ ] Anillo de gastos interactivo: resaltar la porción al pasar el mouse e ir a las transacciones de esa categoría al hacer clic
- [ ] Cargos recurrentes y suscripciones (streaming, débitos automáticos, cuotas):
  - Página propia para darlos de alta y ver el total mensual.
  - Tarjeta compacta «Próximos pagos» en el dashboard, con los próximos 14 días y los vencidos; oculta si no hay suscripciones.
  - Aviso en notificaciones para los cobros vencidos o inminentes.
- [ ] Página de Análisis: evolución de ingresos, gastos y patrimonio en el tiempo
