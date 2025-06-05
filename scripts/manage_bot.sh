#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Функция для вывода сообщений
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка наличия PM2
if ! command -v pm2 &> /dev/null; then
    print_error "PM2 не установлен. Устанавливаем..."
    npm install -g pm2
fi

# Функции управления ботом
start_bot() {
    print_message "Запуск бота..."
    pm2 start main.py --name reviews_wb_bot --interpreter python3
    pm2 save
}

stop_bot() {
    print_message "Остановка бота..."
    pm2 stop reviews_wb_bot
    pm2 save
}

restart_bot() {
    print_message "Перезапуск бота..."
    pm2 restart reviews_wb_bot
}

status_bot() {
    print_message "Статус бота:"
    pm2 status reviews_wb_bot
}

logs_bot() {
    print_message "Логи бота:"
    pm2 logs reviews_wb_bot
}

update_bot() {
    print_message "Обновление бота..."
    git pull origin main
    source venv/bin/activate
    pip install -r requirements.txt
    restart_bot
}

# Обработка команд
case "$1" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot
        ;;
    status)
        status_bot
        ;;
    logs)
        logs_bot
        ;;
    update)
        update_bot
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs|update}"
        exit 1
        ;;
esac

exit 0 