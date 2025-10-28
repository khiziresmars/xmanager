#!/bin/bash

##############################################################################
# XUI-Manager Installation Script
# Автоматическая установка и настройка XUI-Manager для работы с 3x-ui
##############################################################################

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции вывода
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  $1"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    print_error "Пожалуйста, запустите скрипт с правами root (sudo)"
    exit 1
fi

print_header "XUI-Manager - Автоматическая установка"

# 1. Проверка наличия 3x-ui
print_info "Шаг 1/8: Проверка наличия 3x-ui..."

XUI_DB="/etc/x-ui/x-ui.db"
XUI_INSTALLED=false

if [ -f "$XUI_DB" ]; then
    print_success "Найдена база данных 3x-ui: $XUI_DB"
    XUI_INSTALLED=true
elif systemctl list-units --full -all | grep -Fq "x-ui.service"; then
    print_success "Найден сервис x-ui"
    XUI_INSTALLED=true
elif command -v x-ui &> /dev/null; then
    print_success "Найдена команда x-ui"
    XUI_INSTALLED=true
fi

if [ "$XUI_INSTALLED" = false ]; then
    print_warning "3x-ui не найден на сервере"
    read -p "Хотите установить 3x-ui сейчас? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Установка 3x-ui..."
        bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
        print_success "3x-ui установлен"
    else
        print_error "XUI-Manager требует наличия 3x-ui"
        exit 1
    fi
fi

# Определение пути к БД
if [ ! -f "$XUI_DB" ]; then
    print_warning "База данных не найдена по стандартному пути"
    read -p "Введите полный путь к x-ui.db: " XUI_DB
    if [ ! -f "$XUI_DB" ]; then
        print_error "Файл $XUI_DB не существует"
        exit 1
    fi
fi

print_success "Путь к БД: $XUI_DB"

# 2. Установка системных зависимостей
print_info "Шаг 2/8: Установка системных зависимостей..."

apt update -qq
apt install -y python3 python3-pip nginx sqlite3 git curl

print_success "Системные пакеты установлены"

# 3. Проверка версии Python
print_info "Шаг 3/9: Проверка версии Python..."

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "Требуется Python 3.8 или выше (найден $PYTHON_VERSION)"
    exit 1
fi

print_success "Python $PYTHON_VERSION - OK"

# 4. Установка Python зависимостей
print_info "Шаг 4/9: Установка Python зависимостей..."

pip3 install -q fastapi uvicorn pydantic python-multipart pydantic-settings aiofiles jinja2

print_success "Python пакеты установлены"

# 5. Копирование файлов
print_info "Шаг 5/9: Копирование файлов проекта..."

INSTALL_DIR="/opt/xui-manager"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Если скрипт запущен не из /opt/xui-manager
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    print_info "Копирование из $SCRIPT_DIR в $INSTALL_DIR..."

    # Создаем директорию если не существует
    mkdir -p "$INSTALL_DIR"

    # Копируем файлы
    rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        --exclude='*.log' --exclude='.env' \
        "$SCRIPT_DIR/" "$INSTALL_DIR/"

    print_success "Файлы скопированы"
else
    print_success "Файлы уже находятся в $INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Создание необходимых директорий
print_info "Создание рабочих директорий..."
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/backups"
mkdir -p "$INSTALL_DIR/app"
mkdir -p "$INSTALL_DIR/templates"

print_success "Директории созданы"

# Создание .env если не существует
if [ ! -f "$INSTALL_DIR/.env" ]; then
    print_info "Создание файла конфигурации .env..."
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"

    # Обновляем путь к БД в .env
    sed -i "s|XUI_DB_PATH=.*|XUI_DB_PATH=$XUI_DB|g" "$INSTALL_DIR/.env"

    print_success "Файл .env создан"
fi

# 6. Создание systemd сервиса
print_info "Шаг 6/9: Создание systemd сервиса..."

cat > /etc/systemd/system/xui-manager.service <<EOF
[Unit]
Description=XUI Manager API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 -m app.main
Restart=always
RestartSec=5
StandardOutput=append:/var/log/xui-manager.log
StandardError=append:/var/log/xui-manager.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xui-manager
systemctl restart xui-manager

sleep 2

if systemctl is-active --quiet xui-manager; then
    print_success "Сервис xui-manager запущен"
else
    print_error "Ошибка запуска сервиса xui-manager"
    print_info "Проверьте логи: journalctl -u xui-manager -n 50"
    exit 1
fi

# 7. Настройка Nginx
print_info "Шаг 7/9: Настройка Nginx..."

# Получение доменного имени
DOMAIN=$(hostname -f 2>/dev/null || hostname)
read -p "Введите доменное имя [По умолчанию: $DOMAIN]: " INPUT_DOMAIN
DOMAIN="${INPUT_DOMAIN:-$DOMAIN}"

print_info "Настройка для домена: $DOMAIN"

# Проверка существующей конфигурации
NGINX_CONFIG="/etc/nginx/sites-available/xui-manager"

if [ -f "$NGINX_CONFIG" ]; then
    print_warning "Конфигурация Nginx уже существует"
    read -p "Перезаписать конфигурацию? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Пропускаем настройку Nginx"
        SKIP_NGINX=true
    fi
fi

if [ "$SKIP_NGINX" != true ]; then
    # Определение портов X-UI
    XUI_PORT=2096
    if command -v x-ui &> /dev/null; then
        # Попытка определить порт из конфигурации
        XUI_PORT_FROM_CONFIG=$(x-ui status 2>/dev/null | grep -oP 'port:\s*\K\d+' || echo "2096")
        XUI_PORT="${XUI_PORT_FROM_CONFIG:-2096}"
    fi

    print_info "Порт X-UI: $XUI_PORT"

    cat > "$NGINX_CONFIG" <<EOF
# HTTP -> HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;

    # SSL configuration (update paths after getting certificates)
    # ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    # Temporary self-signed certificate
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    add_header Strict-Transport-Security "max-age=63072000" always;

    # X-UI Panel
    location /esmars/ {
        proxy_pass http://127.0.0.1:$XUI_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_redirect off;
    }

    # XUI-Manager API
    location /manager/ {
        proxy_pass http://127.0.0.1:8888/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    # Активация конфигурации
    ln -sf "$NGINX_CONFIG" /etc/nginx/sites-enabled/xui-manager

    # Проверка конфигурации
    if nginx -t 2>/dev/null; then
        systemctl reload nginx
        print_success "Nginx настроен и перезагружен"
    else
        print_error "Ошибка в конфигурации Nginx"
        nginx -t
    fi
fi

# 8. Получение SSL сертификата (опционально)
print_info "Шаг 8/9: SSL сертификат..."

if [ "$SKIP_NGINX" != true ]; then
    read -p "Получить Let's Encrypt SSL сертификат? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Установка certbot..."
        apt install -y certbot python3-certbot-nginx

        print_info "Получение сертификата для $DOMAIN..."
        certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || print_warning "Не удалось получить SSL сертификат автоматически"

        # Обновление конфигурации Nginx с настоящими путями
        if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
            sed -i "s|# ssl_certificate /etc/letsencrypt|ssl_certificate /etc/letsencrypt|g" "$NGINX_CONFIG"
            sed -i "/ssl-cert-snakeoil/d" "$NGINX_CONFIG"
            systemctl reload nginx
            print_success "SSL сертификат установлен"
        fi
    fi
fi

# 9. Проверка установки
print_info "Шаг 9/9: Проверка установки..."

# Проверка API
sleep 2
API_RESPONSE=$(curl -s http://localhost:8888/api/health || echo "{}")

if echo "$API_RESPONSE" | grep -q "healthy"; then
    print_success "API работает корректно"
else
    print_warning "API может работать некорректно"
    print_info "Проверьте логи: tail -f /var/log/xui-manager.log"
fi

# Итоговая информация
print_header "Установка завершена!"

echo -e "${GREEN}✅ XUI-Manager успешно установлен!${NC}"
echo ""
echo -e "${BLUE}📋 Информация о доступе:${NC}"
echo ""
echo -e "  🌐 X-UI панель:     ${GREEN}https://$DOMAIN/esmars/${NC}"
echo -e "  💻 XUI-Manager:     ${GREEN}https://$DOMAIN/manager/${NC}"
echo -e "  📚 API документация: ${GREEN}https://$DOMAIN/manager/api/docs${NC}"
echo ""
echo -e "${BLUE}🔧 Полезные команды:${NC}"
echo ""
echo -e "  • Статус сервиса:      ${YELLOW}systemctl status xui-manager${NC}"
echo -e "  • Перезапуск:          ${YELLOW}systemctl restart xui-manager${NC}"
echo -e "  • Просмотр логов:      ${YELLOW}tail -f /var/log/xui-manager.log${NC}"
echo -e "  • Обновление проекта:  ${YELLOW}cd /opt/xui-manager && ./update.sh${NC}"
echo ""
echo -e "${BLUE}📁 Файлы проекта:      ${GREEN}/opt/xui-manager/${NC}"
echo -e "${BLUE}📄 Конфигурация:       ${GREEN}/opt/xui-manager/.env${NC}"
echo -e "${BLUE}📊 База данных:        ${GREEN}$XUI_DB${NC}"
echo ""

if [ "$SKIP_NGINX" != true ] && [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    print_warning "Для получения SSL сертификата выполните:"
    echo -e "  ${YELLOW}certbot --nginx -d $DOMAIN${NC}"
    echo ""
fi

print_success "Готово к работе! 🎉"
