# XUI Manager - 3x-ui Control Panel Agent

[English](#english) | [Русский](#russian)

---

<a name="english"></a>
# English

Modern web interface and REST API for managing 3x-ui panel users with advanced automation features.

**Works with any version of 3x-ui** - automatically detects database schema

## Quick Installation

```bash
git clone https://github.com/khiziresmars/xmanager.git
cd xmanager
sudo bash install.sh
```

The script will automatically:
- Create Python virtual environment
- Install all dependencies
- Configure systemd service
- Integrate with Nginx
- Obtain Let's Encrypt SSL certificate

**Requirements:**
- OS: Debian 11+, Ubuntu 20.04+
- Python 3.8+
- 3x-ui (any version)
- Root access

**After installation:** `https://your-domain/manager/`

---

## Features

### User Management
- Create up to 5000 users via queue system
- Bulk operations (create, delete, block)
- Support for VLESS, Trojan, VMess, Shadowsocks
- Search by email, filter by inbound
- Traffic and expiry management

### Inbound Management
- Visual inbound editor with tabs (Basic, Transport, Security, Advanced)
- X25519 key generation for Reality
- UUID, Short ID, random port/path generation
- Support for all transport types (WS, gRPC, HTTPUpgrade, SplitHTTP)
- Nginx configuration generation

### Automation
- Scheduled backups with retention policy
- SSL certificate monitoring and auto-renewal
- Service health monitoring (X-UI, Nginx, WARP)
- WARP status checking and auto-restart

### Monitoring
- Online users tracking
- CPU/Memory/Disk usage
- Network statistics
- Server uptime

### Security
- Panel credentials management
- Nginx camouflage with fake websites (170+ templates)
- Bot blocking (Clash, Hiddify, V2box user-agents)
- SNI scanner for Reality targets

---

## Complete API Reference

### Authentication
```
POST /api/auth/login          - Login with credentials
POST /api/auth/logout         - Logout
POST /api/tokens/generate     - Generate API token
GET  /api/tokens              - List API tokens
DELETE /api/tokens/{id}       - Delete token
```

### Users
```
GET    /api/users              - List all users (paginated)
POST   /api/users              - Create single user
DELETE /api/users/{id}         - Delete user
PUT    /api/users/{id}/toggle  - Enable/disable user
PUT    /api/users/{id}/expiry  - Set expiry time
PUT    /api/users/{id}/traffic - Set traffic limit
POST   /api/users/bulk-create  - Create up to 100 users
GET    /api/users/by-email/{email} - Find user by email
GET    /api/users/unlimited    - List unlimited users
GET    /api/users/low-traffic  - List low traffic users
GET    /api/users/expired      - List expired users
GET    /api/users/disabled     - List disabled users
POST   /api/users/reset-traffic - Reset traffic for users
POST   /api/users/add-traffic  - Add traffic to users
POST   /api/users/set-limit    - Set traffic limit for users
POST   /api/users/extend-expiry - Extend expiry for users
POST   /api/users/toggle-status - Bulk enable/disable
```

### Queues
```
POST   /api/queues/bulk-create - Create up to 5000 users via queue
GET    /api/queues             - List all queues
GET    /api/queues/{id}        - Get queue status
POST   /api/queues/{id}/cancel - Cancel queue
DELETE /api/queues/{id}        - Delete queue
```

### Inbounds
```
GET    /api/inbounds           - List all inbounds
GET    /api/inbounds/{id}      - Get inbound details
GET    /api/inbounds/{id}/full - Get full inbound with parsed settings
PUT    /api/inbounds/{id}      - Update inbound
POST   /api/inbounds/import    - Import inbound from template
POST   /api/inbounds/toggle    - Enable/disable inbound
GET    /api/inbounds/templates - Get preset templates
```

### Generator (Xray Values)
```
GET  /api/generator/uuid       - Generate UUID
GET  /api/generator/x25519     - Generate X25519 key pair
GET  /api/generator/short-id   - Generate short ID
GET  /api/generator/password   - Generate password
GET  /api/generator/credentials - Generate full credentials set
GET  /api/generator/available-port - Find available port
GET  /api/generator/sni-targets - Get recommended SNI targets
GET  /api/generator/fingerprints - Get browser fingerprints
GET  /api/generator/inbound-types - Get available inbound types
GET  /api/generator/ss-password - Generate Shadowsocks password
POST /api/generator/vless-reality - Generate VLESS+Reality config
POST /api/generator/inbound    - Generate inbound by template type
```

### Automation
```
GET  /api/automation/status    - Get automation status
GET  /api/automation/settings  - Get automation settings
PUT  /api/automation/settings  - Update automation settings
GET  /api/automation/services  - Get services status
POST /api/automation/service/{name}/restart - Restart service
```

### Backups
```
GET    /api/automation/backups  - List all backups
POST   /api/automation/backup/create - Create backup
POST   /api/automation/backup/restore/{name} - Restore from backup
DELETE /api/automation/backup/{name} - Delete backup
```

### SSL Certificates
```
GET  /api/automation/ssl/check - Check SSL certificates
POST /api/automation/ssl/renew - Renew SSL certificates
```

### WARP
```
GET  /api/automation/warp/status  - Get WARP status
POST /api/automation/warp/restart - Restart WARP
```

### Panel Management
```
GET  /api/panel/credentials    - Get panel credentials
PUT  /api/panel/credentials    - Update panel credentials
POST /api/panel/credentials/generate - Generate random credentials
GET  /api/panel/settings       - Get panel settings
PUT  /api/panel/settings       - Update panel settings
```

### Nginx
```
GET  /api/nginx/status         - Get nginx status
GET  /api/nginx/config         - Get nginx configuration
PUT  /api/nginx/config         - Update nginx configuration
POST /api/nginx/reload         - Reload nginx
POST /api/nginx/test           - Test nginx configuration
GET  /api/nginx/sites          - List available sites
POST /api/nginx/site/enable    - Enable site
POST /api/nginx/site/disable   - Disable site
```

### Camouflage
```
GET  /api/camouflage/status    - Get camouflage status
GET  /api/camouflage/templates - List available templates
POST /api/camouflage/apply     - Apply camouflage template
DELETE /api/camouflage/remove  - Remove camouflage
```

### SNI Scanner
```
GET  /api/sni/targets          - Get SNI targets list
POST /api/sni/scan             - Scan domain for Reality compatibility
GET  /api/sni/test             - Test specific SNI target
```

### System
```
GET  /api/health               - Health check
GET  /api/stats                - System statistics
GET  /api/server/info          - Server information
GET  /api/system/version       - Current version
GET  /api/system/update/check  - Check for updates
POST /api/system/update        - Perform update
GET  /api/system/releases      - List available releases
POST /api/system/rollback      - Rollback to backup
GET  /api/monitoring/health    - Monitoring health
GET  /api/monitoring/online-users - Online users list
```

---

## Service Management

```bash
# Status
systemctl status xui-manager

# Restart
systemctl restart xui-manager

# Logs
journalctl -u xui-manager -f
tail -f /var/log/xui-manager.log
```

---

## Architecture

```
┌─────────────────────────────────────┐
│        NGINX (HTTPS:443)            │
└─────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  /manager/  → XUI-Manager (8888)     │
│  /esmars/   → X-UI Panel (2096)      │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  FastAPI + SQLite                    │
│  /etc/x-ui/x-ui.db                   │
└──────────────────────────────────────┘
```

---

## Version History

- **v2.3.0** - Automation, Visual Inbound Editor, WARP integration
- **v2.2.0** - Monitoring, Region manager, Mobile UI
- **v2.1.0** - Panel management, Nginx tools, Camouflage
- **v2.0.0** - Xray generator, CDN templates
- **v1.5.0** - Auto-update system
- **v1.4.0** - Subscription sync

---

<a name="russian"></a>
# Русский

Современный веб-интерфейс и REST API для управления пользователями 3x-ui панели с продвинутыми функциями автоматизации.

**Работает с любой версией 3x-ui** - автоматически определяет схему базы данных

## Быстрая установка

```bash
git clone https://github.com/khiziresmars/xmanager.git
cd xmanager
sudo bash install.sh
```

Скрипт автоматически:
- Создаст виртуальное окружение Python
- Установит все зависимости
- Настроит systemd сервис
- Интегрируется с Nginx
- Получит SSL сертификат Let's Encrypt

**Требования:**
- OS: Debian 11+, Ubuntu 20.04+
- Python 3.8+
- 3x-ui (любая версия)
- Root доступ

**После установки:** `https://ваш-домен/manager/`

---

## Возможности

### Управление пользователями
- Создание до 5000 пользователей через систему очередей
- Массовые операции (создание, удаление, блокировка)
- Поддержка VLESS, Trojan, VMess, Shadowsocks
- Поиск по email, фильтрация по inbound
- Управление трафиком и сроками

### Управление Inbounds
- Визуальный редактор с вкладками (Основное, Транспорт, Безопасность, Расширенные)
- Генерация X25519 ключей для Reality
- Генерация UUID, Short ID, случайных портов/путей
- Поддержка всех типов транспорта (WS, gRPC, HTTPUpgrade, SplitHTTP)
- Генерация конфигурации Nginx

### Автоматизация
- Запланированные бэкапы с политикой хранения
- Мониторинг SSL сертификатов и авто-продление
- Мониторинг состояния сервисов (X-UI, Nginx, WARP)
- Проверка статуса WARP и авто-перезапуск

### Мониторинг
- Отслеживание онлайн пользователей
- Использование CPU/RAM/Диска
- Сетевая статистика
- Время работы сервера

### Безопасность
- Управление учётными данными панели
- Камуфляж Nginx с fake сайтами (170+ шаблонов)
- Блокировка ботов (Clash, Hiddify, V2box user-agents)
- SNI сканер для Reality

---

## Полный справочник API

### Аутентификация
```
POST /api/auth/login          - Вход
POST /api/auth/logout         - Выход
POST /api/tokens/generate     - Генерация API токена
GET  /api/tokens              - Список токенов
DELETE /api/tokens/{id}       - Удаление токена
```

### Пользователи
```
GET    /api/users              - Список пользователей
POST   /api/users              - Создать пользователя
DELETE /api/users/{id}         - Удалить
PUT    /api/users/{id}/toggle  - Включить/выключить
PUT    /api/users/{id}/expiry  - Установить срок
PUT    /api/users/{id}/traffic - Установить лимит трафика
POST   /api/users/bulk-create  - Создать до 100 пользователей
GET    /api/users/by-email/{email} - Найти по email
GET    /api/users/unlimited    - Безлимитные
GET    /api/users/low-traffic  - Низкий трафик
GET    /api/users/expired      - Истекшие
GET    /api/users/disabled     - Отключенные
POST   /api/users/reset-traffic - Сбросить трафик
POST   /api/users/add-traffic  - Добавить трафик
POST   /api/users/extend-expiry - Продлить срок
```

### Очереди
```
POST   /api/queues/bulk-create - Создать до 5000 через очередь
GET    /api/queues             - Список очередей
GET    /api/queues/{id}        - Статус очереди
POST   /api/queues/{id}/cancel - Отменить
DELETE /api/queues/{id}        - Удалить
```

### Inbounds
```
GET    /api/inbounds           - Список inbounds
GET    /api/inbounds/{id}/full - Полные данные
PUT    /api/inbounds/{id}      - Обновить
POST   /api/inbounds/import    - Импорт из шаблона
GET    /api/inbounds/templates - Шаблоны
```

### Генератор (Xray значения)
```
GET  /api/generator/uuid       - UUID
GET  /api/generator/x25519     - X25519 ключи
GET  /api/generator/short-id   - Short ID
GET  /api/generator/password   - Пароль
GET  /api/generator/credentials - Все учётные данные
GET  /api/generator/available-port - Свободный порт
GET  /api/generator/sni-targets - SNI цели
GET  /api/generator/fingerprints - Fingerprints
POST /api/generator/vless-reality - VLESS+Reality конфиг
POST /api/generator/inbound    - Inbound по шаблону
```

### Автоматизация
```
GET  /api/automation/status    - Статус
GET  /api/automation/settings  - Настройки
PUT  /api/automation/settings  - Обновить настройки
GET  /api/automation/services  - Статус сервисов
POST /api/automation/service/{name}/restart - Перезапуск
```

### Бэкапы
```
GET    /api/automation/backups  - Список бэкапов
POST   /api/automation/backup/create - Создать
POST   /api/automation/backup/restore/{name} - Восстановить
DELETE /api/automation/backup/{name} - Удалить
```

### SSL сертификаты
```
GET  /api/automation/ssl/check - Проверка SSL
POST /api/automation/ssl/renew - Продление SSL
```

### WARP
```
GET  /api/automation/warp/status  - Статус WARP
POST /api/automation/warp/restart - Перезапуск WARP
```

### Управление панелью
```
GET  /api/panel/credentials    - Учётные данные
PUT  /api/panel/credentials    - Обновить
POST /api/panel/credentials/generate - Генерировать
GET  /api/panel/settings       - Настройки
PUT  /api/panel/settings       - Обновить настройки
```

### Nginx
```
GET  /api/nginx/status         - Статус nginx
GET  /api/nginx/config         - Конфигурация
PUT  /api/nginx/config         - Обновить
POST /api/nginx/reload         - Перезагрузить
POST /api/nginx/test           - Тест конфигурации
```

### Камуфляж
```
GET  /api/camouflage/status    - Статус камуфляжа
GET  /api/camouflage/templates - Шаблоны
POST /api/camouflage/apply     - Применить
DELETE /api/camouflage/remove  - Удалить
```

### SNI сканер
```
GET  /api/sni/targets          - Список SNI целей
POST /api/sni/scan             - Сканировать домен
GET  /api/sni/test             - Тест SNI цели
```

### Система
```
GET  /api/health               - Health check
GET  /api/stats                - Статистика
GET  /api/server/info          - Информация о сервере
GET  /api/system/version       - Версия
GET  /api/system/update/check  - Проверка обновлений
POST /api/system/update        - Обновление
GET  /api/system/releases      - Релизы
POST /api/system/rollback      - Откат
```

---

## Управление сервисом

```bash
# Статус
systemctl status xui-manager

# Перезапуск
systemctl restart xui-manager

# Логи
journalctl -u xui-manager -f
tail -f /var/log/xui-manager.log
```

---

## Архитектура

```
┌─────────────────────────────────────┐
│        NGINX (HTTPS:443)            │
└─────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  /manager/  → XUI-Manager (8888)     │
│  /esmars/   → X-UI Panel (2096)      │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  FastAPI + SQLite                    │
│  /etc/x-ui/x-ui.db                   │
└──────────────────────────────────────┘
```

---

## История версий

- **v2.3.0** - Автоматизация, Визуальный редактор Inbounds, интеграция WARP
- **v2.2.0** - Мониторинг, Менеджер регионов, Мобильный UI
- **v2.1.0** - Управление панелью, Nginx инструменты, Камуфляж
- **v2.0.0** - Генератор Xray, CDN шаблоны
- **v1.5.0** - Система авто-обновлений
- **v1.4.0** - Синхронизация подписок

---

**Версия:** 2.3.0
**Совместимость:** 3x-ui 2.x+, Python 3.8+
