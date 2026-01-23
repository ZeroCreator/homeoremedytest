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
                self.log_info(f"📝 LocalStorage.load: Файл не существует, создаем пустую структуру")
                return {"cards": [], "next_id": 1}

            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.log_info(f"✅ LocalStorage.load: Загружено {len(data.get('cards', []))} карточек")
                return data

        except json.JSONDecodeError as e:
            self.log_error(f"LocalStorage.load: Ошибка JSON: {e}")
            return {"cards": [], "next_id": 1}
        except Exception as e:
            self.log_error(f"LocalStorage.load: Ошибка: {e}")
            return {"cards": [], "next_id": 1}

    def save(self, data):
        """Сохранение данных в локальный файл"""
        try:
            # НА VERCEL ЛОКАЛЬНОЕ СОХРАНЕНИЕ НЕВОЗМОЖНО
            if self.is_vercel:
                # Возвращаем True для совместимости, но не пытаемся сохранить
                return True

            self.log_info(f"💾 LocalStorage.save: Сохраняем в {self.filepath}")
            self.log_info(f"📊 LocalStorage.save: Карточек для сохранения: {len(data.get('cards', []))}")

            # Проверяем структуру данных
            if not isinstance(data, dict):
                self.log_error(f"LocalStorage.save: ОШИБКА: данные не словарь!")
                return False

            if 'cards' not in data:
                self.log_error(f"LocalStorage.save: ОШИБКА: нет ключа 'cards'!")
                return False

            # Создаем директорию если нужно
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self.log_info(f"📁 LocalStorage.save: Директория создана: {self.filepath.parent}")

            # Сохраняем файл
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.log_info(f"✅ LocalStorage.save: Файл записан")

            # Проверяем что файл существует и читается
            if self.filepath.exists():
                file_size = self.filepath.stat().st_size
                self.log_info(f"📏 LocalStorage.save: Размер файла: {file_size} байт")

                # Читаем обратно для проверки
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    saved_count = len(saved_data.get('cards', []))
                    self.log_info(f"📖 LocalStorage.save: Проверка: загружено {saved_count} карточек")

                    if saved_count == len(data.get('cards', [])):
                        self.log_info(f"✅ LocalStorage.save: Все карточки сохранены успешно!")
                        return True
                    else:
                        self.log_error(f"LocalStorage.save: ОШИБКА: сохранено {saved_count}, ожидалось {len(data.get('cards', []))}")
                        return False
            else:
                self.log_error(f"LocalStorage.save: ОШИБКА: файл не существует после записи!")
                return False

        except Exception as e:
            self.log_error(f"LocalStorage.save: ОШИБКА: {e}")
            import traceback
            traceback.print_exc()
            return False
