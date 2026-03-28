[Readme.md](https://github.com/user-attachments/files/26317843/Readme.md)
# SGETV Táctil - Sistema de Gestión de Equipos Telereparo Vigo

Sistema de gestión táctil para taller de reparaciones con interfaz optimizada para pantallas táctiles.

## 📋 Características

- ✨ **Interfaz táctil optimizada** - Botones grandes y diseño adaptado para pantallas táctiles
- 👥 **Gestión de clientes** - Alta, modificación y eliminación de clientes
- 📱 **Control de equipos** - Registro y seguimiento de equipos reparados
- 🔧 **Gestión de reparaciones** - Control de tareas y trabajos realizados
- 💰 **Presupuestos** - Creación, aceptación/rechazo y exportación de presupuestos
- 📊 **Estadísticas** - Informes y análisis de reparaciones
- 💾 **Respaldo de base de datos** - Copias de seguridad automáticas
- 🖨️ **Exportación** - Generación de informes en PDF y CSV
- 🔐 **Auditoría** - Registro de todos los cambios realizados
- 🌍 **Multiplataforma** - Funciona en Linux (Debian/Ubuntu/Parrot) y Windows

## 📋 Requisitos del Sistema

### Linux (Debian/Ubuntu/Parrot)
- Python 3.8 o superior
- MariaDB 10.0 o superior
- Tkinter (para interfaz gráfica)
- Conectores MySQL para Python

### Windows
- Python 3.8 o superior
- MySQL 5.7 o superior
- Tkinter (incluido en Python)

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/sgetv-tactil.git
cd sgetv-tactil

2. Configurar la base de datos
En Linux (Debian/Ubuntu/Parrot):
bash

# Instalar MariaDB
sudo apt update
sudo apt install mariadb-server mariadb-client -y

# Iniciar MariaDB
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Configurar contraseña de root
sudo mysql << EOF
ALTER USER 'root'@'localhost' IDENTIFIED BY 'tu_clave';
CREATE DATABASE IF NOT EXISTS \`Reparaciones Telereparo Vigo\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON \`Reparaciones Telereparo Vigo\`.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
EOF

# Importar tu archivo SQL (reemplaza "tu_archivo.sql" con la ruta real)
mysql -u root -p'tu_clave' "Reparaciones Telereparo Vigo" < tu_archivo.sql

En Windows:
bash

# Acceder a MySQL
mysql -u root -p

# Crear base de datos
CREATE DATABASE IF NOT EXISTS `Reparaciones Telereparo Vigo` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON `Reparaciones Telereparo Vigo`.* TO 'root'@'localhost';
FLUSH PRIVILEGES;

# Importar tu archivo SQL
USE `Reparaciones Telereparo Vigo`;
SOURCE ruta/a/tu/archivo.sql;

3. Instalar dependencias
En Linux (Debian/Ubuntu/Parrot):
bash

# Instalar dependencias del sistema
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-tk \
    python3-pil \
    python3-pil.imagetk \
    python3-reportlab \
    mariadb-server \
    mariadb-client

# Instalar dependencias Python
sudo pip install mysql-connector-python tkcalendar fpdf2 --break-system-packages

En Windows:
bash

# Instalar dependencias Python
pip install mysql-connector-python
pip install reportlab
pip install pillow
pip install fpdf2
pip install tkcalendar

4. Configurar la aplicación

Crea un archivo config.py con tus datos de conexión:
python

# Configuración de la base de datos
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "tu_clave",
    "database": "Reparaciones Telereparo Vigo"
}

5. Ejecutar la aplicación
bash

python3 sgetv_tactil.py

📁 Estructura del Proyecto
text

sgetv-tactil/
├── sgetv_tactil.py          # Aplicación principal
├── config.example.py        # Ejemplo de configuración
├── requirements.txt         # Dependencias
├── README.md               # Documentación
├── .gitignore              # Archivos ignorados por Git
├── presupuestos/           # Carpeta para presupuestos generados
├── notas_entrega/          # Carpeta para notas de entrega
└── logo_embed.py           # Logo embebido (opcional)

🎮 Uso de la Aplicación
Menú Principal

    Registrar equipos - Alta de nuevos equipos en el sistema

    Ver registros - Consulta y filtrado de equipos registrados

    Ver presupuestos - Gestión de presupuestos generados

    Gestión de clientes - Administración de la base de clientes

    Estadísticas - Informes y análisis de reparaciones

    Respaldo de base de datos - Creación de copias de seguridad

    Comprobar conexión - Diagnóstico de conexión a la base de datos

    Salir - Cerrar la aplicación

Atajos de Teclado

    F11 - Activar/Desactivar modo pantalla completa

    Esc - Salir del modo pantalla completa

    Alt+F4 - Cerrar la aplicación

📊 Funcionalidades Detalladas
Registro de Equipos

    Datos del cliente (selector desplegable)

    Tipo de equipo, marca y modelo

    Categoría (Móvil, Tablet, Laptop, PC, Periférico, Otro)

    Diagnóstico inicial

    Garantía en días

Gestión de Tareas

    Registro de tareas realizadas

    Control de tiempos y precios

    Registro de piezas utilizadas

    Cierre de reparación con cálculo de total

Presupuestos

    Creación desde tareas

    Aceptación/Rechazo

    Exportación a PDF

    Validez de 15 días

Exportaciones

    CSV - Listado de registros filtrados

    PDF - Informes profesionales

    Notas de entrega - Documentos para clientes

🔧 Solución de Problemas
Error de conexión a la base de datos
bash

# Verificar que MariaDB está corriendo
sudo systemctl status mariadb

# Reiniciar MariaDB
sudo systemctl restart mariadb

# Verificar credenciales
mysql -u root -p'tu_clave' -e "SELECT VERSION();"

Error "externally-managed-environment"

Usa el entorno virtual incluido:
bash

# Activar entorno virtual
source venv_sgetv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicación
python sgetv_tactil.py

📝 Estructura de la Base de Datos
Tablas Principales

    clientes - Información de clientes

    estados_reparacion - Estados posibles de las reparaciones

    recepciones_despachos - Registro de equipos recibidos

    reparaciones - Tareas realizadas en cada equipo

    piezas_utilizadas - Piezas empleadas en reparaciones

    presupuestos - Presupuestos generados

    copias_seguridad - Historial de respaldos

    auditoria_cambios - Registro de modificaciones

🔒 Seguridad

    Las credenciales de base de datos están separadas en config.py

    Auditoría de todos los cambios en la base de datos

    Respaldos automáticos programables

🛠️ Desarrollo

Entorno de desarrollo
bash

# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate  # Linux
venv\Scripts\activate      # Windows

# Instalar dependencias de desarrollo
pip install -r requirements.txt

Ejecutar pruebas
bash

# Probar conexión a la base de datos
python3 -c "import mysql.connector; print('✓ OK')"

# Verificar todas las importaciones
python3 -c "import reportlab; import PIL; from fpdf import FPDF; import tkcalendar; print('✓ OK')"

📄 Licencia

© Gabriel Carbon Garcia 2026 Vigo

Todos los derechos reservados. Este software es propiedad de Gabriel Carbon Garcia y no puede ser copiado, modificado, distribuido o utilizado sin autorización expresa.
👤 Autor

Gabriel Carbon Garcia

    Desarrollo completo del sistema

    Diseño de interfaz táctil

    Arquitectura de base de datos

    Documentación

🤝 Soporte

Para reportar errores o solicitar mejoras:

    Abre un issue en GitHub

    Proporciona detalles del error (logs, capturas)

    Describe los pasos para reproducir el problema

📦 Dependencias

    mysql-connector-python - Conector para base de datos

    reportlab - Generación de informes PDF

    pillow - Procesamiento de imágenes

    fpdf2 - Generación de PDF alternativo

    tkcalendar - Widget de calendario

🎯 Características Especiales

    Modo quiosco - Pantalla completa para uso en terminales táctiles

    Teclado virtual - Compatible con onboard (Linux) y osk (Windows)

    Diseño adaptable - Interfaz que se adapta a diferentes resoluciones

    Exportación profesional - Documentos con formato corporativo

SGETV Táctil - La solución completa para la gestión de talleres de reparación
