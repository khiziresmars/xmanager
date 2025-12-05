# 📡 Система управления Inbounds в XUI Manager

## Оглавление
- [Архитектура](#архитектура)
- [Готовые шаблоны (Preset Templates)](#готовые-шаблоны-preset-templates)
- [API для работы с Inbounds](#api-для-работы-с-inbounds)
- [Создание Inbound через шаблон](#создание-inbound-через-шаблон)
- [Редактирование Inbound](#редактирование-inbound)
- [Примеры использования](#примеры-использования)

---

## Архитектура

### 📁 Структура файлов

```
app/
├── preset_templates.py     # Готовые шаблоны конфигураций
├── xui_client.py           # Клиент для работы с 3x-ui API
├── xray_generator.py       # Генератор ключей и конфигураций Xray
├── database.py             # Работа с БД (чтение inbounds)
└── main.py                 # API endpoints
```

### 🗄️ Хранение данных

**База данных:** `/etc/x-ui/x-ui.db`
- Таблица `inbounds` - все созданные inbound'ы
- Таблица `client_traffics` - пользователи каждого inbound

**Формат в БД:**
```sql
CREATE TABLE inbounds (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    up INTEGER,
    down INTEGER,
    total INTEGER,
    remark TEXT,
    enable INTEGER,
    expiry_time INTEGER,
    listen TEXT,
    port INTEGER UNIQUE,
    protocol TEXT,
    settings TEXT,          -- JSON строка
    stream_settings TEXT,   -- JSON строка
    tag TEXT UNIQUE,
    sniffing TEXT           -- JSON строка
);
```

---

## Готовые шаблоны (Preset Templates)

### 📋 Доступные шаблоны

Файл: `app/preset_templates.py`

#### 1️⃣ **VLESS + Reality** (рекомендуется)
- **ID:** `vless_reality`
- **Протокол:** VLESS
- **Транспорт:** TCP
- **Безопасность:** Reality (маскировка под HTTPS)
- **Порт:** 443
- **Параметры:**
  - `domain` - домен сайта-обманки
  - `private_key` - приватный ключ Reality
  - `short_id` - короткий ID
  - `region` - регион (RU/CN/IR/GLOBAL) для выбора оптимального dest

#### 2️⃣ **VLESS + WebSocket + TLS**
- **ID:** `vless_ws_tls`
- **Протокол:** VLESS
- **Транспорт:** WebSocket
- **Безопасность:** TLS
- **Порт:** 443
- **Использование:** Прямое подключение с SSL сертификатом

#### 3️⃣ **VLESS + WS (CDN/Nginx)**
- **ID:** `vless_ws_cdn`
- **Протокол:** VLESS
- **Транспорт:** WebSocket
- **Безопасность:** None (за Nginx/CDN)
- **Порт:** Custom
- **Использование:** За Nginx reverse proxy или Cloudflare CDN
- **Генерирует:** Готовую конфигурацию Nginx location

#### 4️⃣ **VMess + WebSocket + TLS**
- **ID:** `vmess_ws_tls`
- **Протокол:** VMess
- **Транспорт:** WebSocket
- **Классический протокол для CDN**

#### 5️⃣ **Trojan + WebSocket + TLS**
- **ID:** `trojan_ws_tls`
- **Протокол:** Trojan
- **Транспорт:** WebSocket

#### 6️⃣ **ShadowSocks 2022**
- **ID:** `ss_2022_aes256` или `ss_2022_chacha`
- **Протокол:** Shadowsocks 2022
- **Методы:** AES-256-GCM или ChaCha20-Poly1305

### 🌍 Региональная оптимизация Reality

Для каждого региона есть список рекомендуемых доменов для маскировки:

**Россия (RU):**
- `www.microsoft.com`
- `www.google.com`
- `www.cloudflare.com`
- `www.apple.com`
- `www.nvidia.com`

**Китай (CN):**
- `www.apple.com`
- `itunes.apple.com`
- `www.microsoft.com`
- `www.samsung.com`

**Иран (IR):**
- `www.speedtest.net`
- `www.samsung.com`
- `www.nvidia.com`

---

## API для работы с Inbounds

### 📥 Получение списка шаблонов

```bash
GET /api/preset-templates
```

**Ответ:**
```json
{
  "success": true,
  "templates": [
    {
      "id": "vless_reality",
      "name": "VLESS + Reality",
      "description": "Recommended protocol with HTTPS masquerading",
      "description_ru": "Рекомендуемый протокол с маскировкой под HTTPS",
      "protocol": "vless",
      "port": 443
    },
    ...
  ]
}
```

### 📄 Получение деталей шаблона

```bash
GET /api/preset-templates/{template_id}
```

**Пример:** `GET /api/preset-templates/vless_reality`

**Ответ:**
```json
{
  "success": true,
  "template": {
    "id": "vless_reality",
    "name": "VLESS + Reality",
    "description": "...",
    "protocol": "vless",
    "port": 443
  },
  "params": [
    {
      "name": "domain",
      "label": "Domain",
      "label_ru": "Домен",
      "required": true,
      "type": "string"
    },
    {
      "name": "private_key",
      "label": "Private Key (Reality)",
      "required": true,
      "type": "string"
    },
    {
      "name": "region",
      "label": "Target Region",
      "type": "select",
      "options": ["RU", "CN", "IR", "GLOBAL"],
      "default": "GLOBAL"
    }
  ]
}
```

### 👁️ Предпросмотр конфигурации

```bash
GET /api/preset-templates/{template_id}/preview?domain=example.com&port=443
```

**Ответ:** Готовая конфигурация inbound в формате 3x-ui

### ✨ Применение шаблона (создание Inbound)

```bash
POST /api/preset-templates/{template_id}/apply
Content-Type: application/json

{
  "remark": "My VLESS Reality Server",
  "domain": "example.com",
  "private_key": "gK3C...",
  "short_id": "abcd1234",
  "region": "RU",
  "port": 443
}
```

**Ответ:**
```json
{
  "success": true,
  "message": "Inbound 'My VLESS Reality Server' создан",
  "inbound": {
    "id": 1,
    "remark": "My VLESS Reality Server",
    "protocol": "vless",
    "port": 443,
    ...
  }
}
```

### 📋 Получение списка Inbounds

```bash
GET /api/inbounds
```

**Ответ:**
```json
{
  "inbounds": [
    {
      "id": 1,
      "remark": "VLESS Reality Main",
      "protocol": "vless",
      "port": 443,
      "enable": true,
      "up": 1234567,
      "down": 9876543,
      "total": 0,
      "client_count": 25
    },
    ...
  ]
}
```

### 🔍 Получение конкретного Inbound

```bash
GET /api/inbounds/{inbound_id}
```

### ✏️ Редактирование Inbound

```bash
PUT /api/inbounds/{inbound_id}
Content-Type: application/json

{
  "remark": "Updated name",
  "enable": true,
  "settings": {...},
  "streamSettings": {...}
}
```

---

## Создание Inbound через шаблон

### Вариант 1: Через Frontend

1. Открыть `/manager/`
2. Перейти в раздел "Inbounds" → "Создать из шаблона"
3. Выбрать шаблон (например, VLESS + Reality)
4. Заполнить параметры:
   - Название (remark)
   - Домен (для TLS шаблонов)
   - Регион (для Reality)
   - Порт (если требуется)
5. Нажать "Создать"

### Вариант 2: Через API

```bash
# 1. Получить список шаблонов
curl -X GET "https://your-domain/api/preset-templates" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 2. Посмотреть требуемые параметры
curl -X GET "https://your-domain/api/preset-templates/vless_reality" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Применить шаблон
curl -X POST "https://your-domain/api/preset-templates/vless_reality/apply" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "remark": "VPN Server RU",
    "region": "RU",
    "private_key": "gK3C_GENERATED_KEY_HERE",
    "short_id": "a1b2c3d4",
    "port": 443
  }'
```

### Вариант 3: Программно (Python)

```python
import requests

API_URL = "https://your-domain/api"
TOKEN = "your_api_token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Применить шаблон VLESS Reality
response = requests.post(
    f"{API_URL}/preset-templates/vless_reality/apply",
    headers=headers,
    json={
        "remark": "Russia Server",
        "region": "RU",
        "private_key": "YOUR_PRIVATE_KEY",
        "short_id": "12345678",
        "port": 443
    }
)

result = response.json()
if result["success"]:
    print(f"Inbound created: {result['inbound']['id']}")
else:
    print(f"Error: {result['message']}")
```

---

## Редактирование Inbound

### Основные операции

#### 1. Изменение порта

```bash
POST /api/inbounds/{id}/update-port?new_port=8443
```

#### 2. Обновление Reality настроек

```bash
POST /api/inbounds/{id}/update-reality
Content-Type: application/json

{
  "dest": "www.google.com:443",
  "serverNames": ["www.google.com"],
  "privateKey": "new_key",
  "shortIds": ["abcd1234"]
}
```

#### 3. Настройка Sniffing (детекция трафика)

```bash
POST /api/inbounds/{id}/update-sniffing
Content-Type: application/json

{
  "enabled": true,
  "destOverride": ["http", "tls", "quic", "fakedns"]
}
```

#### 4. Обновление Fingerprint (для обхода блокировок)

```bash
POST /api/inbounds/{id}/update-fingerprints
Content-Type: application/json

{
  "fingerprint": "chrome"
}
```

Доступные fingerprints:
- `chrome` - Google Chrome
- `firefox` - Mozilla Firefox
- `safari` - Apple Safari
- `edge` - Microsoft Edge
- `ios` - iOS Safari
- `android` - Android Chrome
- `random` - случайный

---

## Примеры использования

### Пример 1: Создание VLESS Reality для России

```bash
# Генерация ключей Reality (если нужно)
curl -X POST "https://your-domain/api/xray/generate-keys" \
  -H "Authorization: Bearer TOKEN"
# Ответ: {"privateKey": "...", "publicKey": "..."}

# Создание inbound
curl -X POST "https://your-domain/api/preset-templates/vless_reality/apply" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "remark": "RU VLESS Reality",
    "region": "RU",
    "private_key": "gK3C...",
    "port": 443
  }'
```

### Пример 2: Создание VLESS WS для CDN (Cloudflare)

```bash
curl -X POST "https://your-domain/api/preset-templates/vless_ws_cdn/apply" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "remark": "CF CDN Server",
    "port": 8080,
    "ws_path": "/vless-ws",
    "host": "your-domain.com"
  }'
```

После создания вы получите:
1. Созданный inbound на порту 8080
2. Готовую конфигурацию Nginx для добавления в `/etc/nginx/sites-enabled/`

### Пример 3: Массовое создание Inbounds для разных регионов

```python
import requests

API_URL = "https://your-domain/api"
TOKEN = "your_token"

regions = ["RU", "CN", "IR"]
private_key = "gK3C_YOUR_KEY"

for region in regions:
    response = requests.post(
        f"{API_URL}/preset-templates/vless_reality/apply",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "remark": f"VLESS Reality {region}",
            "region": region,
            "private_key": private_key,
            "port": 443  # или разные порты: 443 + offset
        }
    )

    result = response.json()
    if result["success"]:
        print(f"✓ Created {region}: inbound ID {result['inbound']['id']}")
    else:
        print(f"✗ Failed {region}: {result['message']}")
```

---

## 🔧 Расширение системы шаблонов

### Добавление своего шаблона

Отредактируйте `app/preset_templates.py`:

```python
PRESET_TEMPLATES = {
    # ... существующие шаблоны ...

    "my_custom_template": {
        "name": "My Custom Protocol",
        "description": "Custom configuration",
        "protocol": "vless",  # или vmess, trojan, shadowsocks
        "port": 8443,
        "settings": {
            "clients": [],
            "decryption": "none"
        },
        "streamSettings": {
            "network": "tcp",  # tcp, ws, grpc, quic, kcp
            "security": "reality",  # none, tls, reality, xtls
            # ... настройки транспорта ...
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls"]
        }
    }
}
```

### Использование плейсхолдеров

В шаблонах можно использовать переменные:

- `{{DOMAIN}}` - домен
- `{{PORT}}` - порт
- `{{PRIVATE_KEY}}` - приватный ключ Reality
- `{{SHORT_ID}}` - короткий ID Reality
- `{{WS_PATH}}` - путь WebSocket
- `{{PASSWORD}}` - пароль (для SS)

Они автоматически заменяются при применении шаблона.

---

## 📚 Дополнительные ресурсы

- [3x-ui GitHub](https://github.com/MHSanaei/3x-ui)
- [Xray Документация](https://xtls.github.io/)
- [Reality Protocol](https://github.com/XTLS/REALITY)

---

**Версия документации:** 2.3.4
**Последнее обновление:** 2025-12-05
