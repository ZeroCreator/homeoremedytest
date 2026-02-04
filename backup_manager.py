import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import os
from dataclasses import dataclass


@dataclass
class BackupInfo:
    filename: str
    path: Path
    created_at: datetime
    card_count: int
    file_size: int
    source: str = 'local'  # 'local' или 'yandex'
    description: str = ""  # Добавлено поле для описания

    def __post_init__(self):
        """Инициализация после создания объекта"""
        # Убедимся, что created_at - это datetime объект
        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at)
            except:
                self.created_at = datetime.now()

        # Удаляем информацию о часовом поясе для сравнения
        if hasattr(self.created_at, 'tzinfo') and self.created_at.tzinfo is not None:
            self.created_at = self.created_at.replace(tzinfo=None)


class BackupManager:
    """Менеджер для работы с бэкапами"""

    def __init__(self, base_backup_dir: Path, storage, yandex_backup_path=None, max_backups=50):
        """
        Args:
            base_backup_dir: Базовая директория для бэкапов
            storage: Гибридное хранилище
            yandex_backup_path: путь для бэкапов на Яндекс.Диске
            max_backups: максимальное количество хранимых бэкапов (0 = без ограничений)
        """
        from config import IS_VERCEL

        self.base_backup_dir = base_backup_dir
        self.storage = storage
        self.is_vercel = IS_VERCEL
        self.yandex_backup_path = yandex_backup_path or 'backups'
        self.max_backups = max_backups

        # Проверяем, не является ли это рестартом в режиме отладки
        self.is_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

        # Кеш списка бэкапов
        self._backups_cache = None
        self._backups_cache_time = None
        self._cache_ttl = 300  # 5 минут

        # Создаем директорию для бэкапов
        if not self.is_vercel:
            try:
                self.base_backup_dir.mkdir(parents=True, exist_ok=True)
                self.log_info(f"✅ Директория для бэкапов: {self.base_backup_dir}")
            except Exception as e:
                self.log_error(f"❌ Ошибка создания директории бэкапов: {e}")

    def log_info(self, message):
        """Логирование информационных сообщений с учетом режима рестарта"""
        if not self.is_reloader:
            print(message)

    def log_error(self, message):
        """Логирование ошибок (всегда выводится)"""
        print(f"❌ {message}")

    def create_backup(self, description: str = "", backup_target: str = 'both') -> Tuple[bool, str]:
        """
        Создание бэкапа текущих данных

        Args:
            description: описание бэкапа
            backup_target: куда сохранять ('local', 'yandex', 'both')

        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Загружаем текущие данные через хранилище
            data = self.storage.load()
            if not data or 'cards' not in data:
                return False, "Нет данных для бэкапа"

            # Создаем имя файла с временной меткой
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if description:
                safe_desc = description.replace(' ', '_').replace('/', '_')
                filename = f"backup_{timestamp}_{safe_desc}.json"
            else:
                filename = f"backup_{timestamp}.json"

            results = []

            # Добавляем метаданные в бэкап
            backup_data = {
                **data,
                "_backup_info": {
                    "created_at": datetime.now().isoformat(),
                    "description": description,
                    "created_by": "HomeoRemedyTest",
                    "backup_target": backup_target
                }
            }

            # Сохраняем локально
            local_success = False
            if backup_target in ['local', 'both'] and not self.is_vercel:
                local_success = self._save_local_backup(filename, backup_data)
                if local_success:
                    results.append("локально")
                    # Очищаем старые бэкапы, если превышен лимит
                    if self.max_backups > 0:
                        self._cleanup_old_backups(source='local')
                else:
                    results.append("локально: ошибка")

            # Сохраняем на Яндекс.Диск
            yandex_success = False
            if backup_target in ['yandex', 'both'] and self.storage.has_yandex:
                yandex_success = self._save_yandex_backup(filename, backup_data)
                if yandex_success:
                    results.append("Яндекс.Диск")
                    # Очищаем старые бэкапы, если превышен лимит
                    if self.max_backups > 0:
                        self._cleanup_old_backups(source='yandex')
                else:
                    results.append("Яндекс.Диск: ошибка")

            # Формируем сообщение
            if backup_target == 'both':
                if local_success and yandex_success:
                    message = f"Бэкап создан локально и на Яндекс.Диске ({filename})"
                elif local_success:
                    message = f"Бэкап создан локально, ошибка Яндекс.Диска ({filename})"
                elif yandex_success:
                    message = f"Бэкап создан на Яндекс.Диске, ошибка локального сохранения ({filename})"
                else:
                    message = f"Ошибка создания бэкапа"
            elif backup_target == 'local':
                if local_success:
                    message = f"Бэкап создан локально ({filename})"
                else:
                    message = f"Ошибка локального создания бэкапа"
            elif backup_target == 'yandex':
                if yandex_success:
                    message = f"Бэкап создан на Яндекс.Диске ({filename})"
                else:
                    message = f"Ошибка создания бэкапа на Яндекс.Диске"
            else:
                message = f"Неизвестная цель бэкапа"

            # Очищаем кеш, так как добавили новый бэкап
            self._backups_cache = None
            self._backups_cache_time = None

            return (local_success or yandex_success), message

        except Exception as e:
            return False, f"Ошибка создания бэкапа: {str(e)}"

    def _cleanup_old_backups(self, source: str = 'local'):
        """Очистка старых бэкапов при превышении лимита"""
        try:
            backups = self.list_backups(force_refresh=True)

            # Фильтруем бэкапы по источнику
            source_backups = [b for b in backups if b.source == source]

            # Сортируем по дате (самые старые первыми)
            source_backups.sort(key=lambda x: x.created_at)

            # Удаляем лишние
            while len(source_backups) > self.max_backups:
                oldest = source_backups.pop(0)
                self.log_info(f"🚮 Удаление старого бэкапа ({source}): {oldest.filename}")
                self.delete_backup(oldest.filename, from_yandex=(source == 'yandex'))

        except Exception as e:
            self.log_error(f"Ошибка очистки старых бэкапов ({source}): {e}")

    def _save_local_backup(self, filename: str, data: dict) -> bool:
        """Сохранение локального бэкапа"""
        try:
            backup_path = self.base_backup_dir / filename
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.log_error(f"Ошибка локального сохранения бэкапа: {e}")
            return False

    def _save_yandex_backup(self, filename: str, data: dict) -> bool:
        """Сохранение бэкапа на Яндекс.Диск"""
        try:
            if not self.storage.has_yandex:
                return False

            # Создаем папку для бэкапов на Яндекс.Диске
            if not self._create_yandex_folder(self.yandex_backup_path):
                self.log_error(f"Не удалось создать папку {self.yandex_backup_path} на Яндекс.Диске")
                return False

            # Сохраняем файл
            yandex_path = f"{self.yandex_backup_path}/{filename}"
            return self._upload_to_yandex_disk(yandex_path, data)

        except Exception as e:
            self.log_error(f"Ошибка сохранения бэкапа на Яндекс.Диск: {e}")
            return False

    def _create_yandex_folder(self, folder_name: str) -> bool:
        """Создание папки на Яндекс.Диске"""
        try:
            import requests

            headers = {
                'Authorization': f'OAuth {self.storage.yandex_storage.oauth_token}',
                'Accept': 'application/json'
            }

            response = requests.put(
                f"{self.storage.yandex_storage.base_url}/resources",
                headers=headers,
                params={'path': f'/{folder_name}'},
                timeout=10
            )

            # 201 - создана, 409 - уже существует (это нормально)
            if response.status_code in [201, 409]:
                return True
            else:
                self.log_error(f"Ошибка создания папки {folder_name}: {response.status_code}")
                return False

        except Exception as e:
            self.log_error(f"Ошибка при создании папки на Яндекс.Диске: {e}")
            return False

    def _upload_to_yandex_disk(self, path: str, data: dict) -> bool:
        """Загрузка файла на Яндекс.Диск"""
        try:
            import requests
            import json

            headers = {
                'Authorization': f'OAuth {self.storage.yandex_storage.oauth_token}',
                'Accept': 'application/json'
            }

            # Получаем ссылку для загрузки
            response = requests.get(
                f"{self.storage.yandex_storage.base_url}/resources/upload",
                headers=headers,
                params={'path': f'/{path}', 'overwrite': 'true'},
                timeout=10
            )

            if response.status_code != 200:
                self.log_error(f"Ошибка получения ссылки для загрузки {path}: {response.status_code}")
                return False

            upload_url = response.json().get('href')
            if not upload_url:
                self.log_error(f"Не удалось получить ссылку для загрузки {path}")
                return False

            # Конвертируем данные в JSON
            json_data = json.dumps(data, ensure_ascii=False, indent=2)

            # Загружаем файл
            upload_response = requests.put(
                upload_url,
                data=json_data.encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if upload_response.status_code in [200, 201, 202]:
                self.log_info(f"Успешно сохранено на Яндекс.Диск: {path}")
                return True
            else:
                self.log_error(f"Ошибка загрузки на Яндекс.Диск {path}: {upload_response.status_code}")
                return False

        except Exception as e:
            self.log_error(f"Ошибка сохранения на Яндекс.Диск: {e}")
            return False

    def list_backups(self, force_refresh=False) -> List[BackupInfo]:
        """Получение списка доступных бэкапов (с кешированием)"""
        # Проверяем кеш
        current_time = time.time()
        if (not force_refresh and
                self._backups_cache is not None and
                self._backups_cache_time is not None and
                (current_time - self._backups_cache_time) < self._cache_ttl):
            return self._backups_cache

        backups = []
        try:
            self.log_info(f"🔍 Загрузка списка бэкапов...")

            # Локальные бэкапы
            if not self.is_vercel and self.base_backup_dir.exists():
                local_files = list(self.base_backup_dir.glob("backup_*.json"))
                self.log_info(f"📁 Найдено {len(local_files)} локальных файлов")

                for filepath in local_files:
                    backup_info = self._get_backup_info(filepath, source='local')
                    if backup_info:
                        backups.append(backup_info)

            # Бэкапы на Яндекс.Диске
            if self.storage.has_yandex:
                yandex_backups = self._list_yandex_backups()
                self.log_info(f"☁️ Найдено {len(yandex_backups)} бэкапов на Яндекс.Диске")
                backups.extend(yandex_backups)

            # Сортируем по дате (новые сначала)
            if backups:
                try:
                    backups.sort(key=lambda x: x.created_at, reverse=True)
                    self.log_info(f"📊 Всего бэкапов: {len(backups)}")
                except Exception as e:
                    self.log_error(f"⚠️ Ошибка сортировки бэкапов: {e}")

            # Сохраняем в кеш
            self._backups_cache = backups
            self._backups_cache_time = current_time

        except Exception as e:
            self.log_error(f"❌ Ошибка получения списка бэкапов: {e}")

        return backups

    def _get_backup_info(self, filepath: Path, source: str) -> Optional[BackupInfo]:
        """Получение информации о локальном бэкапе"""
        try:
            filename = filepath.name

            # Извлекаем дату из имени файла
            date_str = filename.replace('backup_', '').replace('.json', '')

            # Парсим дату - исправленная логика
            try:
                # Пробуем извлечь временную метку (первые 15 симвов формата YYYYMMDD_HHMMSS)
                if '_' in date_str:
                    # Разделяем по знакам подчеркивания
                    parts = date_str.split('_')
                    if len(parts) >= 2:
                        date_part = parts[0] + '_' + parts[1]
                        try:
                            # Формат: YYYYMMDD_HHMMSS
                            if len(date_part) == 15 and '_' in date_part:
                                created_at = datetime.strptime(date_part, '%Y%m%d_%H%M%S')
                            else:
                                created_at = datetime.fromtimestamp(filepath.stat().st_ctime)
                        except:
                            created_at = datetime.fromtimestamp(filepath.stat().st_ctime)
                    else:
                        created_at = datetime.fromtimestamp(filepath.stat().st_ctime)
                else:
                    created_at = datetime.fromtimestamp(filepath.stat().st_ctime)
            except:
                created_at = datetime.fromtimestamp(filepath.stat().st_ctime)

            # Читаем файл для подсчета карточек
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                card_count = len(data.get('cards', []))

            # ДОБАВЛЕНО: Получаем описание из метаданных
            description = ""
            if '_backup_info' in data and 'description' in data['_backup_info']:
                description = data['_backup_info'].get('description', '')

            return BackupInfo(
                filename=filename,
                path=filepath,
                created_at=created_at,
                card_count=card_count,
                file_size=filepath.stat().st_size,
                source=source,
                description=description  # Добавляем описание
            )

        except Exception as e:
            self.log_error(f"Ошибка чтения бэкапа {filepath}: {e}")
            return None

    def _list_yandex_backups(self) -> List[BackupInfo]:
        """Получение списка бэкапов с Яндекс.Диска"""
        backups = []

        try:
            if not self.storage.has_yandex or not self.storage.yandex_storage:
                return backups

            self.log_info(f"🔍 Поиск бэкапов на Яндекс.Диске в папке: {self.yandex_backup_path}")

            # Используем метод из yandex_storage для получения списка файлов
            import requests

            headers = {
                'Authorization': f'OAuth {self.storage.yandex_storage.oauth_token}',
                'Accept': 'application/json'
            }

            # Проверяем, существует ли папка с бэкапами
            response = requests.get(
                f"{self.storage.yandex_storage.base_url}/resources",
                headers=headers,
                params={'path': f'/{self.yandex_backup_path}'},
                timeout=30
            )

            if response.status_code == 404:
                self.log_info(f"📁 Папка {self.yandex_backup_path} не существует на Яндекс.Диске")
                return backups

            if response.status_code != 200:
                self.log_error(f"❌ Ошибка получения списка бэкапов с Яндекс.Диска: {response.status_code}")
                return backups

            items = response.json().get('_embedded', {}).get('items', [])
            self.log_info(f"📊 Найдено {len(items)} файлов в папке {self.yandex_backup_path}")

            for item in items:
                filename = item.get('name', '')
                if filename.startswith('backup_') and filename.endswith('.json'):
                    try:
                        self.log_info(f"🔄 Обработка бэкапа: {filename}")

                        # Получаем информацию о файле
                        created_at_str = item['modified'].replace('Z', '+00:00')
                        created_at = datetime.fromisoformat(created_at_str)
                        created_at = created_at.replace(tzinfo=None)

                        # Загружаем файл для получения информации
                        file_path = f"{self.yandex_backup_path}/{filename}"
                        data = self._download_from_yandex_disk(file_path)

                        if data:
                            card_count = len(data.get('cards', []))
                            # Получаем описание из метаданных
                            description = ""
                            if '_backup_info' in data and 'description' in data['_backup_info']:
                                description = data['_backup_info'].get('description', '')
                        else:
                            card_count = 0
                            description = ""

                        # Создаем объект BackupInfo с указанием источника
                        backup_info = BackupInfo(
                            filename=filename,
                            path=Path(f"yandex:{item['path']}"),
                            created_at=created_at,
                            card_count=card_count,
                            file_size=item.get('size', 0),
                            source='yandex',  # Важно: указываем источник
                            description=description
                        )

                        # ДОБАВЛЕНО: Проверяем, что источник правильно установлен
                        self.log_info(f"✅ Создан BackupInfo: {filename}, источник: {backup_info.source}")

                        backups.append(backup_info)

                    except Exception as e:
                        self.log_error(f"❌ Ошибка обработки бэкапа {filename}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue

            self.log_info(f"✅ Найдено {len(backups)} бэкапов на Яндекс.Диске")

        except Exception as e:
            self.log_error(f"❌ Ошибка получения бэкапов с Яндекс.Диска: {e}")
            import traceback
            traceback.print_exc()

        return backups

    def _download_from_yandex_disk(self, path: str) -> Optional[Dict]:
        """Загрузка файла с Яндекс.Диска"""
        try:
            import requests

            headers = {
                'Authorization': f'OAuth {self.storage.yandex_storage.oauth_token}',
                'Accept': 'application/json'
            }

            # Получаем ссылку для скачивания
            response = requests.get(
                f"{self.storage.yandex_storage.base_url}/resources/download",
                headers=headers,
                params={'path': f'/{path}'},
                timeout=10
            )

            if response.status_code != 200:
                self.log_error(f"Ошибка загрузки файла {path}: {response.status_code}")
                return None

            download_url = response.json().get('href')
            if not download_url:
                self.log_error(f"Не удалось получить ссылку для скачивания {path}")
                return None

            # Скачиваем файл
            file_response = requests.get(download_url, timeout=10)
            if file_response.status_code == 200:
                return json.loads(file_response.text)
            else:
                self.log_error(f"Ошибка скачивания файла {path}: {file_response.status_code}")
                return None

        except Exception as e:
            self.log_error(f"Ошибка загрузки с Яндекс.Диска: {e}")
            return None

    def restore_backup(self, backup_name: str, from_yandex: bool = False, restore_target: str = 'local') -> Tuple[
        bool, str]:
        """
        Восстановление из бэкапа

        Args:
            backup_name: имя файла бэкапа
            from_yandex: True если бэкап с Яндекс.Диска
            restore_target: куда восстанавливать ('local', 'yandex', 'both')

        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            self.log_info(f"\n🔄 Восстановление бэкапа:")
            self.log_info(f"   📂 Файл: {backup_name}")
            self.log_info(f"   📍 Источник: {'Яндекс.Диск' if from_yandex else 'локальный'}")
            self.log_info(f"   🎯 Цель: {restore_target}")

            # Загружаем данные из бэкапа
            if from_yandex:
                if not self.storage.has_yandex:
                    return False, "Яндекс.Диск не настроен"

                # Формируем путь к бэкапу на Яндекс.Диске
                yandex_path = f"{self.yandex_backup_path}/{backup_name}"
                self.log_info(f"📥 Загрузка с Яндекс.Диска: {yandex_path}")
                data = self._download_from_yandex_disk(yandex_path)
                if data is None:
                    return False, "Не удалось загрузить бэкап с Яндекс.Диска"
            else:
                backup_path = self.base_backup_dir / backup_name
                self.log_info(f"📥 Загрузка локально: {backup_path}")
                if not backup_path.exists():
                    return False, "Локальный бэкап не найден"

                with open(backup_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            if not data or 'cards' not in data:
                return False, "Неверный формат бэкапа"

            card_count = len(data.get('cards', []))
            self.log_info(f"📊 Карточек в бэкапе: {card_count}")

            # Удаляем служебную информацию о бэкапе
            if '_backup_info' in data:
                del data['_backup_info']

            # Восстанавливаем next_id если его нет
            if 'next_id' not in data:
                max_id = max((card.get('id', 0) for card in data.get('cards', [])), default=0)
                data['next_id'] = max_id + 1

            results = []

            # ВОССТАНАВЛИВАЕМ ЛОКАЛЬНО
            if restore_target in ['local', 'both']:
                self.log_info("💾 Восстановление в локальный файл данных...")

                # Путь к основному файлу данных
                local_path = self.storage.local_storage.filepath
                self.log_info(f"   📍 Путь к файлу данных: {local_path}")

                try:
                    # Сохраняем напрямую в файл
                    with open(local_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    # Проверяем сохранение
                    if local_path.exists():
                        with open(local_path, 'r', encoding='utf-8') as f:
                            saved_data = json.load(f)
                            saved_count = len(saved_data.get('cards', []))

                        if saved_count == card_count:
                            self.log_info(f"✅ Основной файл данных успешно восстановлен: {saved_count} карточек")
                            results.append(f"локально ({saved_count} карточек)")

                            # Обновляем кэш хранилища
                            self.storage.local_storage.data = data
                        else:
                            self.log_error(f"❌ Ошибка: в файле {saved_count} карточек вместо {card_count}")
                            return False, f"Ошибка: сохранено {saved_count} карточек вместо {card_count}"
                    else:
                        self.log_error("❌ Основной файл данных не создан")
                        return False, "Основной файл данных не создан"

                except Exception as e:
                    self.log_error(f"❌ Ошибка сохранения локально: {e}")
                    import traceback
                    traceback.print_exc()
                    return False, f"Ошибка сохранения в основной файл: {str(e)}"

            # ВОССТАНАВЛИВАЕМ НА ЯНДЕКС.ДИСК
            if restore_target in ['yandex', 'both'] and self.storage.has_yandex:
                self.log_info("☁️ Восстановление на Яндекс.Диск...")

                try:
                    # Сохраняем в основной файл на Яндекс.Диске
                    yandex_success = self.storage.yandex_storage.save(data)

                    if yandex_success:
                        self.log_info(f"✅ Данные восстановлены на Яндекс.Диск: {card_count} карточек")
                        results.append(f"Яндекс.Диск ({card_count} карточек)")
                    else:
                        self.log_error("❌ Не удалось сохранить на Яндекс.Диск")
                        results.append("Яндекс.Диск: ошибка")

                except Exception as e:
                    self.log_error(f"❌ Ошибка сохранения на Яндекс.Диск: {e}")
                    import traceback
                    traceback.print_exc()
                    results.append("Яндекс.Диск: ошибка")

            if results:
                message = f"Данные восстановлены в: {', '.join(results)}"
                self.log_info(f"✅ {message}")

                # Очищаем кеш бэкапов после восстановления
                self._backups_cache = None
                self._backups_cache_time = None

                return True, message
            else:
                return False, "Не удалось восстановить данные ни в одно хранилище"

        except Exception as e:
            self.log_error(f"❌ Ошибка восстановления: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Ошибка восстановления: {str(e)}"

    def delete_backup(self, backup_name: str, from_yandex: bool = False) -> Tuple[bool, str]:
        """Удаление бэкапа"""
        try:
            if from_yandex:
                # Удаляем с Яндекс.Диска
                if not self.storage.has_yandex:
                    return False, "Яндекс.Диск не настроен"

                import requests

                headers = {
                    'Authorization': f'OAuth {self.storage.yandex_storage.oauth_token}',
                    'Accept': 'application/json'
                }

                path = f"{self.yandex_backup_path}/{backup_name}"
                response = requests.delete(
                    f"{self.storage.yandex_storage.base_url}/resources",
                    headers=headers,
                    params={'path': f'/{path}', 'permanently': 'true'},
                    timeout=10
                )

                if response.status_code in [200, 202, 204]:
                    # Очищаем кеш после удаления
                    self._backups_cache = None
                    self._backups_cache_time = None
                    return True, f"Бэкап {backup_name} удален с Яндекс.Диска"
                else:
                    return False, f"Ошибка удаления: {response.status_code}"
            else:
                # Удаляем локальный файл
                if self.is_vercel:
                    return False, "На Vercel нельзя удалять локальные файлы"

                backup_path = self.base_backup_dir / backup_name
                if backup_path.exists():
                    backup_path.unlink()
                    # Очищаем кеш после удаления
                    self._backups_cache = None
                    self._backups_cache_time = None
                    return True, f"Локальный бэкап {backup_name} удален"
                else:
                    return False, "Бэкап не найден"

        except Exception as e:
            return False, f"Ошибка удаления: {str(e)}"
