from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import logging
from datetime import datetime
from contextlib import contextmanager
import os
from dotenv import load_dotenv
import pymysql

# Загрузка переменных окружения
load_dotenv()

# Конфигурация подключения к базе данных
DB_USER = "u3132037_default"
DB_PASSWORD = "YiZJ8l4oDyCPw49d"
DB_HOST = "localhost"  # или IP-адрес сервера, если отличается
DB_NAME = "u3132037_default"

# Создание URL для подключения к базе данных
DATABASE_URL = os.getenv("DATABASE_URL")

# Создание движка SQLAlchemy с явным указанием драйвера
engine = create_engine(DATABASE_URL)

# Создание базового класса для моделей
Base = declarative_base()

# Определение моделей
class Store(Base):
    __tablename__ = 'stores'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    wb_api_key = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=False)
    telegram_user_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    statistics = relationship("StoreStatistics", back_populates="store", uselist=False)

class StoreStatistics(Base):
    __tablename__ = 'store_statistics'
    
    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    total_reviews = Column(Integer, default=0)
    answered_reviews = Column(Integer, default=0)
    last_check_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    store = relationship("Store", back_populates="statistics")

# Создание сессии
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def session_scope():
    """Контекстный менеджер для работы с сессией базы данных"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(bind=engine)

def add_store(name: str, wb_api_key: str, prompt: str, telegram_user_id: str) -> bool:
    """Добавление нового магазина"""
    try:
        with session_scope() as session:
            store = Store(
                name=name,
                wb_api_key=wb_api_key,
                prompt=prompt,
                telegram_user_id=telegram_user_id
            )
            session.add(store)
        return True
    except Exception as e:
        logging.error(f"Ошибка при добавлении магазина: {e}")
        return False

def get_store(name: str) -> Store:
    """Получение магазина по имени"""
    with session_scope() as session:
        return session.query(Store).filter_by(name=name).first()

def get_user_stores(telegram_user_id: str) -> list[Store]:
    """Получение всех магазинов пользователя или всех магазинов, если id не указан"""
    with session_scope() as session:
        if telegram_user_id is None:
            return session.query(Store).all()
        return session.query(Store).filter_by(telegram_user_id=telegram_user_id).all()

def delete_store(name: str, telegram_user_id: str) -> bool:
    """Удаление магазина"""
    try:
        with session_scope() as session:
            store = session.query(Store).filter_by(name=name, telegram_user_id=telegram_user_id).first()
            if store:
                session.delete(store)
                return True
            return False
    except Exception as e:
        logging.error(f"Ошибка при удалении магазина: {e}")
        return False

def get_store_by_api_key(wb_api_key: str) -> Store:
    """Получение магазина по API-ключу"""
    with session_scope() as session:
        return session.query(Store).filter_by(wb_api_key=wb_api_key).first()

def update_store_statistics(store_id: int, total_reviews: int, answered_reviews: int, last_check_time: datetime):
    """Обновление статистики магазина"""
    with session_scope() as session:
        stats = session.query(StoreStatistics).filter(StoreStatistics.store_id == store_id).first()
        if not stats:
            stats = StoreStatistics(store_id=store_id)
            session.add(stats)
        
            stats.total_reviews = total_reviews
            stats.answered_reviews = answered_reviews
        stats.last_check_time = last_check_time
        session.commit()

def get_store_statistics(store_id: int) -> StoreStatistics:
    """Получение статистики магазина"""
    with session_scope() as session:
        return session.query(StoreStatistics).filter_by(store_id=store_id).first() 