import os
import json
import sys
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

# Импортируем пути из единого источника
from paths import JSON_FILE, UPLOAD_DIR, STATIC_DIR, TEMPLATE_DIR, IS_VERCEL

# Импортируем конфигурацию
from config import Config

# Импортируем модули для работы с Excel
from excel_utils.exporter import ExcelExporter
from excel_utils.importer import ExcelImporter

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

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


# Создаем необходимые папки при запуске
def init_folders():
    try:
        # Создаем папку для загрузок
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Created upload dir: {UPLOAD_DIR}")

        # Создаем JSON файл если не существует
        if not JSON_FILE.exists():
            data = {
                "cards": [],
                "themes": Config.DEFAULT_THEMES.copy(),
                "next_id": 1
            }
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Created JSON file with default data: {JSON_FILE}")
        else:
            # Проверяем содержимое файла
            try:
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cards_count = len(data.get('cards', []))
                    print(f"JSON file exists with {cards_count} cards: {JSON_FILE}")
            except json.JSONDecodeError:
                print(f"Warning: JSON file is corrupted, recreating: {JSON_FILE}")
                data = {
                    "cards": [],
                    "themes": Config.DEFAULT_THEMES.copy(),
                    "next_id": 1
                }
                with open(JSON_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"Error in init_folders: {e}", file=sys.stderr)


# Инициализируем папки
init_folders()


def allowed_file(filename):
    """Проверка расширения файла"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Функции для работы с данными
def load_cards():
    """Загрузка карточек из JSON файла"""
    try:
        json_file = app.config['JSON_FILE']
        print(f"DEBUG: Loading cards from {json_file}")

        if json_file.exists():
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"DEBUG: Successfully loaded {len(data.get('cards', []))} cards")
                return data
        else:
            print(f"DEBUG: JSON file not found, creating default")
            data = {
                "cards": [],
                "themes": Config.DEFAULT_THEMES.copy(),
                "next_id": 1
            }
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data

    except Exception as e:
        print(f"Ошибка загрузки: {e}", file=sys.stderr)
        return {
            "cards": [],
            "themes": Config.DEFAULT_THEMES.copy(),
            "next_id": 1
        }


def save_cards(data):
    """Сохранение карточек"""
    try:
        json_file = app.config['JSON_FILE']
        print(f"DEBUG: Saving {len(data.get('cards', []))} cards to {json_file}")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения: {e}", file=sys.stderr)
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


# Маршруты
@app.route('/')
def index():
    try:
        cards_data = load_cards()

        # Новые параметры фильтрации
        theme_filter = request.args.get('theme', '').strip()
        search_query = request.args.get('search', '').lower()
        show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'

        # Подсчет скрытых карточек
        hidden_count = sum(1 for card in cards_data.get('cards', []) if card.get('hidden', False))

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

        # Получаем все уникальные темы для сайдбара
        all_themes = extract_themes(cards_data)
        theme_counts = get_theme_counts(cards_data)

        # Сортировка тем по популярности (по количеству карточек)
        sorted_themes = sorted(all_themes, key=lambda x: (-theme_counts.get(x, 0), x))

        return render_template('index.html',
                               cards=filtered_cards,
                               all_themes=sorted_themes,
                               theme_counts=theme_counts,
                               current_theme=theme_filter,
                               search_query=search_query,
                               show_hidden=show_hidden,
                               hidden_count=hidden_count,
                               total_cards=len(cards_data.get('cards', []))
                               )
    except Exception as e:
        print(f"Ошибка в index: {e}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return render_template('index.html',
                               cards=[],
                               all_themes=[],
                               total_cards=0,
                               hidden_count=0,
                               show_hidden=False)


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
        if request.method == 'POST':
            cards_data = load_cards()

            # Получаем данные
            theme = request.form.get('theme', '').strip()
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()

            # Валидация
            if not theme or not question or not answer:
                all_themes = extract_themes(cards_data)
                theme_counts = get_theme_counts(cards_data)  # Добавляем
                flash('Все поля обязательны для заполнения', 'error')
                return render_template('create_card.html',
                                       all_themes=all_themes,
                                       theme_counts=theme_counts,  # Добавляем
                                       difficulty_levels=Config.DIFFICULTY_LEVELS)

            # Создаем карточку
            new_card = {
                "id": cards_data['next_id'],
                "theme": theme,
                "question": question,
                "answer": answer,
                "explanation": request.form.get('explanation', '').strip(),
                "difficulty": request.form.get('difficulty', 'medium'),
                "hidden": False,
            }

            cards_data['cards'].append(new_card)
            cards_data['next_id'] += 1

            save_cards(cards_data)
            flash('Вопрос успешно добавлен!', 'success')
            return redirect(url_for('index'))

        # GET запрос
        cards_data = load_cards()
        all_themes = extract_themes(cards_data)
        theme_counts = get_theme_counts(cards_data)  # Добавляем

        return render_template('create_card.html',
                               all_themes=all_themes,
                               theme_counts=theme_counts,  # Добавляем
                               difficulty_levels=Config.DIFFICULTY_LEVELS
                               )
    except Exception as e:
        print(f"Ошибка в create_card: {e}")
        flash('Произошла ошибка при создании вопроса', 'error')
        return redirect(url_for('index'))


@app.route('/card/<int:card_id>')
def card_detail(card_id):
    """Детальная страница карточки"""
    try:
        cards_data = load_cards()

        # Ищем карточку
        card = None
        for c in cards_data.get('cards', []):
            if c.get('id') == card_id:
                card = c
                break

        if not card:
            flash('Карточка не найдена', 'error')
            return redirect(url_for('index'))

        # Получаем информацию о сложности
        difficulty_info = Config.DIFFICULTY_LEVELS.get(
            card.get('difficulty', 'medium'),
            Config.DIFFICULTY_LEVELS['medium']
        )

        return render_template('card_detail.html',
                               card=card,
                               difficulty_info=difficulty_info
                               )
    except Exception as e:
        print(f"Ошибка в card_detail: {e}")
        flash('Произошла ошибка при загрузке карточки', 'error')
        return redirect(url_for('index'))


@app.route('/card/<int:card_id>/edit', methods=['GET', 'POST'])
def edit_card(card_id):
    """Редактирование карточки"""
    try:
        cards_data = load_cards()

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
            # Получаем данные
            theme = request.form.get('theme', '').strip()
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()

            # Валидация
            if not theme or not question or not answer:
                all_themes = extract_themes(cards_data)
                theme_counts = get_theme_counts(cards_data)  # Добавляем
                flash('Все поля обязательны для заполнения', 'error')
                return render_template('edit_card.html',
                                       card=card,
                                       all_themes=all_themes,
                                       theme_counts=theme_counts,  # Добавляем
                                       difficulty_levels=Config.DIFFICULTY_LEVELS)

            # Обновляем данные
            card['theme'] = theme
            card['question'] = question
            card['answer'] = answer
            card['explanation'] = request.form.get('explanation', '').strip()
            card['difficulty'] = request.form.get('difficulty', 'medium')
            card['hidden'] = card.get('hidden', False)

            save_cards(cards_data)
            flash('Вопрос успешно обновлен!', 'success')
            return redirect(url_for('card_detail', card_id=card_id))

        # GET запрос
        all_themes = extract_themes(cards_data)
        theme_counts = get_theme_counts(cards_data)  # Добавляем

        return render_template('edit_card.html',
                               card=card,
                               all_themes=all_themes,
                               theme_counts=theme_counts,  # Добавляем
                               difficulty_levels=Config.DIFFICULTY_LEVELS)
    except Exception as e:
        print(f"Ошибка в edit_card: {e}")
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
        # Используем путь из конфига приложения
        json_file = str(app.config['JSON_FILE'])

        # Создаем экспортер
        exporter = ExcelExporter(json_file)

        # Получаем Excel файл
        buffer, filename = exporter.export_to_excel()

        # Отправляем файл пользователю
        return send_file(
            buffer,
            download_name=filename,
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except ValueError as e:
        flash(str(e), 'warning')
        return redirect(url_for('index'))

    except Exception as e:
        print(f"Ошибка при экспорте в Excel: {e}", file=sys.stderr)
        flash('Произошла ошибка при экспорте данных в Excel', 'error')
        return redirect(url_for('index'))


@app.route('/import', methods=['GET', 'POST'])
def import_cards():
    """Страница импорта карточек"""
    if request.method == 'GET':
        return render_template('import.html')

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

        # Используем путь из конфига приложения
        json_file = str(app.config['JSON_FILE'])
        importer = ExcelImporter(json_file)

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


# Контекстный процессор для шаблонов
@app.context_processor
def inject_globals():
    return {
        'current_year': datetime.now().year,
        'app_name': 'Тесты по гомеопатии'
    }


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
