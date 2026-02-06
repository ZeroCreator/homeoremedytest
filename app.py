import sys
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
import os
import shutil
import json


# Импортируем всё из config
from config import Config, BASE_DIR, IS_VERCEL

# Используем JSON_FILE из Config
JSON_FILE = Config.JSON_FILE

# Создаем Flask приложение
app = Flask(__name__,
            static_folder=str(Config.STATIC_DIR),
            template_folder=str(Config.TEMPLATE_DIR))


app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['JSON_FILE'] = JSON_FILE
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_DIR


# Импорты остальных модулей
from excel_utils.exporter import create_exporter
from excel_utils.importer import create_importer
from backup_manager import BackupManager
from storage import HybridStorage


# Создаем гибридное хранилище
storage = HybridStorage(
    mode=Config.STORAGE_MODE,
    local_path=JSON_FILE,
    yandex_token=Config.YANDEX_DISK_TOKEN,
    yandex_path=Config.YANDEX_DISK_PATH
)


# Создаем менеджер бэкапов с использованием MAX_BACKUPS
backup_manager = BackupManager(
    base_backup_dir=Config.BACKUP_DIR,
    storage=storage,
    yandex_backup_path=Config.YANDEX_DISK_BACKUP_PATH,
    max_backups=Config.MAX_BACKUPS  # ДОБАВЛЕНО!
)


ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def allowed_file(filename):
    """Проверка расширения файла"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Копирование файлов на Vercel (после создания app)
if IS_VERCEL:
    print(f"🔍 Vercel окружение: копирование файлов...")

    # Копируем шаблоны
    templates_src = BASE_DIR / 'templates'
    if templates_src.exists():
        print(f"📁 Копирование шаблонов из {templates_src} в {Config.TEMPLATE_DIR}")
        for item in templates_src.iterdir():
            if item.is_dir():
                shutil.copytree(item, Config.TEMPLATE_DIR / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, Config.TEMPLATE_DIR / item.name)

    # Копируем данные
    data_src = BASE_DIR / 'data'
    if data_src.exists():
        print(f"📁 Копирование данных из {data_src} в {Config.DATA_DIR}")
        for item in data_src.iterdir():
            if item.is_file() and item.suffix == '.json':
                shutil.copy2(item, Config.DATA_DIR / item.name)

    # Копируем пример данных если основной файл не существует
    if not JSON_FILE.exists():
        sample_data = BASE_DIR / 'data' / 'test_cards.json'
        if sample_data.exists():
            shutil.copy2(sample_data, JSON_FILE)
            print(f"✅ Скопированы примеры данных в {JSON_FILE}")


# Автоматическое создание бэкапа при запуске (если настроено)
if Config.BACKUP_ON_START and not os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    try:
        print("🔄 Создание автоматического бэкапа при запуске...")
        success, message = backup_manager.create_backup(
            description="Автоматический бэкап при запуске",
            backup_target='both'
        )
        if success:
            print(f"✅ {message}")
        else:
            print(f"⚠️ {message}")
    except Exception as e:
        print(f"⚠️ Ошибка при создании автоматического бэкапа: {e}")


def load_cards():
    """Загрузка карточек из хранилища"""
    return storage.load()


def save_cards(data):
    """Сохранение карточек через хранилище"""
    try:
        results = storage.save(data)

        # На Vercel в гибридном режиме
        if storage.is_vercel and storage.mode == 'hybrid':
            success = results.get('yandex', False)
            if success:
                flash('✅ Данные сохранены на Яндекс.Диск', 'success')
            else:
                flash('❌ Ошибка сохранения на Яндекс.Диск на Vercel', 'error')

        # Локально в гибридном режиме
        elif storage.mode == 'hybrid':
            success = results.get('local', False)
            if success:
                if results.get('yandex', False):
                    flash('✅ Данные сохранены локально и на Яндекс.Диск', 'success')
                elif storage.has_yandex:
                    flash('⚠️ Данные сохранены локально (не удалось на Яндекс.Диск)', 'warning')
                else:
                    flash('✅ Данные сохранены локально', 'success')
            else:
                flash('❌ Ошибка сохранения данных', 'error')

        # Режим только Яндекс.Диск
        elif storage.mode == 'yandex':
            success = results.get('yandex', False)
            if success:
                flash('✅ Данные сохранены на Яндекс.Диск', 'success')
            else:
                flash('❌ Ошибка сохранения на Яндекс.Диск', 'error')

        # Режим только локальный
        else:
            success = results.get('local', False)
            if success:
                flash('✅ Данные сохранены локально', 'success')
            else:
                flash('❌ Ошибка локального сохранения', 'error')

        return success

    except Exception as e:
        flash(f'❌ Ошибка: {str(e)}', 'error')
        return False


def extract_themes(cards_data):
    """Извлечение уникальных тем (поддержка нескольких тем через запятую)"""
    themes = set()
    for card in cards_data.get('cards', []):
        if 'theme' in card and card['theme']:
            # Разделяем темы по запятым
            card_themes = [t.strip() for t in card['theme'].split(',')]
            for theme in card_themes:
                if theme:  # Проверяем, что тема не пустая
                    themes.add(theme)
    return sorted(list(themes))


def get_theme_counts(cards_data):
    """Подсчет количества карточек для каждой темы"""
    theme_counts = {}
    for card in cards_data.get('cards', []):
        if 'theme' in card and card['theme']:
            card_themes = [t.strip() for t in card['theme'].split(',')]
            for theme in card_themes:
                if theme:
                    theme_counts[theme] = theme_counts.get(theme, 0) + 1
    return theme_counts


def get_difficulty_counts(cards_data):
    """Подсчет количества карточек по сложности"""
    difficulty_counts = {'easy': 0, 'medium': 0, 'hard': 0}
    for card in cards_data.get('cards', []):
        difficulty = card.get('difficulty', 'medium')
        if difficulty in difficulty_counts:
            difficulty_counts[difficulty] += 1
    return difficulty_counts


def get_version_counts(cards_data):
    """Подсчет количества карточек по версиям"""
    version_counts = {}
    for card in cards_data.get('cards', []):
        version = card.get('version')
        if version:
            version_counts[version] = version_counts.get(version, 0) + 1
    return version_counts


def extract_versions(cards_data):
    """Извлечение уникальных версий"""
    versions = set()
    for card in cards_data.get('cards', []):
        version = card.get('version')
        if version:
            versions.add(version)
    return sorted(list(versions))


def get_template_variables(cards_data, **overrides):
    """Получение всех переменных для шаблона с возможностью переопределения"""
    base_vars = {
        'all_themes': extract_themes(cards_data),
        'theme_counts': get_theme_counts(cards_data),
        'difficulty_counts': get_difficulty_counts(cards_data),
        'version_counts': get_version_counts(cards_data),
        'all_versions': extract_versions(cards_data),
        'total_cards': len(cards_data.get('cards', [])),
        'hidden_count': sum(1 for card in cards_data.get('cards', []) if card.get('hidden', False)),
        'current_theme': '',
        'current_difficulty': '',
        'current_version': '',
        'search_query': '',
        'show_hidden': False,
        'view_mode': 'grid',
        'storage_mode': storage.mode,
        'has_yandex': storage.has_yandex,
        'show_filters': True,
        # Параметры пагинации по умолчанию (для режима сетки)
        'page': 1,
        'per_page': 20,
        'total_pages': 0,
        'start_idx': 0,
        'end_idx': 0
    }
    base_vars.update(overrides)
    return base_vars


def sync_cards_to_yandex():
    """Синхронизация локальных карточек на Яндекс.Диск"""
    if not storage.has_yandex:
        return False, "Яндекс.Диск не настроен"

    try:
        # Загружаем локальные данные
        local_data = storage.local_storage.load()

        # Сохраняем на Яндекс.Диск (полная перезапись)
        success = storage.yandex_storage.save(local_data)

        if success:
            return True, f"Синхронизировано {len(local_data.get('cards', []))} карточек на Яндекс.Диск"
        return False, "Не удалось сохранить на Яндекс.Диск"

    except Exception as e:
        return False, f"Ошибка синхронизации: {str(e)}"


def sync_cards_from_yandex():
    """Синхронизация карточек с Яндекс.Диска на локальное хранилище"""
    if not storage.has_yandex:
        return False, "Яндекс.Диск не настроен"

    try:
        # Загружаем данные с Яндекс.Диска
        yandex_data = storage.yandex_storage.load()
        if not yandex_data:
            return False, "На Яндекс.Диске нет данных"

        # Сохраняем локально (полная замена)
        success = storage.local_storage.save(yandex_data)

        if success:
            return True, f"Синхронизировано {len(yandex_data.get('cards', []))} карточек с Яндекс.Диска"
        return False, "Не удалось сохранить локально"

    except Exception as e:
        return False, f"Ошибка синхронизации: {str(e)}"


# Маршруты
@app.route('/')
def index():
    try:
        cards_data = load_cards()

        # Параметры фильтрации
        theme_filter = request.args.get('theme', '').strip()
        difficulty_filter = request.args.get('difficulty', '').strip()
        version_filter = request.args.get('version', '').strip()
        search_query = request.args.get('search', '').lower()
        show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'
        view_mode = request.args.get('view', 'grid')

        # Параметры пагинации (только для режима сетки)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)  # 20 карточек на страницу

        # Получаем базовые переменные
        template_vars = get_template_variables(
            cards_data,
            current_theme=theme_filter,
            current_difficulty=difficulty_filter,
            current_version=version_filter,
            search_query=search_query,
            show_hidden=show_hidden,
            view_mode=view_mode
        )

        # Фильтрация
        filtered_cards = []
        for card in cards_data.get('cards', []):
            # Фильтр по скрытым карточкам
            if not show_hidden and card.get('hidden', False):
                continue

            # Фильтр по теме
            if theme_filter:
                card_themes = [t.strip() for t in card.get('theme', '').split(',')]
                if theme_filter not in card_themes:
                    continue

            # Фильтр по сложности
            if difficulty_filter and card.get('difficulty') != difficulty_filter:
                continue

            # Фильтр по версии
            if version_filter and card.get('version') != version_filter:
                continue

            # Поиск по тексту
            if search_query:
                question = card.get('question', '').lower()
                answer = card.get('answer', '').lower()
                explanation = card.get('explanation', '').lower()
                if (search_query not in question and
                        search_query not in answer and
                        search_query not in explanation):
                    continue

            filtered_cards.append(card)

        # Сортируем карточки по ID
        filtered_cards.sort(key=lambda x: x.get('id', 0))

        # Для режима стопки - все карточки, без пагинации
        if view_mode == 'stack':
            template_vars.update({
                'cards': filtered_cards,
                'total_cards': len(filtered_cards),
                'page': 1,
                'total_pages': 1,
                'start_idx': 1,
                'end_idx': len(filtered_cards)
            })
        else:
            # Для режима сетки - применяем пагинацию
            total_cards = len(filtered_cards)
            total_pages = max(1, (total_cards + per_page - 1) // per_page)  # Округление вверх

            # Ограничиваем номер страницы
            if page < 1:
                page = 1
            elif page > total_pages and total_pages > 0:
                page = total_pages

            # Вычисляем индексы для текущей страницы
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_cards)
            cards_on_page = filtered_cards[start_idx:end_idx]

            # Добавляем переменные пагинации
            template_vars.update({
                'cards': cards_on_page,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'total_cards': total_cards,
                'start_idx': start_idx + 1 if cards_on_page else 0,
                'end_idx': end_idx
            })

        # Выбираем шаблон
        template_name = 'stack_view.html' if view_mode == 'stack' else 'index.html'

        if view_mode == 'stack':
            base_dir = Path(__file__).parent
            stack_template_path = base_dir / 'templates' / 'stack_view.html'
            if not stack_template_path.exists():
                template_name = 'index.html'
                flash('Режим стопки карточек временно недоступен', 'info')

        return render_template(template_name, **template_vars)
    except Exception as e:
        print(f"Ошибка в index: {e}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return render_template('index.html',
                               cards=[],
                               all_themes=[],
                               all_versions=[],
                               theme_counts={},
                               difficulty_counts={'easy': 0, 'medium': 0, 'hard': 0},
                               version_counts={},
                               page=1,
                               per_page=20,
                               total_pages=0,
                               total_cards=0,
                               start_idx=0,
                               end_idx=0,
                               show_hidden=False,
                               view_mode='grid',
                               storage_mode=storage.mode,
                               has_yandex=storage.has_yandex)


@app.route('/card/<int:card_id>/toggle_hidden', methods=['POST'])
def toggle_hidden(card_id):
    """Переключение состояния скрытия карточки"""
    try:
        cards_data = load_cards()

        for card in cards_data.get('cards', []):
            if card.get('id') == card_id:
                # Переключаем состояние
                card['hidden'] = not card.get('hidden', False)
                save_cards(cards_data)

                status = "скрыта" if card['hidden'] else "показана"
                flash(f'Карточка {status}!', 'success')
                return redirect(url_for('card_detail', card_id=card_id))

        flash('Карточка не найдена', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Ошибка в toggle_hidden: {e}")
        flash('Произошла ошибка', 'error')
        return redirect(url_for('index'))


@app.route('/create', methods=['GET', 'POST'])
def create_card():
    """Создание карточки"""
    try:
        # Загружаем текущие данные
        cards_data = load_cards()
        print(
            f"🔍 create_card: Загружено {len(cards_data.get('cards', []))} карточек, next_id: {cards_data.get('next_id', 0)}")

        # Получаем переменные для шаблона
        template_vars = get_template_variables(cards_data)

        if request.method == 'POST':
            # Получаем данные из формы
            theme = request.form.get('theme', '').strip()
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()

            # Валидация
            if not theme or not question or not answer:
                flash('Все поля обязательны для заполнения', 'error')
                return render_template('create_card.html',
                                       difficulty_levels=Config.DIFFICULTY_LEVELS,
                                       **template_vars)

            # Создаем новую карточку
            new_card = {
                "id": cards_data['next_id'],
                "theme": theme,
                "question": question,
                "answer": answer,
                "explanation": request.form.get('explanation', '').strip(),
                "difficulty": request.form.get('difficulty', 'medium'),
                "version": request.form.get('version', '').strip() or None,
                "hidden": False,
            }

            print(f"🔍 create_card: Создаем карточку ID: {new_card['id']}")

            # Добавляем карточку в данные
            cards_data['cards'].append(new_card)
            cards_data['next_id'] += 1

            print(
                f"🔍 create_card: После добавления - карточек: {len(cards_data.get('cards', []))}, next_id: {cards_data['next_id']}")

            # Сохраняем данные
            if save_cards(cards_data):
                print(f"✅ create_card: Карточка {new_card['id']} успешно создана и сохранена")
                flash('Вопрос успешно добавлен!', 'success')
                return redirect(url_for('index'))
            else:
                print(f"❌ create_card: Ошибка сохранения карточки")
                flash('Ошибка сохранения карточки', 'error')

        # GET запрос - показываем форму
        return render_template('create_card.html',
                               difficulty_levels=Config.DIFFICULTY_LEVELS,
                               **template_vars)
    except Exception as e:
        print(f"❌ Ошибка в create_card: {e}")
        import traceback
        traceback.print_exc()
        flash('Произошла ошибка при создании вопроса', 'error')
        return redirect(url_for('index'))


@app.route('/card/<int:card_id>')
def card_detail(card_id):
    """Детальная страница карточки"""
    try:
        print(f"DEBUG: Loading card_detail for card_id={card_id}")
        cards_data = load_cards()
        template_vars = get_template_variables(cards_data)

        # Ищем карточку
        card = None
        for c in cards_data.get('cards', []):
            if c.get('id') == card_id:
                card = c
                break

        if not card:
            print(f"DEBUG: Card {card_id} not found!")
            flash('Карточка не найдена', 'error')
            return redirect(url_for('index'))

        print(f"DEBUG: Found card: {card}")

        # Получаем информацию о сложности
        difficulty_info = Config.DIFFICULTY_LEVELS.get(
            card.get('difficulty', 'medium'),
            Config.DIFFICULTY_LEVELS['medium']
        )

        template_vars['card'] = card
        template_vars['difficulty_info'] = difficulty_info
        return render_template('card_detail.html', **template_vars)
    except Exception as e:
        print(f"Ошибка в card_detail: {e}")
        import traceback
        traceback.print_exc()
        flash('Произошла ошибка при загрузке карточки', 'error')
        return redirect(url_for('index'))


@app.route('/card/<int:card_id>/edit', methods=['GET', 'POST'])
def edit_card(card_id):
    """Редактирование карточки"""
    try:
        cards_data = load_cards()

        # Ищем карточку
        card = None
        card_index = -1
        for i, c in enumerate(cards_data.get('cards', [])):
            if c.get('id') == card_id:
                card = c
                card_index = i
                break

        if not card:
            flash('Карточка не найдена', 'error')
            return redirect(url_for('index'))

        if request.method == 'POST':
            # Получаем данные
            theme = request.form.get('theme', '').strip()
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()

            # Валидация
            if not theme or not question or not answer:
                flash('Все поля обязательны для заполнения', 'error')
                return render_template('edit_card.html',
                                       card=card,
                                       difficulty_levels=Config.DIFFICULTY_LEVELS,
                                       **get_template_variables(cards_data))

            # Обновляем поля
            cards_data['cards'][card_index]['theme'] = theme
            cards_data['cards'][card_index]['question'] = question
            cards_data['cards'][card_index]['answer'] = answer
            cards_data['cards'][card_index]['explanation'] = request.form.get('explanation', '').strip()
            cards_data['cards'][card_index]['difficulty'] = request.form.get('difficulty', 'medium')

            version = request.form.get('version', '').strip()
            if version:
                cards_data['cards'][card_index]['version'] = version
            elif 'version' in cards_data['cards'][card_index]:
                del cards_data['cards'][card_index]['version']

            # Сохраняем
            if save_cards(cards_data):
                flash('Вопрос успешно обновлен!', 'success')
                return redirect(url_for('card_detail', card_id=card_id))
            else:
                flash('Ошибка сохранения', 'error')

        # GET запрос или ошибка
        return render_template('edit_card.html',
                               card=card,
                               difficulty_levels=Config.DIFFICULTY_LEVELS,
                               **get_template_variables(cards_data))

    except Exception as e:
        print(f"❌ Ошибка в edit_card: {e}")
        flash('Произошла ошибка при редактировании', 'error')
        return redirect(url_for('index'))


@app.route('/card/<int:card_id>/delete', methods=['POST'])
def delete_card(card_id):
    """Удаление карточки (через форму)"""
    try:
        cards_data = load_cards()

        # Удаляем карточку
        initial_count = len(cards_data.get('cards', []))
        cards_data['cards'] = [c for c in cards_data.get('cards', []) if c['id'] != card_id]

        if len(cards_data.get('cards', [])) < initial_count:
            if save_cards(cards_data):
                flash('Вопрос успешно удален!', 'success')
            else:
                flash('Ошибка сохранения удаления', 'error')
        else:
            flash('Карточка не найдена', 'error')

        return redirect(url_for('index'))
    except Exception as e:
        flash('Произошла ошибка при удалении', 'error')
        return redirect(url_for('index'))


@app.route('/export/xlsx')
def export_xlsx():
    """Экспорт карточек в Excel"""
    try:
        print(f"DEBUG: Экспорт запрошен. Режим хранения: {storage.mode}")

        # Загружаем данные через хранилище
        data = storage.load()
        print(f"DEBUG: Загружено {len(data.get('cards', []))} карточек")

        if not data.get('cards'):
            flash('Нет данных для экспорта', 'warning')
            return redirect(url_for('index'))

        # Создаем экспортер с гибридным хранилищем
        exporter = create_exporter(storage=storage)

        # Получаем Excel файл
        buffer, filename = exporter.export_to_excel()

        print(f"DEBUG: Экспорт успешен, файл: {filename}")

        # Отправляем файл пользователю
        return send_file(
            buffer,
            download_name=filename,
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except ValueError as e:
        print(f"Ошибка экспорта: {e}")
        flash(str(e), 'warning')
        return redirect(url_for('index'))

    except Exception as e:
        print(f"Ошибка при экспорте в Excel: {e}")
        import traceback
        traceback.print_exc()
        flash('Произошла ошибка при экспорте данных в Excel', 'error')
        return redirect(url_for('index'))


@app.route('/import', methods=['GET', 'POST'])
def import_cards():
    """Страница импорта карточек"""
    if request.method == 'GET':
        # Получаем данные для сайдбара
        cards_data = load_cards()
        template_vars = get_template_variables(cards_data)
        template_vars['show_filters'] = False
        return render_template('import.html', **template_vars)

    # POST запрос
    try:
        if 'file' not in request.files:
            flash('Файл не выбран', 'error')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('Файл не выбран', 'error')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Разрешены только файлы Excel (.xlsx, .xls)', 'error')
            return redirect(request.url)

        # Режим импорта
        mode = request.form.get('mode', 'append')
        if mode not in ['append', 'replace']:
            mode = 'append'

        # Сохраняем файл
        filename = secure_filename(file.filename)
        upload_folder = app.config['UPLOAD_FOLDER']
        file_path = upload_folder / f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        file.save(file_path)

        importer = create_importer(storage=storage)

        # Валидируем файл
        is_valid, message = importer.validate_excel_file(file_path)
        if not is_valid:
            if file_path.exists():
                file_path.unlink()
            flash(f'Ошибка валидации файла: {message}', 'error')
            return redirect(request.url)

        # Импортируем
        success, result = importer.import_from_excel(file_path, mode=mode)

        # Удаляем временный файл
        if file_path.exists():
            file_path.unlink()

        if success:
            flash(f'Импорт успешно завершен! Импортировано {result["imported"]} карточек, '
                  f'пропущено {result["skipped"]}. Всего карточек: {result["total"]}', 'success')
        else:
            flash(f'Ошибка импорта: {result.get("error", "Неизвестная ошибка")}', 'error')

        return redirect(url_for('index'))

    except Exception as e:
        print(f"Ошибка импорта: {e}")
        flash(f'Произошла ошибка при импорте: {str(e)}', 'error')
        return redirect(request.url)


@app.route('/import/preview', methods=['POST'])
def import_preview():
    """Предпросмотр данных перед импортом"""
    try:
        print(f"DEBUG: Получен запрос на предпросмотр")

        if 'file' not in request.files:
            print(f"DEBUG: Нет файла в запросе")
            return jsonify({
                'success': False,
                'error': 'Файл не выбран'
            }), 400

        file = request.files['file']
        print(f"DEBUG: Файл получен: {file.filename}")

        if file.filename == '':
            print(f"DEBUG: Имя файла пустое")
            return jsonify({
                'success': False,
                'error': 'Файл не выбран'
            }), 400

        if not allowed_file(file.filename):
            print(f"DEBUG: Неподдерживаемый формат файла: {file.filename}")
            return jsonify({
                'success': False,
                'error': 'Разрешены только файлы Excel (.xlsx, .xls)'
            }), 400

        # Создаем временную папку для загрузок
        upload_folder = app.config['UPLOAD_FOLDER']
        upload_folder.mkdir(parents=True, exist_ok=True)

        # Сохраняем файл
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(file.filename)
        file_path = upload_folder / f"preview_{timestamp}_{filename}"
        file.save(file_path)

        print(f"DEBUG: Файл сохранен в {file_path}")

        importer = create_importer(storage=storage)

        # Получаем предпросмотр
        success, result = importer.get_import_preview(file_path)

        # Удаляем временный файл
        if file_path.exists():
            file_path.unlink()
            print(f"DEBUG: Временный файл удален")

        if success:
            print(f"DEBUG: Предпросмотр успешно получен, строк: {result.get('total_rows', 0)}")
            return jsonify({
                'success': True,
                **result
            })
        else:
            print(f"DEBUG: Ошибка предпросмотра: {result}")
            return jsonify({
                'success': False,
                'error': result
            }), 400

    except Exception as e:
        print(f"DEBUG: Ошибка в import_preview: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Произошла ошибка: {str(e)}'
        }), 500


@app.route('/system/status')
def system_status():
    """Страница статуса системы"""
    try:
        cards_data = load_cards()
        template_vars = get_template_variables(cards_data)
        template_vars['show_filters'] = False

        # Статус хранилища
        status = {
            'storage_mode': storage.mode,
            'local_file_exists': JSON_FILE.exists(),
            'local_file_size': f"{JSON_FILE.stat().st_size} байт" if JSON_FILE.exists() else "Файл не существует",
            'local_file_path': str(JSON_FILE),
            'has_yandex': storage.has_yandex,
            'yandex_connected': False,
            'yandex_info': "Настроен" if storage.has_yandex else "Не настроен",
            'total_cards': len(cards_data.get('cards', [])),
            'visible_cards': sum(1 for card in cards_data.get('cards', []) if not card.get('hidden', False)),
            'hidden_cards': sum(1 for card in cards_data.get('cards', []) if card.get('hidden', False)),
            'themes_count': len(template_vars['all_themes']),
            'versions_count': len(template_vars['all_versions']),
            'max_backups': Config.MAX_BACKUPS,
            'backup_on_start': Config.BACKUP_ON_START
        }

        # Проверяем подключение к Яндекс.Диску
        if storage.has_yandex and hasattr(storage, 'yandex_storage'):
            try:
                status['yandex_connected'] = storage.yandex_storage.test_connection()
            except:
                status['yandex_connected'] = False

        # Получаем список бэкапов
        backups = backup_manager.list_backups()
        backup_list = []
        for backup in backups:
            try:
                source_display = 'Яндекс.Диск' if backup.source == 'yandex' else 'Локальный'

                if hasattr(backup, 'created_at'):
                    date_str = backup.created_at.strftime('%d.%m.%Y %H:%M')
                else:
                    date_str = 'Неизвестно'

                size_kb = backup.file_size / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"

                backup_list.append({
                    'filename': backup.filename,
                    'source': backup.source,
                    'source_display': source_display,
                    'date': date_str,
                    'card_count': backup.card_count,
                    'size': size_str,
                    'from_yandex': backup.source == 'yandex'
                })
            except Exception as e:
                print(f"Ошибка обработки бэкапа {backup.filename}: {e}")
                continue

        template_vars['status'] = status
        template_vars['backups'] = backup_list

        return render_template('system_status.html', **template_vars)
    except Exception as e:
        print(f"Ошибка в system_status: {e}")
        import traceback
        traceback.print_exc()
        flash('Ошибка получения статуса системы', 'error')
        return redirect(url_for('index'))


@app.route('/debug/storage')
def debug_storage():
    """Страница отладки хранилища"""
    try:
        cards_data = load_cards()
        template_vars = get_template_variables(cards_data)
        template_vars['show_filters'] = False

        # Проверяем локальный файл
        local_path = JSON_FILE
        local_exists = local_path.exists()
        local_size = local_path.stat().st_size if local_exists else 0

        # Проверяем Яндекс.Диск
        yandex_status = {}
        if storage.has_yandex and storage.yandex_storage:
            yandex_status['connected'] = storage.yandex_storage.test_connection()
            yandex_status['file_exists'] = storage.yandex_storage.file_exists()

            # Пробуем прочитать файл
            try:
                yandex_data = storage.yandex_storage.load()
                yandex_status['cards_count'] = len(yandex_data.get('cards', []))
            except:
                yandex_status['cards_count'] = 0

        # Получаем список бэкапов
        backups = backup_manager.list_backups()
        backup_list = []
        for backup in backups:
            try:
                source_display = 'Яндекс.Диск' if backup.source == 'yandex' else 'Локальный'

                if hasattr(backup, 'created_at'):
                    date_str = backup.created_at.strftime('%d.%m.%Y %H:%M')
                else:
                    date_str = 'Неизвестно'

                size_kb = backup.file_size / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"

                backup_list.append({
                    'filename': backup.filename,
                    'source': backup.source,
                    'source_display': source_display,
                    'date': date_str,
                    'card_count': backup.card_count,
                    'size': size_str,
                    'from_yandex': backup.source == 'yandex'
                })
            except Exception as e:
                print(f"Ошибка обработки бэкапа {backup.filename}: {e}")
                continue

        template_vars.update({
            'local_exists': local_exists,
            'local_size': local_size,
            'local_cards': len(cards_data.get('cards', [])),
            'has_yandex': storage.has_yandex,
            'yandex_status': yandex_status,
            'backups': backup_list
        })

        return render_template('debug_storage.html', **template_vars)
    except Exception as e:
        print(f"Ошибка в debug_storage: {e}")
        import traceback
        traceback.print_exc()
        flash('Ошибка отладки хранилища', 'error')
        return redirect(url_for('index'))


@app.route('/documentation')
def documentation():
    """Страница документации"""

    base_dir = Path(__file__).parent
    templates_dir = base_dir / 'templates' / 'docs'

    # Определяем пути к HTML файлам
    docs_structure = {
        'welcome': templates_dir / 'index.html',
        'first_steps': templates_dir / 'getting-started' / 'first-steps.html',
        'cards': templates_dir / 'usage' / 'cards.html',
        'features': templates_dir / 'usage' / 'features.html',
        'filters': templates_dir / 'usage' / 'filters.html',
        'import_export': templates_dir / 'usage' / 'import-export.html',
        'view_modes': templates_dir / 'usage' / 'view-modes.html',
        'data_format': templates_dir / 'reference' / 'data-format.html',
        'faq': templates_dir / 'reference' / 'faq.html',
        'storage_backup': templates_dir / 'reference' / 'storage-backup.html',  # НОВОЕ
        'sync': templates_dir / 'reference' / 'sync.html',  # НОВОЕ
    }

    # Загружаем содержимое каждого файла
    docs_content = {}
    for key, filepath in docs_structure.items():
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                    # Извлекаем содержимое body
                    body_start = content.find('<body>')
                    body_end = content.find('</body>')

                    if body_start != -1 and body_end != -1:
                        content = content[body_start + 6:body_end].strip()

                    # Удаляем возможные стили
                    while '<style>' in content and '</style>' in content:
                        style_start = content.find('<style>')
                        style_end = content.find('</style>') + 8
                        content = content[:style_start] + content[style_end:]

                    docs_content[f'{key}_content'] = content
            else:
                docs_content[
                    f'{key}_content'] = f'<div class="alert alert-warning"><p>Файл документации не найден: {filepath}</p></div>'

        except Exception as e:
            docs_content[
                f'{key}_content'] = f'<div class="alert alert-error"><p>Ошибка загрузки раздела {key}: {str(e)}</p></div>'

    return render_template('documentation.html', **docs_content)


@app.route('/backup/create', methods=['POST'])
def create_backup():
    """Создание бэкапа"""
    try:
        description = request.form.get('description', '').strip()
        backup_target = request.form.get('backup_target', 'both')

        success, message = backup_manager.create_backup(description, backup_target)

        if success:
            flash(message, 'success')
        else:
            flash(f'Ошибка: {message}', 'error')

    except Exception as e:
        flash(f'Ошибка создания бэкапа: {str(e)}', 'error')

    return redirect(url_for('backup_management'))


@app.route('/backup/manage')
def backup_management():
    try:
        cards_data = load_cards()
        template_vars = get_template_variables(cards_data)
        template_vars['show_filters'] = False

        # Получаем список бэкапов
        backups = backup_manager.list_backups()

        # Подготавливаем данные для отображения
        backup_list = []
        for backup in backups:
            try:
                # Определяем источник бэкапа
                source_display = 'Яндекс.Диск' if backup.source == 'yandex' else 'Локальный'

                # Форматируем дату
                if hasattr(backup, 'created_at'):
                    date_str = backup.created_at.strftime('%d.%m.%Y %H:%M')
                else:
                    date_str = 'Неизвестно'

                # Форматируем размер
                size_kb = backup.file_size / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"

                # Получаем описание
                description = getattr(backup, 'description', '')

                backup_list.append({
                    'filename': backup.filename,
                    'source': backup.source,
                    'source_display': source_display,
                    'date': date_str,
                    'card_count': backup.card_count,
                    'size': size_str,
                    'description': description,
                    'from_yandex': backup.source == 'yandex',
                    'created_at': backup.created_at if hasattr(backup, 'created_at') else None
                })
            except Exception as e:
                print(f"Ошибка обработки бэкапа {backup.filename}: {e}")
                continue

        template_vars['backups'] = backup_list

        # Передаем настройки бэкапов
        template_vars['max_backups'] = Config.MAX_BACKUPS
        template_vars['backup_on_start'] = Config.BACKUP_ON_START

        return render_template('backup_management.html', **template_vars)
    except Exception as e:
        print(f"Ошибка в backup_management: {e}")
        import traceback
        traceback.print_exc()
        flash('Ошибка загрузки списка бэкапов', 'error')
        return redirect(url_for('index'))

@app.route('/backup/restore', methods=['POST'])
def restore_backup():
    """Восстановление из бэкапа"""
    try:
        backup_name = request.form.get('backup_name')
        from_yandex = request.form.get('from_yandex', 'false').lower() == 'true'
        restore_target = request.form.get('restore_target', 'both')

        if not backup_name:
            flash('Не выбран бэкап для восстановления', 'error')
            return redirect(url_for('backup_management'))

        success, message = backup_manager.restore_backup(
            backup_name,
            from_yandex,
            restore_target
        )

        if success:
            flash(message, 'success')
        else:
            flash(f'Ошибка восстановления: {message}', 'error')

    except Exception as e:
        flash(f'Ошибка восстановления: {str(e)}', 'error')

    return redirect(url_for('backup_management'))


@app.route('/backup/delete', methods=['POST'])
def delete_backup():
    """Удаление бэкапа"""
    try:
        backup_name = request.form.get('backup_name')
        from_yandex = request.form.get('from_yandex', 'false').lower() == 'true'

        if not backup_name:
            return jsonify({'success': False, 'error': 'Не выбран бэкап для удаления'}), 400

        success, message = backup_manager.delete_backup(backup_name, from_yandex)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка удаления: {str(e)}'}), 500

@app.route('/backup/auto_create')
def auto_create_backup():
    """Автоматическое создание бэкапа (например, по расписанию)"""
    try:
        success, message = backup_manager.create_backup("Автоматический бэкап")
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/storage/sync_to_yandex', methods=['POST'])
def sync_to_yandex():
    """Ручная синхронизация на Яндекс.Диск"""
    try:
        # Загружаем локальные данные
        data = storage.local_storage.load()

        if storage.has_yandex:
            success = storage.yandex_storage.save(data)
            if success:
                flash(f'✅ Синхронизировано {len(data.get("cards", []))} карточек', 'success')
            else:
                flash('❌ Ошибка синхронизации с Яндекс.Диском', 'error')
        else:
            flash('❌ Яндекс.Диск не настроен', 'error')

        return redirect(url_for('system_status'))
    except Exception as e:
        flash(f'❌ Ошибка синхронизации: {str(e)}', 'error')
        return redirect(url_for('system_status'))


@app.route('/storage/load_from_yandex', methods=['POST'])
def load_from_yandex():
    """Принудительная загрузка с Яндекс.Диска"""
    try:
        if not storage.has_yandex:
            flash('❌ Яндекс.Диск не настроен', 'error')
            return redirect(url_for('system_status'))

        # Загружаем с Яндекс.Диска
        data = storage.yandex_storage.load()
        if data:
            # Сохраняем локально (полная замена)
            storage.local_storage.save(data)
            flash(f'✅ Загружено {len(data.get("cards", []))} карточек', 'success')
        else:
            flash('❌ Не удалось загрузить данные', 'error')

        return redirect(url_for('system_status'))
    except Exception as e:
        flash(f'❌ Ошибка загрузки: {str(e)}', 'error')
        return redirect(url_for('system_status'))


# Контекстный процессор для шаблонов
@app.context_processor
def inject_globals():
    return {
        'current_year': datetime.now().year,
        'app_name': 'Тесты по гомеопатии',
        'storage_mode': storage.mode,
        'has_yandex': storage.has_yandex,
        'yandex_path': Config.YANDEX_DISK_PATH,
        'local_path': str(Config.JSON_FILE),
        'backup_count': len(backup_manager.list_backups())
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
