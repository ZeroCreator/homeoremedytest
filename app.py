import os
import json
import sys
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from excel_utils.exporter import create_exporter
from excel_utils.importer import create_importer

# Загружаем переменные окружения
load_dotenv()

# Импортируем конфигурацию
from config import Config

# Выводим конфигурацию
Config.print_config()

# Импортируем пути из paths.py
from paths import UPLOAD_DIR, STATIC_DIR, TEMPLATE_DIR, IS_VERCEL

# Используем JSON_FILE из Config
JSON_FILE = Config.JSON_FILE

# Импортируем модули для работы с Excel
from excel_utils.exporter import ExcelExporter
from excel_utils.importer import ExcelImporter

# Импортируем гибридное хранилище
from storage import HybridStorage

print(f"Starting app...")
print(f"JSON file path: {JSON_FILE}")
print(f"Upload dir: {UPLOAD_DIR}")
print(f"Is Vercel: {IS_VERCEL}")

# Создаем Flask приложение
app = Flask(__name__,
            static_folder=str(STATIC_DIR),
            template_folder=str(TEMPLATE_DIR))

app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['JSON_FILE'] = JSON_FILE
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR

# Создаем гибридное хранилище
storage = HybridStorage(
    mode=Config.STORAGE_MODE,
    local_path=JSON_FILE,
    yandex_token=Config.YANDEX_DISK_TOKEN,
    yandex_path=Config.YANDEX_DISK_PATH
)

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def allowed_file(filename):
    """Проверка расширения файла"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Инициализируем папки
def init_folders():
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Created upload dir: {UPLOAD_DIR}")

        # Загружаем начальные данные через хранилище
        data = storage.load()
        print(f"Initial data loaded: {len(data.get('cards', []))} cards")

    except Exception as e:
        print(f"Error in init_folders: {e}", file=sys.stderr)


# Инициализируем папки
init_folders()


# Функции для работы с данными через гибридное хранилище
def load_cards():
    """Загрузка карточек через гибридное хранилище"""
    try:
        return storage.load()
    except Exception as e:
        print(f"Ошибка загрузки через хранилище: {e}", file=sys.stderr)
        return {"cards": [], "themes": Config.DEFAULT_THEMES.copy(), "next_id": 1}


def save_cards(data):
    """Сохранение карточек через гибридное хранилище"""
    try:
        results = storage.save(data)

        # Проверяем результаты сохранения
        if results.get('yandex') is False:
            flash('Данные сохранены локально, но не удалось синхронизировать с Яндекс.Диском', 'warning')
        elif results.get('yandex') is True:
            flash('Данные успешно сохранены и синхронизированы с Яндекс.Диском', 'success')
        else:
            flash('Данные успешно сохранены локально', 'success')

    except Exception as e:
        print(f"Ошибка сохранения через хранилище: {e}", file=sys.stderr)
        flash('Ошибка сохранения данных', 'error')


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
        # Параметры пагинации по умолчанию (для режима сетки)
        'page': 1,
        'per_page': 20,
        'total_pages': 0,
        'start_idx': 0,
        'end_idx': 0
    }
    base_vars.update(overrides)
    return base_vars


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
            stack_template_path = Path(TEMPLATE_DIR) / 'stack_view.html'
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
        cards_data = load_cards()
        template_vars = get_template_variables(cards_data)

        if request.method == 'POST':
            # Получаем данные
            theme = request.form.get('theme', '').strip()
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()

            # Валидация
            if not theme or not question or not answer:
                flash('Все поля обязательны для заполнения', 'error')
                return render_template('create_card.html',
                                       difficulty_levels=Config.DIFFICULTY_LEVELS,
                                       **template_vars)

            # Создаем карточку
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

            cards_data['cards'].append(new_card)
            cards_data['next_id'] += 1

            save_cards(cards_data)
            flash('Вопрос успешно добавлен!', 'success')
            return redirect(url_for('index'))

        # GET запрос
        return render_template('create_card.html',
                               difficulty_levels=Config.DIFFICULTY_LEVELS,
                               **template_vars)
    except Exception as e:
        print(f"Ошибка в create_card: {e}")
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
        print(f"DEBUG: edit_card called for card_id={card_id}, method={request.method}")
        cards_data = load_cards()
        template_vars = get_template_variables(cards_data)

        # Ищем карточку
        card = None
        for c in cards_data.get('cards', []):
            if c.get('id') == card_id:
                card = c
                break

        if not card:
            flash('Карточка не найдена', 'error')
            return redirect(url_for('index'))

        if request.method == 'POST':
            print(f"DEBUG: Processing POST data: {request.form}")
            # Получаем данные
            theme = request.form.get('theme', '').strip()
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()

            # Валидация
            if not theme or not question or not answer:
                flash('Все поля обязательны для заполнения', 'error')
                template_vars['card'] = card
                return render_template('edit_card.html',
                                       card=card,
                                       difficulty_levels=Config.DIFFICULTY_LEVELS,
                                       **template_vars)

            # Обновляем данные карточки
            card['theme'] = theme
            card['question'] = question
            card['answer'] = answer
            card['explanation'] = request.form.get('explanation', '').strip()
            card['difficulty'] = request.form.get('difficulty', 'medium')
            version = request.form.get('version', '').strip()
            card['version'] = version if version else None

            print(f"DEBUG: Updated card data: {card}")
            save_cards(cards_data)

            flash('Вопрос успешно обновлен!', 'success')
            return redirect(url_for('card_detail', card_id=card_id))

        # GET запрос
        template_vars['card'] = card
        return render_template('edit_card.html',
                               card=card,
                               difficulty_levels=Config.DIFFICULTY_LEVELS,
                               **template_vars)

    except Exception as e:
        print(f"Ошибка в edit_card: {e}")
        import traceback
        traceback.print_exc()
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
            save_cards(cards_data)
            flash('Вопрос успешно удален!', 'success')
        else:
            flash('Карточка не найдена', 'error')

        return redirect(url_for('index'))
    except Exception as e:
        print(f"Ошибка в delete_card: {e}")
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

        status_info = {
            'storage_mode': storage.mode,
            'has_yandex': storage.has_yandex,
            'local_file_exists': JSON_FILE.exists(),
            'local_file_path': str(JSON_FILE),
            'yandex_connected': False,
            'total_cards': len(cards_data.get('cards', [])),
            'visible_cards': sum(1 for card in cards_data.get('cards', []) if not card.get('hidden', False)),
            'hidden_cards': sum(1 for card in cards_data.get('cards', []) if card.get('hidden', False)),
            'themes_count': len(template_vars['all_themes']),
            'versions_count': len(template_vars['all_versions']),
            'yandex_path': Config.YANDEX_DISK_PATH,
            'local_path': str(Config.JSON_FILE)
        }

        # Получаем информацию о локальном файле
        if JSON_FILE.exists():
            size = JSON_FILE.stat().st_size
            status_info['local_file_size'] = f"{size} байт ({size / 1024:.1f} KB)"
        else:
            status_info['local_file_size'] = "Файл не существует"

        # Проверяем подключение к Яндекс.Диску
        if storage.has_yandex and hasattr(storage, 'yandex_storage'):
            try:
                status_info['yandex_connected'] = storage.yandex_storage.test_connection()
                status_info['yandex_info'] = "Настроен и подключен"
            except:
                status_info['yandex_connected'] = False
                status_info['yandex_info'] = "Ошибка подключения"
        else:
            status_info['yandex_info'] = "Не настроен"

        template_vars['status'] = status_info
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
            yandex_data = storage.yandex_storage.load()
            yandex_status['cards_count'] = len(yandex_data.get('cards', []))

        template_vars['local_exists'] = local_exists
        template_vars['local_size'] = local_size
        template_vars['local_cards'] = len(cards_data.get('cards', []))
        template_vars['yandex_status'] = yandex_status
        template_vars['yandex_path'] = Config.YANDEX_DISK_PATH
        template_vars['local_path'] = str(Config.JSON_FILE)

        return render_template('debug_storage.html', **template_vars)
    except Exception as e:
        print(f"Ошибка в debug_storage: {e}")
        import traceback
        traceback.print_exc()
        flash('Ошибка отладки хранилища', 'error')
        return redirect(url_for('index'))


@app.route('/docs')
@app.route('/documentation')
def documentation():
    """Страница документации"""
    return redirect('https://zerocreator.github.io/homeoremedytest/')


# Контекстный процессор для шаблонов
@app.context_processor
def inject_globals():
    return {
        'current_year': datetime.now().year,
        'app_name': 'Тесты по гомеопатии',
        'storage_mode': storage.mode,
        'has_yandex': storage.has_yandex,
        'yandex_path': Config.YANDEX_DISK_PATH,
        'local_path': str(Config.JSON_FILE)
    }


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
