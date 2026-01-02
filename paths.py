import os
from pathlib import Path

# Определяем корень проекта
BASE_DIR = Path(__file__).resolve().parent

# Проверяем окружение
IS_VERCEL = os.environ.get('VERCEL') == '1'

# Путь к локальному файлу (по умолчанию)
LOCAL_DATA_PATH = Path('app/data/test_cards.json')
# Если путь относительный, делаем абсолютным
if not LOCAL_DATA_PATH.is_absolute():
    LOCAL_DATA_PATH = BASE_DIR / LOCAL_DATA_PATH

# Для совместимости
JSON_FILE = LOCAL_DATA_PATH

if IS_VERCEL:
    # На Vercel: uploads в /tmp
    UPLOAD_DIR = Path('/tmp/uploads')
    print(f"VERCEL environment detected")
else:
    # Локальная разработка
    UPLOAD_DIR = BASE_DIR / 'uploads'
    print("LOCAL environment")

# Статические пути
STATIC_DIR = BASE_DIR / 'public' / 'static'
TEMPLATE_DIR = BASE_DIR / 'app' / 'templates'

# Выводим для отладки
print(f"JSON_FILE: {JSON_FILE}")
print(f"JSON exists: {JSON_FILE.exists()}")
print(f"UPLOAD_DIR: {UPLOAD_DIR}")
