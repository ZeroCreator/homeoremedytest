import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['JSON_FILE'] = 'data/test_cards.json'

# Создаем необходимые директории
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)


# Загружаем или создаем JSON файл
def load_cards():
    if os.path.exists(app.config['JSON_FILE']):
        with open(app.config['JSON_FILE'], 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Создаем базовую структуру
        data = {
            "cards": [],
            "themes": [],
            "next_id": 1
        }
        save_cards(data)
        return data


def save_cards(data):
    with open(app.config['JSON_FILE'], 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_themes(cards_data):
    themes = set()
    for card in cards_data['cards']:
        if 'theme' in card:
            themes.add(card['theme'])
    return sorted(list(themes))


@app.route('/')
def index():
    cards_data = load_cards()

    # Получаем фильтры из GET-параметров
    theme_filter = request.args.get('theme', '')
    search_query = request.args.get('search', '').lower()

    # Фильтруем карточки
    filtered_cards = []
    for card in cards_data['cards']:
        # Применяем фильтр по теме
        if theme_filter and card.get('theme') != theme_filter:
            continue

        # Применяем поиск по вопросу и ответу
        if search_query:
            if (search_query not in card.get('question', '').lower() and
                    search_query not in card.get('answer', '').lower()):
                continue

        filtered_cards.append(card)

    # Извлекаем все темы
    all_themes = extract_themes(cards_data)

    return render_template('index.html',
                           cards=filtered_cards,
                           all_themes=all_themes,
                           current_theme=theme_filter,
                           search_query=search_query)


@app.route('/create', methods=['GET', 'POST'])
def create_card():
    if request.method == 'POST':
        cards_data = load_cards()

        # Создаем новую карточку
        new_card = {
            "id": cards_data['next_id'],
            "theme": request.form.get('theme'),
            "question": request.form.get('question'),
            "answer": request.form.get('answer'),
            "explanation": request.form.get('explanation', ''),
            "difficulty": request.form.get('difficulty', 'medium')
        }

        # Добавляем карточку
        cards_data['cards'].append(new_card)
        cards_data['next_id'] += 1

        # Сохраняем
        save_cards(cards_data)

        return redirect(url_for('index'))

    return render_template('create_card.html')


@app.route('/card/<int:card_id>')
def card_detail(card_id):
    cards_data = load_cards()

    # Находим карточку по ID
    card = next((c for c in cards_data['cards'] if c['id'] == card_id), None)

    if card is None:
        return "Карточка не найдена", 404

    return render_template('card_detail.html', card=card)


@app.route('/api/cards', methods=['GET'])
def api_get_cards():
    cards_data = load_cards()
    return jsonify(cards_data)


@app.route('/api/cards', methods=['POST'])
def api_create_card():
    cards_data = load_cards()

    new_card = {
        "id": cards_data['next_id'],
        "theme": request.json.get('theme'),
        "question": request.json.get('question'),
        "answer": request.json.get('answer'),
        "explanation": request.json.get('explanation', ''),
        "difficulty": request.json.get('difficulty', 'medium')
    }

    cards_data['cards'].append(new_card)
    cards_data['next_id'] += 1
    save_cards(cards_data)

    return jsonify(new_card), 201


@app.route('/api/cards/<int:card_id>', methods=['DELETE'])
def api_delete_card(card_id):
    cards_data = load_cards()

    # Находим и удаляем карточку
    cards_data['cards'] = [c for c in cards_data['cards'] if c['id'] != card_id]

    save_cards(cards_data)
    return jsonify({"message": "Card deleted"}), 200


if __name__ == '__main__':
    app.run(debug=True)
