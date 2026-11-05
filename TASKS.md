# Tareas

## v0.0 — Base de trabajo

- [x] `.gitignore`, `CLAUDE.md`, `NOTES.md`, `TASKS.md`, `README.md` y plantilla de planes

## v0.1 — MVP usable

Plan: `docs/plans/001-v0.1-mvp.md`. Se usa desde el código fuente.

- [x] 1. Entorno y cimientos: venv, `pyproject.toml`, ventana vacía, `Database` con migraciones, `Money`
- [x] 2. Dominio y datos: modelos, repositorios, categorías por defecto, servicios (cuentas, categorías, transacciones y transferencias, cotizaciones)
- [ ] 3. Interfaz base: tema claro/oscuro, ventana con barra lateral, `EventBus`, script de capturas
- [ ] 4. Cuentas (ARS y USD)
- [ ] 5. Categorías de gasto y de ingreso: set predeterminado corto, alta, edición y borrado por el usuario
- [ ] 6. Transacciones: tabla con filtros, Gasto/Ingreso/Transferencia
- [ ] 7. Ajustes: tema, cotización manual con historial, ubicación de los datos
- [ ] 8. Dashboard: patrimonio ARS/USD, flujo del mes, gastos por categoría, últimas transacciones
- [ ] 9. Cierre: prueba de punta a punta, README con capturas, etiqueta `v0.1.0`

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
- [ ] Gráfico de evolución del saldo
- [ ] Reembolsos vinculados al gasto original (gasto neto)
- [ ] Beneficiarios (payees)
- [ ] Grupos de cuentas
- [ ] Divisiones de transacciones (splits)
- [ ] Etiquetas
- [ ] Transacciones planificadas y suscripciones
- [ ] Reportes: flujo de caja y patrimonio
- [ ] Metas de ahorro
