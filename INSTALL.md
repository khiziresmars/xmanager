# 🚀 Быстрая установка XUI-Manager

## Установка в одну команду

### На текущем сервере (если проект уже загружен)

```bash
cd /opt/xui-manager && chmod +x install.sh && sudo ./install.sh
```

---

## Установка с GitHub (после загрузки проекта)

### Вариант 1: Клонирование через SSH (рекомендуется для приватных репозиториев)

```bash
cd /opt && git clone git@github.com:YOUR_USERNAME/xui-manager.git && cd xui-manager && chmod +x install.sh && sudo ./install.sh
```

### Вариант 2: Загрузка через curl (если репозиторий публичный)

```bash
bash <(curl -Ls https://raw.githubusercontent.com/YOUR_USERNAME/xui-manager/main/install.sh)
```

---

## Что делает install.sh автоматически?

✅ Проверяет наличие 3x-ui (предлагает установить если нет)
✅ Устанавливает системные зависимости (python3, nginx, sqlite3)
✅ Устанавливает Python пакеты (fastapi, uvicorn, pydantic)
✅ Копирует файлы проекта в `/opt/xui-manager/`
✅ Создаёт конфигурацию `.env`
✅ Создаёт systemd сервис `xui-manager.service`
✅ Настраивает Nginx с HTTPS поддержкой
✅ Предлагает получить SSL сертификат Let's Encrypt
✅ Запускает и проверяет работу API

---

## После установки

Интерфейсы будут доступны по адресам:

- 🌐 **X-UI панель**: `https://your-domain.com/esmars/`
- 💻 **XUI-Manager**: `https://your-domain.com/manager/`
- 📚 **API документация**: `https://your-domain.com/manager/api/docs`

---

## Управление сервисом

```bash
# Проверка статуса
systemctl status xui-manager

# Перезапуск
systemctl restart xui-manager

# Просмотр логов
tail -f /var/log/xui-manager.log
journalctl -u xui-manager -f

# Остановка
systemctl stop xui-manager

# Запуск
systemctl start xui-manager
```

---

## Обновление проекта

```bash
cd /opt/xui-manager && sudo ./update.sh
```

---

## Требования

- **OS**: Ubuntu 20.04+ / Debian 11+
- **3x-ui**: Версия 2.8.5 или выше
- **Python**: 3.8+
- **Права**: root или sudo

---

## Структура после установки

```
/opt/xui-manager/          # Директория проекта
├── app/                   # Backend код
├── templates/             # Веб-интерфейс
├── .env                   # Конфигурация
├── install.sh             # Установочный скрипт
└── update.sh              # Скрипт обновления

/etc/x-ui/x-ui.db          # База данных X-UI
/var/log/xui-manager.log   # Логи приложения
/etc/systemd/system/       # Сервис
/etc/nginx/sites-available/ # Nginx конфигурация
```

---

## Помощь

📖 **Полная документация**: См. [README.md](README.md)
🔧 **Настройка GitHub**: См. [GITHUB_SETUP.md](GITHUB_SETUP.md)
⚡ **Быстрый старт**: См. [QUICK_START.md](QUICK_START.md)

---

## Удаление

Если нужно удалить XUI-Manager:

```bash
# Остановка и отключение сервиса
systemctl stop xui-manager
systemctl disable xui-manager
rm /etc/systemd/system/xui-manager.service
systemctl daemon-reload

# Удаление файлов
rm -rf /opt/xui-manager

# Удаление Nginx конфигурации
rm /etc/nginx/sites-enabled/xui-manager
rm /etc/nginx/sites-available/xui-manager
systemctl reload nginx

# Очистка логов
rm /var/log/xui-manager.log
```

---

**Готово! Установка занимает 2-5 минут.** 🎉
