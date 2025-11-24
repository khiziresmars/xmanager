#!/usr/bin/env python3
"""
Модуль аутентификации для XUI-Manager
"""

import hashlib
import secrets
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from fastapi import Cookie, HTTPException, Request, Response, Header
from fastapi.responses import RedirectResponse
import logging
from config import settings

logger = logging.getLogger(__name__)

# Учетные данные из конфигурации
ADMIN_USERNAME = os.getenv("XUI_MANAGER_USERNAME", settings.ADMIN_USERNAME)
ADMIN_PASSWORD = os.getenv("XUI_MANAGER_PASSWORD", settings.ADMIN_PASSWORD)
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

# Хранилище активных сессий (в продакшене лучше использовать Redis)
active_sessions = {}

# Файл для хранения API токенов
TOKENS_FILE = "/opt/xui-manager/api_tokens.json"

class SessionManager:
    """Управление сессиями пользователей"""

    @staticmethod
    def create_session(username: str) -> str:
        """Создание новой сессии"""
        session_id = secrets.token_urlsafe(32)
        active_sessions[session_id] = {
            "username": username,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        logger.info(f"Session created for user: {username}")
        return session_id

    @staticmethod
    def validate_session(session_id: Optional[str]) -> bool:
        """Проверка валидности сессии"""
        if not session_id or session_id not in active_sessions:
            return False

        session = active_sessions[session_id]

        # Проверяем время последней активности (таймаут 24 часа)
        if datetime.now() - session["last_activity"] > timedelta(hours=24):
            del active_sessions[session_id]
            return False

        # Обновляем время последней активности
        session["last_activity"] = datetime.now()
        return True

    @staticmethod
    def destroy_session(session_id: str):
        """Удаление сессии"""
        if session_id in active_sessions:
            username = active_sessions[session_id].get("username", "unknown")
            del active_sessions[session_id]
            logger.info(f"Session destroyed for user: {username}")

def authenticate_user(username: str, password: str) -> bool:
    """Проверка учетных данных"""
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH

async def get_current_user(session_id: Optional[str] = Cookie(None, alias="xui_session")):
    """Dependency для проверки аутентификации"""
    if not SessionManager.validate_session(session_id):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return active_sessions[session_id]["username"]

async def optional_user(session_id: Optional[str] = Cookie(None, alias="xui_session")):
    """Dependency для опциональной проверки аутентификации"""
    if SessionManager.validate_session(session_id):
        return active_sessions[session_id]["username"]
    return None

class TokenManager:
    """Управление API токенами"""

    @staticmethod
    def _load_tokens() -> Dict:
        """Загрузка токенов из файла"""
        if os.path.exists(TOKENS_FILE):
            try:
                with open(TOKENS_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading tokens: {e}")
        return {}

    @staticmethod
    def _save_tokens(tokens: Dict):
        """Сохранение токенов в файл"""
        try:
            os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
            with open(TOKENS_FILE, 'w') as f:
                json.dump(tokens, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")

    @staticmethod
    def generate_token(name: str, username: str) -> Dict:
        """Генерация нового API токена"""
        token = f"xui_{secrets.token_urlsafe(32)}"
        tokens = TokenManager._load_tokens()

        tokens[token] = {
            "name": name,
            "username": username,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "active": True
        }

        TokenManager._save_tokens(tokens)
        logger.info(f"API token created: {name} for user {username}")
        return {"token": token, "name": name}

    @staticmethod
    def validate_token(token: str) -> bool:
        """Проверка валидности токена"""
        tokens = TokenManager._load_tokens()

        if token in tokens and tokens[token].get("active", False):
            # Обновляем время последнего использования
            tokens[token]["last_used"] = datetime.now().isoformat()
            TokenManager._save_tokens(tokens)
            return True

        return False

    @staticmethod
    def revoke_token(token: str) -> bool:
        """Отзыв токена"""
        tokens = TokenManager._load_tokens()

        if token in tokens:
            tokens[token]["active"] = False
            TokenManager._save_tokens(tokens)
            logger.info(f"API token revoked: {tokens[token].get('name')}")
            return True

        return False

    @staticmethod
    def delete_token(token: str) -> bool:
        """Удаление токена"""
        tokens = TokenManager._load_tokens()

        if token in tokens:
            name = tokens[token].get('name')
            del tokens[token]
            TokenManager._save_tokens(tokens)
            logger.info(f"API token deleted: {name}")
            return True

        return False

    @staticmethod
    def list_tokens() -> List[Dict]:
        """Получение списка всех токенов"""
        tokens = TokenManager._load_tokens()
        result = []

        for token, data in tokens.items():
            result.append({
                "token_preview": token[:20] + "...",  # Показываем только начало токена
                "full_token": token,  # Полный токен для копирования
                "name": data.get("name"),
                "username": data.get("username"),
                "created_at": data.get("created_at"),
                "last_used": data.get("last_used"),
                "active": data.get("active", True)
            })

        return result

def validate_api_token(authorization: Optional[str] = Header(None)) -> bool:
    """Dependency для проверки API токена"""
    if not authorization:
        return False

    # Ожидаем формат: Bearer <token>
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        return TokenManager.validate_token(token)

    return False
