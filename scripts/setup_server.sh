#!/bin/bash

# Установка необходимых пакетов
sudo apt update
sudo apt install -y python3-pip python3-venv git nodejs npm

# Установка PM2
sudo npm install -g pm2

# Создание директории для бота
mkdir -p ~/reviews_wb_bot
cd ~/reviews_wb_bot

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Создание файла .env если его нет
if [ ! -f .env ]; then
    echo "Создайте файл .env с необходимыми переменными окружения"
    touch .env
fi

# Настройка PM2 для автозапуска
pm2 startup
pm2 start main.py --name reviews_wb_bot
pm2 save 