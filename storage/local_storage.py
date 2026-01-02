import json
from pathlib import Path


class LocalStorage:
    """Локальное хранилище (для совместимости и fallback)"""

    def __init__(self, filepath):
        self.filepath = Path(filepath)

    def load(self):
        """Загрузка данных из локального файла"""
        try:
            if self.filepath.exists():
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"Загружено {len(data.get('cards', []))} карточек из локального файла")
                    return data
            return {"cards": [], "themes": [], "next_id": 1}
        except Exception as e:
            print(f"Ошибка загрузки локального файла: {e}")
            return {"cards": [], "themes": [], "next_id": 1}

    def save(self, data):
        """Сохранение данных в локальный файл"""
        try:
            # Создаем папку если нет
            self.filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Сохранено {len(data.get('cards', []))} карточек в локальный файл")
            return True
        except Exception as e:
            print(f"Ошибка сохранения локального файла: {e}")
            return False
