"""
Configuración de ejemplo para SGETV
Copia este archivo como config.py y modifica los valores según tu entorno
"""

# Configuración de la base de datos
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "tu_contraseña",
    "database": "Reparaciones Telereparo Vigo"
}

# Configuración de la aplicación
APP_CONFIG = {
    "window_width": 1366,
    "window_height": 768,
    "min_width": 1200,
    "min_height": 700,
    "title": "SGETV Táctil - Sistema de Gestión de Equipos Telereparo Vigo"
}

# Configuración de respaldos
BACKUP_CONFIG = {
    "default_path": "~/Desktop",
    "filename_prefix": "telereparo_respaldo_"
}

# Configuración de exportación
EXPORT_CONFIG = {
    "presupuestos_folder": "presupuestos",
    "notas_folder": "notas_entrega"
}

# Configuración de PDF
PDF_CONFIG = {
    "company_name": "Telereparo Vigo",
    "footer_text": "Sistema de Gestión de Equipos Telereparo Vigo"
}
