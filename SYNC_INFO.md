# Синхронизация данных между client_traffics и inbounds.settings

## Обзор

Начиная с x-ui версии 2.8.5, веб-панель требует, чтобы данные клиентов хранились как в таблице `client_traffics`, так и в JSON поле `inbounds.settings`.

Все функции в `database.py` теперь автоматически синхронизируют данные между этими двумя источниками.

## Синхронизируемые поля

| Поле в client_traffics | Поле в JSON | Описание |
|----------------------|-------------|----------|
| `expiry_time` | `expiryTime` | Время истечения в миллисекундах |
| `total` | `totalGB` | Лимит трафика в байтах |
| `enable` | `enable` | Статус активности (boolean) |
| `reset` | `reset` | Период сброса трафика |

## Обновленные функции

Все следующие функции автоматически синхронизируют изменения в JSON:

### Управление трафиком
- `update_user_traffic(user_id, new_limit)` - обновление лимита трафика
- `reset_traffic_for_users(user_ids, new_limit)` - сброс трафика и установка нового лимита

### Управление статусом
- `toggle_user_status(user_id, enable)` - блокировка/разблокировка одного пользователя
- `bulk_toggle_users(user_ids, enable)` - массовая блокировка/разблокировка

### Управление сроком действия
- `update_user_expiry(user_id, expiry_time)` - обновление срока действия
- `bulk_extend_expiry(user_ids, days)` - продление срока на N дней

### Создание пользователей
- `create_user(user_data)` - создание нового пользователя с полной структурой для x-ui 2.8.5

## Внутренние функции

### `_sync_client_to_json(cursor, user_id, email=None)`
Синхронизирует данные одного клиента из `client_traffics` в `inbounds.settings` JSON.

**Параметры:**
- `cursor` - курсор БД
- `user_id` - ID пользователя
- `email` - Email пользователя (опционально)

**Возвращает:** `True` если синхронизация успешна

### `_sync_multiple_clients_to_json(cursor, user_ids)`
Синхронизирует несколько клиентов.

**Параметры:**
- `cursor` - курсор БД
- `user_ids` - список ID пользователей

**Возвращает:** количество успешно синхронизированных клиентов

## Структура клиента в JSON (x-ui 2.8.5)

```json
{
  "email": "user@example.com",
  "id": "uuid-or-number",
  "enable": true,
  "expiryTime": 1786116809000,
  "totalGB": 107374182400,
  "limitIp": 0,
  "reset": 0,
  "comment": "",
  "tgId": "",
  "subId": "",
  "created_at": 1761582643000,
  "updated_at": 1761582737611,

  // Для Shadowsocks:
  "method": "chacha20-ietf-poly1305",
  "password": "password"
}
```

## Тестирование синхронизации

Используйте скрипт `/tmp/test_sync.py` для проверки синхронизации данных:

```bash
python3 /tmp/test_sync.py
```

## Миграция существующих данных

Если у вас есть старые клиенты без полей в JSON, используйте скрипт `/tmp/sync_client_expiry_to_json.py`:

```bash
python3 /tmp/sync_client_expiry_to_json.py
systemctl restart x-ui
```

## Важные замечания

1. **Автоматическая синхронизация**: Все операции через xui-manager API автоматически синхронизируют данные
2. **Ручные изменения**: Если вы изменяете данные напрямую в БД, запустите скрипт синхронизации
3. **Перезапуск x-ui**: После массовых изменений рекомендуется перезапустить x-ui для обновления кэша
4. **Timestamp**: Каждое изменение обновляет поле `updated_at` в JSON

## API примеры

### Продление срока
```bash
curl -X POST http://localhost:8888/api/users/extend-expiry \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["user-id-1", "user-id-2"], "days": 30}'
```

### Сброс трафика
```bash
curl -X POST http://localhost:8888/api/users/reset-traffic \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["user-id-1"], "new_limit": 107374182400}'
```

### Блокировка пользователей
```bash
curl -X POST http://localhost:8888/api/users/toggle-status \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["user-id-1"], "enable": false}'
```
