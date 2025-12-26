import os
from pathlib import Path

# Определяем корень проекта
BASE_DIR = Path(__file__).resolve().parent

# Проверяем окружение
IS_VERCEL = os.environ.get('VERCEL') == '1'

if IS_VERCEL:
    # На Vercel используем /tmp
    DATA_DIR = Path('/tmp')
    JSON_FILE = DATA_DIR / 'test_cards.json'
    UPLOAD_DIR = DATA_DIR / 'uploads'
    print("VERCEL environment detected - using /tmp for data")
else:
    # Локальная разработка
    DATA_DIR = BASE_DIR / 'app' / 'data'
    JSON_FILE = DATA_DIR / 'test_cards.json'
    UPLOAD_DIR = BASE_DIR / 'uploads'
    print("LOCAL environment - using project folders")

# Статические пути (всегда в проекте)
STATIC_DIR = BASE_DIR / 'public' / 'static'
TEMPLATE_DIR = BASE_DIR / 'app' / 'templates'

# Выводим для отладки
print(f"JSON_FILE: {JSON_FILE}")
print(f"UPLOAD_DIR: {UPLOAD_DIR}")
print(f"DATA_DIR: {DATA_DIR}")
