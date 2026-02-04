import os
from pathlib import Path

# Определяем корень проекта
BASE_DIR = Path(__file__).resolve().parent

# Проверяем окружение
IS_VERCEL = os.environ.get('VERCEL') == '1'

# Путь к локальному файлу (по умолчанию)
LOCAL_DATA_PATH = Path('data/test_cards.json')
# Если путь относительный, делаем абсолютным
if not LOCAL_DATA_PATH.is_absolute():
    LOCAL_DATA_PATH = BASE_DIR / LOCAL_DATA_PATH

# Для совместимости
JSON_FILE = LOCAL_DATA_PATH

if IS_VERCEL:
    # На Vercel: uploads в /tmp
    UPLOAD_DIR = Path('/tmp/uploads')
    # На Vercel: templates в /tmp (так как файлы read-only)
    TEMPLATE_DIR = Path('/tmp/templates')
    # На Vercel: data в /tmp
    DATA_DIR = Path('/tmp/data')
else:
    # Локальная разработка
    UPLOAD_DIR = BASE_DIR / 'uploads'
    TEMPLATE_DIR = BASE_DIR / 'templates'
    DATA_DIR = BASE_DIR / 'data'

# Статические пути
STATIC_DIR = BASE_DIR / 'public' / 'static'
