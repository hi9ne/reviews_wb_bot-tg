# Wildberries Reviews Bot

<<<<<<< HEAD
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
=======
Бот для автоматического ответа на отзывы в Wildberries с поддержкой нескольких магазинов через Telegram.
>>>>>>> 3fbc23b31498ea9f04595cfef8c26548fdc8465c

## Возможности

- Управление несколькими магазинами через Telegram бота
- Индивидуальные промпты для каждого магазина
- Автоматическая обработка отзывов с использованием DeepSeek AI
- Поддержка различных типов отзывов (текст, оценка)
- Асинхронная обработка для высокой производительности

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd reviews_wb_bot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` в корневой директории проекта со следующими переменными:
```env
TELEGRAM_TOKEN=your_telegram_bot_token
DEEPSEEK_API_KEY=your_deepseek_api_key
REVIEWS_PER_PAGE=50
CHECK_INTERVAL_MINUTES=5
MAX_RETRIES=3
RETRY_DELAY_SECONDS=0.5
MAX_CONCURRENT_REQUESTS=10
BATCH_SIZE=50
DEEPSEEK_TIMEOUT_SECONDS=10
WB_TIMEOUT_SECONDS=5
RATE_LIMIT_DELAY_SECONDS=1.0
```

## Использование

1. Запустите Telegram бота:
```bash
python tg_bot.py
```

2. В Telegram используйте следующие команды:
- `/start` - Начало работы с ботом
- `/help` - Показать справку
- `/add_store` - Добавить новый магазин
- `/list_stores` - Показать список магазинов
- `/delete_store` - Удалить магазин

3. Для добавления магазина вам потребуется:
- Название магазина
- API ключ Wildberries
- Промпт для генерации ответов

## Структура проекта

- `tg_bot.py` - Telegram бот для управления магазинами
- `wb_bot.py` - Основной код для работы с API Wildberries
- `database.py` - Работа с базой данных
- `requirements.txt` - Зависимости проекта
- `.env` - Конфигурация (создается вручную)

## Требования

- Python 3.7+
- Telegram Bot Token
- DeepSeek API Key
- Wildberries API Key для каждого магазина

## Безопасность

- API ключи хранятся в базе данных
- Каждый пользователь имеет доступ только к своим магазинам
- Проверка валидности API ключей при добавлении
