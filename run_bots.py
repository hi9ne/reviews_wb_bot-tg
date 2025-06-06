import subprocess
import sys
import os
from threading import Thread
import logging
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('run_bots.log'),
        logging.StreamHandler()
    ]
)

def run_telegram_bot():
    try:
        logging.info("Запуск Telegram бота...")
        subprocess.run([sys.executable, "tg_bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при запуске Telegram бота: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при запуске Telegram бота: {e}")

def run_wb_bot():
    try:
        logging.info("Запуск WB бота...")
        subprocess.run([sys.executable, "wb_bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при запуске WB бота: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при запуске WB бота: {e}")

if __name__ == "__main__":
    logging.info("Начало запуска ботов")
    
    # Создаем потоки для каждого бота
    tg_thread = Thread(target=run_telegram_bot)
    wb_thread = Thread(target=run_wb_bot)
    
    # Запускаем ботов
    tg_thread.start()
    time.sleep(2)  # Даем время первому боту запуститься
    wb_thread.start()
    
    # Ждем завершения обоих ботов
    tg_thread.join()
    wb_thread.join()
    
    logging.info("Боты завершили работу") 