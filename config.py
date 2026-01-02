import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

class Config:
    # Безопасность
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Настройки хранилища
    STORAGE_MODE = os.environ.get('STORAGE_MODE', 'hybrid')  # local, yandex, hybrid
    YANDEX_DISK_TOKEN = os.environ.get('YANDEX_DISK_TOKEN')
    YANDEX_DISK_PATH = os.environ.get('YANDEX_DISK_PATH', 'HomeoRemedyTest/app/data/test_cards.json')

    # Путь к локальному файлу данных
    LOCAL_DATA_PATH = os.environ.get('LOCAL_DATA_PATH', 'app/data/test_cards.json')
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

    @classmethod
    def print_config(cls):
        """Вывод конфигурации для отладки"""
        print("=" * 60)
        print("КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ")
        print("=" * 60)

        # Безопасность (частично скрыто)
        print(
            f"SECRET_KEY: {'установлен' if cls.SECRET_KEY and cls.SECRET_KEY != 'dev-secret-key-change-in-production' else 'используется дефолтный'}")

        # Хранилище
        print(f"STORAGE_MODE: {cls.STORAGE_MODE}")
        print(f"YANDEX_DISK_TOKEN: {'установлен' if cls.YANDEX_DISK_TOKEN else 'не установлен'}")
        print(f"YANDEX_DISK_PATH: {cls.YANDEX_DISK_PATH}")
        print(f"LOCAL_DATA_PATH: {cls.LOCAL_DATA_PATH}")
        print(f"JSON_FILE: {cls.JSON_FILE}")

        # Приложение
        print(f"CARDS_PER_PAGE: {cls.CARDS_PER_PAGE}")
        print(f"SEARCH_DELAY: {cls.SEARCH_DELAY}")
        print("=" * 60)
