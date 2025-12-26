import os
from pathlib import Path


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'secret')

    # Пути будут импортироваться из paths.py
    # Импортируем здесь, чтобы избежать циклических импортов
    from paths import STATIC_DIR, TEMPLATE_DIR, JSON_FILE, UPLOAD_DIR

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
