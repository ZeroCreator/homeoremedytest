import os
from pathlib import Path
from dotenv import load_dotenv

# Определяем окружение
IS_VERCEL = os.environ.get('VERCEL') == '1'

# Загружаем .env локально, но не на Vercel
if not IS_VERCEL:
    load_dotenv()

class Config:
    # Безопасность
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Настройки хранилища
    STORAGE_MODE = os.environ.get('STORAGE_MODE', 'hybrid')  # local, yandex, hybrid
    YANDEX_DISK_TOKEN = os.environ.get('YANDEX_DISK_TOKEN')

    # Путь на Яндекс.Диске
    YANDEX_DISK_PATH = os.environ.get('YANDEX_DISK_PATH', 'HomeoRemedyTest/data/test_cards.json')

    # Путь к локальному файлу данных
    LOCAL_DATA_PATH = os.environ.get('LOCAL_DATA_PATH', 'data/test_cards.json')
    # Преобразуем в абсолютный путь
    _base_dir = Path(__file__).parent.parent
    JSON_FILE = _base_dir / LOCAL_DATA_PATH if not Path(LOCAL_DATA_PATH).is_absolute() else Path(LOCAL_DATA_PATH)

    # Настройки приложения
    CARDS_PER_PAGE = int(os.environ.get('CARDS_PER_PAGE', 20))
    SEARCH_DELAY = int(os.environ.get('SEARCH_DELAY', 500))

    # Структура карточки
    DEFAULT_FIELDS = {
        "id": 0,
        "theme": "",
        "question": "",
        "answer": "",
        "explanation": "",
        "difficulty": "medium",
        "hidden": False
    }

    # Список тем по умолчанию
    DEFAULT_THEMES = ['Растения', 'Животные', 'Минералы', 'Нозоды', 'Саркоды']

    # Уровни сложности
    DIFFICULTY_LEVELS = {
        'easy': {'name': 'Легкий', 'color': '#2e7d32', 'icon': 'fa-leaf'},
        'medium': {'name': 'Средний', 'color': '#ef6c00', 'icon': 'fa-balance-scale'},
        'hard': {'name': 'Сложный', 'color': '#c62828', 'icon': 'fa-fire'}
    }

    # Настройки бэкапов
    BACKUP_DIR = Path('backups')
    MAX_BACKUPS = int(os.environ.get('MAX_BACKUPS', 50))  # Максимальное количество хранимых бэкапов
    BACKUP_ON_START = os.environ.get('BACKUP_ON_START', 'false').lower() == 'true'
    # Путь на Яндекс.Диске для бэкапов
    YANDEX_DISK_BACKUP_PATH = os.environ.get('YANDEX_DISK_BACKUP_PATH', 'HomeoRemedyTest/backups')

    # Синхронизация при старте
    # Если True - всегда синхронизировать с Яндекс.Диском при старте
    # Если False - загружать только локальные данные, если файл существует
    SYNC_ON_STARTUP = True  # Измените на True если хотите всегда синхронизировать
