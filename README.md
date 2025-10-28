# XUI-Manager - Управление 3x-ui через Web API

Универсальный инструмент для управления пользователями 3x-ui (VPN/Proxy панели) через REST API и веб-интерфейс.

## 📋 Оглавление

- [Описание проекта](#описание-проекта)
- [Архитектура](#архитектура)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Настройка домена и HTTPS](#настройка-домена-и-https)
- [Управление несколькими серверами](#управление-несколькими-серверами)
- [API Документация](#api-документация)
- [Веб-интерфейс](#веб-интерфейс)
- [Файлы проекта](#файлы-проекта)
- [Устранение неполадок](#устранение-неполадок)

---

## 📖 Описание проекта

**XUI-Manager** - это FastAPI приложение для управления базой пользователей 3x-ui панели. Предоставляет:

- 🌐 **Web API** - REST API для автоматизации управления пользователями
- 💻 **Веб-интерфейс** - современный темный интерфейс для управления через браузер
- 🔄 **Синхронизация данных** - автоматическая синхронизация между БД и JSON конфигурацией x-ui
- 📊 **Аналитика** - статистика по трафику, пользователям, инбаундам
- ⚡ **Массовые операции** - создание, удаление, блокировка множества пользователей

### Зачем это нужно?

3x-ui хранит данные в двух местах:
1. **SQLite база данных** (`/etc/x-ui/x-ui.db`) - таблица `client_traffics`
2. **JSON конфигурация** - поле `inbounds.settings` в той же БД

Веб-панель x-ui отображает данные из JSON, но многие операции обновляют только таблицу. XUI-Manager решает эту проблему, синхронизируя оба источника данных при каждой операции.

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                         NGINX (HTTPS)                        │
│  - verassger1.uspn.io:443                                    │
│  - SSL сертификаты Let's Encrypt                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌──────────────────────────────────────┐
        │         Nginx Proxy Routing          │
        ├──────────────────────────────────────┤
        │ /esmars/   → 127.0.0.1:2096 (x-ui)   │
        │ /manager/  → 127.0.0.1:8888 (API)    │
        │ /sub/      → 127.0.0.1:2097 (sub)    │
        └──────────────────────────────────────┘
                    ↓                  ↓
        ┌───────────────────┐  ┌──────────────────┐
        │   X-UI Panel      │  │  XUI-Manager API │
        │   Port: 2096      │  │  Port: 8888      │
        │   /etc/x-ui/      │  │  FastAPI + Python│
        └───────────────────┘  └──────────────────┘
                    ↓                  ↓
        ┌─────────────────────────────────────────┐
        │        SQLite Database                  │
        │        /etc/x-ui/x-ui.db                │
        ├─────────────────────────────────────────┤
        │  • client_traffics (таблица)            │
        │  • inbounds.settings (JSON)             │
        └─────────────────────────────────────────┘
```

### Компоненты системы:

1. **FastAPI Backend** (`/opt/xui-manager/app/`)
   - `main.py` - REST API endpoints
   - `database.py` - работа с БД, синхронизация
   - `models.py` - Pydantic модели
   - `config.py` - настройки приложения

2. **Web Interface** (`/opt/xui-manager/templates/`)
   - `index.html` - темный минималистичный интерфейс
   - Вкладки: Пользователи, Массовое создание, Низкий трафик, Безлимит

3. **X-UI Integration**
   - База данных: `/etc/x-ui/x-ui.db`
   - Конфигурация: `/etc/x-ui/config.json`
   - Логи: `/var/log/x-ui/x-ui.log`

---

## 🚀 Установка

### Предварительные требования

- **OS**: Ubuntu/Debian Linux
- **3x-ui**: Установленная панель 3x-ui (версия 2.8.5+)
- **Python**: 3.8+
- **Nginx**: Для проксирования и HTTPS
- **SSL**: Сертификаты Let's Encrypt (опционально)

### Шаг 1: Установка зависимостей

```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Python и зависимостей
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Установка x-ui (если еще не установлен)
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
```

### Шаг 2: Клонирование/создание проекта

```bash
# Создание директории проекта
mkdir -p /opt/xui-manager/{app,templates,static}
cd /opt/xui-manager

# Создание виртуального окружения (опционально)
python3 -m venv venv
source venv/bin/activate

# Установка Python зависимостей
pip3 install fastapi uvicorn pydantic python-multipart
```

### Шаг 3: Копирование файлов

Скопируйте файлы проекта в `/opt/xui-manager/`:

```
/opt/xui-manager/
├── app/
│   ├── main.py          # REST API endpoints
│   ├── database.py      # Работа с БД
│   ├── models.py        # Pydantic модели
│   └── config.py        # Настройки
├── templates/
│   └── index.html       # Веб-интерфейс
├── static/              # Статические файлы (если есть)
└── README.md            # Эта документация
```

### Шаг 4: Создание systemd сервиса

```bash
cat > /etc/systemd/system/xui-manager.service <<'EOF'
[Unit]
Description=XUI Manager API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/xui-manager
ExecStart=/usr/bin/python3 -m app.main
Restart=always
RestartSec=5
StandardOutput=append:/var/log/xui-manager.log
StandardError=append:/var/log/xui-manager.log

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd и запуск сервиса
systemctl daemon-reload
systemctl enable xui-manager
systemctl start xui-manager

# Проверка статуса
systemctl status xui-manager
```

### Шаг 5: Проверка работы API

```bash
# Проверка здоровья API
curl http://localhost:8888/api/health

# Должен вернуть:
# {"status":"healthy","timestamp":"...","database":true}
```

---

## ⚙️ Конфигурация

### Файл: `/opt/xui-manager/app/config.py`

```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API настройки
    HOST: str = "0.0.0.0"
    PORT: int = 8888
    DEBUG: bool = False

    # База данных X-UI
    DB_PATH: str = "/etc/x-ui/x-ui.db"

    # X-UI настройки
    XUI_USERNAME: str = os.getenv("XUI_USERNAME", "admin")
    XUI_PASSWORD: str = os.getenv("XUI_PASSWORD", "admin")

    class Config:
        env_file = ".env"

settings = Settings()
```

### Переменные окружения

Создайте файл `/opt/xui-manager/.env`:

```env
HOST=0.0.0.0
PORT=8888
DEBUG=False
DB_PATH=/etc/x-ui/x-ui.db
XUI_USERNAME=admin
XUI_PASSWORD=your_secure_password
```

### Важные параметры базы данных

XUI-Manager работает с базой данных x-ui по пути: `/etc/x-ui/x-ui.db`

**Таблица `client_traffics`:**
```sql
CREATE TABLE client_traffics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbound_id INTEGER,
    enable INTEGER,
    email TEXT,
    up INTEGER,
    down INTEGER,
    total INTEGER,
    expiry_time INTEGER,
    reset INTEGER,
    all_time INTEGER,
    last_online INTEGER
);
```

**Таблица `inbounds` (поле settings):**
```json
{
  "clients": [
    {
      "id": 123,
      "email": "user@example.com",
      "enable": true,
      "expiryTime": 1735689600000,
      "totalGB": 107374182400,
      "method": "chacha20-ietf-poly1305",
      "password": "secure_password",
      "reset": 0,
      "limitIp": 0
    }
  ]
}
```

---

## 🌐 Настройка домена и HTTPS

### Шаг 1: Получение SSL сертификата

```bash
# Получение сертификата Let's Encrypt
certbot certonly --nginx -d yourdomain.com

# Сертификаты будут в:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### Шаг 2: Настройка Nginx

Создайте файл `/etc/nginx/sites-available/xui-manager`:

```nginx
# HTTP -> HTTPS редирект
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS сервер
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com;

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    add_header Strict-Transport-Security "max-age=63072000" always;

    # Проксирование X-UI панели
    location /esmars/ {
        proxy_pass http://127.0.0.1:2096;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_redirect off;
    }

    # Проксирование XUI-Manager API
    location /manager/ {
        proxy_pass http://127.0.0.1:8888/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Проксирование подписки (если используется)
    location /sub/ {
        proxy_pass http://127.0.0.1:2097;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Шаг 3: Активация конфигурации

```bash
# Создание символической ссылки
ln -s /etc/nginx/sites-available/xui-manager /etc/nginx/sites-enabled/

# Проверка конфигурации
nginx -t

# Перезагрузка Nginx
systemctl reload nginx
```

### Доступ к интерфейсам:

- **X-UI панель**: `https://yourdomain.com/esmars/`
- **XUI-Manager**: `https://yourdomain.com/manager/`
- **API docs**: `https://yourdomain.com/manager/api/docs`

---

## 🖥️ Управление несколькими серверами

### Вариант 1: Установка на каждом сервере

Повторите установку на каждом сервере с 3x-ui. Каждый сервер будет иметь свой XUI-Manager, управляющий локальной БД.

**Преимущества:**
- Независимое управление каждым сервером
- Нет единой точки отказа
- Простота настройки

### Вариант 2: Централизованное управление

Установите XUI-Manager на один сервер и настройте удаленное подключение к БД других серверов.

#### Настройка удаленного доступа:

1. **На удаленном сервере** настройте доступ к БД:

```bash
# Установка SSH ключей для безопасного доступа
ssh-keygen -t ed25519 -C "xui-manager"
ssh-copy-id root@remote-server

# Или используйте NFS/SSHFS для монтирования /etc/x-ui/
```

2. **Создайте конфигурацию для множественных серверов:**

`/opt/xui-manager/servers.json`:
```json
{
  "servers": [
    {
      "name": "Server 1",
      "host": "server1.example.com",
      "db_path": "/etc/x-ui/x-ui.db",
      "api_url": "https://server1.example.com/manager"
    },
    {
      "name": "Server 2",
      "host": "server2.example.com",
      "db_path": "/mnt/server2-xui/x-ui.db",
      "api_url": "https://server2.example.com/manager"
    }
  ]
}
```

3. **Модифицируйте `database.py` для поддержки множественных БД:**

```python
class MultiServerDatabase:
    def __init__(self, servers_config):
        self.servers = self._load_servers(servers_config)

    def get_connection(self, server_name):
        server = self.servers.get(server_name)
        return sqlite3.connect(server['db_path'])

    # Методы для работы с несколькими серверами
```

### Вариант 3: Использование API для удаленного управления

Используйте REST API XUI-Manager для управления серверами через HTTP запросы.

**Пример скрипта управления:**

```python
#!/usr/bin/env python3
import requests

SERVERS = [
    "https://server1.example.com/manager",
    "https://server2.example.com/manager",
    "https://server3.example.com/manager",
]

def create_user_on_all_servers(user_data):
    """Создание пользователя на всех серверах"""
    for server in SERVERS:
        response = requests.post(
            f"{server}/api/users",
            json=user_data
        )
        print(f"{server}: {response.json()}")

# Пример использования
user_data = {
    "email": "newuser@example.com",
    "inbound_id": 1,
    "total": 107374182400,  # 100GB
    "expiry_time": 0,
    "method": "chacha20-ietf-poly1305",
    "password": "secure_password"
}

create_user_on_all_servers(user_data)
```

---

## 📚 API Документация

### Базовый URL

- Локально: `http://localhost:8888`
- С доменом: `https://yourdomain.com/manager`

### Swagger UI

Интерактивная документация доступна по адресу: `/api/docs`

### Основные эндпоинты

#### 1. Health Check
```http
GET /api/health
```

**Ответ:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-27T20:00:00",
  "database": true
}
```

#### 2. Получение списка пользователей
```http
GET /api/users?inbound_id=1&limit=100&offset=0&search=user
```

**Параметры:**
- `inbound_id` (optional) - фильтр по инбаунду
- `limit` (optional, default: 100) - количество записей
- `offset` (optional, default: 0) - смещение
- `search` (optional) - поиск по email

**Ответ:**
```json
{
  "users": [
    {
      "id": 123,
      "email": "user@example.com",
      "inbound_id": 1,
      "enable": true,
      "total": 107374182400,
      "used": 1073741824,
      "remaining": 106300440576,
      "expiry_time": 1735689600000,
      "reset": 0
    }
  ],
  "total": 1
}
```

#### 3. Создание пользователя
```http
POST /api/users
Content-Type: application/json

{
  "email": "newuser@example.com",
  "inbound_id": 1,
  "total": 107374182400,
  "expiry_time": 1735689600000,
  "method": "chacha20-ietf-poly1305",
  "password": "secure_password"
}
```

**Ответ:**
```json
{
  "message": "User created successfully",
  "user": {
    "id": 124,
    "email": "newuser@example.com",
    ...
  }
}
```

#### 4. Удаление пользователя
```http
DELETE /api/users/{user_id}
```

**Ответ:**
```json
{
  "message": "User deleted successfully"
}
```

#### 5. Массовое создание пользователей
```http
POST /api/users/bulk-create
Content-Type: application/json

{
  "template": {
    "name": "Bulk Users",
    "prefix": "user",
    "total": 107374182400,
    "expiry_time": 1735689600000,
    "method": "chacha20-ietf-poly1305"
  },
  "count": 10,
  "inbound_id": 1
}
```

**Ответ:**
```json
{
  "message": "Created 10 users",
  "created": 10,
  "users": [...]
}
```

#### 6. Пользователи с низким трафиком
```http
GET /api/users/low-traffic?threshold=1073741824&sort_by=remaining&order=asc
```

**Параметры:**
- `threshold` - порог в байтах (default: 1024)
- `sort_by` - сортировка (remaining, used, total)
- `order` - порядок (asc, desc)

#### 7. Безлимитные пользователи
```http
GET /api/users/unlimited?filter_type=both&enabled_only=false
```

**Параметры:**
- `filter_type` - тип фильтра:
  - `expiry` - бессрочные (expiry_time = 0)
  - `traffic` - без лимита трафика (total = 0)
  - `both` - оба условия
- `enabled_only` - только активные

#### 8. Обновление лимита трафика
```http
PUT /api/users/{user_id}/traffic
Content-Type: application/json

{
  "traffic_limit": 214748364800
}
```

#### 9. Сброс трафика
```http
POST /api/users/reset-traffic
Content-Type: application/json

{
  "user_ids": [123, 124, 125],
  "new_limit": 107374182400
}
```

#### 10. Блокировка/разблокировка
```http
POST /api/users/toggle-status
Content-Type: application/json

{
  "user_ids": [123, 124],
  "enable": false
}
```

#### 11. Продление срока действия
```http
POST /api/users/extend-expiry
Content-Type: application/json

{
  "user_ids": [123, 124],
  "days": 30
}
```

#### 12. Получение инбаундов
```http
GET /api/inbounds
```

#### 13. Статистика системы
```http
GET /api/stats
```

**Ответ:**
```json
{
  "total_users": 3679,
  "active_users": 3234,
  "disabled_users": 445,
  "total_traffic_used": 1234567890123,
  "total_traffic_limit": 9876543210987
}
```

---

## 💻 Веб-интерфейс

### Вкладки интерфейса

1. **📊 Пользователи**
   - Просмотр всех пользователей
   - Поиск по email
   - Фильтр по инбаунду
   - Информация о трафике и сроках

2. **➕ Массовое создание**
   - Создание множества пользователей
   - Настройка префикса
   - Установка лимита трафика (GB)
   - Установка срока действия (дни)
   - Выбор метода шифрования
   - Выбор инбаунда

3. **⚠️ Низкий трафик**
   - Пользователи с остатком < 1GB
   - Настройка порога
   - Сортировка по остатку
   - Массовая блокировка
   - Массовое удаление
   - Сброс трафика

4. **♾️ Безлимит**
   - Бессрочные пользователи
   - Без лимита трафика
   - Фильтрация по типу
   - Массовое управление

### Особенности UI

- **Темная тема** - минималистичный дизайн
- **Адаптивность** - работает на мобильных
- **Toast уведомления** - обратная связь по действиям
- **Подсветка при hover** - интуитивность
- **Кастомные dropdown** - стилизованные select
- **Shadows на кнопках** - глубина интерфейса

---

## 📂 Файлы проекта

### Структура директорий

```
/opt/xui-manager/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI приложение, REST endpoints
│   ├── database.py          # Работа с БД, синхронизация
│   ├── models.py            # Pydantic модели для валидации
│   └── config.py            # Конфигурация приложения
├── templates/
│   ├── index.html           # Веб-интерфейс (текущий)
│   └── index.html.old       # Резервная копия
├── static/                  # Статические файлы (CSS, JS, изображения)
├── .env                     # Переменные окружения
├── README.md                # Документация
└── SYNC_INFO.md             # Информация о синхронизации

/etc/x-ui/
├── x-ui.db                  # База данных X-UI
└── config.json              # Конфигурация X-UI

/etc/systemd/system/
└── xui-manager.service      # Systemd сервис

/etc/nginx/
├── nginx.conf
└── sites-available/
    └── xui-manager          # Nginx конфигурация

/var/log/
├── xui-manager.log          # Логи XUI-Manager
└── x-ui/
    └── x-ui.log             # Логи X-UI
```

### Ключевые файлы и их назначение

#### `/opt/xui-manager/app/main.py`
- REST API endpoints
- FastAPI маршруты
- Обработка HTTP запросов
- CORS middleware

#### `/opt/xui-manager/app/database.py`
- Подключение к SQLite
- CRUD операции
- **Функции синхронизации:**
  - `_sync_client_to_json()` - синхронизация одного клиента
  - `_sync_multiple_clients_to_json()` - массовая синхронизация
- Все функции изменения данных вызывают синхронизацию

#### `/opt/xui-manager/app/models.py`
- Pydantic модели для валидации
- UserCreate, UserUpdate
- BulkCreateRequest, BulkDeleteRequest
- Схемы запросов и ответов

#### `/opt/xui-manager/app/config.py`
- Настройки приложения
- Пути к файлам
- Параметры подключения
- Environment variables

#### `/opt/xui-manager/templates/index.html`
- Темный веб-интерфейс
- JavaScript для API вызовов
- **Важно:** Использует относительные URL (`API_URL = ''`) для совместимости с HTTPS

#### `/etc/x-ui/x-ui.db`
- SQLite база данных X-UI
- Таблицы:
  - `users` - учетные записи панели
  - `inbounds` - настройки инбаундов (с JSON)
  - `client_traffics` - данные клиентов
  - `settings` - настройки системы

---

## 🔧 Устранение неполадок

### Проблема 1: API не запускается

**Симптомы:** Сервис падает сразу после запуска

**Проверка:**
```bash
systemctl status xui-manager
journalctl -u xui-manager -n 50
```

**Решения:**
1. Проверьте, что порт 8888 свободен:
   ```bash
   netstat -tlnp | grep 8888
   ```

2. Проверьте права доступа к БД:
   ```bash
   ls -la /etc/x-ui/x-ui.db
   chmod 644 /etc/x-ui/x-ui.db
   ```

3. Проверьте Python зависимости:
   ```bash
   pip3 list | grep -E "fastapi|uvicorn|pydantic"
   ```

### Проблема 2: Mixed Content Error (HTTPS/HTTP)

**Симптомы:** В консоли браузера ошибки "Mixed Content", данные не загружаются

**Причина:** Страница загружается по HTTPS, но API вызовы идут по HTTP

**Решение:**

В `/opt/xui-manager/templates/index.html` измените:
```javascript
// Неправильно:
const API_URL = 'http://yourdomain.com:8888';

// Правильно (для использования с nginx proxy):
const API_URL = '';
```

Nginx должен проксировать `/manager/` на `http://127.0.0.1:8888/`

### Проблема 3: Database locked

**Симптомы:** Ошибка "database is locked" в логах

**Причина:** Множественные процессы пытаются писать в БД одновременно

**Решение:**
```bash
# Убейте все Python процессы xui-manager
ps aux | grep "app.main" | grep -v grep | awk '{print $2}' | xargs -r kill -9

# Перезапустите сервис
systemctl restart xui-manager

# Проверьте, что запущен только один процесс
ps aux | grep "app.main" | grep -v grep
```

### Проблема 4: Пользователи не синхронизируются

**Симптомы:** Изменения в client_traffics не отражаются в x-ui панели

**Проверка синхронизации:**

Создайте тестовый скрипт `/tmp/test_sync.py`:
```python
#!/usr/bin/env python3
import sqlite3
import json

db = sqlite3.connect('/etc/x-ui/x-ui.db')
cursor = db.cursor()

# Проверка клиента
email = "test_user@example.com"

cursor.execute("SELECT expiry_time FROM client_traffics WHERE email=?", (email,))
db_expiry = cursor.fetchone()[0]

cursor.execute("SELECT settings FROM inbounds WHERE id=1")
settings = json.loads(cursor.fetchone()[0])
client = next(c for c in settings['clients'] if c['email'] == email)
json_expiry = client['expiryTime']

print(f"DB expiry: {db_expiry}")
print(f"JSON expiry: {json_expiry}")
print(f"Синхронизировано: {db_expiry == json_expiry}")
```

**Решение:** Запустите ручную синхронизацию:
```bash
python3 /tmp/sync_client_expiry_to_json.py
```

### Проблема 5: X-UI панель показывает ∞ (infinity)

**Причина:** Поле `expiryTime` в JSON не обновлено или равно 0

**Решение:**
```bash
# Запустите миграцию данных
python3 /tmp/sync_client_expiry_to_json.py

# Перезапустите x-ui
systemctl restart x-ui
```

### Проблема 6: Nginx 502 Bad Gateway

**Симптомы:** Страница не загружается, ошибка 502

**Проверка:**
```bash
# Проверьте, запущен ли API
systemctl status xui-manager
curl http://localhost:8888/api/health

# Проверьте логи Nginx
tail -f /var/log/nginx/error.log

# Проверьте конфигурацию Nginx
nginx -t
```

**Решение:**
```bash
# Перезапустите сервисы
systemctl restart xui-manager
systemctl reload nginx
```

### Проблема 7: SSL сертификат не работает

**Проверка сертификата:**
```bash
certbot certificates
openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -noout -dates
```

**Обновление сертификата:**
```bash
certbot renew
systemctl reload nginx
```

### Проблема 8: Высокая нагрузка на БД

**Симптомы:** Медленные запросы, высокий CPU

**Оптимизация:**
```sql
-- Создание индексов
sqlite3 /etc/x-ui/x-ui.db <<EOF
CREATE INDEX IF NOT EXISTS idx_email ON client_traffics(email);
CREATE INDEX IF NOT EXISTS idx_inbound ON client_traffics(inbound_id);
CREATE INDEX IF NOT EXISTS idx_enable ON client_traffics(enable);
EOF
```

### Логи для диагностики

```bash
# XUI-Manager логи
tail -f /var/log/xui-manager.log

# X-UI логи
tail -f /var/log/x-ui/x-ui.log

# Nginx логи
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Systemd логи
journalctl -u xui-manager -f
journalctl -u x-ui -f
```

---

## 🧪 Тестирование

### Тест полного цикла создания/удаления

Файл `/tmp/test_full_cycle.sh`:
```bash
#!/bin/bash
set -e

echo "=== ПОЛНЫЙ ТЕСТ СОЗДАНИЯ И УДАЛЕНИЯ ПОЛЬЗОВАТЕЛЯ ==="

# 1. Создание
CREATE_RESULT=$(curl -s -X POST http://localhost:8888/api/users \
  -H "Content-Type: application/json" \
  -d '{"email": "cycle_test", "inbound_id": 1, "total": 107374182400, "expiry_time": 0, "method": "chacha20-ietf-poly1305", "password": "test123"}')

USER_ID=$(echo "$CREATE_RESULT" | python3 -c "import json, sys; print(json.load(sys.stdin)['user']['id'])")
echo "✅ Создан пользователь с ID: $USER_ID"

# 2. Проверка в БД
sqlite3 /etc/x-ui/x-ui.db "SELECT id, email, enable FROM client_traffics WHERE id = $USER_ID"
echo "✅ Найдено в БД"

# 3. Проверка в JSON
COUNT_IN_JSON=$(sqlite3 /etc/x-ui/x-ui.db "SELECT settings FROM inbounds WHERE id=1" | python3 -c "
import json, sys
data = json.load(sys.stdin)
clients = [c for c in data['clients'] if c.get('email') == 'cycle_test']
print(len(clients))
")
echo "Найдено в JSON: $COUNT_IN_JSON клиентов"

# 4. Удаление
curl -s -X DELETE http://localhost:8888/api/users/$USER_ID > /dev/null
echo "✅ Пользователь удален"

# 5. Проверка удаления
COUNT_IN_DB=$(sqlite3 /etc/x-ui/x-ui.db "SELECT COUNT(*) FROM client_traffics WHERE id = $USER_ID")
COUNT_IN_JSON_AFTER=$(sqlite3 /etc/x-ui/x-ui.db "SELECT settings FROM inbounds WHERE id=1" | python3 -c "
import json, sys
data = json.load(sys.stdin)
clients = [c for c in data['clients'] if c.get('email') == 'cycle_test']
print(len(clients))
")

if [ "$COUNT_IN_DB" -eq 0 ] && [ "$COUNT_IN_JSON_AFTER" -eq 0 ]; then
    echo "✅ ТЕСТ ПРОЙДЕН"
else
    echo "❌ ТЕСТ ПРОВАЛЕН"
fi
```

Запуск:
```bash
chmod +x /tmp/test_full_cycle.sh
/tmp/test_full_cycle.sh
```

---

## 📝 Дополнительная информация

### Резервное копирование

```bash
# Резервная копия БД
cp /etc/x-ui/x-ui.db /backup/x-ui-$(date +%Y%m%d-%H%M%S).db

# Через API
curl -X POST http://localhost:8888/api/system/backup
```

### Обновление проекта

```bash
# Остановка сервиса
systemctl stop xui-manager

# Обновление кода
cd /opt/xui-manager
git pull  # если используется git
# или скопируйте новые файлы

# Установка зависимостей
pip3 install -r requirements.txt

# Запуск
systemctl start xui-manager
```

### Мониторинг

```bash
# Проверка статуса всех сервисов
systemctl status xui-manager x-ui nginx

# Использование ресурсов
ps aux | grep -E "xui-manager|x-ui" | grep -v grep
```

---

## 🤝 Поддержка

### Полезные команды

```bash
# Перезапуск всех сервисов
systemctl restart xui-manager x-ui nginx

# Проверка портов
netstat -tlnp | grep -E "2096|8888"

# Анализ БД
sqlite3 /etc/x-ui/x-ui.db ".tables"
sqlite3 /etc/x-ui/x-ui.db "SELECT COUNT(*) FROM client_traffics"

# Очистка логов
truncate -s 0 /var/log/xui-manager.log
```

### Безопасность

1. **Смените дефолтные пароли** x-ui панели
2. **Используйте HTTPS** для всех подключений
3. **Ограничьте доступ** к API через firewall
4. **Регулярно обновляйте** систему и зависимости
5. **Делайте резервные копии** БД

### Рекомендации

- Используйте **systemd** для автозапуска
- Настройте **автообновление SSL** сертификатов
- Мониторьте **логи** на предмет ошибок
- Регулярно проверяйте **синхронизацию** данных

---

## 📄 Лицензия

Проект распространяется "как есть" для личного использования и управления собственными серверами.

---

## ✅ Чеклист установки

- [ ] Установлен Python 3.8+
- [ ] Установлен X-UI 2.8.5+
- [ ] Установлен Nginx
- [ ] Скопированы файлы в `/opt/xui-manager/`
- [ ] Установлены Python зависимости
- [ ] Создан systemd сервис
- [ ] Сервис запущен и работает
- [ ] Nginx настроен и работает
- [ ] SSL сертификат получен и настроен
- [ ] Веб-интерфейс доступен через HTTPS
- [ ] API отвечает на запросы
- [ ] Тест создания/удаления пользователя пройден
- [ ] Синхронизация данных работает корректно

---

**Версия документации:** 1.0
**Дата:** 27 октября 2025
**Совместимость:** X-UI 2.8.5+, XUI-Manager 1.0
