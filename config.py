import os
from pathlib import Path

class Config:
    SECRET_KEY = 'secret'

    # Получаем абсолютный путь к текущему файлу (config.py)
    BASE_DIR = Path(__file__).resolve().parent  # Корень проекта

    # Пути для Flask
    STATIC_DIR = BASE_DIR / 'public' / 'static'
    TEMPLATE_DIR = BASE_DIR / 'app' / 'templates'

    # Пути к данным
    DATA_DIR = BASE_DIR / 'app' / 'data'
    JSON_FILE = DATA_DIR / 'test_cards.json'

    # Настройки приложения
    CARDS_PER_PAGE = 20
    SEARCH_DELAY = 500

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
