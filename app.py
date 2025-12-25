import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from datetime import datetime
from pathlib import Path

# Импортируем конфигурацию
from config import Config

# Создаем Flask приложение с ПРАВИЛЬНЫМИ путями
app = Flask(__name__,
            static_folder=str(Config.STATIC_DIR),
            template_folder=str(Config.TEMPLATE_DIR))

app.config['SECRET_KEY'] = Config.SECRET_KEY


# Функции для работы с данными
def load_cards():
    """Загрузка карточек из JSON файла"""
    try:
        # Проверяем и создаем директорию если нужно
        Config.DATA_DIR.mkdir(parents=True, exist_ok=True)

        if Config.JSON_FILE.exists():
            with open(Config.JSON_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки: {e}")

    # Данные по умолчанию
    return {
        "cards": [],
        "themes": Config.DEFAULT_THEMES.copy(),
        "next_id": 1
    }


def save_cards(data):
    """Сохранение карточек"""
    try:
        with open(Config.JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        flash('Ошибка сохранения данных', 'error')


def extract_themes(cards_data):
    """Извлечение уникальных тем"""
    themes = set()
    for card in cards_data.get('cards', []):
        if 'theme' in card and card['theme']:
            themes.add(card['theme'])
    return sorted(list(themes))


# Маршруты
@app.route('/')
def index():
    """Главная страница"""
    try:
        cards_data = load_cards()

        # Фильтры
        theme_filter = request.args.get('theme', '')
        search_query = request.args.get('search', '').lower()

        # Фильтрация
        filtered_cards = []
        for card in cards_data.get('cards', []):
            if theme_filter and card.get('theme') != theme_filter:
                continue

            if search_query:
                question = card.get('question', '').lower()
                answer = card.get('answer', '').lower()
                explanation = card.get('explanation', '').lower()
                if (search_query not in question and
                    search_query not in answer and
                    search_query not in explanation):
                    continue

            filtered_cards.append(card)

        all_themes = extract_themes(cards_data)

        return render_template('index.html',
                               cards=filtered_cards,
                               all_themes=all_themes,
                               current_theme=theme_filter,
                               search_query=search_query,
                               total_cards=len(cards_data.get('cards', []))
                               )
    except Exception as e:
        print(f"Ошибка в index: {e}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return render_template('index.html',
                               cards=[],
                               all_themes=[],
                               total_cards=0)


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
                flash('Все поля обязательны для заполнения', 'error')
                return render_template('create_card.html',
                                       all_themes=all_themes,
                                       difficulty_levels=Config.DIFFICULTY_LEVELS)

            # Создаем карточку
            new_card = {
                "id": cards_data['next_id'],
                "theme": theme,
                "question": question,
                "answer": answer,
                "explanation": request.form.get('explanation', '').strip(),
                "difficulty": request.form.get('difficulty', 'medium'),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            cards_data['cards'].append(new_card)
            cards_data['next_id'] += 1

            # Обновляем темы
            if theme not in cards_data['themes']:
                cards_data['themes'].append(theme)
                cards_data['themes'].sort()

            save_cards(cards_data)
            flash('Вопрос успешно добавлен!', 'success')
            return redirect(url_for('index'))

        # GET запрос
        cards_data = load_cards()
        all_themes = extract_themes(cards_data)

        return render_template('create_card.html',
                               all_themes=all_themes,
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
                flash('Все поля обязательны для заполнения', 'error')
                return render_template('edit_card.html',
                                      card=card,
                                      all_themes=all_themes,
                                      difficulty_levels=Config.DIFFICULTY_LEVELS)

            # Обновляем данные
            card['theme'] = theme
            card['question'] = question
            card['answer'] = answer
            card['explanation'] = request.form.get('explanation', '').strip()
            card['difficulty'] = request.form.get('difficulty', 'medium')
            card['updated_at'] = datetime.now().isoformat()

            # Обновляем темы
            if theme not in cards_data['themes']:
                cards_data['themes'].append(theme)
                cards_data['themes'].sort()

            save_cards(cards_data)
            flash('Вопрос успешно обновлен!', 'success')
            return redirect(url_for('card_detail', card_id=card_id))

        # GET запрос
        all_themes = extract_themes(cards_data)
        return render_template('edit_card.html',
                              card=card,
                              all_themes=all_themes,
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
            # Обновляем темы
            cards_data['themes'] = extract_themes(cards_data)
            save_cards(cards_data)
            flash('Вопрос успешно удален!', 'success')
        else:
            flash('Карточка не найдена', 'error')

        return redirect(url_for('index'))
    except Exception as e:
        print(f"Ошибка в delete_card: {e}")
        flash('Произошла ошибка при удалении', 'error')
        return redirect(url_for('index'))


# API endpoints
@app.route('/api/cards')
def api_cards():
    """API для получения всех карточек"""
    try:
        cards_data = load_cards()
        return jsonify(cards_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cards/<int:card_id>', methods=['DELETE'])
def api_delete_card(card_id):
    """API для удаления карточки (через fetch)"""
    try:
        cards_data = load_cards()

        # Удаляем карточку
        initial_count = len(cards_data.get('cards', []))
        cards_data['cards'] = [c for c in cards_data.get('cards', []) if c['id'] != card_id]

        if len(cards_data.get('cards', [])) < initial_count:
            # Обновляем темы
            cards_data['themes'] = extract_themes(cards_data)
            save_cards(cards_data)
            return jsonify({"success": True, "message": "Карточка удалена"}), 200
        else:
            return jsonify({"success": False, "error": "Карточка не найдена"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/cards', methods=['POST'])
def api_create_card():
    """API для создания карточки"""
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Content-Type должен быть application/json"}), 400

        cards_data = load_cards()
        data = request.get_json()

        # Валидация
        if not data.get('theme') or not data.get('question') or not data.get('answer'):
            return jsonify({"success": False, "error": "Все поля обязательны"}), 400

        # Создаем карточку
        new_card = {
            "id": cards_data['next_id'],
            "theme": data.get('theme', '').strip(),
            "question": data.get('question', '').strip(),
            "answer": data.get('answer', '').strip(),
            "explanation": data.get('explanation', '').strip(),
            "difficulty": data.get('difficulty', 'medium'),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        cards_data['cards'].append(new_card)
        cards_data['next_id'] += 1

        if new_card['theme'] not in cards_data['themes']:
            cards_data['themes'].append(new_card['theme'])
            cards_data['themes'].sort()

        save_cards(cards_data)

        return jsonify({"success": True, "data": new_card}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Контекстный процессор для шаблонов
@app.context_processor
def inject_globals():
    return {
        'current_year': datetime.now().year,
        'app_name': 'Тесты по гомеопатии'
    }


# Обработчики ошибок
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500


# Для локального запуска
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
