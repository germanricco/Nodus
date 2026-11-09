# Novedades de Nodus

Lo que trae cada versión, de la más nueva a la más vieja. Para actualizar, instala la versión nueva encima de la anterior: tus datos se conservan.

## 1.1.1

- Arreglo: Nodus anclado a la barra de tareas muestra su ícono en lugar de un recuadro en blanco. Si ya lo tenías anclado, desánclalo y vuelve a anclarlo después de actualizar.

## 1.1.0 — 2026-11-07

- Cuentas en euros y en pesos chilenos, con su cotización oficial automática.
- Billetera virtual como tipo de cuenta, para Mercado Pago, Ualá y similares.
- Ordena tus cuentas arrastrándolas en Cuentas.
- Cualquier color para categorías y etiquetas, con un círculo cromático.
- Nodus puede abrirse solo al iniciar Windows (en Ajustes).
- Envía comentarios desde el globo de la barra superior, y apoya el proyecto desde Ajustes.
- Novedades como estas al actualizar, y qué trae cada versión nueva antes de instalarla.
- Supr elimina lo seleccionado en las listas, con confirmación.
- Arreglos y pequeñas mejoras en la interfaz.

## 1.0.1 — 2026-11-06

- Los filtros de Transacciones (cuenta, categoría, beneficiario y etiqueta) terminan con «Editar», que lleva directo a la página de esa lista.
- El formulario de transacción se ajusta a sus campos: al pasar a «Transferencia» ya no queda grande y con espacios en blanco.

## 1.0.0 — 2026-11-06

La primera versión estable.

- Rendimiento de ahorros e inversiones: en Cuentas, «Actualizar valor» anota lo que vale hoy la cuenta y guarda la diferencia como rendimiento. Mueve el saldo y el patrimonio sin contar como ingreso ni gasto, y la cuenta muestra cuánto rindió. El último ajuste se puede deshacer.
- Un ojo en la barra superior oculta los saldos y el patrimonio («$ ••••»), y Nodus lo recuerda. La lista de CUENTAS de la barra lateral se pliega con un clic en su título.
- El panel lateral se contrae a solo íconos y se expande con el botón de abajo.
- Filtros de Transacciones más claros: sin usar muestran su nombre en gris y los activos se destacan con color. Las listas de categorías separan gastos e ingresos con títulos de sección y muestran las subcategorías con sangría.
- La descripción de los movimientos ya no queda recortada en pantallas chicas.
- Capturas de cada pantalla en el README.

## 0.9.1 — 2026-11-06

- Cargos recurrentes en dólares que se pagan desde una cuenta en pesos, como una suscripción con precio fijo cobrada con la tarjeta: al crear el cargo, marca «Se cobra en dólares».
- Recurrentes, «Próximos pagos» y el total mensual muestran cuántos pesos se esperan («US$ 100,00 ≈ $ 165.000,00»), con la cotización de tu último pago, impuestos de la tarjeta incluidos; la primera vez, con la cotización guardada.
- Al pagar, anotas los pesos que realmente salieron; el gasto queda en pesos y la nota dice los dólares del cargo.

## 0.9.0 — 2026-11-06

Reembolsos, etiquetas y cualquier rango de fechas.

- Reembolsos: un ingreso se vincula con el gasto que devuelve y cuenta como un gasto menor, en la categoría del gasto original y en el mes en que volvió el dinero. Lo ven el Dashboard, los presupuestos y Análisis.
- En Transacciones, los dos lados de un reembolso llevan la marca ↺ y se filtran con «Reembolsos»; al editar un gasto se ve cuánto se reembolsó, y la exportación CSV suma la columna «Reembolso de».
- Etiquetas: cada movimiento puede llevar varias, como «Vacaciones 2026», y se crean al escribirlas en el formulario.
- Nueva página Etiquetas, con cuántos movimientos y cuánto dinero suma cada una; se pueden renombrar, cambiar de color, unir o eliminar sin perder movimientos.
- Transacciones filtra por etiqueta y las muestra en una columna; Análisis suma el desglose «Por etiqueta».
- Al pie de Transacciones, los ingresos, gastos y neto de lo que se ve.
- Todos los selectores de período ofrecen «Personalizado…», con cualquier rango de fechas.
- El gráfico de patrimonio ya no encima sus dos últimas fechas.

## 0.8.0 — 2026-11-06

Análisis: hacia dónde va tu dinero, mes a mes.

- Nueva página Análisis, con los últimos 12 meses por defecto y el mismo selector de período del Dashboard.
- Tendencias: gastos, ingresos o ahorro mes a mes, en barras apiladas por categoría con la línea del promedio mensual; el total frente al período anterior y el desglose por categoría y por beneficiario.
- Flujo de caja: ingresos, gastos, ahorro y tasa de ahorro frente al período anterior, con las barras y una tabla de cada mes.
- Patrimonio: la evolución en pesos o en dólares y una tabla del fin de cada mes con su variación.
- Un clic en una barra o en una fila abre los movimientos que la forman.

## 0.7.0 — 2026-11-06

Beneficiarios: a quién le pagas y de quién cobras.

- Cada gasto o ingreso puede llevar un beneficiario: el supermercado, la empresa de luz, tu empleador. Escribes unas letras y Nodus sugiere los que ya existen, sin importar mayúsculas ni tildes; un nombre nuevo se crea solo al guardar.
- Al elegir un beneficiario, la categoría se completa con su categoría predeterminada o con la última que usaste con él.
- Nueva sección Beneficiarios: cuántos movimientos tiene cada uno, cuánto se fue o entró y su categoría habitual, con búsqueda y orden por columna. Desde ahí se crean, se editan, se unen los repetidos («Coto» y «Coto Online») y se eliminan.
- «Ver movimientos» abre Transacciones con todo el historial de ese beneficiario.
- Transacciones suma la columna y el filtro por beneficiario, y el buscador también encuentra por su nombre. La exportación a CSV incluye la columna Beneficiario.

## 0.6.0 — 2026-11-06

Presupuestos: un límite mensual por categoría para frenar a tiempo.

- Nueva sección Presupuestos: pones un límite mensual a las categorías de gasto que quieres cuidar y ves cuánto llevas gastado y cuánto te queda, mes a mes.
- La barra de cada categoría va en verde mientras vas bien, en amarillo cuando gastas más rápido de lo que avanza el mes y en rojo cuando te pasas; una marca indica dónde deberías ir hoy.
- Para elegir el límite, Nodus sugiere el promedio de los últimos tres meses. Cambiarlo rige desde ese mes y los anteriores conservan el suyo.
- Debajo, lo gastado en las categorías sin límite; un clic en una categoría abre sus movimientos del mes.
- Tarjeta Presupuestos en el Dashboard, junto al flujo de caja, con las categorías más cerca de su límite.
- La campana avisa cuando un presupuesto se pasa en el mes.

## 0.5.0 — 2026-11-06

Cargos recurrentes y suscripciones: los gastos fijos, a la vista y a dos clics.

- Nueva sección Recurrentes: alquiler, servicios, suscripciones o el gimnasio, cada uno con su frecuencia (semanal a anual) y su próxima fecha de cobro. Arriba, cuánto suman por mes y por año.
- Los cargos se agrupan en vencidos, próximos 7 días, más adelante y en pausa.
- Pagar un cargo abre un diálogo ya completado; el monto se puede corregir. Se registra como gasto y la fecha avanza al próximo cobro, aunque lo pagues tarde. También se puede omitir un cobro, pausar el cargo o editarlo.
- Tarjeta Próximos pagos en el Dashboard, con lo vencido y lo que vence en los próximos 14 días.
- La campana avisa cuando un cargo está vencido o vence en los próximos 3 días.
- Dashboard reordenado: el patrimonio con los próximos pagos y las últimas transacciones al lado; debajo, los gastos por categoría junto a la comparación con el período anterior y, al final, el flujo de caja. Las tarjetas se acomodan al ancho de la ventana y la página se desplaza en lugar de apretarlas.
- Arreglo: el gráfico de patrimonio etiqueta todas las fechas que entran, a paso regular.

## 0.4.0 — 2026-11-06

Un dashboard más completo, con gráficos que se mueven.

- Selector de período en el Dashboard y en Transacciones: mes actual, últimos 3, 6 o 12 meses, este año o el anterior; las flechas pasan al período previo o al siguiente.
- Patrimonio en pesos o en dólares, con una curva de su evolución, cuánto cambió en el período y qué parte está en cada moneda. Cuentas muestra la misma tarjeta, más chica.
- Flujo de caja: el ahorro del período y los ingresos y gastos de cada mes lado a lado.
- Gastos por categoría interactivos: al pasar el mouse se resalta la categoría y un clic abre sus transacciones de ese período.
- Comparación de cada categoría con el período anterior.
- Los gráficos y las cifras se actualizan solos, con una transición, al cargar un movimiento.
- Campana de notificaciones en la barra superior: nueva versión, cotización del dólar vieja o faltante y copia de seguridad fallida. El engranaje abre Ajustes.
- Arreglo: el patrimonio de un período pasado usa los saldos de esa fecha.

## 0.3.0 — 2026-11-06

Datos seguros y menos carga manual.

- Copia de seguridad automática una vez por día al abrir Nodus (se conservan las últimas 10). Desde Ajustes: hacer una copia en el momento, abrir la carpeta de copias y restaurar una.
- Exportar a CSV, listo para Excel: lo que se ve en Transacciones o todo el historial.
- Cotización del dólar automática desde DolarApi: elige MEP, Blue u Oficial en Ajustes. Una cotización cargada a mano en el día nunca se reemplaza sola.
- El formulario de transacción ofrece la última cuenta usada.

## 0.2.0 — 2026-11-06

La primera versión con instalador para Windows.

- Instalador por usuario, sin permisos de administrador, con acceso en el menú Inicio. Para actualizar se instala encima; los datos no se tocan.
- Logo propio en la ventana, la barra de tareas y el menú Inicio.
- Aviso de nueva versión al abrir la app, desactivable en Ajustes.
- Nueva tarjeta «Acerca de Nodus» en Ajustes.

## 0.1.1 — 2026-11-05

- Las cuentas se pueden eliminar, con un aviso de cuántas transacciones se borran con ellas.
- Botón «Limpiar filtros» en Transacciones.
- Arreglos en Ajustes y en el calendario: el selector de tema, «Abrir carpeta» de los datos y los días de dos dígitos.

## 0.1.0 — 2026-11-05

La primera versión usable: cuentas en pesos y en dólares, gastos, ingresos y transferencias, categorías propias, la cotización del dólar con su historial y un dashboard con el patrimonio, el flujo del mes y los gastos por categoría.
