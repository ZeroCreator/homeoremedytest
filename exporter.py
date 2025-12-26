"""
Модуль для экспорта данных в Excel с использованием xlsxwriter
"""
import json
from datetime import datetime
from pathlib import Path
from io import BytesIO
import xlsxwriter


class ExcelExporter:
    """Класс для экспорта данных в Excel с использованием xlsxwriter"""

    # Константы для форматирования
    HEADER_COLOR = '#4A6FA5'      # Синий цвет заголовков
    FONT_NAME = 'Calibri'
    FONT_SIZE = 11
    HEADER_FONT_SIZE = 12

    # Цвета для сложности
    DIFFICULTY_COLORS = {
        'Легкий': '#E8F5E8',      # Светло-зеленый
        'Средний': '#FFF3E0',     # Светло-оранжевый
        'Сложный': '#FFEBEE'      # Светло-красный
    }

    # Минимальные и максимальные значения
    MIN_ROW_HEIGHT = 15
    MAX_ROW_HEIGHT = 400
    MIN_COLUMN_WIDTH = 5
    MAX_COLUMN_WIDTH = 100

    # Коэффициенты для расчета высоты строк
    PIXELS_PER_CHAR = 7.5          # Пикселей на символ (Calibri 11pt)
    PIXELS_PER_LINE = 15           # Пикселей на строку текста
    LINE_SPACING = 1.2             # Межстрочный интервал

    def __init__(self, json_file_path=None):
        """
        Инициализация экспортера

        Args:
            json_file_path: Путь к JSON файлу с данными
        """
        if json_file_path:
            self.json_file_path = Path(json_file_path)
        else:
            # Путь по умолчанию
            from config import Config
            self.json_file_path = Config.JSON_FILE

    def load_cards(self):
        """Загрузка карточек из JSON файла"""
        try:
            if self.json_file_path.exists():
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки JSON: {e}")

        return {"cards": [], "themes": [], "next_id": 1}

    def export_to_excel(self):
        """
        Создание Excel файла с карточками

        Returns:
            BytesIO: Буфер с Excel файлом
            str: Имя файла для скачивания
        """
        try:
            # Загружаем данные
            cards_data = self.load_cards()
            cards = cards_data.get('cards', [])

            if not cards:
                raise ValueError("Нет данных для экспорта")

            # Создаем буфер для записи Excel
            buffer = BytesIO()

            # Создаем рабочую книгу Excel
            workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})

            # Добавляем рабочий лист
            worksheet = workbook.add_worksheet('Карточки')

            # Определяем форматы
            formats = self._create_formats(workbook)

            # Настраиваем ширину колонок на основе данных
            column_widths = self._calculate_column_widths(cards)

            # Устанавливаем ширину колонок
            for col_idx, width in enumerate(column_widths):
                worksheet.set_column(col_idx, col_idx, width)

            # Записываем заголовки
            self._write_headers(worksheet, formats['header'])

            # Записываем данные
            self._write_data(worksheet, cards, formats)

            # Настраиваем высоту строк на основе содержимого
            self._adjust_row_heights(worksheet, cards, column_widths)

            # Настраиваем фильтры
            worksheet.autofilter(0, 0, len(cards), len(column_widths) - 1)

            # Замораживаем заголовки
            worksheet.freeze_panes(1, 0)

            # Закрываем книгу (важно!)
            workbook.close()

            # Перемещаем указатель в начало буфера
            buffer.seek(0)

            # Генерируем имя файла
            filename = self._generate_filename()

            return buffer, filename

        except Exception as e:
            print(f"Ошибка при экспорте в Excel: {e}")
            raise

    def _create_formats(self, workbook):
        """Создание форматов для ячеек"""
        formats = {}

        # Формат заголовков
        formats['header'] = workbook.add_format({
            'bold': True,
            'font_color': 'white',
            'bg_color': self.HEADER_COLOR,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': self.HEADER_FONT_SIZE,
            'font_name': self.FONT_NAME,
            'border': 1,
            'border_color': 'black',
            'text_wrap': True
        })

        # Базовый формат данных
        formats['data'] = workbook.add_format({
            'font_size': self.FONT_SIZE,
            'font_name': self.FONT_NAME,
            'valign': 'top',
            'text_wrap': True,
            'border': 1,
            'border_color': '#CCCCCC'
        })

        # Формат для центрированных данных (ID, сложность, скрытый)
        formats['center'] = workbook.add_format({
            'font_size': self.FONT_SIZE,
            'font_name': self.FONT_NAME,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'border': 1,
            'border_color': '#CCCCCC'
        })

        # Форматы для разных уровней сложности
        for difficulty, color in self.DIFFICULTY_COLORS.items():
            formats[f'data_{difficulty}'] = workbook.add_format({
                'font_size': self.FONT_SIZE,
                'font_name': self.FONT_NAME,
                'valign': 'top',
                'text_wrap': True,
                'border': 1,
                'border_color': '#CCCCCC',
                'bg_color': color
            })

            formats[f'center_{difficulty}'] = workbook.add_format({
                'font_size': self.FONT_SIZE,
                'font_name': self.FONT_NAME,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'border': 1,
                'border_color': '#CCCCCC',
                'bg_color': color
            })

        return formats

    def _calculate_column_widths(self, cards):
        """Расчет оптимальной ширины колонок на основе данных"""
        # Начальные ширины
        widths = [8, 70, 60, 60, 40, 15, 12]  # A, B, C, D, E, F, G

        # Собираем максимальную длину текста в каждой колонке
        max_lengths = [0] * 7

        # Проверяем заголовки
        headers = ['№', 'Вопрос', 'Ответ', 'Объяснение', 'Тема', 'Сложность', 'Скрытый']
        for i, header in enumerate(headers):
            max_lengths[i] = max(max_lengths[i], len(header))

        # Проверяем данные карточек
        for card in cards:
            # Преобразуем сложность
            difficulty_map = {'easy': 'Легкий', 'medium': 'Средний', 'hard': 'Сложный'}
            difficulty_text = difficulty_map.get(card.get('difficulty', 'medium'), 'Средний')
            hidden_text = 'Да' if card.get('hidden', False) else 'Нет'

            # Данные для проверки
            data_items = [
                str(card['id']),
                card['question'],
                card['answer'],
                card.get('explanation', ''),
                card['theme'],
                difficulty_text,
                hidden_text
            ]

            for i, item in enumerate(data_items):
                if item:
                    # Разбиваем на строки и берем максимальную длину
                    lines = str(item).split('\n')
                    max_line_length = max(len(line) for line in lines) if lines else 0
                    max_lengths[i] = max(max_lengths[i], max_line_length)

        # Рассчитываем ширину колонок
        column_widths = []
        for i in range(7):
            # Базовая ширина + запас на границы и отступы
            # В xlsxwriter ширина измеряется в символах (приблизительно)
            calculated_width = min(
                self.MAX_COLUMN_WIDTH,
                max(self.MIN_COLUMN_WIDTH, max_lengths[i] * 1.1 + 2)
            )

            # Используем максимальное значение из начальной ширины и рассчитанной
            final_width = max(widths[i], calculated_width)
            column_widths.append(final_width)

        return column_widths

    def _write_headers(self, worksheet, header_format):
        """Запись заголовков в таблицу"""
        headers = ['№', 'Вопрос', 'Ответ', 'Объяснение', 'Тема', 'Сложность', 'Скрытый']

        for col_idx, header in enumerate(headers):
            worksheet.write(0, col_idx, header, header_format)

        # Устанавливаем высоту строки заголовка
        worksheet.set_row(0, 30)  # 30 пикселей

    def _write_data(self, worksheet, cards, formats):
        """Запись данных карточек"""
        difficulty_map = {
            'easy': 'Легкий',
            'medium': 'Средний',
            'hard': 'Сложный'
        }

        for row_idx, card in enumerate(cards, start=1):
            # Преобразуем данные
            difficulty_text = difficulty_map.get(card.get('difficulty', 'medium'), 'Средний')
            hidden_text = 'Да' if card.get('hidden', False) else 'Нет'

            # Определяем формат в зависимости от сложности
            data_format = formats.get(f'data_{difficulty_text}', formats['data'])
            center_format = formats.get(f'center_{difficulty_text}', formats['center'])

            # Данные для записи
            data = [
                card['id'],                    # №
                card['question'],              # Вопрос
                card['answer'],                # Ответ
                card.get('explanation', ''),   # Объяснение
                card['theme'],                 # Тема
                difficulty_text,               # Сложность
                hidden_text                    # Скрытый
            ]

            # Записываем данные с соответствующими форматами
            for col_idx, value in enumerate(data):
                if col_idx in [0, 5, 6]:  # №, Сложность, Скрытый - центрировать
                    worksheet.write(row_idx, col_idx, value, center_format)
                else:  # Остальные - выравнивание по верхнему краю
                    worksheet.write(row_idx, col_idx, value, data_format)

    def _calculate_row_height(self, text, column_width_chars):
        """
        Точный расчет высоты строки в пикселях

        Args:
            text: Текст для расчета
            column_width_chars: Ширина колонки в символах

        Returns:
            int: Высота строки в пикселях
        """
        if not text:
            return self.MIN_ROW_HEIGHT

        text_str = str(text)

        # Разбиваем текст на строки (учитываем явные переносы)
        lines = text_str.split('\n')
        total_visual_lines = 0

        for line in lines:
            if not line.strip():
                total_visual_lines += 1  # Пустая строка
                continue

            # Количество символов в строке
            line_length = len(line)

            if column_width_chars > 0:
                # Рассчитываем, сколько виртуальных строк займет эта строка
                # Учитываем, что в ячейке может быть перенос текста
                lines_needed = (line_length + column_width_chars - 1) // column_width_chars
                total_visual_lines += max(1, lines_needed)
            else:
                total_visual_lines += 1

        # Рассчитываем высоту в пикселях
        # Базовый расчет: PIXELS_PER_LINE на строку с учетом межстрочного интервала
        base_height = total_visual_lines * self.PIXELS_PER_LINE * self.LINE_SPACING

        # Добавляем отступы сверху и снизу
        height_with_padding = base_height + 10

        # Ограничиваем минимальной и максимальной высотой
        final_height = max(self.MIN_ROW_HEIGHT, min(int(height_with_padding), self.MAX_ROW_HEIGHT))

        return final_height

    def _adjust_row_heights(self, worksheet, cards, column_widths):
        """Настройка высоты строк на основе содержимого"""
        difficulty_map = {'easy': 'Легкий', 'medium': 'Средний', 'hard': 'Сложный'}

        for row_idx, card in enumerate(cards, start=1):
            max_height = self.MIN_ROW_HEIGHT

            # Проверяем все текстовые колонки для этой строки
            text_columns = [
                (1, card['question']),          # Колонка B: Вопрос
                (2, card['answer']),            # Колонка C: Ответ
                (3, card.get('explanation', '')), # Колонка D: Объяснение
                (4, card['theme'])              # Колонка E: Тема
            ]

            for col_idx, text in text_columns:
                if text:
                    column_width = column_widths[col_idx]
                    row_height = self._calculate_row_height(text, column_width)
                    max_height = max(max_height, row_height)

            # Устанавливаем высоту строки
            # В xlsxwriter высота измеряется в пикселях
            worksheet.set_row(row_idx, max_height)

            # Для отладки: выводим информацию о высоких строках
            if max_height > 60:
                print(f"Строка {row_idx}: высота {max_height}px, вопрос: {card['question'][:50]}...")

    def _generate_filename(self):
        """Генерация имени файла с датой"""
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        return f"homeopathy_cards_{date_str}.xlsx"

    def export_to_file(self, output_path=None):
        """
        Экспорт в файл на диск

        Args:
            output_path: Путь для сохранения файла

        Returns:
            str: Путь к сохраненному файлу
        """
        if not output_path:
            output_path = Path.cwd() / self._generate_filename()

        buffer, _ = self.export_to_excel()

        with open(output_path, 'wb') as f:
            f.write(buffer.getvalue())

        return str(output_path)


# Фабричная функция для удобного использования
def create_exporter(json_file_path=None):
    """Создание экземпляра экспортера"""
    return ExcelExporter(json_file_path)


# Тестовые функции
def test_exporter():
    """Тестирование экспортера"""
    print("Тестирование экспорта в Excel с xlsxwriter...")

    exporter = create_exporter("app/data/test_cards.json")

    try:
        # Экспорт в файл
        file_path = exporter.export_to_file("test_xlsxwriter.xlsx")
        print(f"✅ Файл успешно создан: {file_path}")

        # Проверяем размер файла
        import os
        file_size = os.path.getsize(file_path) / 1024
        print(f"📊 Размер файла: {file_size:.2f} KB")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_height_calculation():
    """Тестирование расчета высоты строк"""
    print("\nТестирование расчета высоты строк:")
    print("-" * 50)

    exporter = ExcelExporter()

    # Тестовые случаи
    test_cases = [
        ("Короткий текст", 50, "Короткий текст"),
        ("Средняя длина", 30, "Текст средней длины, который должен уместиться"),
        ("Длинный текст", 20, "Очень длинный текст " * 5),
        ("Многострочный", 40, "Первая строка\nВторая строка\nТретья строка"),
        ("Очень длинный", 15, "Очень длинный текст с множеством слов, который точно не поместится в одну строку " * 3),
    ]

    for test_name, col_width, text in test_cases:
        height = exporter._calculate_row_height(text, col_width)
        lines = text.count('\n') + 1
        print(f"{test_name}:")
        print(f"  Ширина колонки: {col_width} символов")
        print(f"  Количество строк: {lines}")
        print(f"  Длина текста: {len(text)} символов")
        print(f"  Рассчитанная высота: {height} пикселей")
        print()


if __name__ == "__main__":
    # Запуск тестов
    test_height_calculation()

    if test_exporter():
        print("\n✅ Все тесты пройдены успешно!")
    else:
        print("\n❌ Тестирование завершилось с ошибками")
