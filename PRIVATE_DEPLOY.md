# 🔐 Приватная установка XUI-Manager через SSH

Инструкция для быстрого развертывания XUI-Manager на удаленном сервере с 3x-ui через SSH с использованием приватного ключа.

---

## 📋 Предварительные требования

### На сервере должно быть установлено:
- Ubuntu/Debian (20.04+)
- 3x-ui панель (уже установлена и работает)
- SSH доступ с правами root или sudo

### На локальной машине:
- SSH клиент
- Git (опционально)
- Приватный SSH ключ для доступа к серверу

---

## ⚡ Быстрая установка (3 команды)

### Вариант 1: Через SSH одной командой

```bash
# Подключитесь к серверу и запустите установку одной командой
ssh -i ~/.ssh/your_private_key root@your-server-ip "bash <(curl -Ls https://raw.githubusercontent.com/khiziresmars/xmanager/main/install.sh)"
```

### Вариант 2: Пошаговая установка

#### Шаг 1: Подключитесь к серверу

```bash
# Используйте ваш приватный ключ для подключения
ssh -i ~/.ssh/your_private_key root@your-server-ip

# Или если ключ добавлен в ssh-agent
ssh root@your-server-ip
```

#### Шаг 2: Клонируйте репозиторий

```bash
cd /root
git clone https://github.com/khiziresmars/xmanager.git
cd xmanager
```

#### Шаг 3: Запустите установку

```bash
sudo bash install.sh
```

Скрипт спросит:
1. **Домен** - введите ваш домен или оставьте hostname
2. **SSL сертификат** - нажмите `y` для автоматической установки Let's Encrypt

---

## 🔧 Детальная инструкция

### 1. Подготовка SSH ключа

Если у вас еще нет SSH ключа:

```bash
# Создайте новый SSH ключ (на локальной машине)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Скопируйте публичный ключ на сервер
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@your-server-ip
```

### 2. Настройка SSH конфигурации (опционально)

Создайте файл `~/.ssh/config` для упрощения подключения:

```bash
Host xui-server
    HostName your-server-ip
    User root
    IdentityFile ~/.ssh/your_private_key
    Port 22
```

Теперь можно подключаться просто: `ssh xui-server`

### 3. Проверка 3x-ui перед установкой

```bash
# Подключитесь к серверу
ssh xui-server

# Проверьте статус 3x-ui
systemctl status x-ui

# Проверьте наличие базы данных
ls -lh /etc/x-ui/x-ui.db
```

### 4. Установка XUI-Manager

```bash
# Загрузите проект
cd /root
git clone https://github.com/khiziresmars/xmanager.git
cd xmanager

# Запустите установку
bash install.sh
```

### 5. Что происходит при установке

Скрипт `install.sh` выполнит 9 шагов:

1. ✅ **Проверка 3x-ui** - найдет установленную панель
2. ✅ **Установка системных зависимостей** - Python, Nginx, SQLite, Git
3. ✅ **Проверка Python 3.8+** - убедится в совместимости
4. ✅ **Установка Python пакетов** - FastAPI, Uvicorn и др.
5. ✅ **Копирование файлов** - в `/opt/xui-manager/`
6. ✅ **Создание systemd сервиса** - автозапуск при старте сервера
7. ✅ **Настройка Nginx** - reverse proxy для безопасного доступа
8. ✅ **SSL сертификат** - автоматическое получение Let's Encrypt (опционально)
9. ✅ **Проверка** - тест работоспособности API

### 6. Интерактивные вопросы

Во время установки вас спросят:

```bash
# Если 3x-ui не найден
Хотите установить 3x-ui сейчас? (y/n): n

# Домен для Nginx
Введите доменное имя [По умолчанию: hostname]: your-domain.com

# SSL сертификат
Получить Let's Encrypt SSL сертификат? (y/n): y
```

---

## 🌐 Доступ после установки

После успешной установки вы увидите:

```
✅ XUI-Manager успешно установлен!

📋 Информация о доступе:

  🌐 X-UI панель:     https://your-domain.com/esmars/
  💻 XUI-Manager:     https://your-domain.com/manager/
  📚 API документация: https://your-domain.com/manager/api/docs

🔧 Полезные команды:

  • Статус сервиса:      systemctl status xui-manager
  • Перезапуск:          systemctl restart xui-manager
  • Просмотр логов:      tail -f /var/log/xui-manager.log
  • Обновление проекта:  cd /opt/xui-manager && ./update.sh
```

### Откройте в браузере:

1. **XUI-Manager (Web UI)**: `https://your-domain.com/manager/`
2. **API документация (Swagger)**: `https://your-domain.com/manager/api/docs`
3. **3x-ui панель**: `https://your-domain.com/esmars/`

---

## 🔐 Настройка безопасности

### 1. Защита API ключом (опционально)

```bash
# Отредактируйте .env файл
nano /opt/xui-manager/.env

# Добавьте API ключ
API_KEY=your-super-secret-api-key-here

# Перезапустите сервис
systemctl restart xui-manager
```

Теперь для доступа к API нужен заголовок:
```bash
curl -H "X-API-Key: your-super-secret-api-key-here" \
  https://your-domain.com/manager/api/stats
```

### 2. Ограничение доступа по IP (Nginx)

```bash
# Отредактируйте конфигурацию Nginx
nano /etc/nginx/sites-available/xui-manager

# Добавьте в location /manager/
location /manager/ {
    allow 192.168.1.0/24;  # Ваша сеть
    allow 1.2.3.4;          # Ваш IP
    deny all;

    proxy_pass http://127.0.0.1:8888/;
    # ... остальные настройки
}

# Перезагрузите Nginx
nginx -t && systemctl reload nginx
```

### 3. Настройка firewall

```bash
# Установите ufw если не установлен
apt install ufw

# Разрешите SSH
ufw allow 22/tcp

# Разрешите HTTPS
ufw allow 443/tcp

# Разрешите HTTP (для Let's Encrypt)
ufw allow 80/tcp

# Включите firewall
ufw enable
```

---

## 🔄 Обновление

### Автоматическое обновление:

```bash
ssh xui-server "cd /opt/xui-manager && bash update.sh"
```

### Ручное обновление:

```bash
ssh xui-server

cd /opt/xui-manager
git pull origin main
pip3 install -r requirements.txt --upgrade
systemctl restart xui-manager
```

---

## 🛠️ Управление сервисом

### Основные команды:

```bash
# Статус
systemctl status xui-manager

# Перезапуск
systemctl restart xui-manager

# Остановка
systemctl stop xui-manager

# Запуск
systemctl start xui-manager

# Автозапуск (включить/выключить)
systemctl enable xui-manager
systemctl disable xui-manager
```

### Просмотр логов:

```bash
# Логи сервиса
journalctl -u xui-manager -f

# Логи приложения
tail -f /var/log/xui-manager.log

# Последние 100 строк
tail -n 100 /var/log/xui-manager.log
```

---

## 📊 Проверка работоспособности

### Тест API:

```bash
# Health check
curl http://localhost:8888/api/health

# Статистика
curl http://localhost:8888/api/stats

# Список пользователей
curl http://localhost:8888/api/users?limit=10
```

### Проверка доступа через Nginx:

```bash
# С локальной машины
curl https://your-domain.com/manager/api/health
```

---

## 🐛 Устранение неполадок

### Проблема: API не отвечает

```bash
# Проверьте статус
systemctl status xui-manager

# Проверьте логи
journalctl -u xui-manager -n 50

# Проверьте, слушает ли порт 8888
netstat -tlnp | grep 8888
```

### Проблема: Nginx ошибка 502

```bash
# Проверьте, запущен ли XUI-Manager
systemctl status xui-manager

# Проверьте логи Nginx
tail -f /var/log/nginx/error.log

# Проверьте конфигурацию
nginx -t
```

### Проблема: SSL сертификат не работает

```bash
# Проверьте сертификаты
certbot certificates

# Обновите сертификат вручную
certbot --nginx -d your-domain.com

# Проверьте конфигурацию Nginx
cat /etc/nginx/sites-available/xui-manager | grep ssl_certificate
```

### Проблема: База данных не найдена

```bash
# Проверьте путь в конфигурации
cat /opt/xui-manager/.env | grep XUI_DB_PATH

# Проверьте существование БД
ls -lh /etc/x-ui/x-ui.db

# Исправьте путь в .env
nano /opt/xui-manager/.env
# Измените: XUI_DB_PATH=/etc/x-ui/x-ui.db

# Перезапустите
systemctl restart xui-manager
```

---

## 📝 Быстрая шпаргалка команд

```bash
# === ПОДКЛЮЧЕНИЕ ===
ssh -i ~/.ssh/key root@server-ip

# === УСТАНОВКА ===
git clone https://github.com/khiziresmars/xmanager.git && cd xmanager && bash install.sh

# === УПРАВЛЕНИЕ ===
systemctl status xui-manager    # Статус
systemctl restart xui-manager   # Перезапуск
journalctl -u xui-manager -f    # Логи

# === ОБНОВЛЕНИЕ ===
cd /opt/xui-manager && bash update.sh

# === ПРОВЕРКА ===
curl http://localhost:8888/api/health
curl https://domain.com/manager/api/health

# === КОНФИГУРАЦИЯ ===
nano /opt/xui-manager/.env
nano /etc/nginx/sites-available/xui-manager

# === ЛОГИ ===
tail -f /var/log/xui-manager.log
tail -f /var/log/nginx/access.log
journalctl -u xui-manager -n 100
```

---

## ✅ Чек-лист после установки

- [ ] XUI-Manager сервис запущен: `systemctl status xui-manager`
- [ ] API отвечает: `curl http://localhost:8888/api/health`
- [ ] Nginx настроен: `nginx -t`
- [ ] Домен открывается: `https://your-domain.com/manager/`
- [ ] SSL сертификат активен (зеленый замок в браузере)
- [ ] 3x-ui панель доступна: `https://your-domain.com/esmars/`
- [ ] API документация работает: `https://your-domain.com/manager/api/docs`
- [ ] Firewall настроен: `ufw status`
- [ ] Резервная копия БД создана: `ls /opt/xui-manager/backups/`

---

## 💡 Советы

1. **Регулярные бэкапы**: Настройте автоматическое резервное копирование БД
   ```bash
   # Добавьте в crontab
   0 */6 * * * /usr/bin/python3 -c "from app.database import XUIDatabase; XUIDatabase().create_backup()"
   ```

2. **Мониторинг**: Установите мониторинг для отслеживания доступности
   ```bash
   # Простой health check каждые 5 минут
   */5 * * * * curl -s http://localhost:8888/api/health || systemctl restart xui-manager
   ```

3. **Обновления**: Проверяйте обновления раз в неделю
   ```bash
   cd /opt/xui-manager && git fetch && git status
   ```

---

## 🆘 Поддержка

Если возникли проблемы:

1. Проверьте логи: `journalctl -u xui-manager -n 100`
2. Проверьте документацию: [README.md](README.md)
3. Создайте issue на GitHub: https://github.com/khiziresmars/xmanager/issues

---

**Готово!** 🎉 Теперь у вас работает XUI-Manager на сервере!
