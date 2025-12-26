import os
from pathlib import Path

# Определяем корень проекта
BASE_DIR = Path(__file__).resolve().parent

# Проверяем окружение
IS_VERCEL = os.environ.get('VERCEL') == '1'

# ВСЕГДА используем JSON из репозитория (он доступен на чтение)
JSON_FILE = BASE_DIR / 'app' / 'data' / 'test_cards.json'

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
print(f"JSON_FILE: {JSON_FILE} (always from repository)")
print(f"JSON exists: {JSON_FILE.exists()}")
print(f"UPLOAD_DIR: {UPLOAD_DIR}")
