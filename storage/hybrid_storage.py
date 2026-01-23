import os
import json
from datetime import datetime
from pathlib import Path
import hashlib
from enum import Enum


class StorageMode(Enum):
    """Режимы хранения данных"""
    LOCAL = "local"  # Только локальный файл
    YANDEX_DISK = "yandex"  # Только Яндекс.Диск
    HYBRID = "hybrid"  # Гибридный режим (только чтение из облака)


class HybridStorage:
    """Гибридное хранилище с приоритетом (только чтение из Яндекс.Диска)"""

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
        """Загрузка данных с приоритетом"""
        self.log_info(f"Загрузка данных в режиме: {self.mode}")
        self.log_info(f"Локальный файл: {self.local_path}")
        self.log_info(f"Путь на Яндекс.Диске: {self.yandex_path}")

        # Локальный режим
        if self.mode == 'local':
            return self.local_storage.load()

        # Режим Яндекс.Диск
        elif self.mode == 'yandex':
            if not self.has_yandex:
                self.log_error("Внимание: режим Яндекс.Диск выбран, но токен не указан")
                return self.local_storage.load()

            data = self.yandex_storage.load()
            # Сохраняем локальную копию как кэш
            if data:
                self.local_storage.save(data)
            return data

        # Гибридный режим - ТОЛЬКО ЗАГРУЗКА С ЯНДЕКС.ДИСКА (если есть и новее)
        elif self.mode == 'hybrid':
            if not self.has_yandex:
                self.log_error("Внимание: гибридный режим без Яндекс.Диска, используем локальный")
                return self.local_storage.load()

            try:
                # Сначала пытаемся загрузить локальные данные
                local_data = None
                if self.local_path.exists():
                    try:
                        local_data = self.local_storage.load()
                        self.log_info(f"✅ Локальные данные загружены: {len(local_data.get('cards', []))} карточек")
                    except Exception as e:
                        self.log_error(f"⚠️ Ошибка загрузки локальных данных: {e}")
                        local_data = None

                # Пытаемся загрузить с Яндекс.Диска
                self.log_info(f"🔄 Проверяем Яндекс.Диск на наличие обновлений...")
                yandex_data = self.yandex_storage.load()

                if yandex_data:
                    self.log_info(f"✅ Данные с Яндекс.Диска загружены: {len(yandex_data.get('cards', []))} карточек")

                    # Если локальных данных нет - сохраняем Яндекс.Диск локально
                    if not local_data:
                        self.log_info("📝 Локальных данных нет, сохраняем данные с Яндекс.Диска...")
                        self.local_storage.save(yandex_data)
                        return yandex_data

                    # Если локальные данные есть - проверяем, нужно ли обновить
                    else:
                        # Проверяем дату изменения на Яндекс.Диске
                        yandex_info = self.yandex_storage.get_file_info()
                        local_mtime = datetime.fromtimestamp(self.local_path.stat().st_mtime)

                        if yandex_info and yandex_info.get('modified') > local_mtime:
                            # Яндекс.Диск новее - обновляем локальные данные
                            self.log_info("🔄 Яндекс.Диск новее, обновляем локальные данные...")
                            self.local_storage.save(yandex_data)
                            return yandex_data
                        else:
                            # Локальные данные актуальны или новее
                            self.log_info("✅ Локальные данные актуальны")
                            return local_data
                else:
                    self.log_error("❌ Не удалось загрузить данные с Яндекс.Диска")
                    if local_data:
                        self.log_info("📝 Используем локальные данные")
                        return local_data
                    else:
                        raise Exception("Нет данных ни в одном источнике")

            except Exception as e:
                self.log_error(f"❌ Ошибка в гибридном режиме: {e}")
                # Пытаемся загрузить локально
                try:
                    self.log_info(f"🔄 Пробуем загрузить локально...")
                    return self.local_storage.load()
                except Exception as local_error:
                    self.log_error(f"❌ Ошибка загрузки локальных данных: {local_error}")
                    # Возвращаем пустую структуру
                    return {"cards": [], "next_id": 1}

        # По умолчанию локальный
        else:
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
