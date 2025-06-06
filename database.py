from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import logging
from datetime import datetime
from contextlib import contextmanager

Base = declarative_base()

class Store(Base):
    __tablename__ = 'stores'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    wb_api_key = Column(String(500), nullable=False)
    prompt = Column(Text, nullable=False)
    telegram_user_id = Column(Integer, nullable=False)
    statistics = relationship("StoreStatistics", back_populates="store", uselist=False)

class StoreStatistics(Base):
    __tablename__ = 'store_statistics'
    
    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    total_reviews = Column(Integer, default=0)
    answered_reviews = Column(Integer, default=0)
    last_check_time = Column(DateTime, default=datetime.utcnow)
    store = relationship("Store", back_populates="statistics")

# Создаем базу данных
engine = create_engine('sqlite:///stores.db', echo=True)
Base.metadata.create_all(engine)

# Создаем фабрику сессий
Session = sessionmaker(bind=engine)

@contextmanager
def session_scope():
    """Контекстный менеджер для работы с сессиями"""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def add_store(name: str, wb_api_key: str, prompt: str, telegram_user_id: int) -> bool:
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

def get_user_stores(telegram_user_id: int) -> list[Store]:
    """Получение всех магазинов пользователя или всех магазинов, если id не указан"""
    with session_scope() as session:
        if telegram_user_id is None:
            return session.query(Store).all()
        return session.query(Store).filter_by(telegram_user_id=telegram_user_id).all()

def delete_store(name: str, telegram_user_id: int) -> bool:
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

def update_store_statistics(store_id: int, total_reviews: int = None, answered_reviews: int = None) -> bool:
    """Обновление статистики магазина"""
    try:
        with session_scope() as session:
            stats = session.query(StoreStatistics).filter_by(store_id=store_id).first()
            
            if not stats:
                stats = StoreStatistics(store_id=store_id)
                session.add(stats)
            
            if total_reviews is not None:
                stats.total_reviews = total_reviews
            if answered_reviews is not None:
                stats.answered_reviews = answered_reviews
                
            stats.last_check_time = datetime.utcnow()
        return True
    except Exception as e:
        logging.error(f"Ошибка при обновлении статистики: {e}")
        return False

def get_store_statistics(store_id: int) -> StoreStatistics:
    """Получение статистики магазина"""
    with session_scope() as session:
        return session.query(StoreStatistics).filter_by(store_id=store_id).first() 