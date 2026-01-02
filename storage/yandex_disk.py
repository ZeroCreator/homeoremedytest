import json
import requests
from pathlib import Path
import time


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
        self.base_url = "https://cloud-api.yandex.net/v1/disk"
        self.headers = {
            'Authorization': f'OAuth {oauth_token}',
            'Accept': 'application/json'
        }
        print(f"Инициализировано хранилище Яндекс.Диск для файла: {filename}")

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
            print(f"⚠️ Таймаут запроса {method} {url}")
            return None
        except Exception as e:
            print(f"⚠️ Ошибка запроса {method} {url}: {type(e).__name__}")
            return None

    def file_exists(self):
        """Проверяет, существует ли файл на Яндекс.Диске через REST API"""
        try:
            response = requests.get(
                f"{self.base_url}/resources",
                headers=self.headers,
                params={'path': f'/{self.filename}'},
                timeout=10
            )

            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                return False
            else:
                print(f"⚠️ Неожиданный статус при проверке файла: {response.status_code}")
                print(f"   Ответ: {response.text[:100]}")
                return False

        except Exception as e:
            print(f"⚠️ Ошибка проверки существования файла: {e}")
            return False

    def load(self):
        """Загрузка данных с Яндекс.Диска через REST API"""
        try:
            print(f"🔄 Загрузка данных с Яндекс.Диска...")

            # Получаем ссылку для скачивания через REST API
            response = requests.get(
                f"{self.base_url}/resources/download",
                headers=self.headers,
                params={'path': f'/{self.filename}'},
                timeout=10
            )

            if response.status_code == 404:
                print("📭 Файл не найден на Яндекс.Диске, создаем начальные данные")
                return {"cards": [], "themes": [], "next_id": 1}

            if response.status_code != 200:
                print(f"❌ Ошибка получения ссылки для скачивания: {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
                return {"cards": [], "themes": [], "next_id": 1}

            download_url = response.json().get('href')
            if not download_url:
                print("❌ Не удалось получить ссылку для скачивания")
                return {"cards": [], "themes": [], "next_id": 1}

            # Скачиваем файл по полученной ссылке
            file_response = requests.get(download_url, timeout=10)

            if file_response.status_code == 200:
                try:
                    data = json.loads(file_response.text)
                    print(f"✅ Успешно загружено {len(data.get('cards', []))} карточек с Яндекс.Диска")
                    return data
                except json.JSONDecodeError as e:
                    print(f"❌ Файл на Яндекс.Диске поврежден (невалидный JSON): {e}")
                    print(f"   Содержимое: {file_response.text[:200]}...")
                    return {"cards": [], "themes": [], "next_id": 1}
            else:
                print(f"❌ Ошибка скачивания файла: {file_response.status_code}")
                return {"cards": [], "themes": [], "next_id": 1}

        except Exception as e:
            print(f"❌ Критическая ошибка при загрузке: {type(e).__name__}: {e}")
            return {"cards": [], "themes": [], "next_id": 1}

    def save(self, data):
        """Сохранение данных на Яндекс.Диск через REST API"""
        try:
            print(f"🔄 Сохранение данных на Яндекс.Диск...")

            # Получаем ссылку для загрузки через REST API
            response = requests.get(
                f"{self.base_url}/resources/upload",
                headers=self.headers,
                params={
                    'path': f'/{self.filename}',
                    'overwrite': 'true'
                },
                timeout=10
            )

            if response.status_code != 200:
                print(f"❌ Ошибка получения ссылки для загрузки: {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
                return False

            upload_url = response.json().get('href')
            if not upload_url:
                print("❌ Не удалось получить ссылку для загрузки")
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
                print(f"✅ Успешно сохранено {len(data.get('cards', []))} карточек на Яндекс.Диск")
                return True
            elif file_response.status_code == 507:
                print("❌ Недостаточно места на Яндекс.Диске")
                return False
            elif file_response.status_code == 403:
                print("❌ Нет прав на запись на Яндекс.Диск")
                return False
            else:
                print(f"❌ Ошибка загрузки на Яндекс.Диск: {file_response.status_code}")
                print(f"   Ответ: {file_response.text[:200]}")
                return False

        except Exception as e:
            print(f"❌ Критическая ошибка при сохранении: {type(e).__name__}: {e}")
            return False

    def test_connection(self):
        """Тестирование подключения к Яндекс.Диску через REST API"""
        try:
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
                print("❌ Ошибка 401: Недействительный токен")
                return False
            elif response.status_code == 403:
                print("❌ Ошибка 403: Нет прав доступа")
                return False
            else:
                print(f"❌ Ошибка подключения: {response.status_code}")
                return False

        except requests.exceptions.ConnectionError:
            print("❌ Нет подключения к интернету")
            return False
        except requests.exceptions.Timeout:
            print("❌ Таймаут подключения")
            return False
        except Exception as e:
            print(f"❌ Неизвестная ошибка: {type(e).__name__}: {e}")
            return False
