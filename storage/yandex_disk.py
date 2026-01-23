import json
import requests
from pathlib import Path
import time
import os


class YandexDiskStorage:
    """Хранилище на Яндекс.Диске через REST API (работает!)"""

    def __init__(self, oauth_token, filename="test_cards.json"):
        """
        Инициализация хранилища Яндекс.Диск

        Args:
            oauth_token: OAuth токен Яндекс ID
            filename: имя файла на Яндекс.Диске (в корне)
        """
        self.oauth_token = oauth_token
        self.filename = filename
        self.file_path = f'/{filename}'  # Полный путь для API запросов
        self.base_url = "https://cloud-api.yandex.net/v1/disk"
        self.headers = {
            'Authorization': f'OAuth {oauth_token}',
            'Accept': 'application/json'
        }

        # Проверяем, не является ли это рестартом в режиме отладки
        self.is_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

        # Выводим сообщение только если это не рестарт
        if not self.is_reloader:
            print(f"Инициализировано хранилище Яндекс.Диск для файла: {filename}")

    def log_info(self, message):
        """Логирование информационных сообщений с учетом режима рестарта"""
        if not self.is_reloader:
            print(message)

    def log_error(self, message):
        """Логирование ошибок (всегда выводится)"""
        print(f"❌ {message}")

    def log_warning(self, message):
        """Логирование предупреждений (всегда выводится)"""
        print(f"⚠️ {message}")

    def _make_request(self, method, url, **kwargs):
        """Универсальный метод для запросов с обработкой ошибок"""
        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                timeout=10,
                **kwargs
            )
            return response
        except requests.exceptions.Timeout:
            self.log_error(f"Таймаут запроса {method} {url}")
            return None
        except Exception as e:
            self.log_error(f"Ошибка запроса {method} {url}: {type(e).__name__}")
            return None

    def file_exists(self):
        """Проверяет, существует ли файл на Яндекс.Диске через REST API"""
        try:
            response = requests.get(
                f"{self.base_url}/resources",
                headers=self.headers,
                params={'path': self.file_path},
                timeout=10
            )

            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                return False
            else:
                self.log_warning(f"Неожиданный статус при проверке файла: {response.status_code}")
                self.log_warning(f"   Ответ: {response.text[:100]}")
                return False

        except Exception as e:
            self.log_error(f"Ошибка проверки существования файла: {e}")
            return False

    def load(self):
        """Загрузка данных с Яндекс.Диска через REST API"""
        try:
            self.log_info(f"🔄 Загрузка данных с Яндекс.Диска...")

            # Получаем ссылку для скачивания через REST API
            response = requests.get(
                f"{self.base_url}/resources/download",
                headers=self.headers,
                params={'path': self.file_path},
                timeout=10
            )

            # ИЗМЕНЕНИЕ: При 404 возвращаем None, а не пустую структуру
            if response.status_code == 404:
                self.log_info("📭 Файл не найден на Яндекс.Диске")
                return None  # Важно: возвращаем None для обозначения "файла нет"

            if response.status_code != 200:
                self.log_error(f"Ошибка получения ссылки для скачивания: {response.status_code}")
                self.log_error(f"   Ответ: {response.text[:200]}")
                return None  # Возвращаем None при других ошибках

            download_url = response.json().get('href')
            if not download_url:
                self.log_error("Не удалось получить ссылку для скачивания")
                return None

            # Скачиваем файл по полученной ссылке
            file_response = requests.get(download_url, timeout=10)

            if file_response.status_code == 200:
                try:
                    data = json.loads(file_response.text)
                    self.log_info(f"✅ Успешно загружено {len(data.get('cards', []))} карточек с Яндекс.Диска")
                    return data
                except json.JSONDecodeError as e:
                    self.log_error(f"Файл на Яндекс.Диске поврежден (невалидный JSON): {e}")
                    self.log_error(f"   Содержимое: {file_response.text[:200]}...")
                    return None  # Возвращаем None при поврежденном файле
            else:
                self.log_error(f"Ошибка скачивания файла: {file_response.status_code}")
                return None

        except Exception as e:
            self.log_error(f"Критическая ошибка при загрузке: {type(e).__name__}: {e}")
            return None  # Возвращаем None при любых исключениях

    def save(self, data, custom_path=None):
        """Сохранение данных на Яндекс.Диск через REST API"""
        try:
            self.log_info(f"🔄 Сохранение данных на Яндекс.Диск...")

            # Используем custom_path если указан, иначе стандартный filename
            path_to_save = custom_path if custom_path else self.file_path

            # Получаем ссылку для загрузки через REST API
            response = requests.get(
                f"{self.base_url}/resources/upload",
                headers=self.headers,
                params={
                    'path': path_to_save,
                    'overwrite': 'true'
                },
                timeout=10
            )

            if response.status_code != 200:
                self.log_error(f"Ошибка получения ссылки для загрузки: {response.status_code}")
                self.log_error(f"   Ответ: {response.text[:200]}")
                return False

            upload_url = response.json().get('href')
            if not upload_url:
                self.log_error("Не удалось получить ссылку для загрузки")
                return False

            # Конвертируем данные в JSON
            json_data = json.dumps(data, ensure_ascii=False, indent=2)

            # Загружаем файл по полученной ссылке
            file_response = requests.put(
                upload_url,
                data=json_data.encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if file_response.status_code in [200, 201, 202]:
                self.log_info(f"✅ Успешно сохранено {len(data.get('cards', []))} карточек на Яндекс.Диск")
                return True
            elif file_response.status_code == 507:
                self.log_error("Недостаточно места на Яндекс.Диске")
                return False
            elif file_response.status_code == 403:
                self.log_error("Нет прав на запись на Яндекс.Диск")
                return False
            else:
                self.log_error(f"Ошибка загрузки на Яндекс.Диск: {file_response.status_code}")
                self.log_error(f"   Ответ: {file_response.text[:200]}")
                return False

        except Exception as e:
            self.log_error(f"Критическая ошибка при сохранении: {type(e).__name__}: {e}")
            return False

    def test_connection(self):
        """Тестирование подключения к Яндекс.Диску через REST API"""
        try:
            if not self.is_reloader:
                print("🔍 Тестируем подключение к Яндекс.Диску (REST API)...")
                print(f"   Путь к файлу: {self.filename}")

            # Простой запрос к REST API
            response = requests.get(
                f"{self.base_url}/",
                headers=self.headers,
                timeout=5
            )

            if response.status_code == 200:
                user_info = response.json()

                if not self.is_reloader:
                    user_name = user_info.get('user', {}).get('display_name', 'Неизвестно')
                    used_gb = user_info.get('used_space', 0) / (1024 ** 3)
                    total_gb = user_info.get('total_space', 0) / (1024 ** 3)

                    print("✅ REST API подключение успешно")
                    print(f"   👤 Пользователь: {user_name}")
                    print(f"   💾 Используется: {used_gb:.2f} ГБ из {total_gb:.2f} ГБ")
                    print(f"   📁 Файл данных: {self.filename}")

                    # Проверяем существование файла
                    if self.file_exists():
                        print("✅ Файл данных существует на Яндекс.Диске")
                    else:
                        print("⚠️ Файл данных не найден на Яндекс.Диске")

                return True
            elif response.status_code == 401:
                self.log_error("Ошибка 401: Недействительный токен")
                return False
            elif response.status_code == 403:
                self.log_error("Ошибка 403: Нет прав доступа")
                return False
            else:
                self.log_error(f"Ошибка подключения: {response.status_code}")
                return False

        except requests.exceptions.ConnectionError:
            self.log_error("Нет подключения к интернету")
            return False
        except requests.exceptions.Timeout:
            self.log_error("Таймаут подключения")
            return False
        except Exception as e:
            self.log_error(f"Неизвестная ошибка: {type(e).__name__}: {e}")
            return False

    def get_file_info(self):
        """Получить информацию о файле (размер, дата изменения)"""
        try:
            response = requests.get(
                f"{self.base_url}/resources",
                headers=self.headers,
                params={'path': self.file_path, 'fields': 'size,modified'},
                timeout=10
            )

            if response.status_code == 200:
                info = response.json()
                modified_str = info.get('modified')
                if modified_str:
                    # Конвертируем строку в datetime
                    from datetime import datetime
                    try:
                        # Формат: "2024-01-16T12:18:58+00:00"
                        modified = datetime.fromisoformat(modified_str.replace('Z', '+00:00'))
                    except:
                        modified = datetime.now()

                    return {
                        'size': info.get('size', 0),
                        'modified': modified,
                        'name': info.get('name')
                    }
            return None
        except Exception as e:
            self.log_error(f"Ошибка получения информации о файле: {e}")
            return None
