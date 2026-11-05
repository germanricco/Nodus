# Tareas

## v0.0 — Base de trabajo

- [x] `.gitignore`, `CLAUDE.md`, `NOTES.md`, `TASKS.md`, `README.md` y plantilla de planes

## v0.1 — MVP usable (propuesta, se cierra en el plan 001)

Se usa desde el código fuente.

- [ ] Plan `docs/plans/001-v0.1-mvp.md` acordado con el usuario
- [ ] Entorno: venv, `pyproject.toml`, PySide6, pytest, ruff
- [ ] Arquitectura: paquete único con capas `models`, `database` (repositorios sobre SQLite), `services` y `ui`; punto de entrada que verifica o crea la base y abre la ventana
- [ ] Ventana principal al estilo MoneyMatter: barra lateral (Dashboard, Cuentas, Transacciones, Categorías, Ajustes) y tema claro/oscuro
- [ ] Cuentas manuales: crear, editar y archivar, con saldo inicial; una sola moneda
- [ ] Transacciones: ingreso, gasto y transferencia entre cuentas; lista con filtros por cuenta, categoría y fechas; crear, editar y borrar
- [ ] Categorías con un set por defecto, editables
- [ ] Dashboard: saldo total, ingresos y gastos del mes, gastos por categoría (gráfico) y últimas transacciones
- [ ] Tests de modelos, servicios y repositorios
- [ ] README actualizado con funciones, instalación y capturas

## v0.2 — Distribución

- [ ] Ejecutable con PyInstaller y logo incrustado
- [ ] GitHub Actions: compilar y publicar en Releases al crear una versión
- [ ] Aviso de nueva versión consultando la API de GitHub

## Más adelante (de MoneyMatter, a priorizar)

- [ ] Presupuestos
- [ ] Importación CSV
- [ ] Exportación y backup
- [ ] Multimoneda
- [ ] Etiquetas
- [ ] Transacciones planificadas y suscripciones
- [ ] Reportes: flujo de caja y patrimonio
- [ ] Metas de ahorro
