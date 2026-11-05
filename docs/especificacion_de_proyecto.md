# Documento de Definición de Proyecto: Nodus (Aplicación de Finanzas Personales Local-First)

## Resumen Ejecutivo

El presente documento describe los lineamientos para el desarrollo de una aplicación de escritorio dedicada a la gestión de finanzas personales. El producto busca ocupar un nicho desatendido en el mercado actual: combinar la estética fluida y moderna de las aplicaciones web contemporáneas (SaaS) con la privacidad, velocidad y control absoluto de los sistemas tradicionales basados en almacenamiento local. La premisa fundamental es eliminar la dependencia de servidores externos, cuentas de usuario y suscripciones, ofreciendo una experiencia robusta y de código abierto que se ejecute enteramente en la máquina del usuario final.

## Identidad de Marca y Nomenclatura

El proyecto opera bajo el nombre de **Nodus**. En latín, este término significa nodo o punto de intersección. Esta identidad refleja de manera directa la arquitectura central del sistema: la computadora del usuario es el único lugar donde convergen, se procesan y existen sus datos financieros. El nombre evoca solidez matemática, control local y modernidad técnica, estableciendo una marca corta, memorable y con fuerte presencia visual para el entorno de escritorio.

## Arquitectura del Sistema

### Paradigma de Desarrollo

La aplicación se construirá bajo una arquitectura de escritorio nativa e independiente. A diferencia de las soluciones web autoalojadas que requieren la virtualización de servidores o el uso de contenedores, este sistema operará mediante un proceso único en el sistema operativo del usuario. Esto garantiza tiempos de carga casi instantáneos y un consumo mínimo de memoria RAM, operando con la misma eficiencia que una hoja de cálculo tradicional.

### Stack Tecnológico

Para lograr el equilibrio entre un rendimiento nativo y una interfaz gráfica de alta fidelidad, se ha definido el siguiente conjunto de tecnologías:

* **Lenguaje Base:** Python, elegido por su ecosistema de procesamiento de datos y su rapidez de desarrollo.

* **Motor Gráfico:** PySide6 (Qt for Python). Se priorizará el uso de componentes con diseño moderno, ya sea mediante la integración de QML para interfaces declarativas animadas, o el uso de librerías de estilos avanzados (como QFluentWidgets) para emular estándares de diseño actuales.

* **Motor de Base de Datos:** SQLite. Actuará como el núcleo de persistencia de la aplicación.

## Estrategia de Datos y Privacidad

El manejo de la información seguirá un enfoque estrictamente local. La base de datos completa de un usuario residirá en un único archivo físico dentro de su sistema de archivos. Este diseño elimina los riesgos asociados a brechas de seguridad en la nube y otorga al usuario la propiedad absoluta de su historial financiero. La aplicación interactuará con este archivo mediante consultas SQL ejecutadas directamente en memoria, lo que permitirá generar gráficos y reportes complejos sin latencia de red.

## Estructura del Código Fuente

El repositorio se organizará mediante una arquitectura de separación de responsabilidades para facilitar su escalabilidad y posterior compilación. Todo el código fuente funcional quedará encapsulado dentro de un directorio principal, aislando la lógica de negocio de los archivos de configuración del repositorio.

Internamente, el proyecto dividirá la interfaz gráfica, la conexión a la base de datos y los modelos de datos en módulos independientes. Se establecerá un único punto de entrada (archivo principal) cuya única responsabilidad será inicializar la aplicación gráfica y verificar la integridad o existencia del archivo de base de datos local antes de cargar la interfaz al usuario.

## Distribución y Ciclo de Vida

### Empaquetado

Para asegurar una adopción libre de fricciones, el usuario final no deberá interactuar con terminales, intérpretes de Python ni dependencias. El código fuente se congelará utilizando herramientas de empaquetado (como PyInstaller) para generar un archivo ejecutable monolítico, al cual se le incrustará la identidad visual (logotipo) del proyecto.

### Despliegue Automatizado

El repositorio en GitHub actuará como el centro de distribución oficial. Se configurarán flujos de trabajo de Integración y Entrega Continua (CI/CD) mediante GitHub Actions. Cada vez que el código alcance una nueva versión estable, los servidores de GitHub compilarán automáticamente el ejecutable y lo publicarán en la sección de lanzamientos del repositorio, dejándolo listo para su descarga pública.

### Sistema de Actualizaciones

Para mantener el software al día sin depender de infraestructuras costosas, la aplicación integrará un mecanismo de consulta pasiva. Al iniciarse, la aplicación consultará la API pública de GitHub para comparar su versión actual con el último lanzamiento disponible. En caso de existir una nueva versión, se notificará al usuario de manera no intrusiva dentro de la misma interfaz gráfica, facilitando un enlace directo para la descarga del instalador actualizado.