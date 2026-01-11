import json
from pathlib import Path


class LocalStorage:
    """Локальное хранилище (для совместимости и fallback)"""

    def __init__(self, filepath):
        self.filepath = Path(filepath)

    def load(self):
        """Загрузка данных из локального файла"""
        try:
            if not self.filepath.exists():
                return {"cards": [], "next_id": 1}

            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)

        except json.JSONDecodeError:
            return {"cards": [], "next_id": 1}
        except Exception as e:
            print(f"Ошибка загрузки локального файла: {e}")
            return {"cards": [], "next_id": 1}

    def save(self, data):
        """Сохранение данных в локальный файл"""
        try:
            # Проверяем структуру данных
            if not isinstance(data, dict):
                return False

            if 'cards' not in data:
                return False

            # Создаем директорию если нужно
            self.filepath.parent.mkdir(parents=True, exist_ok=True)

            # Сохраняем файл
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Сохранено {len(data.get('cards', []))} карточек в локальный файл")
            return True
        except Exception as e:
            print(f"Ошибка сохранения локального файла: {e}")
            return False
