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
    XUI_CONFIG_PATH: str = "/usr/local/x-ui/bin/config.json"
    
    # API ключ для защиты (опционально)
    API_KEY: str = os.getenv("XUI_MANAGER_API_KEY", "")
    
    # Пути
    BACKUP_DIR: str = "/opt/xui-manager/backups"
    TEMPLATES_FILE: str = "/opt/xui-manager/templates.json"
    LOG_FILE: str = "/opt/xui-manager/logs/app.log"
    
    # Лимиты
    MAX_BULK_CREATE: int = 100
    MAX_BULK_DELETE: int = 500
    
    class Config:
        env_file = "/opt/xui-manager/.env"
        env_file_encoding = 'utf-8'

# Создаем экземпляр настроек
settings = Settings()