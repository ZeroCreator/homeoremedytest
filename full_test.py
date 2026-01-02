import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from storage.hybrid_storage import HybridStorage
from storage.yandex_disk import YandexDiskStorage
from config import Config

# Загружаем конфигурацию
load_dotenv()
Config.print_config()

print("🧪 Полное тестирование системы Яндекс.Диск с гибридным хранилищем")
print("=" * 60)

token = Config.YANDEX_DISK_TOKEN
if not token:
    print("❌ Токен не найден в конфигурации")
    print("   Убедитесь, что YANDEX_DISK_TOKEN установлен в .env файле")
    exit(1)

# Создаем тестовый путь для файла на Яндекс.Диске
yandex_path = Config.YANDEX_DISK_PATH
if yandex_path:
    # Создаем тестовый путь из оригинального
    path_obj = Path(yandex_path)
    test_path = str(path_obj.with_name(f"test_{path_obj.name}"))
else:
    test_path = "test_cards.json"

print(f"📁 Основной путь на Яндекс.Диске: {yandex_path}")
print(f"📁 Тестовый путь на Яндекс.Диске: {test_path}")

# 1. Проверка подключения через REST API
print("\n1. 🔌 Проверка подключения через REST API...")
response = requests.get('https://cloud-api.yandex.net/v1/disk',
                        headers={'Authorization': f'OAuth {token}'},
                        timeout=10)

if response.status_code == 200:
    print("✅ REST API: OK")
    data = response.json()
    user_name = data.get('user', {}).get('display_name', 'Неизвестно')
    used_gb = data.get('used_space', 0) / (1024 ** 3)
    total_gb = data.get('total_space', 0) / (1024 ** 3)
    print(f"   👤 Пользователь: {user_name}")
    print(f"   💾 Используется: {used_gb:.1f} ГБ из {total_gb:.1f} ГБ")
else:
    print(f"❌ REST API: Ошибка {response.status_code}")
    if response.status_code == 401:
        print("   Недействительный токен")
    elif response.status_code == 403:
        print("   Нет прав доступа")

# 2. Тестирование YandexDiskStorage
print(f"\n2. 📊 Тестирование YandexDiskStorage...")
yandex_storage = YandexDiskStorage(
    oauth_token=token,
    filename=test_path
)

# Тест подключения
print("\n2.1. 🔌 Тест подключения YandexDiskStorage...")
if yandex_storage.test_connection():
    print("✅ Подключение успешно")
else:
    print("❌ Подключение не удалось")

# Проверка существования файла
print(f"\n2.2. 🔍 Проверка существования тестового файла '{test_path}'...")
if yandex_storage.file_exists():
    print(f"✅ Тестовый файл существует")
else:
    print(f"⚠️ Тестовый файл не найден (ожидаемо для нового теста)")

# 3. Тестирование HybridStorage
print(f"\n3. 🚀 Тестирование HybridStorage...")

# Создаем временный локальный файл для теста
temp_local_path = Path('/tmp/test_cards_temp.json')
print(f"   Локальный тестовый файл: {temp_local_path}")

# Инициализируем HybridStorage в режиме Яндекс.Диск
hybrid_storage = HybridStorage(
    mode='yandex',
    local_path=temp_local_path,
    yandex_token=token,
    yandex_path=test_path
)

# 4. Тест сохранения данных
print("\n4. 💾 Тест сохранения данных на Яндекс.Диск...")
test_data = {
    "cards": [
        {
            "id": 999,
            "theme": "Тестовая тема",
            "question": "Это тестовый вопрос?",
            "answer": "Да, это тестовый ответ",
            "explanation": "Это объяснение для тестовой карточки",
            "difficulty": "easy",
            "version": "test",
            "hidden": False
        }
    ],
    "themes": ["Тестовая тема", "Другая тема"],
    "next_id": 1000
}

try:
    # Сохраняем через HybridStorage
    save_results = hybrid_storage.save(test_data)
    print(f"✅ Результаты сохранения:")
    print(f"   Локально: {'Успешно' if save_results.get('local') else 'Ошибка'}")
    print(f"   Яндекс.Диск: {'Успешно' if save_results.get('yandex') else 'Ошибка'}")

    if save_results.get('yandex'):
        print(f"   🎉 Данные успешно сохранены на Яндекс.Диск!")
    else:
        print(f"   ❌ Не удалось сохранить данные на Яндекс.Диск")

except Exception as e:
    print(f"❌ Ошибка при сохранении: {e}")

# 5. Тест загрузки данных
print("\n5. 📥 Тест загрузки данных с Яндекс.Диска...")
try:
    loaded_data = hybrid_storage.load()
    if loaded_data and 'cards' in loaded_data:
        print(f"✅ Данные успешно загружены")
        print(f"   Карточек загружено: {len(loaded_data.get('cards', []))}")

        # Проверяем, что загруженные данные совпадают с сохраненными
        if loaded_data.get('cards'):
            test_card = loaded_data['cards'][0]
            if test_card.get('id') == 999 and test_card.get('theme') == 'Тестовая тема':
                print(f"   ✅ Тестовая карточка найдена и корректна")
            else:
                print(f"   ⚠️ Тестовая карточка не найдена или повреждена")
    else:
        print(f"❌ Не удалось загрузить данные или данные пусты")

except Exception as e:
    print(f"❌ Ошибка при загрузке: {e}")

# 6. Тест статуса хранилища
print("\n6. 📊 Тест статуса хранилища...")
try:
    status = hybrid_storage.get_status()
    print(f"✅ Статус получен:")
    print(f"   Режим: {status.get('mode')}")
    print(f"   Локальный файл существует: {status.get('local_exists')}")
    print(f"   Настроен Яндекс.Диск: {status.get('has_yandex')}")
    print(f"   Карточек в локальном хранилище: {status.get('card_count')}")

    if status.get('has_yandex'):
        print(f"   Подключение к Яндекс.Диску: {status.get('yandex_connected', 'Не проверено')}")

except Exception as e:
    print(f"❌ Ошибка получения статуса: {e}")

# 7. Очистка тестовых данных
print("\n7. 🧹 Очистка тестовых данных...")

# Удаляем тестовый файл с Яндекс.Диска через REST API
print(f"7.1. Удаление тестового файла '{test_path}' с Яндекс.Диска...")
try:
    response = requests.delete(
        f'https://cloud-api.yandex.net/v1/disk/resources',
        headers={'Authorization': f'OAuth {token}'},
        params={'path': f'/{test_path}', 'permanently': 'true'},
        timeout=10
    )

    if response.status_code in [200, 202, 204]:
        print(f"✅ Тестовый файл удален с Яндекс.Диска")
    elif response.status_code == 404:
        print(f"⚠️ Тестовый файл не найден на Яндекс.Диске (возможно, не был создан)")
    else:
        print(f"❌ Ошибка удаления: {response.status_code} - {response.text[:100]}")

except Exception as e:
    print(f"❌ Ошибка при удалении файла: {e}")

# Удаляем временный локальный файл
print(f"\n7.2. Удаление локального тестового файла...")
try:
    if temp_local_path.exists():
        temp_local_path.unlink()
        print(f"✅ Локальный тестовый файл удален")
    else:
        print(f"⚠️ Локальный тестовый файл не существует")
except Exception as e:
    print(f"❌ Ошибка удаления локального файла: {e}")

# 8. Тестирование всех режимов HybridStorage
print("\n8. 🎛️ Тестирование всех режимов HybridStorage...")

test_modes = ['local', 'yandex', 'hybrid']
test_data_small = {"cards": [], "themes": [], "next_id": 1}

for mode in test_modes:
    print(f"\n   Режим: {mode}")

    # Пропускаем режим yandex если нет токена
    if mode in ['yandex', 'hybrid'] and not token:
        print(f"   ⚠️ Пропущен (требуется токен Яндекс.Диска)")
        continue

    try:
        # Создаем хранилище в текущем режиме
        test_storage = HybridStorage(
            mode=mode,
            local_path=Path(f'/tmp/test_{mode}.json'),
            yandex_token=token if mode in ['yandex', 'hybrid'] else None,
            yandex_path=f'test_{mode}.json'
        )

        # Тест сохранения
        save_ok = test_storage.save(test_data_small)['local']

        # Тест загрузки
        loaded = test_storage.load()

        print(f"   ✅ Сохранение: {'OK' if save_ok else 'FAIL'}")
        print(f"   ✅ Загрузка: {'OK' if loaded else 'FAIL'}")

        # Очистка
        if Path(f'/tmp/test_{mode}.json').exists():
            Path(f'/tmp/test_{mode}.json').unlink()

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

# 9. Проверка конфигурации
print(f"\n9. ⚙️ Проверка конфигурации приложения...")
print(f"   Текущий режим хранения: {Config.STORAGE_MODE}")
print(f"   Путь к локальному файлу: {Config.JSON_FILE}")
print(f"   Путь на Яндекс.Диске: {Config.YANDEX_DISK_PATH}")
print(f"   Токен Яндекс.Диска: {'установлен' if Config.YANDEX_DISK_TOKEN else 'не установлен'}")

# Проверяем существование локального файла
if Config.JSON_FILE.exists():
    size = Config.JSON_FILE.stat().st_size
    print(f"   📁 Локальный файл существует: {size} байт ({size / 1024:.1f} KB)")

    # Загружаем данные для проверки
    try:
        with open(Config.JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            cards_count = len(data.get('cards', []))
            print(f"   🃏 Карточек в локальном файле: {cards_count}")
    except:
        print(f"   ⚠️ Не удалось прочитать локальный файл")
else:
    print(f"   ⚠️ Локальный файл не существует")

print("\n" + "=" * 60)
print("🎉 Тестирование завершено!")
print("=" * 60)

# Рекомендации
print("\n📋 Рекомендации по настройке:")
print("1. Для локальной разработки используйте режим 'local'")
print("2. Для продакшена с синхронизацией используйте режим 'hybrid'")
print("3. Убедитесь, что YANDEX_DISK_TOKEN указан в .env файле")
print("4. Проверьте, что YANDEX_DISK_PATH указывает на нужную папку на Яндекс.Диске")

if Config.YANDEX_DISK_TOKEN:
    print(f"\n✅ Система готова к работе с Яндекс.Диском!")
    print(f"   Токен: {'валиден' if yandex_storage.test_connection() else 'невалиден'}")
else:
    print(f"\n⚠️ Яндекс.Диск не настроен. Используется только локальное хранилище.")
