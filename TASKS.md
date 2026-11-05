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
