from app import app  # Импортируем экземпляр Flask

# Критически важная строка для Vercel!
# Создаем переменную app на верхнем уровне
application = app

# Для локального запуска
if __name__ == "__main__":
    app.run(port=5000, debug=True)
