import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Определяем корень проекта (где находится config.py)
BASE_DIR = Path(__file__).resolve().parent

# Определяем окружение
IS_VERCEL = os.environ.get('VERCEL') == '1'
IS_RELOADER = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

# Загружаем .env локально, но не на Vercel
if not IS_VERCEL:
    load_dotenv()


# Вспомогательные функции для создания путей
def make_path(path_str: str, default: str) -> Path:
    """Создает путь с учетом Vercel"""
    if IS_VERCEL:
        # На Vercel всегда используем /tmp
        return Path('/tmp') / default
    else:
        path = Path(path_str) if path_str else Path(default)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path


def ensure_dir(path: Path):
    """Создает директорию если она не существует"""
    if not IS_RELOADER:  # Не создаем папки при перезагрузке Flask
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Директория создана: {path}")


class Config:
    # Безопасность
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Настройки хранилища
    STORAGE_MODE = os.environ.get('STORAGE_MODE', 'hybrid')  # local, yandex, hybrid
    YANDEX_DISK_TOKEN = os.environ.get('YANDEX_DISK_TOKEN')

    # Пути на Яндекс.Диске
    YANDEX_DISK_PATH = os.environ.get('YANDEX_DISK_PATH', 'HomeoRemedyTest/data/test_cards.json')
    YANDEX_DISK_BACKUP_PATH = os.environ.get('YANDEX_DISK_BACKUP_PATH', 'HomeoRemedyTest/backups')

    # --- ЛОКАЛЬНЫЕ ПУТИ ---
    # Путь к локальному файлу данных (из .env или по умолчанию)
    LOCAL_DATA_PATH_ENV = os.environ.get('LOCAL_DATA_PATH', 'data/test_cards.json')
    JSON_FILE = make_path(LOCAL_DATA_PATH_ENV, 'data/test_cards.json')

    # Путь к локальным бэкапам (из .env или по умолчанию)
    LOCAL_BACKUP_PATH_ENV = os.environ.get('LOCAL_BACKUP_PATH', 'backups')
    BACKUP_DIR = make_path(LOCAL_BACKUP_PATH_ENV, 'backups')

    # Путь для загрузок
    UPLOAD_DIR = make_path('', 'uploads')

    # Путь к шаблонам (всегда из исходного кода на Vercel, копируем в /tmp)
    if IS_VERCEL:
        TEMPLATE_DIR = Path('/tmp/templates')
    else:
        TEMPLATE_DIR = BASE_DIR / 'templates'

    # Путь к статическим файлам
    STATIC_DIR = BASE_DIR / 'public' / 'static'

    # Путь к данным (директория где лежит JSON_FILE)
    DATA_DIR = JSON_FILE.parent

    # --- ИНИЦИАЛИЗАЦИЯ ПУТЕЙ ---
    @classmethod
    def init_paths(cls):
        """Создание всех необходимых директорий"""
        if not IS_RELOADER:
            print(f"\n🔍 Инициализация путей:")
            print(f"   Режим: {'Vercel' if IS_VERCEL else 'Локальный'}")
            print(f"   Базовая директория: {BASE_DIR}")

            # Создаем необходимые директории
            dirs_to_create = [
                (cls.UPLOAD_DIR, 'Загрузки'),
                (cls.BACKUP_DIR, 'Бэкапы'),
                (cls.DATA_DIR, 'Данные'),
            ]

            for directory, name in dirs_to_create:
                try:
                    ensure_dir(directory)
                except Exception as e:
                    print(f"❌ Ошибка создания {name} ({directory}): {e}")

            # На Vercel создаем TEMPLATE_DIR
            if IS_VERCEL:
                try:
                    ensure_dir(cls.TEMPLATE_DIR)
                except Exception as e:
                    print(f"❌ Ошибка создания шаблонов на Vercel: {e}")

    # --- ОСТАЛЬНЫЕ НАСТРОЙКИ ---
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
    MAX_BACKUPS = int(os.environ.get('MAX_BACKUPS', 50))
    BACKUP_ON_START = os.environ.get('BACKUP_ON_START', 'false').lower() == 'true'


# Экспортируем IS_VERCEL для удобства
IS_VERCEL = IS_VERCEL

# Инициализируем пути при импорте
Config.init_paths()
