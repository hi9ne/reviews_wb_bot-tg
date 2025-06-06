# Wildberries Reviews Bot

Телеграм-бот для анализа отзывов на Wildberries с использованием OpenAI API.

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/your-username/reviews_wb_bot.git
cd reviews_wb_bot
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
venv\Scripts\activate  # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` и добавьте необходимые переменные окружения:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
```



## Функциональность

- Анализ отзывов на Wildberries
- Генерация ответов с помощью OpenAI
- Сохранение истории в базе данных
- Управление через Telegram бота

## Структура проекта

- `main.py` - основной файл запуска
- `config.py` - конфигурация и настройки
- `database.py` - работа с базой данных
- `openai_service.py` - сервис для работы с OpenAI API
- `telegram_bot.py` - логика Telegram бота
- `models.py` - модели данных
- `utils.py` - вспомогательные функции

## Возможности

- Управление несколькими магазинами через Telegram бота
- Индивидуальные промпты для каждого магазина
- Автоматическая обработка отзывов с использованием DeepSeek AI
- Поддержка различных типов отзывов (текст, оценка)
- Асинхронная обработка для высокой производительности

## Требования

- Python 3.7+
- Telegram Bot Token
- DeepSeek API Key
- Wildberries API Key для каждого магазина

## Безопасность

- API ключи хранятся в базе данных
- Каждый пользователь имеет доступ только к своим магазинам
- Проверка валидности API ключей при добавлении
