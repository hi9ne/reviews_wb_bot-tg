import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import logging
from typing import Dict, List, Optional, Any
import json
from pathlib import Path
import jwt
from datetime import datetime, timezone
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from database import Store, get_user_stores, update_store_statistics, session_scope, init_db
import openai

# Настройка логирования
def setup_logging() -> None:
    """Настройка системы логирования"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"wb_bot_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Настраиваем формат логов
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Настраиваем файловый обработчик
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Настраиваем консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Настраиваем корневой логгер
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler, console_handler]
    )
    
    logging.debug(f"Логирование настроено. Файл логов: {log_file}")

# Загрузка конфигурации
def load_config() -> Dict[str, Any]:
    """
    Загрузка конфигурации из .env файла.
    Проверяет наличие всех обязательных параметров.
    """
    load_dotenv()
    
    config = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "WB_API_URL": "https://feedbacks-api.wildberries.ru/api/v1",
        "REVIEWS_PER_PAGE": int(os.getenv("REVIEWS_PER_PAGE", "50")),
        "CHECK_INTERVAL_MINUTES": int(os.getenv("CHECK_INTERVAL_MINUTES", "5")),
        "MAX_RETRIES": int(os.getenv("MAX_RETRIES", "3")),
        "RETRY_DELAY_SECONDS": float(os.getenv("RETRY_DELAY_SECONDS", "0.5")),
        "MAX_CONCURRENT_REQUESTS": int(os.getenv("MAX_CONCURRENT_REQUESTS", "10")),
        "BATCH_SIZE": int(os.getenv("BATCH_SIZE", "50")),
        "OPENAI_TIMEOUT_SECONDS": int(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
        "WB_TIMEOUT_SECONDS": int(os.getenv("WB_TIMEOUT_SECONDS", "5")),
        "RATE_LIMIT_DELAY_SECONDS": float(os.getenv("RATE_LIMIT_DELAY_SECONDS", "1.0"))
    }
    
    # Проверка обязательных параметров
    missing_keys = [key for key, value in config.items() if value is None]
    if missing_keys:
        raise ValueError(f"Отсутствуют обязательные параметры в .env: {', '.join(missing_keys)}")
    
    return config

def check_api_key_expiration(api_key: str) -> bool:
    """Проверка срока действия API ключа Wildberries"""
    try:
        # Декодируем JWT токен без проверки подписи
        decoded = jwt.decode(api_key, options={"verify_signature": False})
        
        # Получаем время истечения срока действия
        exp_timestamp = decoded.get('exp')
        if not exp_timestamp:
            logging.error("В API ключе отсутствует время истечения срока действия")
            return False
            
        # Преобразуем timestamp в datetime
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        current_datetime = datetime.now(timezone.utc)
        
        # Проверяем, не истек ли срок
        if current_datetime > exp_datetime:
            logging.error(f"API ключ истек {exp_datetime}")
            return False
            
        # Вычисляем оставшееся время
        time_left = exp_datetime - current_datetime
        logging.debug(f"API ключ действителен еще {time_left}")
        return True
        
    except Exception as e:
        logging.error(f"Ошибка при проверке API ключа: {e}")
        return False

class WBFeedbackBot:
    def __init__(self, config: Dict[str, Any], store_data: Dict[str, Any]):
        self.config = config
        self.store = store_data
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Используем ThreadPoolExecutor для синхронных вызовов
        self.executor = ThreadPoolExecutor(max_workers=self.config["MAX_CONCURRENT_REQUESTS"])
        # Семафор для ограничения параллельных HTTP-запросов к WB
        self.wb_semaphore = asyncio.Semaphore(self.config["MAX_CONCURRENT_REQUESTS"])
        
        # Инициализация OpenAI клиента
        openai.api_key = self.config["OPENAI_API_KEY"]
        self.openai_client = openai.OpenAI(
            api_key=self.config["OPENAI_API_KEY"],
            timeout=self.config["OPENAI_TIMEOUT_SECONDS"]
        )
    
    async def init_session(self):
        """Инициализация aiohttp сессии"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Закрытие aiohttp сессии"""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_reviews(self) -> List[Dict[str, Any]]:
        """Асинхронное получение всех отзывов с Wildberries"""
        all_reviews: List[Dict[str, Any]] = []
        skip = 0
        take = self.config["REVIEWS_PER_PAGE"]  

        logging.debug(f"Начало получения отзывов для магазина {self.store['name']}...")
        
        # Инициализируем сессию, если она еще не создана
        if not self.session:
            await self.init_session()

        # Сначала получаем неотвеченные отзывы
        logging.debug("Получение неотвеченных отзывов...")
        unanswered_reviews = await self._fetch_reviews(skip, take, is_answered=False)
        if unanswered_reviews:
            all_reviews.extend(unanswered_reviews)
            logging.debug(f"Получено {len(unanswered_reviews)} неотвеченных отзывов")

        # Затем получаем отвеченные отзывы
        logging.debug("Получение отвеченных отзывов...")
        answered_reviews = await self._fetch_reviews(skip, take, is_answered=True)
        if answered_reviews:
            all_reviews.extend(answered_reviews)
            logging.debug(f"Получено {len(answered_reviews)} отвеченных отзывов")

        logging.debug(f"Завершено получение отзывов для магазина {self.store['name']}. Всего найдено: {len(all_reviews)}")
        return all_reviews

    async def _fetch_reviews(self, skip: int, take: int, is_answered: bool) -> List[Dict[str, Any]]:
        """Вспомогательный метод для получения отзывов с пагинацией"""
        reviews: List[Dict[str, Any]] = []
        current_skip = skip

        while True:
            for attempt in range(self.config["MAX_RETRIES"]):
                try:
                    if not self.session:
                        await self.init_session()
                        
                    reviews_url = f"{self.config['WB_API_URL']}/feedbacks"
                    reviews_params = {
                        "skip": current_skip,
                        "take": take,
                        "order": "dateDesc",
                        "isAnswered": str(is_answered).lower()
                    }
                    
                    logging.debug(f"Запрос отзывов для магазина {self.store['name']}: skip={current_skip}, take={take}, isAnswered={is_answered}")
                    
                    async with self.wb_semaphore:
                        async with self.session.get(
                            reviews_url,
                            params=reviews_params,
                            headers={"Authorization": f"Bearer {self.store['wb_api_key']}"},
                            timeout=self.config["WB_TIMEOUT_SECONDS"]
                        ) as response:
                            logging.debug(f"Статус ответа: {response.status}")
                            
                            if response.status == 429:
                                retry_after = int(response.headers.get("Retry-After", "5"))
                                logging.warning(f"Превышен лимит запросов. Ожидание {retry_after} секунд...")
                                await asyncio.sleep(retry_after)
                                continue
                                
                            response.raise_for_status()
                            response_data = await response.json()
                            
                            if not response_data:
                                logging.error("Получен пустой ответ от API")
                                if attempt < self.config["MAX_RETRIES"] - 1:
                                    await asyncio.sleep(self.config["RETRY_DELAY_SECONDS"])
                                    continue
                                return reviews
                                
                            if 'data' not in response_data:
                                logging.error(f"В ответе отсутствует поле 'data': {response_data}")
                                if attempt < self.config["MAX_RETRIES"] - 1:
                                    await asyncio.sleep(self.config["RETRY_DELAY_SECONDS"])
                                    continue
                                return reviews
                            
                            feedbacks = response_data['data'].get('feedbacks', [])
                            
                            if feedbacks:
                                reviews.extend(feedbacks)
                                logging.debug(f"Добавлено {len(feedbacks)} отзывов. Всего: {len(reviews)}")
                            else:
                                logging.debug("Нет новых отзывов для обработки.")
                            
                            current_skip += take
                            
                            if len(feedbacks) < take:
                                logging.debug("Получено меньше отзывов, чем запрошено. Прекращаем пагинацию.")
                                return reviews
                            
                            break
                            
                except aiohttp.ClientError as e:
                    logging.error(f"Ошибка сети при запросе (попытка {attempt + 1}/{self.config['MAX_RETRIES']}): {e}")
                    if attempt < self.config["MAX_RETRIES"] - 1:
                        await asyncio.sleep(self.config["RETRY_DELAY_SECONDS"])
                        continue
                    return reviews
                    
                except asyncio.TimeoutError:
                    logging.error(f"Таймаут при запросе (попытка {attempt + 1}/{self.config['MAX_RETRIES']})")
                    if attempt < self.config["MAX_RETRIES"] - 1:
                        await asyncio.sleep(self.config["RETRY_DELAY_SECONDS"])
                        continue
                    return reviews
                    
                except Exception as e:
                    logging.error(f"Неожиданная ошибка при запросе (попытка {attempt + 1}/{self.config['MAX_RETRIES']}): {str(e)}", exc_info=True)
                    if attempt < self.config["MAX_RETRIES"] - 1:
                        await asyncio.sleep(self.config["RETRY_DELAY_SECONDS"])
                        continue
                    return reviews

        return reviews

    async def process_review(self, review: Dict) -> Optional[Dict]:
        """Асинхронная обработка одного отзыва"""
        feedback_id = review.get('id')
        
        if not feedback_id:
            logging.error("Отсутствует ID отзыва")
            return None
            
        try:
            # Проверяем все возможные поля с текстом отзыва
            review_text = review.get('text', '')
            if not review_text:
                review_text = review.get('pros', '')
            if not review_text:
                review_text = review.get('cons', '')
            if not review_text:
                review_text = review.get('comment', '')
                
            # Если нет текста, но есть оценка - используем её как текст
            if not review_text and review.get('productValuation'):
                review_text = f"Оценка: {review.get('productValuation')} звезд"
            
            if not review_text:
                logging.warning(f"Пропуск отзыва {feedback_id}: отсутствует текст отзыва")
                return None
                
            # Получаем оценку продукта
            product_valuation = review.get('productValuation')
            
            # Генерируем ответ с помощью AI
            response_text = self.generate_ai_response(review_text, product_valuation)
            
            if not response_text:
                logging.error(f"Не удалось сгенерировать ответ для отзыва {feedback_id}")
                return None
                
            # Отправляем ответ
            success = await self.send_response(feedback_id, response_text)
            
            if success:
                logging.info(f"Успешно обработан отзыв {feedback_id}")
                return {
                    'id': feedback_id,
                    'text': review_text,
                    'response': response_text,
                    'valuation': product_valuation,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logging.error(f"Не удалось отправить ответ на отзыв {feedback_id}")
                return None
                
        except Exception as e:
            logging.error(f"Ошибка при обработке отзыва {feedback_id}: {str(e)}", exc_info=True)
            return None

    async def send_response(self, feedback_id: str, text: str) -> bool:
        """Отправляет ответ на отзыв через API Wildberries"""
        url = f"{self.config['WB_API_URL']}/feedbacks/answer"
                    
        headers = {
                            "Authorization": f"Bearer {self.store['wb_api_key']}",
                            "Content-Type": "application/json"
        }
        
        data = {
            "id": feedback_id,
            "text": text
        }
        
        for attempt in range(1, 4):
            try:
                logging.debug(f"Отправка ответа на отзыв {feedback_id} (попытка {attempt}/3)")
                async with self.session.post(url, json=data, headers=headers) as response:
                    if response.status in [200, 204]:
                        logging.info(f"✅ Ответ успешно отправлен на отзыв {feedback_id}")
                        return True
                    else:
                        logging.error(f"Ошибка сети при отправке ответа (попытка {attempt}): {response.status}, {response.reason}")
            except Exception as e:
                logging.error(f"Ошибка сети при отправке ответа (попытка {attempt}): {str(e)}")
            
            if attempt < 3:
                await asyncio.sleep(1)
                
        logging.error(f"Не удалось отправить ответ на отзыв {feedback_id}")
        return False
    
    def generate_ai_response(self, review_text: str, product_valuation: Optional[int]) -> Optional[str]:
        """Генерация ответа с помощью AI с обработкой ошибок"""
        try:
            # Формируем контекст для AI
            context = {
                "review": review_text,
                "valuation": product_valuation,
                "store_name": self.store['name'],
                "prompt": self.store['prompt']
            }
            
            logging.debug(f"Генерация ответа для отзыва: {review_text[:100]}...")
            
            # Формируем запрос к API
            request_data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": self.store['prompt']
                    },
                    {
                        "role": "user",
                        "content": f"Отзыв: {review_text}\nОценка: {product_valuation if product_valuation else 'не указана'}"
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            # Отправляем запрос к API
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=request_data["messages"],
                timeout=self.config["OPENAI_TIMEOUT_SECONDS"]
            )
                
            # Извлекаем сгенерированный ответ
            if not response.choices:
                logging.error("В ответе API отсутствует поле choices")
                return None
                
            return response.choices[0].message.content
            
        except requests.exceptions.Timeout:
            logging.error("Таймаут при запросе к API")
            return None
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при запросе к API: {str(e)}")
            return None
            
        except (KeyError, IndexError) as e:
            logging.error(f"Ошибка при обработке ответа API: {str(e)}")
            return None
            
        except Exception as e:
            logging.error(f"Неожиданная ошибка при генерации ответа: {str(e)}", exc_info=True)
            return None

    async def process_reviews(self) -> None:
        """Обработка всех отзывов с ведением статистики"""
        try:
            logging.info(f"Начало обработки отзывов для магазина {self.store['name']}")
            
            # Получаем все отзывы
            reviews = await self.get_reviews()
            if not reviews:
                logging.info(f"Нет новых отзывов для магазина {self.store['name']}")
                return
                
            logging.info(f"Получено {len(reviews)} отзывов для обработки")
            
            # Статистика обработки
            stats = {
                'total': len(reviews),
                'processed': 0,
                'success': 0,
                'errors': 0,
                'skipped': 0
            }
            
            # Обрабатываем отзывы
            for review in reviews:
                try:
                    result = await self.process_review(review)
                    stats['processed'] += 1
                    
                    if result:
                        stats['success'] += 1
                        logging.info(f"Успешно обработан отзыв {review.get('id')}")
                    else:
                        stats['errors'] += 1
                        logging.error(f"Не удалось обработать отзыв {review.get('id')}")
                        
                except Exception as e:
                    stats['errors'] += 1
                    logging.error(f"Ошибка при обработке отзыва {review.get('id')}: {str(e)}", exc_info=True)
                    
            # Обновляем статистику в базе данных
            try:
                update_store_statistics(
                    store_id=self.store['id'],
                    total_reviews=stats['total'],
                    answered_reviews=stats['success'],
                    last_check_time=datetime.now()
                )
            except Exception as e:
                logging.error(f"Ошибка при обновлении статистики: {str(e)}", exc_info=True)
                
            # Логируем итоговую статистику
            logging.info(
                f"Обработка отзывов завершена для магазина {self.store['name']}:\n"
                f"Всего отзывов: {stats['total']}\n"
                f"Успешно обработано: {stats['success']}\n"
                f"Ошибок: {stats['errors']}\n"
                f"Пропущено: {stats['skipped']}"
            )
            
        except Exception as e:
            logging.error(f"Критическая ошибка при обработке отзывов: {str(e)}", exc_info=True)
            
        finally:
            # Закрываем сессию
            await self.close_session()
        
async def process_all_stores():
    """Параллельная обработка отзывов для всех магазинов"""
    try:
        # Загружаем конфигурацию
        config = load_config()
        
        # Получаем все магазины в рамках одной сессии
        with session_scope() as session:
            stores = session.query(Store).all()
            
            if not stores:
                logging.info("Нет магазинов для обработки")
                return
                
            logging.info(f"Найдено {len(stores)} магазинов для обработки")
            
            # Создаем задачи для каждого магазина
            tasks = []
            for store in stores:
                # Проверяем валидность API ключа
                if not check_api_key_expiration(store.wb_api_key):
                    logging.warning(f"Пропуск магазина {store.name}: недействительный API ключ")
                    continue
                    
                # Создаем копию необходимых данных для бота
                store_data = {
                    'id': store.id,
                    'name': store.name,
                    'wb_api_key': store.wb_api_key,
                    'prompt': store.prompt
                }
                
                bot = WBFeedbackBot(config, store_data)
                task = asyncio.create_task(bot.process_reviews())
                tasks.append((store.name, task))
                
            if not tasks:
                logging.warning("Нет активных задач для обработки")
                return
                
            # Запускаем все задачи параллельно
            logging.info(f"Запуск обработки для {len(tasks)} магазинов")
            results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            # Анализируем результаты
            success_count = 0
            error_count = 0
            
            for (store_name, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    error_count += 1
                    logging.error(f"Ошибка при обработке магазина {store_name}: {str(result)}", exc_info=True)
                else:
                    success_count += 1
                    
            logging.info(
                f"Обработка всех магазинов завершена:\n"
                f"Успешно обработано: {success_count}\n"
                f"Ошибок: {error_count}"
            )
            
    except Exception as e:
        logging.error(f"Критическая ошибка при обработке магазинов: {str(e)}", exc_info=True)
        
    finally:
        # Закрываем все сессии
        for store_name, task in tasks:
            try:
                bot = WBFeedbackBot(config, {'name': store_name})
                await bot.close_session()
            except Exception as e:
                logging.error(f"Ошибка при закрытии сессии для магазина {store_name}: {str(e)}")

async def run_periodic_processing():
    """Периодический запуск обработки отзывов"""
    config = load_config()
    check_interval = config["CHECK_INTERVAL_MINUTES"] * 60
    
    while True:
        try:
            logging.info("Запуск периодической обработки отзывов")
            await process_all_stores()
            
        except Exception as e:
            logging.error(f"Ошибка при периодической обработке: {str(e)}", exc_info=True)
            
        logging.info(f"Ожидание {config['CHECK_INTERVAL_MINUTES']} минут перед следующей проверкой...")
        await asyncio.sleep(check_interval)

if __name__ == "__main__":
    # Настраиваем логирование
    setup_logging()
    
    try:
        # Запускаем периодическую обработку
        asyncio.run(run_periodic_processing())
    except KeyboardInterrupt:
        logging.info("Получен сигнал завершения работы")
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}", exc_info=True)
    finally:
        logging.info("Завершение работы бота")
    