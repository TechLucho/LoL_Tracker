import shutil
import os
from datetime import datetime

# Rutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Subimos un nivel a la raíz
DB_PATH = os.path.join(BASE_DIR, 'data', 'lol_tracker.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'data', 'backups')

# Crear carpeta de backups si no existe
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# Nombre del archivo con fecha
timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
backup_filename = f"backup_{timestamp}.db"
backup_path = os.path.join(BACKUP_DIR, backup_filename)

if os.path.exists(DB_PATH):
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Backup creado con éxito: {backup_filename}")
else:
    print("❌ No se encontró la base de datos original.")