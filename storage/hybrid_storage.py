import os
from enum import Enum
from pathlib import Path


class StorageMode(Enum):
    """Режимы хранения данных"""
    LOCAL = "local"  # Только локальный файл
    YANDEX_DISK = "yandex"  # Только Яндекс.Диск
    HYBRID = "hybrid"  # Гибридный режим


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

    def load(self):
        """Загрузка данных с приоритетом"""
        print(f"Загрузка данных в режиме: {self.mode}")
        print(f"Локальный файл: {self.local_path}")
        print(f"Путь на Яндекс.Диске: {self.yandex_path}")

        # Локальный режим
        if self.mode == 'local':
            return self.local_storage.load()

        # Режим Яндекс.Диск
        elif self.mode == 'yandex':
            if not self.has_yandex:
                print("Внимание: режим Яндекс.Диск выбран, но токен не указан")
                return self.local_storage.load()

            data = self.yandex_storage.load()
            # Сохраняем локальную копию как кэш
            if data:
                self.local_storage.save(data)
            return data

        # Гибридный режим (рекомендуется)
        elif self.mode == 'hybrid':
            if not self.has_yandex:
                print("Внимание: гибридный режим без Яндекс.Диска, используем локальный")
                return self.local_storage.load()

            try:
                # Пробуем загрузить с Яндекс.Диска
                data = self.yandex_storage.load()
                # Обновляем локальную копию
                if data:
                    self.local_storage.save(data)
                return data
            except Exception as e:
                print(f"Не удалось загрузить с Яндекс.Диска: {e}, используем локальную копию")
                return self.local_storage.load()

        # По умолчанию локальный
        else:
            return self.local_storage.load()

    def save(self, data):
        """Сохранение данных во все активные хранилища"""
        print(f"Сохранение данных в режиме: {self.mode}")
        results = {}

        # Всегда сохраняем локально
        results['local'] = self.local_storage.save(data)

        # Сохраняем на Яндекс.Диск если настроено
        if self.has_yandex and self.mode in ['yandex', 'hybrid']:
            try:
                results['yandex'] = self.yandex_storage.save(data)
                if not results['yandex']:
                    print("Внимание: не удалось сохранить на Яндекс.Диск")
            except Exception as e:
                print(f"Ошибка при сохранении на Яндекс.Диск: {e}")
                results['yandex'] = False
        else:
            results['yandex'] = None

        return results

    def get_status(self):
        """Получить статус хранилищ"""
        status = {
            'mode': self.mode,
            'local_exists': self.local_path.exists(),
            'has_yandex': self.has_yandex,
            'local_path': str(self.local_path),
            'yandex_path': self.yandex_path
        }

        if self.has_yandex:
            status['yandex_connected'] = self.yandex_storage.test_connection()

        # Подсчет карточек
        try:
            data = self.local_storage.load()
            status['card_count'] = len(data.get('cards', []))
            status['themes'] = data.get('themes', [])
        except:
            status['card_count'] = 0
            status['themes'] = []

        return status
