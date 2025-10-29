#!/usr/bin/env python3
"""
Модуль аутентификации для XUI-Manager
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Cookie, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
import logging

logger = logging.getLogger(__name__)

# Хардкод учетных данных
ADMIN_USERNAME = "esmarsme"
ADMIN_PASSWORD_HASH = hashlib.sha256("EsmarsMe13AMS1".encode()).hexdigest()

# Хранилище активных сессий (в продакшене лучше использовать Redis)
active_sessions = {}

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
