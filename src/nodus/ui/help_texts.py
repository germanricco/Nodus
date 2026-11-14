"""«Cómo se hace»: short answers for what is not obvious at first sight.

Each text follows what the app really does and names the buttons and fields as the
screen shows them; when a screen changes, its topic here changes with it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HelpTopic:
    title: str
    paragraphs: tuple[str, ...]


HELP_TOPICS = [
    HelpTopic(
        "Cuentas y grupos",
        (
            "Crea una cuenta por cada lugar donde tengas dinero: el banco, el efectivo, una"
            " billetera virtual, tus ahorros en dólares o una tarjeta. En Cuentas, «Agregar"
            " cuenta». El saldo se calcula siempre a partir de los movimientos.",
            "Para ordenarlas, arrástralas; el panel lateral sigue ese orden. Para juntarlas,"
            " usa «Agregar grupo» y luego «Mover a grupo…» en el menú de cada cuenta. Un clic en"
            " el nombre de un grupo en el panel lateral lo pliega y muestra solo su total.",
            "Una cuenta que ya no usas se archiva desde su menú: deja de aparecer en el panel"
            " lateral y en los formularios, y de sumar en tu patrimonio neto, pero sus"
            " movimientos se conservan.",
        ),
    ),
    HelpTopic(
        "Transferencias y compra de dólares",
        (
            "Pasar dinero entre dos de tus cuentas es una transferencia, no un gasto: en el"
            " formulario, elige «Transferencia», la cuenta de origen en «Cuenta» y la de destino"
            " en «Hacia».",
            "Si las cuentas tienen monedas distintas, como al comprar dólares, aparece «Entra»:"
            " anota lo que salió en «Monto» y lo que llegó en «Entra». Nodus te muestra la"
            " cotización que realmente obtuviste.",
        ),
    ),
    HelpTopic(
        "Compras en cuotas",
        (
            "Al anotar un gasto, elige en «Cuotas» en cuántas se paga y si el monto es el"
            " «Total» o lo que vale cada una («Por cuota»). Nodus anota todas las cuotas en"
            " sus fechas, y cada una se descuenta de la cuenta el día que le toca.",
            "Recurrentes muestra cuántas pagaste, la próxima y cuánto se llevan las cuotas cada"
            " mes. Abrir cualquier cuota abre la compra entera, para cambiarla o eliminarla; su"
            " menú tiene «Adelantar las cuotas que faltan».",
        ),
    ),
    HelpTopic(
        "Reembolsos",
        (
            "Cuando un comercio te devuelve dinero o alguien te paga su parte, anota el ingreso"
            " y elige en «Reembolso de» el gasto que devuelve.",
            "Así Nodus lo cuenta como un gasto menor, en la categoría del gasto original y en el"
            " mes en que volvió el dinero, y no como un ingreso: tus presupuestos y Análisis"
            " muestran lo que realmente gastaste.",
        ),
    ),
    HelpTopic(
        "Pagos recurrentes",
        (
            "El alquiler, los servicios y las suscripciones se anotan una sola vez, en"
            " Recurrentes, con «Agregar cargo». Nodus te muestra cuánto suman por mes, qué"
            " vence pronto y qué está atrasado, y la campana te avisa.",
            "«Pagar» registra el gasto y pasa el cargo a su próxima fecha. Si un mes no se"
            " paga, «Omitir» lo salta sin registrar nada.",
        ),
    ),
    HelpTopic(
        "Presupuestos",
        (
            "En Presupuestos, «Agregar presupuesto» le pone un límite mensual a una categoría de"
            " gasto. Nodus te sugiere tu promedio de los últimos meses.",
            "La barra se pone amarilla cuando gastas más rápido de lo que avanza el mes y roja"
            " cuando te pasas. Un límite vale desde ese mes en adelante, hasta que lo cambies o"
            " lo quites.",
        ),
    ),
    HelpTopic(
        "Metas de ahorro",
        (
            "Una meta apunta el saldo de tus cuentas de ahorro o inversión hacia un monto, con"
            " fecha si quieres. En Metas, «Agregar meta»: elige qué cuentas cuentan y qué parte"
            " de cada una, así una misma cuenta sirve a varias metas.",
            "Las metas nunca mueven dinero: crecen cuando pasas plata a sus cuentas. Cada una te"
            " dice si a tu ritmo llegas a tiempo y, si no, cuánto hace falta por mes.",
        ),
    ),
    HelpTopic(
        "Rendimiento de inversiones",
        (
            "Los ahorros y las inversiones cambian de valor solos, con intereses o precios. En"
            " la página de la cuenta, «Actualizar valor» anota cuánto vale hoy, como lo muestra"
            " su app.",
            "Nodus guarda la diferencia como rendimiento: mueve el saldo y tu patrimonio neto,"
            " pero no cuenta como ingreso.",
        ),
    ),
    HelpTopic(
        "Copias de seguridad",
        (
            "Cada día, al abrirse, Nodus guarda una copia de tus datos en tu computadora. En"
            " Ajustes, «Hacer copia» guarda una en el momento y «Restaurar copia…» vuelve a"
            " una anterior, después de guardar cómo están ahora.",
            "Esas copias quedan en el mismo disco, así que una vez al mes conviene guardar"
            " una afuera: «Guardar copia en…», en un pendrive o en una carpeta de Drive. A fin"
            " de mes, Nodus te lo recuerda.",
        ),
    ),
]
