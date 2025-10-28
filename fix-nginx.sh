#!/bin/bash

##############################################################################
# XUI-Manager Nginx Configuration Fixer
# Исправляет конфликт с существующей конфигурацией Nginx
##############################################################################

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    print_error "Запустите скрипт с правами root: sudo bash fix-nginx.sh"
    exit 1
fi

print_info "Поиск существующей конфигурации Nginx..."

# Ищем все конфигурации с доменом
DOMAIN=$(grep -r "server_name" /etc/nginx/sites-enabled/ 2>/dev/null | grep -v "#" | grep -oP 'server_name\s+\K[^;]+' | head -1 | tr -d ' ')

if [ -z "$DOMAIN" ]; then
    print_error "Не найдено активных конфигураций Nginx"
    exit 1
fi

print_success "Найден домен: $DOMAIN"

# Ищем основную конфигурацию (не xui-manager)
MAIN_CONFIG=""
for conf in /etc/nginx/sites-enabled/*; do
    if [ -f "$conf" ] && [ "$conf" != "/etc/nginx/sites-enabled/xui-manager" ]; then
        if grep -q "server_name.*$DOMAIN" "$conf" 2>/dev/null; then
            MAIN_CONFIG="$conf"
            break
        fi
    fi
done

if [ -z "$MAIN_CONFIG" ]; then
    print_error "Не найдена основная конфигурация Nginx"
    exit 1
fi

print_success "Найдена основная конфигурация: $MAIN_CONFIG"

# Проверяем, есть ли уже location /manager/
if grep -q "location /manager/" "$MAIN_CONFIG"; then
    print_warning "Location /manager/ уже существует в конфигурации"
    print_info "Проверьте конфигурацию вручную: cat $MAIN_CONFIG"
    exit 0
fi

print_info "Добавляем location /manager/ в существующую конфигурацию..."

# Создаем backup
cp "$MAIN_CONFIG" "${MAIN_CONFIG}.backup-$(date +%Y%m%d-%H%M%S)"
print_success "Backup создан: ${MAIN_CONFIG}.backup-$(date +%Y%m%d-%H%M%S)"

# Ищем последний блок server с портом 443 или 80
TEMP_FILE=$(mktemp)

# Проверяем наличие HTTPS блока
if grep -q "listen.*443.*ssl" "$MAIN_CONFIG"; then
    print_info "Найден HTTPS блок, добавляем в него..."

    # Добавляем location /manager/ перед последней закрывающей скобкой в HTTPS блоке
    awk '
    /listen.*443.*ssl/ { in_https=1 }
    in_https && /^}/ && !added {
        print "    # XUI-Manager API"
        print "    location /manager/ {"
        print "        proxy_pass http://127.0.0.1:8888/;"
        print "        proxy_http_version 1.1;"
        print "        proxy_set_header Upgrade $http_upgrade;"
        print "        proxy_set_header Connection '\''upgrade'\'';"
        print "        proxy_set_header Host $host;"
        print "        proxy_cache_bypass $http_upgrade;"
        print "        proxy_set_header X-Real-IP $remote_addr;"
        print "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
        print "        proxy_set_header X-Forwarded-Proto $scheme;"
        print "    }"
        print ""
        added=1
        in_https=0
    }
    { print }
    ' "$MAIN_CONFIG" > "$TEMP_FILE"

elif grep -q "listen.*80" "$MAIN_CONFIG"; then
    print_info "Найден HTTP блок, добавляем в него..."

    # Добавляем location /manager/ перед последней закрывающей скобкой в HTTP блоке
    awk '
    /listen.*80/ { in_http=1 }
    in_http && /^}/ && !added {
        print "    # XUI-Manager API"
        print "    location /manager/ {"
        print "        proxy_pass http://127.0.0.1:8888/;"
        print "        proxy_http_version 1.1;"
        print "        proxy_set_header Upgrade $http_upgrade;"
        print "        proxy_set_header Connection '\''upgrade'\'';"
        print "        proxy_set_header Host $host;"
        print "        proxy_cache_bypass $http_upgrade;"
        print "        proxy_set_header X-Real-IP $remote_addr;"
        print "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
        print "        proxy_set_header X-Forwarded-Proto $scheme;"
        print "    }"
        print ""
        added=1
        in_http=0
    }
    { print }
    ' "$MAIN_CONFIG" > "$TEMP_FILE"
else
    print_error "Не найден блок server в конфигурации"
    rm "$TEMP_FILE"
    exit 1
fi

# Применяем изменения
mv "$TEMP_FILE" "$MAIN_CONFIG"

print_success "Location /manager/ добавлен в конфигурацию"

# Отключаем конфликтующую конфигурацию xui-manager
if [ -f "/etc/nginx/sites-enabled/xui-manager" ]; then
    print_info "Отключаем конфликтующую конфигурацию xui-manager..."
    rm "/etc/nginx/sites-enabled/xui-manager"
    print_success "Конфликтующая конфигурация отключена"
fi

# Проверяем конфигурацию Nginx
print_info "Проверка конфигурации Nginx..."
if nginx -t 2>/dev/null; then
    print_success "Конфигурация Nginx корректна"

    print_info "Перезагрузка Nginx..."
    systemctl reload nginx
    print_success "Nginx перезагружен"

    echo ""
    print_success "Готово! XUI-Manager доступен по адресу:"
    echo ""
    if grep -q "listen.*443.*ssl" "$MAIN_CONFIG"; then
        echo "  https://$DOMAIN/manager/"
        echo "  https://$DOMAIN/manager/api/docs"
    else
        echo "  http://$DOMAIN/manager/"
        echo "  http://$DOMAIN/manager/api/docs"
    fi
    echo ""
else
    print_error "Ошибка в конфигурации Nginx:"
    nginx -t
    print_warning "Восстанавливаем backup..."
    mv "${MAIN_CONFIG}.backup-"* "$MAIN_CONFIG"
    print_info "Backup восстановлен"
    exit 1
fi

# Проверяем работу API
sleep 1
print_info "Проверка работы API..."
if curl -s http://localhost:8888/api/health | grep -q "healthy"; then
    print_success "API работает корректно"
else
    print_warning "API может работать некорректно"
    print_info "Проверьте логи: journalctl -u xui-manager -n 50"
fi
