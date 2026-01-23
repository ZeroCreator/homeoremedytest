import json
from pathlib import Path
import os


class LocalStorage:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        # Проверяем, запущено ли на Vercel
        self.is_vercel = os.environ.get('VERCEL') == '1'
        # Проверяем, не является ли это рестартом в режиме отладки
        self.is_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

    def log_info(self, message):
        """Логирование информационных сообщений с учетом режима рестарта"""
        if not self.is_reloader:
            print(message)

    def log_error(self, message):
        """Логирование ошибок (всегда выводится)"""
        print(f"❌ {message}")

    def load(self):
        """Загрузка данных из локального файла"""
        try:
            if self.is_vercel:
                return {"cards": [], "next_id": 1}

            if not self.filepath.exists():
                return {"cards": [], "next_id": 1}

            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data

        except json.JSONDecodeError as e:
            return {"cards": [], "next_id": 1}
        except Exception as e:
            return {"cards": [], "next_id": 1}

    def save(self, data):
        """Сохранение данных в локальный файл"""
        try:
            if self.is_vercel:
                return True

            self.filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            return False
