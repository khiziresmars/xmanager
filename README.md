# Агент Мастера ключей - Управление 3x-ui

Современный веб-интерфейс и REST API для управления пользователями 3x-ui панели.

**✅ Работает с любой версией 3x-ui** - автоматически определяет схему базы данных

---

## ⚡ Быстрая установка

```bash
# Клонируйте репозиторий
git clone https://github.com/khiziresmars/xmanager.git
cd xmanager

# Запустите установку
sudo bash install.sh
```

**Готово!** Скрипт автоматически:
- ✅ Создаст виртуальное окружение Python
- ✅ Установит все зависимости
- ✅ Настроит systemd сервис
- ✅ Интегрируется с Nginx
- ✅ Получит SSL сертификат Let's Encrypt

**Требования:**
- OS: Debian 11+, Ubuntu 20.04+
- Python 3.8+
- 3x-ui (любая версия)
- Root доступ

**После установки:** `https://ваш-домен/manager/`

---

## 🎯 Основные возможности

### 🔐 Аутентификация
- Вход с паролем (login: `esmarsme`, password: `EsmarsMe13AMS1`)
- API токены для программного доступа
- Сессии с таймаутом 24 часа

### 👥 Управление пользователями
- Создание до 5000 пользователей через систему очередей
- Массовые операции (создание, удаление, блокировка)
- Поддержка VLESS, Trojan, VMess, Shadowsocks
- Поиск по email, фильтрация по inbound
- Управление трафиком и сроками

### 📊 Мониторинг
- Онлайн пользователи
- Загрузка CPU/памяти/диска
- Сетевая статистика
- Время работы сервера
- Автообновление каждые 5 секунд

### ⚡ Очереди
- Создание до 5000 пользователей
- Обработка батчами по 100
- Отслеживание прогресса
- Отмена в процессе

### 🔑 API Токены
- Генерация для программного доступа
- Отзыв/удаление токенов
- Отслеживание использования
- Bearer token auth

---

## 📚 API Основные endpoints

### Аутентификация
```bash
POST /api/auth/login
POST /api/auth/logout
POST /api/tokens/generate
```

### Пользователи
```bash
GET  /api/users                # Список пользователей
POST /api/users                # Создать пользователя
DELETE /api/users/{id}         # Удалить пользователя
POST /api/users/bulk-create    # До 100 пользователей
POST /api/queues/bulk-create   # До 5000 через очереди
```

### Трафик
```bash
GET  /api/users/unlimited      # Безлимитные пользователи
GET  /api/users/low-traffic    # Низкий трафик
POST /api/users/reset-traffic  # Сбросить трафик
POST /api/users/add-traffic    # Добавить трафик
POST /api/users/set-limit      # Установить лимит
```

### Управление
```bash
POST /api/users/toggle-status  # Блокировка/разблокировка
POST /api/users/extend-expiry  # Продление срока
```

### Мониторинг
```bash
GET /api/stats                  # Статистика системы
GET /api/monitoring/health      # Состояние сервера
GET /api/monitoring/online-users # Онлайн пользователей
```

### Очереди
```bash
GET    /api/queues             # Список очередей
GET    /api/queues/{id}        # Статус очереди
POST   /api/queues/{id}/cancel # Отменить очередь
DELETE /api/queues/{id}        # Удалить очередь
```

### Система
```bash
GET /api/health                # Health check
GET /api/server/info           # Информация о сервере
GET /api/inbounds              # Список inbounds
```

**Интерактивная документация:** `/api/docs`

---

## 🔧 Управление сервисом

```bash
# Статус
systemctl status xui-manager

# Перезапуск
systemctl restart xui-manager

# Логи
journalctl -u xui-manager -f
tail -f /var/log/xui-manager.log

# Проверка API
curl http://localhost:8888/api/health
```

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────┐
│        NGINX (HTTPS:443)             │
└─────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  /manager/  → API (8888)             │
│  /esmars/   → X-UI (2096)            │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  FastAPI + SQLite                    │
│  /etc/x-ui/x-ui.db                   │
└──────────────────────────────────────┘
```

---

## 🔐 Безопасность

1. **Смените дефолтные пароли** после установки
2. **Используйте HTTPS** для всех подключений
3. **Храните API токены** в безопасном месте
4. **Регулярно обновляйте** систему
5. **Делайте резервные копии** БД

---

## 🚀 Обновление

```bash
cd xmanager
git pull
systemctl restart xui-manager
```

---

## 🐛 Проблемы?

```bash
# Проверка сервисов
systemctl status xui-manager x-ui nginx

# Логи
journalctl -u xui-manager -f

# Порты
netstat -tlnp | grep -E "8888|2096"

# База данных
sqlite3 /etc/x-ui/x-ui.db "SELECT COUNT(*) FROM client_traffics"
```

---

## 📄 Структура проекта

```
/opt/xui-manager/
├── app/
│   ├── main.py          # REST API
│   ├── database.py      # Работа с БД
│   ├── auth.py          # Аутентификация
│   ├── queue.py         # Система очередей
│   ├── models.py        # Pydantic модели
│   └── config.py        # Настройки
├── templates/
│   ├── index.html       # Веб-интерфейс
│   └── login.html       # Страница входа
└── requirements.txt     # Python зависимости
```

---

**Версия:** 1.0
**Совместимость:** X-UI 2.x+, Python 3.8+
