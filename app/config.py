#!/usr/bin/env python3
"""
Конфигурация приложения
"""

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Основные настройки
    APP_NAME: str = "X-UI Manager"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Сетевые настройки
    HOST: str = "0.0.0.0"
    PORT: int = 8888
    
    # База данных
    XUI_DB_PATH: str = "/etc/x-ui/x-ui.db"
    DB_PATH: str = "/etc/x-ui/x-ui.db"  # Alias для совместимости
    XUI_CONFIG_PATH: str = "/usr/local/x-ui/bin/config.json"

    # Аутентификация
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"

    # API ключ для защиты (опционально)
    API_KEY: str = os.getenv("XUI_MANAGER_API_KEY", "")
    
    # Пути
    BACKUP_DIR: str = "/opt/xui-manager/backups"
    TEMPLATES_FILE: str = "/opt/xui-manager/templates.json"
    LOG_FILE: str = "/opt/xui-manager/logs/app.log"
    
    # Лимиты
    MAX_BULK_CREATE: int = 100
    MAX_BULK_DELETE: int = 500

    # Server ID
    SERVER_ID_FILE: str = "/opt/xui-manager/server_id.txt"

    class Config:
        env_file = "/opt/xui-manager/.env"
        env_file_encoding = 'utf-8'

# Создаем экземпляр настроек
settings = Settings()

def get_or_create_server_id() -> str:
    """Получить или создать уникальный ID сервера"""
    import os
    import random

    server_id_file = settings.SERVER_ID_FILE

    # Если файл существует, читаем ID
    if os.path.exists(server_id_file):
        try:
            with open(server_id_file, 'r') as f:
                server_id = f.read().strip()
                if server_id and len(server_id) == 10 and server_id.isdigit():
                    return server_id
        except Exception as e:
            print(f"Error reading server ID: {e}")

    # Генерируем новый 10-значный ID
    server_id = ''.join([str(random.randint(0, 9)) for _ in range(10)])

    # Сохраняем в файл
    try:
        os.makedirs(os.path.dirname(server_id_file), exist_ok=True)
        with open(server_id_file, 'w') as f:
            f.write(server_id)
        print(f"Generated new server ID: {server_id}")
    except Exception as e:
        print(f"Error saving server ID: {e}")

    return server_id

# Генерируем или загружаем Server ID при запуске
SERVER_ID = get_or_create_server_id()