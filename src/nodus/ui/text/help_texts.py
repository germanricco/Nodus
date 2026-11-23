"""The topics of Ayuda: short, friendly answers for what is not obvious at first sight.

Each topic opens with what it is for, then says where it is and how it is done, naming
the buttons as the screen shows them, between «» (the panel shows them in bold). The
texts follow what the app really does; when a screen changes, its topic changes with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from nodus.i18n import N_
from nodus.ui.navigation import PageId

START = N_("Empezar")
MONEY = N_("Tu dinero")
PLANNING = N_("Planificar")
ORDER = N_("Ordenar")
DATA = N_("Tus datos")
HELP_SECTIONS = [START, MONEY, PLANNING, ORDER, DATA]


@dataclass(frozen=True)
class HelpTopic:
    """``key`` names it for ``related``; ``pages`` are the pages it talks about, lit up
    in the sidebar while it is open and reached with «Ir a…». ``title``, ``section``,
    ``intro`` and ``paragraphs`` hold ``N_()`` texts, translated where they are shown."""

    key: str
    title: str
    section: str
    pages: tuple[PageId, ...]
    intro: str
    paragraphs: tuple[str, ...]
    related: tuple[str, ...] = ()


HELP_TOPICS = [
    HelpTopic(
        "overview",
        N_("Cómo está organizado Nodus"),
        START,
        (PageId.DASHBOARD,),
        N_(
            "Nodus junta en un solo lugar tus cuentas, lo que gastas y lo que planeas, y el"
            " Inicio te lo resume de un vistazo."
        ),
        (
            N_(
                "A la izquierda están las páginas y tus cuentas con su saldo. Arriba, «Agregar"
                " transacción» anota un movimiento desde cualquier página, el ojo oculta los"
                " montos, la campana junta los avisos y el «?» abre esta ayuda. El número de la"
                " campana cuenta los avisos que todavía no miraste, que llevan un punto: un clic"
                " en uno te lleva adonde está el problema y lo marca como visto. Con el clic"
                " derecho, algunos se pueden quitar."
            ),
            N_(
                "El Inicio muestra tu patrimonio neto, los próximos pagos, en qué se fue el dinero"
                " y tus presupuestos. Arriba a la derecha eliges el período, y un clic en una"
                " categoría o en un pago te lleva a sus movimientos."
            ),
            N_(
                "Si quieres ver dónde está cada cosa, «Ver el recorrido», al pie de la lista de"
                " temas, te lo muestra en un minuto."
            ),
        ),
        ("first-month", "accounts"),
    ),
    HelpTopic(
        "first-month",
        N_("Tu primer mes con Nodus"),
        START,
        (PageId.DASHBOARD,),
        N_(
            "Empieza por lo que ya tienes y deja que Nodus aprenda con el uso: en un mes vas a"
            " ver con claridad a dónde va tu dinero."
        ),
        (
            N_(
                "Primero, crea una cuenta por cada lugar donde tengas dinero, con el saldo de hoy."
                " Después, anota tus gastos a medida que ocurren; con unos días de movimientos, el"
                " Inicio ya empieza a contar algo."
            ),
            N_(
                "Suma el alquiler, los servicios y las suscripciones en Recurrentes, así Nodus te"
                " avisa antes de que venzan. Cuando tengas un mes de gastos, ponle un límite a las"
                " categorías que quieras cuidar en Presupuestos."
            ),
            N_(
                "Para ver dónde está cada cosa, el botón «Ver el recorrido», al pie de la lista"
                " de temas, recorre la ventana en un minuto."
            ),
        ),
        ("overview", "transactions", "recurring"),
    ),
    HelpTopic(
        "accounts",
        N_("Cuentas y grupos"),
        MONEY,
        (PageId.ACCOUNTS,),
        N_(
            "Usa Cuentas para tener a mano cada lugar donde guardas dinero: el banco, el"
            " efectivo, una billetera virtual, tus ahorros en dólares o una tarjeta."
        ),
        (
            N_(
                "En Cuentas, «Agregar cuenta» te pide el nombre, el tipo, la moneda y el saldo"
                " de hoy. Desde ahí, el saldo se calcula solo a partir de los movimientos."
            ),
            N_(
                "Para ordenarlas, arrástralas: el panel lateral sigue ese orden. Si tienes muchas,"
                " «Agregar grupo» las junta en grupos como Bancos o Billeteras. Para pasar una"
                " cuenta a otro grupo, arrástrala a su tarjeta, aunque esté vacía, o usa «Mover a"
                " grupo…» en su menú; el aviso ofrece «Deshacer». Un clic en el nombre de un"
                " grupo, en el panel lateral, lo pliega y deja a la vista solo su total."
            ),
            N_(
                "Un clic en una cuenta abre su página: cuánto entró y salió este mes, cómo cambió"
                " su saldo y todos sus movimientos. Una cuenta que ya no usas se archiva desde su"
                " menú; deja de sumar en tu patrimonio neto, pero sus movimientos se conservan."
            ),
        ),
        ("investments", "currencies"),
    ),
    HelpTopic(
        "transactions",
        N_("Anotar transacciones"),
        MONEY,
        (PageId.TRANSACTIONS,),
        N_(
            "Usa «Agregar transacción», arriba en cualquier página, para anotar un gasto, un"
            " ingreso o una transferencia en un momento."
        ),
        (
            N_(
                "El formulario ya trae la última cuenta que usaste. En «Beneficiario», unas letras"
                " bastan para elegir a quién le pagaste, y Nodus completa la categoría que sueles"
                " usar con él. Las etiquetas son opcionales y sirven para juntar lo que va junto,"
                " como los gastos de un viaje."
            ),
            N_(
                "Los montos se escriben con coma para los decimales y punto para los miles, como"
                " en 1.234,56. Si escribes uno que se puede leer de dos maneras, como 1,234.56,"
                " Nodus no adivina: te muestra cómo escribirlo."
            ),
            N_(
                "Para cambiar una transacción, haz doble clic en ella. Cada fila tiene su menú «⋯»,"
                " que también se abre con el clic derecho, con todo lo que puedes hacer con ella."
            ),
            N_(
                "Para cambiar varias a la vez, márcalas con Ctrl + clic o Mayús + clic: la barra"
                " que aparece arriba les cambia la categoría, el beneficiario, la nota o las"
                " etiquetas de una vez, o las elimina juntas."
            ),
            N_(
                "Si te equivocaste, el aviso que aparece abajo a la derecha tiene «Deshacer», y"
                " Ctrl + Z hace lo mismo. Eliminar no se deshace: por eso Nodus pregunta antes. Y"
                " si cierras un formulario con cambios, te pregunta si quieres descartarlos."
            ),
        ),
        ("search", "transfers", "refunds"),
    ),
    HelpTopic(
        "search",
        N_("Buscar y filtrar"),
        MONEY,
        (PageId.TRANSACTIONS,),
        N_(
            "Usa los filtros de Transacciones para responder preguntas como «¿cuánto gasté en"
            " el supermercado este año?»."
        ),
        (
            N_(
                "Arriba eliges el período, y debajo filtras por cuenta, categoría, beneficiario,"
                " etiqueta o tipo. «Buscar…» encuentra texto en la nota y en los nombres del"
                " beneficiario y las etiquetas. Al pie, Nodus suma lo que estás viendo."
            ),
            N_(
                "Muchas páginas te traen hasta acá ya filtrado: un clic en una categoría del"
                " Inicio, en una barra de Análisis o en «Ver movimientos» del menú de una fila."
            ),
            N_(
                "«Exportar» guarda lo que ves en un archivo CSV, que se abre en Excel o en"
                " cualquier planilla."
            ),
        ),
        ("transactions", "analysis"),
    ),
    HelpTopic(
        "transfers",
        N_("Transferencias y compra de dólares"),
        MONEY,
        (PageId.TRANSACTIONS,),
        N_(
            "Usa una transferencia cuando el dinero pasa de una de tus cuentas a otra: así no"
            " cuenta como gasto ni como ingreso, porque sigue siendo tuyo."
        ),
        (
            N_(
                "En el formulario, elige «Transferencia», la cuenta de origen en «Cuenta» y la de"
                " destino en «Hacia». Pagar la tarjeta desde el banco también es una"
                " transferencia."
            ),
            N_(
                "Si las cuentas tienen monedas distintas, como al comprar dólares, aparece «Entra»:"
                " anota lo que salió en «Monto» y lo que llegó en «Entra». Nodus te muestra la"
                " cotización que realmente obtuviste."
            ),
        ),
        ("accounts", "currencies"),
    ),
    HelpTopic(
        "installments",
        N_("Compras en cuotas"),
        MONEY,
        (PageId.RECURRING,),
        N_(
            "Usa las cuotas para anotar una compra una sola vez y que Nodus reparta cada pago"
            " en su mes."
        ),
        (
            N_(
                "Al anotar un gasto, elige en «Cuotas» en cuántas se paga y si el monto es el"
                " «Total» o lo que vale cada una («Por cuota»). Nodus anota todas las cuotas en"
                " sus fechas, y cada una se descuenta de la cuenta el día que le toca."
            ),
            N_(
                "Recurrentes te muestra cuántas pagaste, la próxima y cuánto se llevan las cuotas"
                " cada mes. Abrir cualquier cuota abre la compra entera, para cambiarla o"
                " eliminarla, y su menú tiene «Adelantar las cuotas que faltan»."
            ),
        ),
        ("recurring", "transactions"),
    ),
    HelpTopic(
        "refunds",
        N_("Reembolsos"),
        MONEY,
        (PageId.TRANSACTIONS,),
        N_(
            "Usa «Reembolso de» cuando un comercio te devuelve dinero o alguien te paga su parte,"
            " así tus gastos muestran lo que realmente gastaste."
        ),
        (
            N_("Anota el ingreso como siempre y, en «Reembolso de», elige el gasto que devuelve."),
            N_(
                "Nodus lo cuenta entonces como un gasto menor, en la categoría del gasto original y"
                " en el mes en que volvió el dinero, y no como un ingreso. Tus presupuestos, el"
                " Inicio y Análisis lo tienen en cuenta."
            ),
            N_(
                "Si te devuelven más de lo que quedaba, como 1.000 por una parte de 998, Nodus"
                " anota como reembolso lo que quedaba y el resto como un ingreso aparte, en «Otros»"
                " o la categoría que elijas."
            ),
        ),
        ("transactions", "budgets"),
    ),
    HelpTopic(
        "investments",
        N_("Rendimiento de inversiones"),
        MONEY,
        (PageId.ACCOUNTS,),
        N_(
            "Usa «Actualizar valor» para que tus ahorros e inversiones muestren lo que valen hoy,"
            " con sus intereses o sus cambios de precio."
        ),
        (
            N_(
                "En la página de la cuenta, «Actualizar valor» te pide cuánto vale hoy, tal como lo"
                " muestra su app."
            ),
            N_(
                "Nodus guarda la diferencia como rendimiento: mueve el saldo y tu patrimonio neto,"
                " pero no cuenta como ingreso. La página de la cuenta te dice cuánto rindió sobre"
                " lo que invertiste."
            ),
        ),
        ("accounts", "goals"),
    ),
    HelpTopic(
        "recurring",
        N_("Pagos recurrentes"),
        PLANNING,
        (PageId.RECURRING,),
        N_(
            "Usa Recurrentes para el alquiler, los servicios y las suscripciones: los anotas una"
            " vez y Nodus te avisa cuando toca pagarlos."
        ),
        (
            N_(
                "En Recurrentes, «Agregar cargo» te pide cuánto es, cada cuánto se paga y desde qué"
                " cuenta. Nodus te muestra cuánto suman por mes, qué vence pronto y qué está"
                " atrasado, y la campana te avisa. Si ya sabes que viene, «Ya lo vi», en su menú,"
                " calla el aviso hasta el día anterior, y abrir su aviso en la campana hace lo"
                " mismo; lo vencido avisa siempre."
            ),
            N_(
                "«Pagar» registra el gasto y pasa el cargo a su próxima fecha. Si un mes no se"
                " paga, «Omitir» lo salta sin registrar nada. Los dos se pueden deshacer desde el"
                " aviso que aparece abajo, o con Ctrl + Z."
            ),
            N_(
                "Una suscripción en dólares puede pagarse desde una cuenta en pesos: Nodus estima"
                " los pesos con tu último pago, y tú anotas lo que realmente salió."
            ),
        ),
        ("installments", "budgets"),
    ),
    HelpTopic(
        "budgets",
        N_("Presupuestos"),
        PLANNING,
        (PageId.BUDGETS,),
        N_(
            "Usa Presupuestos para ponerle un límite mensual a las categorías que quieres cuidar"
            " y ver a tiempo si te estás pasando."
        ),
        (
            N_(
                "En Presupuestos, «Agregar presupuesto» te pide la categoría y el límite. Para"
                " elegirlo, Nodus te sugiere tu promedio de los últimos meses."
            ),
            N_(
                "La barra se pone amarilla cuando gastas más rápido de lo que avanza el mes, y roja"
                " cuando te pasas. Un límite vale desde ese mes en adelante, hasta que lo cambies o"
                " lo quites."
            ),
        ),
        ("categories", "analysis"),
    ),
    HelpTopic(
        "goals",
        N_("Metas de ahorro"),
        PLANNING,
        (PageId.GOALS,),
        N_(
            "Usa Metas para juntar dinero para algo que quieres: un viaje, una notebook nueva o"
            " un fondo para imprevistos."
        ),
        (
            N_(
                "En Metas, «Agregar meta» te pide cuánto quieres juntar y, si quieres, para cuándo."
                " Después eliges qué cuentas de ahorro cuentan y qué parte de cada una, así una"
                " misma cuenta sirve a varias metas."
            ),
            N_(
                "Las metas nunca mueven dinero: crecen cuando pasas plata a sus cuentas. Cada una"
                " te dice si a tu ritmo llegas a tiempo y, si no, cuánto hace falta por mes. Cuando"
                " llegas, la campana te avisa."
            ),
        ),
        ("accounts", "investments"),
    ),
    HelpTopic(
        "analysis",
        N_("Análisis"),
        PLANNING,
        (PageId.ANALYSIS,),
        N_(
            "Usa Análisis para tomar distancia y mirar el año completo: cómo cambian tus gastos,"
            " cuánto ahorras y cómo crece lo que tienes."
        ),
        (
            N_(
                "«Tendencias» muestra tus gastos, ingresos o ahorro mes a mes, por categoría y"
                " frente a tu promedio, y en qué se fue el dinero por categoría, beneficiario y"
                " etiqueta."
            ),
            N_(
                "«Flujo de caja» compara ingresos, gastos, ahorro y tasa de ahorro con el período"
                " anterior, y «Patrimonio neto» sigue lo que tienes, fin de mes tras fin de mes."
            ),
            N_("Un clic en cualquier barra o fila te lleva a los movimientos que la forman."),
        ),
        ("search", "budgets"),
    ),
    HelpTopic(
        "categories",
        N_("Categorías, beneficiarios y etiquetas"),
        ORDER,
        (PageId.CATEGORIES, PageId.PAYEES, PageId.TAGS),
        N_(
            "Usa estas tres páginas para ordenar tus movimientos: la categoría dice en qué"
            " gastaste, el beneficiario a quién le pagaste y las etiquetas juntan lo que va junto."
        ),
        (
            N_(
                "Categorías muestra cuánto sumó cada una en el período que elijas, de la más"
                " grande a la más chica, con una barra de cuánto pesa en el total. Cada una puede"
                " tener subcategorías,"
                " como Supermercado dentro de"
                " Comida, con «Agregar subcategoría» en su menú. Si eliminas una, sus movimientos"
                " pasan a «Otros» y no se pierden. «Otros» y «Reembolsos» son de sistema: Nodus"
                " las usa, así que no se renombran ni se eliminan. Para el color, además de la"
                " paleta, el «+»"
                " abre una rueda con cualquier otro, y los últimos que elegiste ahí quedan a mano"
                " después de la paleta, también para las etiquetas."
            ),
            N_(
                "Beneficiarios y Etiquetas muestran cuántos movimientos y cuánto dinero suma cada"
                " uno; un doble clic abre su página con todos sus movimientos. Si tienes"
                " repetidos, como «Coto» y «Coto Online», «Unir con…» los junta en uno, y el"
                " aviso que aparece abajo te deja deshacerlo."
            ),
        ),
        ("transactions", "search"),
    ),
    HelpTopic(
        "currencies",
        N_("Monedas y cotizaciones"),
        DATA,
        (PageId.SETTINGS,),
        N_(
            "Usa una cuenta por moneda y deja que Nodus sume todo en tu patrimonio neto, en pesos"
            " o en dólares."
        ),
        (
            N_(
                "En Ajustes, «Cotizaciones» elige de dónde sale el dólar: con MEP, Blue u Oficial,"
                " Nodus trae el valor del día al abrirse; con «Manual», lo cargas tú. El euro y el"
                " peso chileno usan su cotización oficial."
            ),
            N_(
                "En el Inicio, el patrimonio neto se ve en pesos o en dólares con un clic, y te"
                " dice cuánto cambió por la cotización."
            ),
        ),
        ("transfers", "accounts"),
    ),
    HelpTopic(
        "backups",
        N_("Copias de seguridad"),
        DATA,
        (PageId.SETTINGS,),
        N_(
            "Tus datos viven solo en tu computadora, así que Nodus los cuida por ti con una copia"
            " cada día."
        ),
        (
            N_(
                "Cada día, al abrirse, Nodus guarda una copia en tu computadora. Conserva las tres"
                " más recientes, una por cada una de las cuatro semanas anteriores y una por cada"
                " uno de los seis meses anteriores, así puedes volver a medio año atrás si notas"
                " tarde un error. Antes de borrar una cuenta, una categoría o muchas transacciones,"
                " también guarda una, que se queda un mes."
            ),
            N_(
                "En Ajustes, «Hacer copia» guarda una en el momento y «Restaurar copia…» vuelve a"
                " una anterior, después de guardar cómo están ahora. Nodus revisa la copia entera"
                " antes de usarla: si está dañada o incompleta, te avisa y tus datos quedan como"
                " estaban."
            ),
            N_(
                "Esas copias quedan en el mismo disco, así que una vez al mes conviene guardar una"
                " afuera con «Guardar copia en…», en un pendrive o en una carpeta de Drive. A fin"
                " de mes, Nodus te lo recuerda."
            ),
            N_(
                "Si el archivo de tus datos se daña, al abrirse Nodus te ofrece volver a la última"
                " copia sana, y guarda aparte el archivo dañado."
            ),
        ),
        ("moving", "privacy"),
    ),
    HelpTopic(
        "moving",
        N_("Pasar Nodus a otra computadora"),
        DATA,
        (PageId.SETTINGS,),
        N_(
            "Tus datos pasan enteros a otra computadora con una copia: cuentas, movimientos y"
            " ajustes, tal como estaban."
        ),
        (
            N_(
                "En la computadora de siempre, abre Ajustes y toca «Guardar copia en…». Elige un"
                " pendrive o una carpeta de Drive u OneDrive."
            ),
            N_(
                "En la nueva, instala Nodus. El Inicio te ofrece «Traer mis datos de otra"
                " computadora»: elige la copia que guardaste y listo. Más tarde, lo mismo se hace"
                " desde Ajustes, con «Restaurar copia…»."
            ),
            N_(
                "Si la copia viene de una versión anterior de Nodus, se actualiza sola al"
                " traerla. Una de una versión más nueva necesita que primero actualices Nodus."
            ),
        ),
        ("backups",),
    ),
    HelpTopic(
        "privacy",
        N_("Privacidad"),
        DATA,
        (),
        N_(
            "Nodus no tiene cuentas ni servidores: todo lo que anotas queda en un archivo de tu"
            " computadora."
        ),
        (
            N_(
                "Si alguien mira tu pantalla, el ojo de la barra de arriba oculta tus saldos y tu"
                " patrimonio neto. Vuelve a tocarlo para verlos."
            ),
            N_(
                "Nodus solo se conecta a internet para ver si hay una versión nueva y para traer"
                " las cotizaciones, si elegiste una fuente automática. Las dos cosas se apagan en"
                " Ajustes."
            ),
            N_(
                "Para encontrar un error, Nodus anota lo que hace en un registro, sin montos ni"
                " nombres, que queda en tu computadora. Si algo falla, «Enviar reporte» abre el"
                " formulario de comentarios con el error ya escrito, y lo lees antes de enviarlo."
            ),
        ),
        ("backups",),
    ),
]

TOPICS_BY_KEY = {topic.key: topic for topic in HELP_TOPICS}


def topic_for_page(page_id: PageId) -> HelpTopic | None:
    """The first topic about a page: what F1 opens there. Inicio, where Nodus starts,
    opens on the list of topics instead: its own topic only tells how Nodus is
    organized, and the list shows everything the help covers."""
    if page_id is PageId.DASHBOARD:
        return None
    return next((topic for topic in HELP_TOPICS if page_id in topic.pages), None)
