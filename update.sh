#!/bin/bash

##############################################################################
# XUI-Manager Update Script
# Обновление XUI-Manager из GitHub репозитория
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

print_header "XUI-Manager - Обновление"

INSTALL_DIR="/opt/xui-manager"

# Проверка существования установки
if [ ! -d "$INSTALL_DIR" ]; then
    print_error "XUI-Manager не установлен в $INSTALL_DIR"
    print_info "Запустите install.sh для установки"
    exit 1
fi

cd "$INSTALL_DIR"

# Проверка наличия git репозитория
if [ ! -d ".git" ]; then
    print_error "Git репозиторий не инициализирован"
    print_info "Выполните: cd /opt/xui-manager && git init && git remote add origin YOUR_REPO_URL"
    exit 1
fi

# 1. Сохранение текущей конфигурации
print_info "Шаг 1/6: Сохранение текущей конфигурации..."

# Создаем резервную копию .env
if [ -f ".env" ]; then
    cp .env .env.backup
    print_success ".env сохранен"
fi

# Создаем резервную копию БД (если есть)
if [ -f "/etc/x-ui/x-ui.db" ]; then
    cp /etc/x-ui/x-ui.db "/etc/x-ui/x-ui.db.backup-$(date +%Y%m%d-%H%M%S)"
    print_success "Резервная копия БД создана"
fi

# 2. Проверка изменений
print_info "Шаг 2/6: Проверка локальных изменений..."

if [ -n "$(git status --porcelain)" ]; then
    print_warning "Обнаружены локальные изменения:"
    git status --short
    echo ""
    read -p "Сохранить изменения перед обновлением? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git stash save "Auto-stash before update $(date +%Y-%m-%d_%H:%M:%S)"
        print_success "Изменения сохранены в stash"
        STASHED=true
    fi
fi

# 3. Получение обновлений
print_info "Шаг 3/6: Получение обновлений из репозитория..."

git fetch origin

# Получение имени текущей ветки
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
print_info "Текущая ветка: $CURRENT_BRANCH"

# Проверка наличия обновлений
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/$CURRENT_BRANCH)

if [ "$LOCAL" = "$REMOTE" ]; then
    print_success "Уже используется последняя версия"

    # Восстановление stash если был
    if [ "$STASHED" = true ]; then
        print_info "Восстановление локальных изменений..."
        git stash pop
    fi

    exit 0
else
    print_info "Найдены обновления, применяем..."
    git pull origin "$CURRENT_BRANCH"
    print_success "Обновления загружены"
fi

# 4. Восстановление конфигурации
print_info "Шаг 4/6: Восстановление конфигурации..."

if [ -f ".env.backup" ]; then
    # Сравниваем .env.example с существующим .env
    if [ -f ".env.example" ]; then
        # Проверяем, есть ли новые параметры в .env.example
        NEW_PARAMS=$(comm -13 <(grep -v '^#' .env.backup | grep '=' | cut -d'=' -f1 | sort) \
                              <(grep -v '^#' .env.example | grep '=' | cut -d'=' -f1 | sort))

        if [ -n "$NEW_PARAMS" ]; then
            print_warning "Обнаружены новые параметры конфигурации:"
            echo "$NEW_PARAMS"
            print_info "Добавляем их в .env..."

            # Добавляем новые параметры
            echo "" >> .env.backup
            echo "# New parameters added during update" >> .env.backup
            while IFS= read -r param; do
                grep "^$param=" .env.example >> .env.backup
            done <<< "$NEW_PARAMS"
        fi
    fi

    mv .env.backup .env
    print_success "Конфигурация восстановлена"
fi

# Восстановление stash если был
if [ "$STASHED" = true ]; then
    print_info "Восстановление локальных изменений..."
    if git stash pop; then
        print_success "Локальные изменения восстановлены"
    else
        print_warning "Конфликт при восстановлении изменений"
        print_info "Разрешите конфликты вручную: git status"
    fi
fi

# 5. Обновление зависимостей
print_info "Шаг 5/6: Обновление зависимостей..."

pip3 install -q --upgrade fastapi uvicorn pydantic python-multipart pydantic-settings

print_success "Зависимости обновлены"

# 6. Перезапуск сервиса
print_info "Шаг 6/6: Перезапуск сервиса..."

systemctl restart xui-manager

sleep 2

if systemctl is-active --quiet xui-manager; then
    print_success "Сервис xui-manager перезапущен"
else
    print_error "Ошибка перезапуска сервиса"
    print_info "Проверьте логи: journalctl -u xui-manager -n 50"
    exit 1
fi

# Проверка API
API_RESPONSE=$(curl -s http://localhost:8888/api/health || echo "{}")

if echo "$API_RESPONSE" | grep -q "healthy"; then
    print_success "API работает корректно"
else
    print_warning "API может работать некорректно"
    print_info "Проверьте логи: tail -f /var/log/xui-manager.log"
fi

# Итоговая информация
print_header "Обновление завершено!"

echo -e "${GREEN}✅ XUI-Manager успешно обновлен!${NC}"
echo ""
echo -e "${BLUE}📋 Информация о версии:${NC}"
echo ""
echo -e "  • Текущий коммит: ${GREEN}$(git rev-parse --short HEAD)${NC}"
echo -e "  • Ветка: ${GREEN}$CURRENT_BRANCH${NC}"
echo -e "  • Дата обновления: ${GREEN}$(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""
echo -e "${BLUE}🔧 Полезные команды:${NC}"
echo ""
echo -e "  • Просмотр логов:   ${YELLOW}tail -f /var/log/xui-manager.log${NC}"
echo -e "  • Статус сервиса:   ${YELLOW}systemctl status xui-manager${NC}"
echo -e "  • История изменений: ${YELLOW}git log --oneline -10${NC}"
echo ""

print_success "Готово! 🎉"
