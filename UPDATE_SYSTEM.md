# 🔄 Система Обновлений XUI Manager

## Обзор

XUI Manager v1.1.0 включает полнофункциональную систему управления версиями и автоматических обновлений.

## 🎯 Основные возможности

### 1. **Автоматическая проверка обновлений**
- ✅ Проверка каждые 24 часа (фоновая задача)
- ✅ Проверка при загрузке страницы (тихая)
- ✅ Ручная проверка по кнопке
- ✅ Кэширование результатов (1 час)

### 2. **Безопасное обновление**
- ✅ Автоматический backup перед обновлением
- ✅ Git-based обновление (git pull)
- ✅ Блокировка concurrent обновлений
- ✅ Перезапуск сервиса после обновления
- ✅ Rollback через backup при сбое

### 3. **Автоматическая очистка**
- ✅ Отключение просроченных пользователей (каждый час)
- ✅ Мониторинг низкого трафика (каждые 6 часов)
- ✅ Логирование всех операций

### 4. **UI компоненты**
- ✅ Футер с отображением версии
- ✅ Кнопка "Проверить обновления"
- ✅ Кнопка "Обновить" (появляется при наличии update)
- ✅ Visual feedback и уведомления

## 📋 API Endpoints

### Получение версии
```http
GET /api/system/version
Authorization: Required

Response:
{
  "current_version": "1.1.0",
  "version_name": "Агент Мастера ключей",
  "major": 1,
  "minor": 1,
  "patch": 0,
  "repository": "khiziresmars/xmanager",
  "github_url": "https://github.com/khiziresmars/xmanager"
}
```

### Проверка обновлений
```http
GET /api/system/update/check?force=false
Authorization: Required

Response:
{
  "current_version": "1.1.0",
  "latest_version": "1.2.0",
  "update_available": true,
  "release_name": "Feature Release v1.2.0",
  "release_date": "2025-10-30T10:00:00Z",
  "release_url": "https://github.com/.../releases/tag/v1.2.0",
  "changelog": {
    "features": ["New feature 1", "New feature 2"],
    "fixes": ["Bug fix 1"],
    "breaking_changes": []
  },
  "cached": false,
  "last_check": "2025-10-30T12:00:00"
}
```

### Выполнение обновления
```http
POST /api/system/update
Authorization: Required

Response (Success):
{
  "success": true,
  "message": "Update completed successfully",
  "previous_version": "1.1.0",
  "new_version": "1.2.0",
  "backup_file": "/opt/xui-manager/backups/backup_20251030_120000.tar.gz",
  "service_restarted": true,
  "changes": ["file1", "file2"]
}

Response (Error):
{
  "success": false,
  "error": "Update failed: git pull error",
  "backup_file": "/opt/xui-manager/backups/backup_..."
}
```

### Статус обновления
```http
GET /api/system/update/status
Authorization: Required

Response:
{
  "update_in_progress": false,
  "current_version": "1.1.0",
  "last_check": {
    "last_check": "2025-10-30T12:00:00",
    "latest_version": "1.1.0",
    "update_available": false
  }
}
```

### Статус фоновых задач
```http
GET /api/system/background-tasks
Authorization: Required

Response:
{
  "running": true,
  "tasks": {
    "update_checker": {
      "running": true,
      "cancelled": false,
      "done": false
    },
    "expired_cleanup": {
      "running": true,
      "cancelled": false,
      "done": false
    },
    "low_traffic_alerts": {
      "running": true,
      "cancelled": false,
      "done": false
    }
  }
}
```

## 🔧 Конфигурация

### Интервалы фоновых задач

```python
# app/background_tasks.py

# Проверка обновлений
UPDATE_CHECK_INTERVAL = 24 * 60 * 60  # 24 часа

# Очистка просроченных
EXPIRED_CLEANUP_INTERVAL = 60 * 60  # 1 час

# Мониторинг низкого трафика
LOW_TRAFFIC_CHECK_INTERVAL = 6 * 60 * 60  # 6 часов
```

### GitHub Repository

```python
# app/version.py

GITHUB_REPO = "khiziresmars/xmanager"
GITHUB_API_URL = "https://api.github.com/repos/{repo}/releases/latest"
```

## 📦 Структура версий

Используется **Semantic Versioning** (SemVer):

```
MAJOR.MINOR.PATCH[-PRERELEASE]
```

- **MAJOR**: Несовместимые изменения API
- **MINOR**: Новые функции (обратно совместимые)
- **PATCH**: Исправления багов

Примеры:
- `1.0.0` - Первый релиз
- `1.1.0` - Добавлена система обновлений
- `1.1.1` - Исправление багов
- `2.0.0-beta` - Мажорное обновление (beta)

## 🚀 Процесс обновления

### 1. Подготовка GitHub Release

```bash
# 1. Создайте tag
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0

# 2. Создайте Release на GitHub
# - Перейдите в Releases → Create new release
# - Выберите tag v1.2.0
# - Заполните changelog:

## ✨ Features
- Added feature X
- Improved feature Y

## 🐛 Fixes
- Fixed bug Z

## ⚠️ Breaking Changes
- Changed API endpoint format
```

### 2. Обновление на сервере

#### Автоматическое (рекомендуется):

1. Откройте веб-интерфейс XUI Manager
2. В футере нажмите "🔄 Проверить обновления"
3. Если доступно, нажмите "⬆️ Обновить до vX.X.X"
4. Подтвердите действие
5. Дождитесь перезапуска и войдите заново

#### Ручное (через API):

```bash
# Проверка обновлений
curl -X GET https://your-domain.com/manager/api/system/update/check \
  -H "Cookie: session_id=..."

# Выполнение обновления
curl -X POST https://your-domain.com/manager/api/system/update \
  -H "Cookie: session_id=..."
```

#### Через SSH:

```bash
cd /opt/xui-manager
git pull origin main
sudo systemctl restart xui-manager
```

## 🛡️ Безопасность

### Backup файлы

Автоматически создаются в `/opt/xui-manager/backups/`:

```
backup_20251030_120000.tar.gz
backup_20251030_150000.tar.gz
...
```

### Rollback при сбое

Если обновление не удалось:

```bash
# 1. Найдите последний backup
ls -lht /opt/xui-manager/backups/ | head -1

# 2. Распакуйте
cd /opt/xui-manager
tar -xzf backups/backup_YYYYMMDD_HHMMSS.tar.gz

# 3. Перезапустите
sudo systemctl restart xui-manager
```

### Lock файл

Предотвращает concurrent обновления:

```bash
# Проверка наличия
ls /opt/xui-manager/.update_lock

# Ручное удаление (если процесс завис)
rm /opt/xui-manager/.update_lock
```

## 📊 Мониторинг

### Логи

```bash
# Общие логи сервиса
sudo journalctl -u xui-manager -f

# Фильтр по обновлениям
sudo journalctl -u xui-manager | grep -i "update"

# Фильтр по expired cleanup
sudo journalctl -u xui-manager | grep -i "expired"
```

### Метрики

- **Последняя проверка**: `/opt/xui-manager/last_update_check.json`
- **Lock файл**: `/opt/xui-manager/.update_lock`
- **Backups**: `/opt/xui-manager/backups/`

## ⚙️ Фоновые задачи

### 1. Update Checker
- **Интервал**: 24 часа
- **Действие**: Проверяет GitHub releases
- **Логика**: Кэширует результаты, уведомляет через UI

### 2. Expired Users Cleanup
- **Интервал**: 1 час
- **Действие**: Находит и отключает просроченных пользователей
- **Логика**:
  ```python
  if expiry_time > 0 and expiry_time < current_time:
      if user.enable:
          disable_user(user.id)
  ```

### 3. Low Traffic Alerts
- **Интервал**: 6 часов
- **Действие**: Логирует пользователей с трафиком < 1GB
- **Порог**: 1 GB (1024³ bytes)

## 🔍 Troubleshooting

### Проблема: Обновление не появляется

```bash
# Проверьте подключение к GitHub
curl -I https://api.github.com

# Проверьте cache файл
cat /opt/xui-manager/last_update_check.json

# Принудительная проверка (удалите кэш)
rm /opt/xui-manager/last_update_check.json
```

### Проблема: Обновление зависло

```bash
# Проверьте lock файл
ls -la /opt/xui-manager/.update_lock

# Удалите lock
rm /opt/xui-manager/.update_lock

# Перезапустите сервис
sudo systemctl restart xui-manager
```

### Проблема: Git конфликты

```bash
cd /opt/xui-manager
git status

# Если есть изменения
git stash
git pull origin main
git stash pop

# Или сбросить к origin
git reset --hard origin/main
```

## 📈 Будущие улучшения

Планируется добавить:

- [ ] Webhook уведомления о новых releases
- [ ] Scheduled updates (cron-style)
- [ ] A/B testing для canary deployments
- [ ] Multi-server orchestration
- [ ] Rollback UI button
- [ ] Update history log
- [ ] Email notifications
- [ ] Telegram bot integration

## 📝 Примечания

### Онлайн пользователи

Подсчет онлайн пользователей зависит от поля `last_online` в БД:

```python
# Пользователь считается онлайн если:
last_online > (current_time - 5_minutes)
```

**Важно**: Поле `last_online` обновляется самим **3x-ui**, а не xmanager. Если в БД нет этого поля, система вернет количество всех активных пользователей.

### Лимиты GitHub API

- **Rate limit**: 60 requests/hour (unauth)
- **Rate limit**: 5000 requests/hour (auth)
- Кэширование помогает избежать лимитов

## 🤝 Contributing

При разработке новых features:

1. Обновите `CURRENT_VERSION` в `app/version.py`
2. Следуйте SemVer
3. Создайте подробный changelog
4. Тестируйте обновление на dev сервере
5. Создайте GitHub Release с тегом

---

**Версия документации**: 1.0
**Последнее обновление**: 2025-10-30
**Авторы**: Claude Code, khiziresmars
