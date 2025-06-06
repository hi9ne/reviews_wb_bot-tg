import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import asyncio
from database import (
    add_store, 
    get_store, 
    get_user_stores, 
    delete_store, 
    get_store_by_api_key, 
    Session, 
    Store,
    get_store_statistics,
    update_store_statistics
)
from wb_bot import WBFeedbackBot, check_api_key_expiration
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database import Store
from database import session_scope

# Загрузка конфигурации
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Состояния для FSM
class States:
    WAITING_FOR_STORE_NAME = 1
    WAITING_FOR_API_KEY = 2
    WAITING_FOR_PROMPT = 3
    WAITING_FOR_EDIT_PROMPT = 4

# Словарь для хранения временных данных пользователей
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот для управления автоответчиком на отзывы Wildberries.\n\n"
        "Доступные команды:\n"
        "/add_store - Добавить новый магазин\n"
        "/list_stores - Показать список магазинов\n"
        "/delete_store - Удалить магазин\n"
        "/edit_prompt - Изменить промпт магазина\n"
        "/stats - Показать статистику\n"
        "/status - Проверить статус бота\n"
        "/help - Показать справку"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📚 Справка по командам:\n\n"
        "/add_store - Добавить новый магазин. Вам нужно будет указать:\n"
        "1. Название магазина\n"
        "2. API ключ Wildberries\n"
        "3. Промпт для генерации ответов\n\n"
        "/list_stores - Показать список ваших магазинов\n"
        "/delete_store - Удалить магазин из списка\n"
        "/edit_prompt - Изменить промпт для существующего магазина\n"
        "/stats - Показать статистику ответов на отзывы\n"
        "/status - Проверить статус бота и API ключей\n"
        "/help - Показать это сообщение"
    )

async def add_store_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления магазина"""
    user_id = update.effective_user.id
    user_data[user_id] = {}
    context.user_data['state'] = States.WAITING_FOR_STORE_NAME
    
    await update.message.reply_text(
        "Введите название магазина:\n"
        "Используйте /cancel для отмены."
    )

async def handle_store_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия магазина"""
    user_id = update.effective_user.id
    store_name = update.message.text
    
    # Проверяем, не существует ли уже магазин с таким названием
    existing_store = get_store(store_name)
    if existing_store:
        await update.message.reply_text(
            "❌ Магазин с таким названием уже существует. Пожалуйста, выберите другое название:\n"
            "Используйте /cancel для отмены."
        )
        return
    
    user_data[user_id]['store_name'] = store_name
    context.user_data['state'] = States.WAITING_FOR_API_KEY
    
    await update.message.reply_text(
        "Введите API ключ Wildberries:\n"
        "Используйте /cancel для отмены."
    )

async def handle_wb_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wb_api_key = update.message.text

    # Проверяем валидность API ключа
    if not check_api_key_expiration(wb_api_key):
        await update.message.reply_text(
            "❌ Недействительный API ключ. Пожалуйста, проверьте и введите правильный ключ:\n"
            "Используйте /cancel для отмены."
        )
        return

    # Проверяем, существует ли магазин с таким API-ключом
    existing_store = get_store_by_api_key(wb_api_key)
    if existing_store:
        await update.message.reply_text(
            "❌ Магазин с таким API-ключом уже существует. Пожалуйста, введите другой ключ:\n"
            "Используйте /cancel для отмены."
        )
        return

    user_data[user_id]['wb_api_key'] = wb_api_key
    context.user_data['state'] = States.WAITING_FOR_PROMPT
    await update.message.reply_text(
        "Введите промпт для генерации ответов на отзывы. "
        "Этот текст будет использоваться как системный промпт для AI.\n\n"
        "Пример:\n"
        "Ты — вежливый помощник продавца детской одежды. "
        "Отвечай кратко и по существу, сохраняя дружелюбный тон.\n\n"
        "Используйте /cancel для отмены."
    )

async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода промпта и сохранение магазина"""
    user_id = update.effective_user.id
    prompt = update.message.text
    
    # Сохраняем магазин в базу данных
    success = add_store(
        name=user_data[user_id]['store_name'],
        wb_api_key=user_data[user_id]['wb_api_key'],
        prompt=prompt,
        telegram_user_id=user_id
    )
    
    if success:
        await update.message.reply_text(
            "✅ Магазин успешно добавлен!\n\n"
            f"Название: {user_data[user_id]['store_name']}\n"
            "Теперь бот будет автоматически отвечать на отзывы для этого магазина."
        )
    else:
        await update.message.reply_text(
            "❌ Произошла ошибка при добавлении магазина. Пожалуйста, попробуйте снова."
        )
    
    # Очищаем данные пользователя
    del user_data[user_id]
    context.user_data['state'] = None

async def list_stores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список магазинов пользователя"""
    user_id = update.effective_user.id
    
    try:
        with session_scope() as session:
            stores = session.query(Store).filter_by(telegram_user_id=user_id).all()
            
            if not stores:
                await update.message.reply_text(
                    "У вас пока нет добавленных магазинов. Используйте /add_store для добавления."
                )
                return
            
            message = "📋 Ваши магазины:\n\n"
            for store in stores:
                message += f"🏪 {store.name}\n"
            
            await update.message.reply_text(message)
    except Exception as e:
        logging.error(f"Ошибка при получении списка магазинов: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при получении списка магазинов. Пожалуйста, попробуйте позже."
        )

async def delete_store_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды удаления магазина"""
    user_id = update.effective_user.id
    
    with session_scope() as session:
        # Получаем список магазинов пользователя
        stores = session.query(Store).filter(Store.telegram_user_id == user_id).all()
        
        if not stores:
            await update.message.reply_text("У вас нет добавленных магазинов.")
            return
            
        # Создаем клавиатуру с кнопками для каждого магазина
        keyboard = []
        for store in stores:
            keyboard.append([InlineKeyboardButton(store.name, callback_data=f"delete_{store.id}")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Выберите магазин для удаления:",
            reply_markup=reply_markup
        )

async def delete_store_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатия на кнопку удаления магазина"""
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("delete_"):
        return
        
    store_id = int(query.data.split("_")[1])
    user_id = update.effective_user.id
    
    with session_scope() as session:
        # Проверяем существование магазина и права доступа
        store = session.query(Store).filter(
            Store.id == store_id,
            Store.telegram_user_id == user_id
        ).first()
        
        if not store:
            await query.edit_message_text("Магазин не найден или у вас нет прав для его удаления.")
            return
            
        store_name = store.name
        session.delete(store)
        session.commit()
        
        await query.edit_message_text(f"Магазин '{store_name}' успешно удален.")

async def edit_prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса редактирования промпта"""
    user_id = update.effective_user.id
    
    try:
        with session_scope() as session:
            stores = session.query(Store).filter_by(telegram_user_id=user_id).all()
            
            if not stores:
                await update.message.reply_text(
                    "У вас нет магазинов для редактирования."
                )
                return
            
            keyboard = []
            for store in stores:
                # Получаем имя магазина до закрытия сессии
                store_name = store.name
                keyboard.append([InlineKeyboardButton(store_name, callback_data=f"edit_{store_name}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Выберите магазин для редактирования промпта:",
                reply_markup=reply_markup
            )
    except Exception as e:
        logging.error(f"Ошибка при получении списка магазинов: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Пожалуйста, попробуйте снова."
        )

async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия на кнопку редактирования промпта"""
    query = update.callback_query
    await query.answer()
    
    store_name = query.data.replace("edit_", "")
    user_id = update.effective_user.id
    
    try:
        with session_scope() as session:
            # Получаем магазин
            store = session.query(Store).filter_by(name=store_name, telegram_user_id=user_id).first()
            
            if not store:
                await query.edit_message_text(
                    "❌ Магазин не найден или у вас нет прав на его редактирование."
                )
                return
            
            # Сохраняем имя магазина для последующего редактирования
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]['store_name'] = store_name
            context.user_data['state'] = States.WAITING_FOR_EDIT_PROMPT
            
            # Получаем текущий промпт
            current_prompt = store.prompt
            
            await query.edit_message_text(
                f"Текущий промпт для магазина {store_name}:\n\n{current_prompt}\n\n"
                "Введите новый промпт:"
            )
    except Exception as e:
        logging.error(f"Ошибка при получении информации о магазине: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка. Пожалуйста, попробуйте снова."
        )

async def handle_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода нового промпта"""
    user_id = update.effective_user.id
    new_prompt = update.message.text
    
    if 'store_name' not in user_data.get(user_id, {}):
        await update.message.reply_text(
            "❌ Ошибка: не найден магазин для редактирования. Попробуйте снова с команды /edit_prompt"
        )
        del user_data[user_id]
        context.user_data['state'] = None
        return
    
    store_name = user_data[user_id]['store_name']
    
    try:
        with session_scope() as session:
            # Получаем магазин
            store = session.query(Store).filter_by(name=store_name, telegram_user_id=user_id).first()
            
            if not store:
                await update.message.reply_text(
                    "❌ Магазин не найден или у вас нет прав на его редактирование."
                )
                del user_data[user_id]
                context.user_data['state'] = None
                return
            
            # Обновляем промпт
            store.prompt = new_prompt
            session.commit()
            
            # Проверяем, что изменения сохранились
            session.refresh(store)
            if store.prompt != new_prompt:
                raise Exception("Не удалось сохранить изменения в базу данных")
            
            await update.message.reply_text(
                f"✅ Промпт для магазина {store_name} успешно обновлен!\n\n"
                f"Новый промпт:\n{new_prompt}"
            )
    except Exception as e:
        logging.error(f"Ошибка при обновлении промпта: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обновлении промпта. Пожалуйста, попробуйте снова."
        )
    
    del user_data[user_id]
    context.user_data['state'] = None

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику по магазинам"""
    user_id = update.effective_user.id
    
    try:
        with session_scope() as session:
            stores = session.query(Store).filter_by(telegram_user_id=user_id).all()
            
            if not stores:
                await update.message.reply_text(
                    "У вас пока нет добавленных магазинов."
                )
                return
            
            message = "📊 Статистика по магазинам:\n\n"
            
            for store in stores:
                stats = get_store_statistics(store.id)
                api_key_valid = check_api_key_expiration(store.wb_api_key)
                
                message += f"🏪 {store.name}\n"
                if stats:
                    message += f"Всего отзывов: {stats.total_reviews}\n"
                    message += f"Отвечено: {stats.answered_reviews}\n"
                    message += f"Последняя проверка: {stats.last_check_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                else:
                    message += "Статистика пока недоступна\n"
                message += f"API ключ: {'✅ Действителен' if api_key_valid else '❌ Недействителен'}\n\n"
            
            await update.message.reply_text(message)
    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при получении статистики. Пожалуйста, попробуйте позже."
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса бота и API ключей"""
    user_id = update.effective_user.id
    
    try:
        with session_scope() as session:
            stores = session.query(Store).filter_by(telegram_user_id=user_id).all()
            
            if not stores:
                await update.message.reply_text(
                    "У вас пока нет добавленных магазинов."
                )
                return
            
            message = "🔍 Статус бота и API ключей:\n\n"
            
            for store in stores:
                api_key_valid = check_api_key_expiration(store.wb_api_key)
                message += f"🏪 {store.name}\n"
                message += f"API ключ: {'✅ Действителен' if api_key_valid else '❌ Недействителен'}\n\n"
            
            await update.message.reply_text(message)
    except Exception as e:
        logging.error(f"Ошибка при проверке статуса: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при проверке статуса. Пожалуйста, попробуйте позже."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех текстовых сообщений"""
    if 'state' not in context.user_data:
        await update.message.reply_text(
            "Используйте команды для управления ботом. /help для справки."
        )
        return
    
    # Проверяем, не является ли сообщение командой
    if update.message.text.startswith('/'):
        # Если это команда /cancel, отменяем текущее действие
        if update.message.text == '/cancel':
            user_id = update.effective_user.id
            if user_id in user_data:
                del user_data[user_id]
            context.user_data['state'] = None
            await update.message.reply_text(
                "❌ Действие отменено. Используйте команды для управления ботом."
            )
            return
        # Для других команд просто игнорируем их во время ожидания ввода
        await update.message.reply_text(
            "⚠️ Сначала завершите текущее действие или используйте /cancel для отмены."
        )
        return
    
    state = context.user_data['state']
    
    if state == States.WAITING_FOR_STORE_NAME:
        await handle_store_name(update, context)
    elif state == States.WAITING_FOR_API_KEY:
        await handle_wb_api_key(update, context)
    elif state == States.WAITING_FOR_PROMPT:
        await handle_prompt(update, context)
    elif state == States.WAITING_FOR_EDIT_PROMPT:
        await handle_edit_prompt(update, context)

def main():
    """Запуск бота"""
    # Настройка логирования
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Настройка меню команд
    commands = [
        ("start", "Запустить бота"),
        ("help", "Показать справку"),
        ("add_store", "Добавить новый магазин"),
        ("list_stores", "Показать список магазинов"),
        ("delete_store", "Удалить магазин"),
        ("edit_prompt", "Изменить промпт магазина"),
        ("stats", "Показать статистику"),
        ("status", "Проверить статус бота"),
        ("cancel", "Отменить текущее действие")
    ]
    
    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_store", add_store_command))
    application.add_handler(CommandHandler("list_stores", list_stores))
    application.add_handler(CommandHandler("delete_store", delete_store_command))
    application.add_handler(CommandHandler("edit_prompt", edit_prompt_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", handle_message))
    application.add_handler(CallbackQueryHandler(delete_store_callback, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(handle_edit_callback, pattern="^edit_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Установка меню команд
    async def post_init(application: Application) -> None:
        await application.bot.set_my_commands(commands)
    
    application.post_init = post_init
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main() 