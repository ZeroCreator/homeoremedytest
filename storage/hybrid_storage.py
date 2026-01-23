import os
from pathlib import Path
from enum import Enum


class StorageMode(Enum):
    """Режимы хранения данных"""
    LOCAL = "local"  # Только локальный файл
    YANDEX_DISK = "yandex"  # Только Яндекс.Диск
    HYBRID = "hybrid"  # Гибридный режим (только чтение из облака при старте)


class HybridStorage:
    """Гибридное хранилище с приоритетом"""

    def __init__(self, mode=None, local_path=None, yandex_token=None, yandex_path=None):
        """
        Инициализация гибридного хранилища

        Args:
            mode: режим хранения (local, yandex, hybrid)
            local_path: путь к локальному файлу
            yandex_token: OAuth токен Яндекс.Диска
            yandex_path: путь к файлу на Яндекс.Диске
        """
        self.mode = mode or os.environ.get('STORAGE_MODE', 'hybrid')
        self.local_path = Path(local_path) if local_path else Path('app/data/test_cards.json')

        # Проверяем, не является ли это рестартом в режиме отладки
        self.is_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

        # Задаем путь на Яндекс.Диске
        self.yandex_path = yandex_path or 'test_cards.json'

        # Инициализируем хранилища
        from .local_storage import LocalStorage
        from .yandex_disk import YandexDiskStorage

        self.local_storage = LocalStorage(self.local_path)

        if yandex_token and self.mode in ['yandex', 'hybrid']:
            # Передаем путь к файлу на Яндекс.Диске
            self.yandex_storage = YandexDiskStorage(
                oauth_token=yandex_token,
                filename=self.yandex_path
            )
            self.has_yandex = True
        else:
            self.yandex_storage = None
            self.has_yandex = False

    def log_info(self, message):
        """Логирование информационных сообщений с учетом режима рестарта"""
        if not self.is_reloader:
            print(message)

    def log_error(self, message):
        """Логирование ошибок (всегда выводится)"""
        print(message)

    def load(self):
        """Загрузка данных - только локальные данные"""
        # ВСЕГДА загружаем только локальные данные
        return self.local_storage.load()

    def save(self, data):
        """Сохранение данных - ТОЛЬКО локально в гибридном режиме"""
        self.log_info(f"Сохранение данных в режиме: {self.mode}")
        results = {}

        # Всегда сохраняем локально
        results['local'] = self.local_storage.save(data)

        # Сохраняем на Яндекс.Диск только если это режим 'yandex'
        # В гибридном режиме НЕ сохраняем на Яндекс.Диск автоматически!
        if self.mode == 'yandex' and self.has_yandex:
            try:
                results['yandex'] = self.yandex_storage.save(data)
                if not results['yandex']:
                    self.log_error("Внимание: не удалось сохранить на Яндекс.Диск")
            except Exception as e:
                self.log_error(f"Ошибка при сохранении на Яндекс.Диск: {e}")
                results['yandex'] = False
        elif self.mode == 'hybrid':
            # В гибридном режиме явно указываем, что на Яндекс.Диск не сохраняем
            self.log_info("ℹ️ Гибридный режим: сохранено только локально")
            results['yandex'] = None
        else:
            results['yandex'] = None

        return results

    def sync_to_yandex(self):
        """Ручная синхронизация локальных данных на Яндекс.Диск"""
        if not self.has_yandex:
            return False, "Яндекс.Диск не настроен"

        try:
            # Загружаем локальные данные
            local_data = self.local_storage.load()

            self.log_info(f"🔄 Ручная синхронизация на Яндекс.Диск...")
            self.log_info(f"📊 Отправляем {len(local_data.get('cards', []))} карточек")

            # Сохраняем на Яндекс.Диск
            success = self.yandex_storage.save(local_data)

            if success:
                self.log_info(f"✅ Синхронизация успешно завершена")
                return True, f"Синхронизировано {len(local_data.get('cards', []))} карточек"
            else:
                self.log_error("❌ Ошибка синхронизации")
                return False, "Ошибка сохранения на Яндекс.Диск"

        except Exception as e:
            self.log_error(f"❌ Ошибка синхронизации: {e}")
            return False, f"Ошибка: {str(e)}"

    def force_load_from_yandex(self):
        """Принудительная загрузка данных с Яндекс.Диска (с заменой локальных)"""
        if not self.has_yandex:
            return False, "Яндекс.Диск не настроен", None

        try:
            self.log_info(f"🔄 Принудительная загрузка с Яндекс.Диска...")

            # Загружаем данные с Яндекс.Диска
            yandex_data = self.yandex_storage.load()

            if not yandex_data:
                return False, "Не удалось загрузить данные с Яндекс.Диска", None

            # Сохраняем локально
            self.local_storage.save(yandex_data)

            self.log_info(f"✅ Загружено {len(yandex_data.get('cards', []))} карточек")
            return True, f"Загружено {len(yandex_data.get('cards', []))} карточек с Яндекс.Диска", yandex_data

        except Exception as e:
            self.log_error(f"❌ Ошибка загрузки с Яндекс.Диска: {e}")
            return False, f"Ошибка: {str(e)}", None
