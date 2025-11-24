#!/usr/bin/env python3
"""
X-UI Manager API - Управление пользователями 3x-ui
Универсальный инструмент для управления базой пользователей 3x-ui
"""

from fastapi import FastAPI, HTTPException, Depends, Query, Response, Cookie, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
import logging
from datetime import datetime
import os
import sys
import json
import sqlite3
import subprocess

# Добавляем путь для импорта локальных модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import XUIDatabase
from models import *
from config import settings, SERVER_ID
from auth import SessionManager, TokenManager, authenticate_user, get_current_user, optional_user, ADMIN_USERNAME
from app.queue import queue_manager, QueueStatus
from app.version import get_current_version, get_version_info, CURRENT_VERSION
from app.update_manager import update_manager
from app.background_tasks import background_tasks
from app.ssl_manager import ssl_manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI(
    title="X-UI Manager API",
    description="API для управления пользователями 3x-ui",
    version=CURRENT_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware для проверки аутентификации
@app.middleware("http")
async def auth_middleware(request, call_next):
    """Middleware для проверки аутентификации на всех защищенных маршрутах"""
    # Публичные маршруты, не требующие аутентификации
    public_paths = ["/login", "/api/auth/login", "/api/health", "/api/version", "/favicon.ico"]

    # Проверяем, является ли путь публичным
    if request.url.path in public_paths:
        return await call_next(request)

    # Для API маршрутов проверяем сессию или API токен
    if request.url.path.startswith("/api/"):
        # Сначала проверяем API токен в заголовке Authorization
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:]
            if TokenManager.validate_token(token):
                return await call_next(request)

        # Если токена нет или он невалидный, проверяем сессию
        session_id = request.cookies.get("xui_session")
        if not SessionManager.validate_session(session_id):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"}
            )

    # Для главной страницы перенаправление обрабатывается в самом роуте
    return await call_next(request)

# Подключение статических файлов
if os.path.exists("/opt/xui-manager/static"):
    app.mount("/static", StaticFiles(directory="/opt/xui-manager/static"), name="static")

# Favicon route
@app.get("/favicon.ico")
async def favicon():
    """Return a simple key emoji favicon"""
    # 16x16 ICO with key symbol
    import base64
    ico_data = base64.b64decode(
        "AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAQAABILAAASCwAAAAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AIiIiP+IiIj/////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wCIiIj/iIiI/4iIiP////8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8AiIiI/4iIiP+IiIj/////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AIiIiP+IiIj/iIiI/////wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wCIiIj/iIiI/4iIiP////8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8AiIiI/4iIiP+IiIj/iIiI/4iIiP+IiIj/iIiI/4iIiP+IiIj/////AP///wD///8A////AP///wD///8A////AIiIiP+IiIj/iIiI/4iIiP+IiIj/iIiI/4iIiP+IiIj/iIiI/////wD///8A////AP///wD///8A////AP///wCIiIj/iIiI/4iIiP////8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8AiIiI/4iIiP+IiIj/////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AIiIiP+IiIj/iIiI/////wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wCIiIj/iIiI/4iIiP////8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8AiIiI/4iIiP+IiIj/////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AIiIiP+IiIj/////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A//8AAP//AAD8PwAA/D8AAPw/AAD8PwAA/D8AAPw/AAAAAAAAAAAAAAw/AAD8PwAA/D8AAPw/AAD8PwAA/n8AAP//AAA="
    )
    return Response(content=ico_data, media_type="image/x-icon")

# Инициализация базы данных
db = XUIDatabase()

# ==================== LIFECYCLE EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Запуск фоновых задач при старте приложения"""
    logger.info("Application startup - starting background tasks...")
    await background_tasks.start()
    logger.info("Background tasks started successfully")

    # Check SSL certificate and auto-renew if needed
    try:
        ssl_result = ssl_manager.check_and_auto_renew()
        if ssl_result.get("renewed"):
            logger.info(f"SSL certificate auto-renewed: {ssl_result.get('message')}")
        else:
            logger.info(f"SSL check: {ssl_result.get('message')}")
    except Exception as e:
        logger.warning(f"SSL auto-check failed: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Остановка фоновых задач при остановке приложения"""
    logger.info("Application shutdown - stopping background tasks...")
    await background_tasks.stop()
    logger.info("Background tasks stopped successfully")

# ========================= API ENDPOINTS =========================

# ==================== AUTHENTICATION ====================

class LoginRequest(BaseModel):
    """Запрос на вход"""
    username: str
    password: str

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Страница входа"""
    with open("/opt/xui-manager/templates/login.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/auth/login")
async def login(credentials: LoginRequest, response: Response):
    """Аутентификация пользователя"""
    if authenticate_user(credentials.username, credentials.password):
        session_id = SessionManager.create_session(credentials.username)
        response.set_cookie(
            key="xui_session",
            value=session_id,
            httponly=True,
            max_age=86400,  # 24 часа
            samesite="lax"
        )
        return {"success": True, "message": "Login successful"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/auth/logout")
async def logout(response: Response, session_id: Optional[str] = Cookie(None, alias="xui_session")):
    """Выход из системы"""
    if session_id:
        SessionManager.destroy_session(session_id)
    response.delete_cookie(key="xui_session")
    return {"success": True, "message": "Logged out"}

# ==================== API TOKEN MANAGEMENT ====================

class TokenCreateRequest(BaseModel):
    """Запрос на создание токена"""
    name: str = Field(..., description="Название токена")

@app.post("/api/tokens/generate")
async def generate_api_token(request: TokenCreateRequest):
    """Генерация нового API токена (требует аутентификации через сессию)"""
    result = TokenManager.generate_token(request.name, ADMIN_USERNAME)
    return {
        "success": True,
        "token": result["token"],
        "name": result["name"],
        "message": "Token generated successfully. Save it securely - it won't be shown again!"
    }

@app.get("/api/tokens")
async def list_api_tokens():
    """Получение списка всех токенов"""
    tokens = TokenManager.list_tokens()
    return {"tokens": tokens}

@app.post("/api/tokens/{token}/revoke")
async def revoke_api_token(token: str):
    """Отзыв токена (деактивация)"""
    success = TokenManager.revoke_token(token)
    if success:
        return {"success": True, "message": "Token revoked"}
    raise HTTPException(status_code=404, detail="Token not found")

@app.delete("/api/tokens/{token}")
async def delete_api_token(token: str):
    """Удаление токена"""
    success = TokenManager.delete_token(token)
    if success:
        return {"success": True, "message": "Token deleted"}
    raise HTTPException(status_code=404, detail="Token not found")

@app.get("/", response_class=HTMLResponse)
async def web_interface(username: Optional[str] = Depends(optional_user)):
    """Веб-интерфейс для управления"""
    # Если пользователь не авторизован, перенаправляем на страницу входа
    if not username:
        return RedirectResponse(url="login", status_code=302)

    with open("/opt/xui-manager/templates/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db.check_connection(),
        "server_id": SERVER_ID
    }

@app.get("/api/version")
async def get_version():
    """Получение версии приложения"""
    return {
        "version": CURRENT_VERSION,
        "name": "Агент Мастера ключей"
    }

@app.get("/api/stats")
async def get_stats():
    """Получение статистики системы"""
    try:
        stats = db.get_system_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/monitoring/health")
async def get_server_health():
    """Получение информации о состоянии сервера"""
    try:
        health = db.get_server_health()
        return health
    except Exception as e:
        logger.error(f"Error getting server health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/monitoring/online-users")
async def get_online_users():
    """Получение количества онлайн пользователей (последние 2 минуты активности)"""
    try:
        online_count = db.get_truly_online_users_count()
        return {"online_users": online_count}
    except Exception as e:
        logger.error(f"Error getting online users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================

@app.get("/api/users")
async def get_users(
    inbound_id: Optional[int] = None,
    limit: Optional[int] = Query(100, ge=1, le=1000),
    offset: Optional[int] = Query(0, ge=0),
    search: Optional[str] = None
):
    """Получение списка пользователей"""
    try:
        result = db.get_users(inbound_id, limit, offset, search)
        return result
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users")
async def create_user(user: UserCreate):
    """Создание нового пользователя"""
    try:
        result = db.create_user(user.model_dump())
        if result["success"]:
            return {"message": "User created successfully", "user": result["user"]}
        else:
            raise HTTPException(status_code=400, detail=result["error"])
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str):
    """Удаление пользователя"""
    try:
        result = db.delete_user(user_id)
        if result["success"]:
            return {"message": "User deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=result["error"])
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/bulk-create")
async def bulk_create_users(request: BulkCreateRequest):
    """Массовое создание пользователей по шаблону (до 100 пользователей)"""
    try:
        # Для малых объемов (до 100) используем прямое создание
        if request.count > 100:
            raise HTTPException(
                status_code=400,
                detail="For more than 100 users, use /api/queues/bulk-create endpoint"
            )

        result = db.bulk_create_users(
            request.template.model_dump(),
            request.count,
            request.inbound_id
        )
        return {
            "message": f"Created {result['created']} users",
            "created": result['created'],
            "users": result['users']
        }
    except Exception as e:
        logger.error(f"Error in bulk create: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/bulk-create-all-inbounds")
async def bulk_create_users_all_inbounds(request: Dict[str, Any]):
    """Массовое создание пользователей сразу во всех inbounds через параллельные очереди

    Создает одного пользователя с одинаковым email во всех указанных inbound'ах
    Разбивает на несколько параллельных очередей по 100 пользователей для оптимизации

    Request body:
    {
        "template": {...},  # Шаблон пользователя
        "count": 10,        # Количество пользователей
        "inbound_ids": [1, 2, 3]  # Список inbound ID (или "all")
    }
    """
    try:
        template = request.get("template", {})
        count = request.get("count", 0)
        inbound_ids_input = request.get("inbound_ids", [])

        if count <= 0 or count > 1000:
            raise HTTPException(
                status_code=400,
                detail="Count must be between 1 and 1000"
            )

        # Если inbound_ids == "all", получаем все inbounds
        if inbound_ids_input == "all":
            inbounds = db.get_inbounds()
            inbound_ids = [inbound['id'] for inbound in inbounds]
        else:
            inbound_ids = inbound_ids_input

        if not inbound_ids or len(inbound_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one inbound_id is required"
            )

        if len(inbound_ids) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 inbounds allowed"
            )

        # Проверяем общее количество операций
        total_operations = count * len(inbound_ids)
        if total_operations > 5000:
            raise HTTPException(
                status_code=400,
                detail=f"Too many operations ({total_operations}). Maximum 5000 (count * inbounds). Try reducing count or number of inbounds."
            )

        # Получаем информацию обо всех инбаундах для metadata
        all_inbounds = db.get_inbounds()
        inbounds_map = {inbound['id']: inbound for inbound in all_inbounds}

        # ОПТИМИЗАЦИЯ: разбиваем на несколько параллельных очередей по 100 пользователей
        # Например: 250 пользователей в 2 инбаундах = 6 очередей (3 на каждый инбаунд)
        queue_ids = []
        batch_size = 100

        for inbound_id in inbound_ids:
            # Получаем информацию об инбаунде
            inbound_info = inbounds_map.get(inbound_id, {})
            inbound_remark = inbound_info.get('remark', f'Inbound {inbound_id}')
            protocol = inbound_info.get('protocol', 'unknown')

            batches = (count + batch_size - 1) // batch_size  # Округление вверх

            for batch_num in range(batches):
                start_index = batch_num * batch_size
                batch_count = min(batch_size, count - start_index)

                # Создаем обычную bulk очередь для каждого батча с metadata
                queue_id = queue_manager.create_queue(
                    "bulk_create",
                    {
                        "template": template,
                        "count": batch_count,
                        "inbound_id": inbound_id,
                        "start_index": start_index  # Начальный индекс для email
                    },
                    metadata={
                        "inbound_id": inbound_id,
                        "inbound_remark": inbound_remark,
                        "protocol": protocol.upper(),
                        "prefix": template.get('prefix', 'user'),
                        "batch_number": batch_num + 1,
                        "total_batches_for_inbound": batches,
                        "multi_inbound": True
                    }
                )
                queue_ids.append(queue_id)

                logger.info(f"Created queue {queue_id[:8]}... for {inbound_remark} ({protocol}) - batch {batch_num + 1}/{batches}")

                # Запускаем обработку в фоне
                queue_manager.start_queue_processing(queue_id, db)

        return {
            "queue_ids": queue_ids,
            "queues_count": len(queue_ids),
            "message": f"Created {len(queue_ids)} parallel queues for {count} users across {len(inbound_ids)} inbounds ({total_operations} total operations)",
            "count": count,
            "inbound_ids": inbound_ids,
            "total_operations": total_operations
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating multi-inbound queues: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== УПРАВЛЕНИЕ ТРАФИКОМ ====================

@app.get("/api/users/low-traffic")
async def get_low_traffic_users(
    threshold: int = Query(1024, description="Порог трафика в байтах"),
    inbound_id: Optional[int] = Query(None, description="Фильтр по инбаунду"),
    sort_by: str = Query("remaining", description="Поле для сортировки"),
    order: str = Query("asc", description="Порядок сортировки (asc/desc)")
):
    """Получение пользователей с низким остатком трафика"""
    try:
        users = db.get_low_traffic_users(threshold, inbound_id, sort_by, order)
        return {
            "users": users,
            "count": len(users),
            "threshold": threshold
        }
    except Exception as e:
        logger.error(f"Error getting low traffic users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/unlimited")
async def get_unlimited_users(
    inbound_id: Optional[int] = Query(None, description="Фильтр по инбаунду"),
    enabled_only: bool = Query(False, description="Только активные"),
    sort_by: str = Query("used", description="Поле для сортировки"),
    order: str = Query("desc", description="Порядок сортировки (asc/desc)"),
    filter_type: str = Query("expiry", description="Тип фильтра: expiry (бессрочные), traffic (без лимита трафика), both (оба)"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Максимальное количество результатов"),
    offset: Optional[int] = Query(0, ge=0, description="Смещение для пагинации")
):
    """Получение пользователей с безлимитным трафиком или бессрочных"""
    try:
        users = db.get_unlimited_traffic_users(inbound_id, enabled_only, sort_by, order, filter_type)

        # Применяем пагинацию если указан limit
        total_count = len(users)
        if limit is not None:
            users = users[offset:offset + limit]

        return {
            "users": users,
            "count": len(users),
            "total": total_count,
            "filter_type": filter_type,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting unlimited users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/expired")
async def get_expired_users(
    inbound_id: Optional[int] = Query(None, description="Фильтр по инбаунду")
):
    """Получение пользователей с истекшим сроком действия"""
    try:
        users = db.get_expired_users(inbound_id)
        return {
            "users": users,
            "count": len(users)
        }
    except Exception as e:
        logger.error(f"Error getting expired users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/disabled")
async def get_disabled_users(
    inbound_id: Optional[int] = Query(None, description="Фильтр по инбаунду")
):
    """Получение отключенных пользователей"""
    try:
        users = db.get_disabled_users(inbound_id)
        return {
            "users": users,
            "count": len(users)
        }
    except Exception as e:
        logger.error(f"Error getting disabled users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/bulk-delete")
async def bulk_delete_users(
    request: Dict[str, List[int]],
    username: str = Depends(get_current_user)
):
    """Массовое удаление пользователей

    Request body: {"user_ids": [1, 2, 3, ...]}
    """
    try:
        user_ids = request.get("user_ids", [])
        if not user_ids:
            raise HTTPException(status_code=400, detail="user_ids list is required")

        if len(user_ids) > 1000:
            raise HTTPException(status_code=400, detail="Maximum 1000 users can be deleted at once")

        result = db.bulk_delete_users(user_ids)

        if result["success"]:
            return {
                "message": f"Successfully deleted {result['deleted']} users",
                "deleted": result["deleted"],
                "errors": result.get("errors", [])
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Deletion failed: {result.get('errors', ['Unknown error'])}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}/traffic")
async def update_user_traffic(user_id: str, request: UpdateTrafficRequest):
    """Обновление лимита трафика пользователя"""
    try:
        result = db.update_user_traffic(user_id, request.traffic_limit)
        if result["success"]:
            return {"message": "Traffic limit updated successfully"}
        else:
            raise HTTPException(status_code=404, detail=result["error"])
    except Exception as e:
        logger.error(f"Error updating traffic: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/reset-traffic")
async def reset_traffic(request: ResetTrafficRequest):
    """Сброс трафика для группы пользователей"""
    try:
        result = db.reset_traffic_for_users(
            request.user_ids,
            request.new_limit
        )
        return {
            "message": f"Reset traffic for {result['updated']} users",
            "updated": result['updated']
        }
    except Exception as e:
        logger.error(f"Error resetting traffic: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/add-traffic")
async def add_traffic(request: AddTrafficRequest):
    """Добавление трафика к существующему лимиту"""
    try:
        result = db.add_traffic_for_users(
            request.user_ids,
            request.additional_traffic
        )
        return {
            "message": f"Added traffic for {result['updated']} users",
            "updated": result['updated']
        }
    except Exception as e:
        logger.error(f"Error adding traffic: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/set-limit")
async def set_limit(request: SetLimitRequest):
    """Установка лимита трафика без сброса использованного"""
    try:
        result = db.set_limit_for_users(
            request.user_ids,
            request.new_limit
        )
        return {
            "message": f"Set limit for {result['updated']} users",
            "updated": result['updated']
        }
    except Exception as e:
        logger.error(f"Error setting limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== БЛОКИРОВКА И УПРАВЛЕНИЕ СТАТУСОМ ====================

@app.put("/api/users/{user_id}/toggle")
async def toggle_user_status(user_id: int, username: str = Depends(get_current_user)):
    """Переключение статуса одного пользователя (enable/disable)"""
    try:
        # Get current user status from database directly
        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, email, enable, inbound_id
            FROM client_traffics
            WHERE id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        current_enable = row[2]

        # Toggle: if enabled (1 or 'true') -> disable (0), if disabled -> enable (1)
        if current_enable == 1 or current_enable == 'true' or current_enable == True:
            new_status = False
        else:
            new_status = True

        # Use bulk_toggle_users to update
        result = db.bulk_toggle_users([user_id], new_status)
        action = "enabled" if new_status else "disabled"

        return {
            "message": f"User {action}",
            "user_id": user_id,
            "enabled": new_status,
            "updated": result['updated']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling user status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}/expiry")
async def set_user_expiry(
    user_id: int,
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """Установка срока действия для одного пользователя

    Можно указать либо expiry_time (Unix timestamp в миллисекундах),
    либо expiry_days (количество дней от текущего момента).
    expiry_time имеет приоритет.
    """
    try:
        expiry_time = request.get("expiry_time")
        expiry_days = request.get("expiry_days")

        # expiry_time имеет приоритет
        if expiry_time is not None:
            # Используем переданный timestamp напрямую
            final_expiry_time = int(expiry_time)
        elif expiry_days is not None and expiry_days > 0:
            # Calculate expiry timestamp from days
            final_expiry_time = int((datetime.now().timestamp() + expiry_days * 24 * 60 * 60) * 1000)
        else:
            # 0 means no expiry
            final_expiry_time = 0

        # Получаем старое значение для логирования
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT expiry_time FROM client_traffics WHERE id = ?", (user_id,))
        old_result = cursor.fetchone()
        old_expiry = old_result[0] if old_result else 0
        conn.close()

        result = db.update_user_expiry(str(user_id), final_expiry_time)

        if result["success"]:
            logger.info(f"[SYNC] Updated user {user_id}: expiry {old_expiry} -> {final_expiry_time}")
            return {
                "message": f"Expiry updated for user {user_id}",
                "user_id": user_id,
                "old_expiry_time": old_expiry,
                "expiry_time": final_expiry_time
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to update expiry"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting user expiry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}/traffic")
async def set_user_traffic(
    user_id: int,
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """Установка лимита трафика для одного пользователя"""
    try:
        traffic_limit = request.get("traffic_limit", 0)  # в байтах

        result = db.update_user_traffic(str(user_id), traffic_limit)

        if result["success"]:
            return {
                "message": f"Traffic limit updated for user {user_id}",
                "user_id": user_id,
                "traffic_limit": traffic_limit
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to update traffic"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting user traffic: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SYNC ENDPOINTS (by email prefix / chat_id) ====================

@app.get("/api/sync/user/{chat_id}")
async def get_user_clients_by_chat_id(
    chat_id: str,
    username: str = Depends(get_current_user)
):
    """
    Получение всех клиентов пользователя по chat_id.

    Ищет клиентов где email начинается с '{chat_id}-' или '{chat_id}@'
    (например, '932101-vless', '932101-trojan')
    """
    try:
        clients = db.get_clients_by_email_prefix(chat_id)

        if not clients:
            raise HTTPException(
                status_code=404,
                detail=f"No clients found with chat_id '{chat_id}'"
            )

        return {
            "chat_id": chat_id,
            "clients_count": len(clients),
            "clients": clients
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting clients by chat_id: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sync/user/{chat_id}/expiry")
async def sync_user_expiry_by_chat_id(
    chat_id: str,
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """
    Синхронизация срока действия для всех клиентов пользователя по chat_id.

    Ищет всех клиентов где email начинается с '{chat_id}-' или '{chat_id}@'
    и обновляет им expiry_time.

    Args:
        chat_id: ID пользователя (telegram chat_id)
        request: JSON с полем expiry_time (Unix timestamp в миллисекундах)
    """
    try:
        expiry_time = request.get("expiry_time")

        if expiry_time is None:
            raise HTTPException(
                status_code=400,
                detail="expiry_time is required"
            )

        result = db.update_expiry_by_email_prefix(chat_id, int(expiry_time))

        if result["success"]:
            logger.info(f"[SYNC] Synced expiry for chat_id {chat_id}: {result['updated_count']} clients updated")
            return {
                "success": True,
                "chat_id": chat_id,
                "updated_clients": result["updated_count"],
                "updated_ids": result.get("updated_ids", []),
                "expiry_time": expiry_time
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=result.get("error", f"No clients found for chat_id '{chat_id}'")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing user expiry by chat_id: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sync/bulk/expiry")
async def sync_bulk_expiry(
    request: List[Dict[str, Any]],
    username: str = Depends(get_current_user)
):
    """
    Массовая синхронизация сроков для нескольких пользователей.

    Args:
        request: Список объектов [{chat_id: str, expiry_time: int}, ...]
    """
    try:
        results = []
        total_updated = 0

        for item in request:
            chat_id = item.get("chat_id")
            expiry_time = item.get("expiry_time")

            if not chat_id or expiry_time is None:
                results.append({
                    "chat_id": chat_id,
                    "success": False,
                    "error": "Missing chat_id or expiry_time"
                })
                continue

            result = db.update_expiry_by_email_prefix(chat_id, int(expiry_time))

            if result["success"]:
                results.append({
                    "chat_id": chat_id,
                    "success": True,
                    "updated_clients": result["updated_count"]
                })
                total_updated += result["updated_count"]
            else:
                results.append({
                    "chat_id": chat_id,
                    "success": False,
                    "error": result.get("error", "Unknown error")
                })

        return {
            "total_requests": len(request),
            "successful": sum(1 for r in results if r.get("success")),
            "total_clients_updated": total_updated,
            "results": results
        }

    except Exception as e:
        logger.error(f"Error in bulk expiry sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sync/user/{chat_id}/enable")
async def enable_user_clients(
    chat_id: str,
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """
    Включение/выключение всех клиентов пользователя по chat_id.

    Args:
        chat_id: ID пользователя
        request: JSON с полем enable (bool)
    """
    try:
        enable = request.get("enable", True)
        clients = db.get_clients_by_email_prefix(chat_id)

        if not clients:
            raise HTTPException(
                status_code=404,
                detail=f"No clients found with chat_id '{chat_id}'"
            )

        user_ids = [str(c["id"]) for c in clients]
        result = db.bulk_toggle_users(user_ids, enable)

        return {
            "success": True,
            "chat_id": chat_id,
            "enabled": enable,
            "updated_clients": result.get("updated", 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling clients by chat_id: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sync/by-uuid/expiry")
async def sync_expiry_by_uuids(
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """
    Синхронизация срока действия для клиентов по списку UUID.

    UUID - уникальный идентификатор клиента:
    - Для vless/vmess: поле 'id'
    - Для trojan/shadowsocks: поле 'password'

    Args:
        request: JSON с полями:
            - uuids: список UUID клиентов
            - expiry_time: Unix timestamp в миллисекундах
    """
    try:
        uuids = request.get("uuids", [])
        expiry_time = request.get("expiry_time")

        if not uuids:
            raise HTTPException(
                status_code=400,
                detail="uuids list is required"
            )

        if expiry_time is None:
            raise HTTPException(
                status_code=400,
                detail="expiry_time is required"
            )

        result = db.update_expiry_by_uuids(uuids, int(expiry_time))

        if result["success"]:
            logger.info(f"[UUID-SYNC] Synced expiry for {len(uuids)} UUIDs: {result['updated_count']} clients updated")
            return {
                "success": True,
                "updated_count": result["updated_count"],
                "found_uuids": result.get("found_uuids", []),
                "not_found_uuids": result.get("not_found_uuids", []),
                "updated_clients": result.get("updated_clients", []),
                "expiry_time": expiry_time
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Unknown error")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing expiry by UUIDs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sync/by-uuid")
async def get_clients_by_uuids(
    uuids: str = Query(..., description="Comma-separated list of UUIDs"),
    username: str = Depends(get_current_user)
):
    """
    Получение информации о клиентах по списку UUID.

    Args:
        uuids: UUID через запятую (например: "uuid1,uuid2,uuid3")
    """
    try:
        uuid_list = [u.strip() for u in uuids.split(",") if u.strip()]

        if not uuid_list:
            raise HTTPException(
                status_code=400,
                detail="At least one UUID is required"
            )

        clients = db.get_clients_by_uuids(uuid_list)

        return {
            "requested_uuids": len(uuid_list),
            "found_clients": len(clients),
            "clients": clients
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting clients by UUIDs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sync/stats")
async def get_sync_stats(username: str = Depends(get_current_user)):
    """
    Получение статистики по клиентам для синхронизации.

    Возвращает:
    - Общее количество клиентов
    - Активных/неактивных
    - Истекающих в ближайшие дни
    """
    try:
        from datetime import datetime, timedelta

        conn = db._get_connection()
        cursor = conn.cursor()

        # Общее количество
        cursor.execute("SELECT COUNT(*) FROM client_traffics")
        total = cursor.fetchone()[0]

        # Активные
        cursor.execute("SELECT COUNT(*) FROM client_traffics WHERE enable = 1")
        active = cursor.fetchone()[0]

        # Истекающие в течение 7 дней
        now_ms = int(datetime.now().timestamp() * 1000)
        week_ms = now_ms + (7 * 24 * 60 * 60 * 1000)
        cursor.execute("""
            SELECT COUNT(*) FROM client_traffics
            WHERE expiry_time > ? AND expiry_time < ? AND enable = 1
        """, (now_ms, week_ms))
        expiring_soon = cursor.fetchone()[0]

        # Истёкшие
        cursor.execute("""
            SELECT COUNT(*) FROM client_traffics
            WHERE expiry_time > 0 AND expiry_time < ?
        """, (now_ms,))
        expired = cursor.fetchone()[0]

        conn.close()

        return {
            "total_clients": total,
            "active": active,
            "inactive": total - active,
            "expiring_in_7_days": expiring_soon,
            "expired": expired
        }

    except Exception as e:
        logger.error(f"Error getting sync stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/users/toggle-status")
async def toggle_users_status(request: ToggleStatusRequest):
    """Массовая блокировка/разблокировка пользователей"""
    try:
        result = db.bulk_toggle_users(request.user_ids, request.enable)
        action = "enabled" if request.enable else "disabled"
        return {
            "message": f"{action.capitalize()} {result['updated']} users",
            "updated": result['updated']
        }
    except Exception as e:
        logger.error(f"Error toggling status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/extend-expiry")
async def extend_users_expiry(request: ExtendExpiryRequest):
    """Массовое продление срока действия"""
    try:
        result = db.bulk_extend_expiry(request.user_ids, request.days)
        return {
            "message": f"Extended expiry for {result['updated']} users by {request.days} days",
            "updated": result['updated']
        }
    except Exception as e:
        logger.error(f"Error extending expiry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== УПРАВЛЕНИЕ ИНБАУНДАМИ ====================

@app.get("/api/inbounds")
async def get_inbounds():
    """Получение списка всех inbounds"""
    try:
        inbounds = db.get_inbounds()
        return {"inbounds": inbounds}
    except Exception as e:
        logger.error(f"Error getting inbounds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/inbounds/fingerprints")
async def get_inbound_fingerprints(username: str = Depends(get_current_user)):
    """Get fingerprint settings for all inbounds."""
    try:
        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, remark, protocol, stream_settings
            FROM inbounds
            WHERE protocol IN ('vless', 'trojan')
        """)

        inbounds = []
        for row in cursor.fetchall():
            inbound_id, remark, protocol, stream_settings = row
            fingerprint = None
            security = None

            if stream_settings:
                try:
                    settings = json.loads(stream_settings)
                    security = settings.get('security', 'none')

                    # Check Reality settings
                    if security == 'reality':
                        reality = settings.get('realitySettings', {})
                        fingerprint = reality.get('fingerprint', 'chrome')
                    # Check TLS settings
                    elif security == 'tls':
                        tls = settings.get('tlsSettings', {})
                        fingerprint = tls.get('fingerprint', 'chrome')
                except:
                    pass

            if fingerprint:  # Only include inbounds with fingerprint support
                inbounds.append({
                    "id": inbound_id,
                    "remark": remark,
                    "protocol": protocol,
                    "security": security,
                    "fingerprint": fingerprint
                })

        conn.close()

        # Available fingerprint options
        fingerprint_options = [
            "chrome", "firefox", "safari", "ios", "android",
            "edge", "360", "qq", "random", "randomized"
        ]

        return {
            "success": True,
            "inbounds": inbounds,
            "options": fingerprint_options
        }

    except Exception as e:
        logger.error(f"Error getting fingerprints: {e}")
        return {"success": False, "message": str(e), "inbounds": []}

@app.get("/api/inbounds/{inbound_id}")
async def get_inbound(inbound_id: int):
    """Получение информации об inbound"""
    try:
        inbound = db.get_inbound(inbound_id)
        if inbound:
            return inbound
        else:
            raise HTTPException(status_code=404, detail="Inbound not found")
    except Exception as e:
        logger.error(f"Error getting inbound: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/inbounds/{inbound_id}/full")
async def get_inbound_full(inbound_id: int, username: str = Depends(get_current_user)):
    """Get full inbound details with all settings parsed."""
    try:
        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM inbounds WHERE id = ?", (inbound_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Inbound not found")

        columns = [desc[0] for desc in cursor.description]
        inbound = dict(zip(columns, row))

        # Parse JSON fields
        for field in ['settings', 'stream_settings', 'sniffing']:
            if inbound.get(field):
                try:
                    inbound[field] = json.loads(inbound[field])
                except:
                    pass

        conn.close()
        return {"success": True, "inbound": inbound}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inbound: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/inbounds/{inbound_id}")
async def update_inbound(inbound_id: int, request: Request, username: str = Depends(get_current_user)):
    """Update inbound settings."""
    try:
        data = await request.json()

        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        # Check inbound exists
        cursor.execute("SELECT id FROM inbounds WHERE id = ?", (inbound_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Inbound not found")

        # Build update query
        updates = []
        values = []

        # Simple fields
        simple_fields = ['remark', 'port', 'protocol', 'enable', 'expiry_time', 'total', 'listen']
        for field in simple_fields:
            if field in data:
                updates.append(f"{field} = ?")
                values.append(data[field])

        # JSON fields
        json_fields = ['settings', 'stream_settings', 'sniffing']
        for field in json_fields:
            if field in data:
                updates.append(f"{field} = ?")
                if isinstance(data[field], dict):
                    values.append(json.dumps(data[field]))
                else:
                    values.append(data[field])

        if updates:
            values.append(inbound_id)
            query = f"UPDATE inbounds SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()

        conn.close()

        # Restart x-ui to apply changes
        subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

        return {"success": True, "message": "Inbound обновлен"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating inbound: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/inbounds/{inbound_id}/toggle")
async def toggle_inbound(inbound_id: int, username: str = Depends(get_current_user)):
    """Toggle inbound enable/disable."""
    try:
        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        cursor.execute("SELECT enable FROM inbounds WHERE id = ?", (inbound_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Inbound not found")

        new_state = 0 if row[0] == 1 else 1
        cursor.execute("UPDATE inbounds SET enable = ? WHERE id = ?", (new_state, inbound_id))
        conn.commit()
        conn.close()

        subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

        return {
            "success": True,
            "enabled": bool(new_state),
            "message": "Inbound включен" if new_state else "Inbound выключен"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling inbound: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/inbounds/{inbound_id}")
async def delete_inbound(inbound_id: int, username: str = Depends(get_current_user)):
    """Delete inbound and all its users."""
    try:
        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        # Check inbound exists
        cursor.execute("SELECT remark FROM inbounds WHERE id = ?", (inbound_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Inbound not found")

        remark = row[0]

        # Delete users first
        cursor.execute("DELETE FROM client_traffics WHERE inbound_id = ?", (inbound_id,))
        deleted_users = cursor.rowcount

        # Delete inbound
        cursor.execute("DELETE FROM inbounds WHERE id = ?", (inbound_id,))
        conn.commit()
        conn.close()

        subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

        return {
            "success": True,
            "message": f"Inbound '{remark}' удален",
            "deleted_users": deleted_users
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting inbound: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== УПРАВЛЕНИЕ ОЧЕРЕДЯМИ ====================

@app.post("/api/queues/bulk-create")
async def create_bulk_queue(request: QueueBulkCreateRequest):
    """Создание очереди для массового создания пользователей (до 5000)"""
    try:
        if request.count > 5000:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5000 users allowed"
            )

        if request.count <= 0:
            raise HTTPException(
                status_code=400,
                detail="Count must be greater than 0"
            )

        # Создаем очередь
        queue_id = queue_manager.create_queue(
            "bulk_create",
            {
                "template": request.template.model_dump(),
                "count": request.count,
                "inbound_id": request.inbound_id
            }
        )

        # Запускаем обработку
        queue_manager.start_queue_processing(queue_id, db)

        return {
            "queue_id": queue_id,
            "message": "Queue created and processing started",
            "count": request.count
        }

    except Exception as e:
        logger.error(f"Error creating bulk queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/queues")
async def list_queues(status: Optional[str] = Query(None, description="Filter by status")):
    """Получение списка всех очередей"""
    try:
        queues = queue_manager.list_queues(status)
        return {"queues": queues}
    except Exception as e:
        logger.error(f"Error listing queues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/queues/{queue_id}")
async def get_queue_status(queue_id: str):
    """Получение статуса очереди"""
    try:
        queue = queue_manager.get_queue(queue_id)
        if queue:
            return queue
        else:
            raise HTTPException(status_code=404, detail="Queue not found")
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/queues/{queue_id}/cancel")
async def cancel_queue(queue_id: str):
    """Отмена очереди"""
    try:
        success = queue_manager.cancel_queue(queue_id)
        if success:
            return {"message": "Queue cancelled", "queue_id": queue_id}
        else:
            raise HTTPException(status_code=400, detail="Cannot cancel queue")
    except Exception as e:
        logger.error(f"Error cancelling queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/queues/{queue_id}")
async def delete_queue(queue_id: str):
    """Удаление очереди"""
    try:
        success = queue_manager.delete_queue(queue_id)
        if success:
            return {"message": "Queue deleted", "queue_id": queue_id}
        else:
            raise HTTPException(status_code=400, detail="Cannot delete queue (may be processing)")
    except Exception as e:
        logger.error(f"Error deleting queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== СИСТЕМНЫЕ ОПЕРАЦИИ ====================

@app.post("/api/system/xui/restart")
async def restart_xui():
    """Перезапуск сервиса x-ui"""
    try:
        result = db.restart_xui_service()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        logger.error(f"Error restarting x-ui: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/xui/start")
async def start_xui():
    """Запуск сервиса x-ui"""
    try:
        result = db.start_xui_service()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        logger.error(f"Error starting x-ui: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/xui/stop")
async def stop_xui():
    """Остановка сервиса x-ui"""
    try:
        result = db.stop_xui_service()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        logger.error(f"Error stopping x-ui: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/xui/status")
async def get_xui_status():
    """Получение статуса сервиса x-ui"""
    try:
        result = db.get_xui_service_status()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        logger.error(f"Error getting x-ui status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/xray/update")
async def update_xray():
    """Обновление Xray core"""
    try:
        result = db.update_xray_core()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Update failed"))
    except Exception as e:
        logger.error(f"Error updating Xray: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/xray/version")
async def get_xray_version():
    """Получение версии Xray"""
    try:
        result = db.get_xray_version()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        logger.error(f"Error getting Xray version: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/xui/version")
async def get_xui_version():
    """Получение версии x-ui"""
    try:
        result = db.get_xui_version()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=404, detail=result["error"])
    except Exception as e:
        logger.error(f"Error getting x-ui version: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Keep old endpoint for backwards compatibility
@app.post("/api/system/restart-xui")
async def restart_xui_old():
    """Перезапуск сервиса x-ui (deprecated - use /api/system/xui/restart)"""
    return await restart_xui()

@app.post("/api/system/backup")
async def create_backup():
    """Создание резервной копии базы данных"""
    try:
        result = db.create_backup()
        if result["success"]:
            return {
                "message": "Backup created successfully",
                "file": result["file"]
            }
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/logs")
async def get_logs(
    lines: int = Query(100, ge=1, le=1000)
):
    """Получение логов системы"""
    try:
        logs = db.get_system_logs(lines)
        return {"logs": logs}
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ШАБЛОНЫ ====================

@app.get("/api/templates")
async def get_templates():
    """Получение списка шаблонов пользователей"""
    try:
        templates = db.get_user_templates()
        return {"templates": templates}
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/templates")
async def save_template(template: UserTemplate):
    """Сохранение шаблона пользователя"""
    try:
        result = db.save_user_template(template.model_dump())
        if result["success"]:
            return {"message": "Template saved successfully"}
        else:
            raise HTTPException(status_code=400, detail=result["error"])
    except Exception as e:
        logger.error(f"Error saving template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SUBSCRIPTION SYNC ====================

@app.get("/api/users/by-email/{email:path}")
async def get_user_by_email(
    email: str,
    username: str = Depends(get_current_user)
):
    """Получение пользователя по точному совпадению email"""
    try:
        user = db.get_user_by_email(email)
        if user:
            return user
        else:
            raise HTTPException(status_code=404, detail=f"User {email} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/set-expiry")
async def bulk_set_expiry(
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """Массовая установка срока действия

    Можно использовать:
    - users: список объектов с email и expiry_time
    - user_ids + expiry_time: список ID и единый срок для всех
    """
    try:
        users = request.get("users")
        user_ids = request.get("user_ids")
        expiry_time = request.get("expiry_time")

        if users:
            # Режим по email
            result = db.bulk_set_expiry_by_email(users)
        elif user_ids and expiry_time is not None:
            # Режим по ID
            result = db.bulk_set_expiry_by_ids(user_ids, expiry_time)
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either 'users' list or 'user_ids' with 'expiry_time'"
            )

        return {
            "message": f"Updated expiry for {result['updated']} users",
            "updated": result['updated'],
            "failed": result['failed'],
            "errors": result['errors']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk set expiry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/expiry-status")
async def get_expiry_status(username: str = Depends(get_current_user)):
    """Получение статистики по срокам действия подписок

    Возвращает:
    - total_users: общее количество пользователей
    - expired: количество истекших
    - expiring_soon: истекающих в ближайшие 7 дней
    - active: активных (срок > 7 дней)
    - unlimited: бессрочных (expiry_time = 0)
    - expired_users: список истекших пользователей
    - expiring_soon_users: список скоро истекающих
    """
    try:
        status = db.get_expiry_status()
        return status
    except Exception as e:
        logger.error(f"Error getting expiry status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/from-external")
async def sync_from_external(
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """Синхронизация пользователей с внешней системой (Keymaster/Dashboard)

    Принимает список пользователей с email, expiry_time и traffic_limit.
    Обновляет данные для найденных пользователей.

    Request body:
    {
        "users": [
            {
                "email": "user@vless",
                "expiry_time": 1735689599000,
                "traffic_limit": 161061273600
            }
        ]
    }
    """
    try:
        users = request.get("users", [])

        if not users:
            raise HTTPException(status_code=400, detail="Users list is required")

        if len(users) > 1000:
            raise HTTPException(
                status_code=400,
                detail="Maximum 1000 users per sync request"
            )

        result = db.sync_from_external(users)

        return {
            "synced": result['synced'],
            "not_found": result['not_found'],
            "errors": result['errors'],
            "details": result['details']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing from external: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== АНАЛИТИКА ====================

@app.get("/api/analytics/traffic")
async def get_traffic_analytics():
    """Получение аналитики по трафику"""
    try:
        analytics = db.get_traffic_analytics()
        return analytics
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/users")
async def get_users_analytics():
    """Получение аналитики по пользователям"""
    try:
        analytics = db.get_users_analytics()
        return analytics
    except Exception as e:
        logger.error(f"Error getting user analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== VERSION & UPDATE MANAGEMENT ====================

@app.get("/api/system/version")
async def get_version(username: str = Depends(get_current_user)):
    """
    Получение информации о текущей версии системы

    Требует авторизации
    """
    try:
        version_info = get_version_info()
        return version_info
    except Exception as e:
        logger.error(f"Error getting version info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/update/check")
async def check_for_updates(
    username: str = Depends(get_current_user),
    force: bool = Query(False, description="Force check even if checked recently")
):
    """
    Проверка наличия обновлений

    Требует авторизации

    Args:
        force: Принудительная проверка (игнорировать кэш)

    Returns:
        Информация о доступных обновлениях
    """
    try:
        update_info = await update_manager.check_for_updates(force=force)
        return update_info
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/update")
async def perform_update(
    request: Dict[str, Any] = {},
    username: str = Depends(get_current_user)
):
    """
    Выполнение обновления системы

    Требует авторизации администратора

    Request body:
    {
        "version": "1.5.0",  // Конкретная версия или null для latest
        "force": false,       // Принудительное обновление
        "backup": true        // Создать backup перед обновлением
    }

    Процесс обновления:
    1. Создается резервная копия
    2. Скачивается версия с GitHub
    3. Устанавливаются файлы и зависимости
    4. Перезапускается сервис

    ВНИМАНИЕ: Сервис будет перезапущен!
    """
    try:
        # Check if update is already in progress
        if update_manager.is_update_in_progress():
            raise HTTPException(
                status_code=409,
                detail="Update already in progress"
            )

        version = request.get("version")
        force = request.get("force", False)
        backup = request.get("backup", True)

        # Perform update
        result = await update_manager.perform_update_to_version(
            version=version,
            force=force,
            backup=backup
        )

        if result["success"]:
            return result
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Update failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/releases")
async def get_releases(
    limit: int = Query(10, ge=1, le=50),
    username: str = Depends(get_current_user)
):
    """
    Получение списка доступных релизов с GitHub

    Returns:
        releases: Список релизов
        latest: Последняя версия
        current_version: Текущая установленная версия
    """
    try:
        result = await update_manager.get_releases(limit=limit)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting releases: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/install-update-server")
async def install_update_server(username: str = Depends(get_current_user)):
    """Install the backup update server as a systemd service."""
    try:
        # Copy service file
        service_src = "/opt/xui-manager/xui-update-server.service"
        service_dst = "/etc/systemd/system/xui-update-server.service"

        if not os.path.exists(service_src):
            return {"success": False, "message": "Service file not found"}

        # Copy service file
        import shutil
        shutil.copy(service_src, service_dst)

        # Reload systemd and enable/start service
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "enable", "xui-update-server"], capture_output=True)
        result = subprocess.run(["systemctl", "start", "xui-update-server"], capture_output=True, text=True)

        if result.returncode == 0:
            return {
                "success": True,
                "message": "Update server installed and started",
                "port": 8889,
                "note": "Access via http://server:8889 with basic auth"
            }
        else:
            return {
                "success": False,
                "message": "Failed to start update server",
                "error": result.stderr
            }
    except Exception as e:
        logger.error(f"Error installing update server: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/system/update-server-status")
async def get_update_server_status(username: str = Depends(get_current_user)):
    """Check if update server is installed and running."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "xui-update-server"],
            capture_output=True, text=True
        )
        is_running = result.stdout.strip() == "active"

        enabled = subprocess.run(
            ["systemctl", "is-enabled", "xui-update-server"],
            capture_output=True, text=True
        )
        is_enabled = enabled.stdout.strip() == "enabled"

        return {
            "installed": os.path.exists("/etc/systemd/system/xui-update-server.service"),
            "enabled": is_enabled,
            "running": is_running,
            "port": 8889
        }
    except Exception as e:
        return {"installed": False, "running": False, "error": str(e)}

@app.get("/api/system/backups")
async def list_backups(username: str = Depends(get_current_user)):
    """
    Получение списка резервных копий

    Returns:
        Список backup файлов с информацией о размере и дате создания
    """
    try:
        backups = update_manager.list_backups()
        return {"backups": backups, "count": len(backups)}
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/rollback")
async def rollback_update(
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """
    Откат на предыдущую версию из резервной копии

    Request body:
    {
        "backup_path": "/opt/xui-manager/backups/backup_20241122_120000.tar.gz"
    }

    ВНИМАНИЕ: Сервис будет перезапущен!
    """
    try:
        backup_path = request.get("backup_path")
        if not backup_path:
            raise HTTPException(status_code=400, detail="backup_path is required")

        if update_manager.is_update_in_progress():
            raise HTTPException(
                status_code=409,
                detail="Update in progress, cannot rollback"
            )

        result = update_manager.rollback(backup_path)

        if result["success"]:
            return result
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Rollback failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during rollback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/system/backups/{backup_filename}")
async def delete_backup(
    backup_filename: str,
    username: str = Depends(get_current_user)
):
    """
    Удаление резервной копии
    """
    try:
        backup_path = f"/opt/xui-manager/backups/{backup_filename}"
        result = update_manager.delete_backup(backup_path)

        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/update/status")
async def get_update_status(username: str = Depends(get_current_user)):
    """
    Получение статуса обновления с прогрессом

    Требует авторизации

    Returns:
        Информация о статусе обновления и прогрессе
    """
    update_progress = update_manager.get_update_status()

    return {
        "update_in_progress": update_manager.is_update_in_progress(),
        "current_version": CURRENT_VERSION,
        "last_check": update_manager.last_check_data,
        "progress": update_progress
    }

@app.get("/api/system/background-tasks")
async def get_background_tasks_status(username: str = Depends(get_current_user)):
    """
    Получение статуса фоновых задач

    Требует авторизации

    Returns:
        Статус всех фоновых задач
    """
    try:
        status = background_tasks.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting background tasks status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== KEY GENERATION ====================

@app.post("/api/keys/generate")
async def generate_keys(
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """
    Генерация новых ключей для протокола.

    Request body:
    {
        "protocol": "vless",
        "count": 10,
        "traffic_limit_gb": 700,
        "days_valid": 30
    }

    Returns:
        Список сгенерированных ключей с UUID и key_string
    """
    import uuid
    from datetime import datetime, timedelta
    import json

    try:
        protocol = request.get("protocol", "vless")
        count = min(request.get("count", 10), 100)  # Max 100 keys at once
        traffic_limit_gb = request.get("traffic_limit_gb", 700)
        days_valid = request.get("days_valid", 30)

        # Найти inbound для протокола
        inbound = db.get_inbound_by_protocol(protocol)
        if not inbound:
            raise HTTPException(
                status_code=404,
                detail=f"No inbound found for protocol {protocol}"
            )

        inbound_id = inbound["id"]
        expiry_time = int((datetime.now() + timedelta(days=days_valid)).timestamp() * 1000)
        total_bytes = int(traffic_limit_gb * 1024 * 1024 * 1024)

        generated_keys = []

        for i in range(count):
            # Генерация уникального UUID
            key_uuid = str(uuid.uuid4())
            remark = f"auto_{key_uuid[:8]}"

            # Создание клиента в 3x-ui
            client_data = {
                "id": key_uuid,
                "alterId": 0,
                "email": remark,
                "limitIp": 0,
                "totalGB": traffic_limit_gb,
                "expiryTime": expiry_time,
                "enable": True,
                "tgId": "",
                "subId": ""
            }

            success = db.add_client_to_inbound(inbound_id, client_data)

            if success:
                # Генерация key_string
                key_string = db.generate_key_string(
                    protocol=protocol,
                    uuid=key_uuid,
                    inbound_id=inbound_id
                )

                generated_keys.append({
                    "uuid": key_uuid,
                    "remark": remark,
                    "inbound_id": inbound_id,
                    "key_string": key_string,
                    "expiry_time": expiry_time,
                    "traffic_limit_gb": traffic_limit_gb
                })

        logger.info(f"Generated {len(generated_keys)} {protocol} keys")

        return {
            "success": True,
            "protocol": protocol,
            "generated": len(generated_keys),
            "keys": generated_keys
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/bulk/expiry")
async def bulk_sync_expiry(
    request: Dict[str, Any],
    username: str = Depends(get_current_user)
):
    """
    Пакетная синхронизация сроков для нескольких пользователей.

    Request body:
    {
        "users": [
            {"chat_id": "123456", "expiry_time": 1735689599000},
            {"chat_id": "789012", "expiry_time": 1735689599000}
        ]
    }

    Returns:
        Результаты синхронизации для каждого пользователя
    """
    try:
        users = request.get("users", [])
        if not users:
            raise HTTPException(status_code=400, detail="users list is required")

        results = {
            "total_users": len(users),
            "total_updated": 0,
            "details": []
        }

        for user_data in users:
            chat_id = user_data.get("chat_id")
            expiry_time = user_data.get("expiry_time")

            if not chat_id or not expiry_time:
                results["details"].append({
                    "chat_id": chat_id,
                    "error": "Missing chat_id or expiry_time"
                })
                continue

            try:
                update_result = db.update_expiry_by_email_prefix(str(chat_id), expiry_time)
                updated = update_result.get("updated", 0)
                results["total_updated"] += updated
                results["details"].append({
                    "chat_id": chat_id,
                    "updated": updated
                })
            except Exception as e:
                results["details"].append({
                    "chat_id": chat_id,
                    "error": str(e)
                })

        logger.info(f"Bulk sync: {results['total_updated']} clients for {len(users)} users")
        return {"success": True, **results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health/detailed")
async def health_detailed():
    """
    Детальная проверка здоровья системы.

    Returns:
        Статус БД, количество клиентов, использование диска
    """
    import os
    import shutil

    try:
        # Проверка БД
        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM client_traffics")
        total_clients = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM client_traffics WHERE enable = 1")
        active_clients = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM inbounds")
        inbounds = cursor.fetchone()[0]

        conn.close()

        # Использование диска
        db_path = "/etc/x-ui/x-ui.db"
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        disk_usage = shutil.disk_usage("/")

        return {
            "status": "healthy",
            "database": {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "inactive_clients": total_clients - active_clients,
                "inbounds": inbounds,
                "size_mb": round(db_size / 1024 / 1024, 2)
            },
            "disk": {
                "total_gb": round(disk_usage.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk_usage.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk_usage.free / 1024 / 1024 / 1024, 2),
                "percent_used": round(disk_usage.used / disk_usage.total * 100, 1)
            },
            "version": CURRENT_VERSION
        }

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "version": CURRENT_VERSION
        }


@app.delete("/api/users/expired/cleanup")
async def cleanup_expired_users(
    days_expired: int = Query(30, description="Delete users expired more than N days ago"),
    dry_run: bool = Query(True, description="Only show what would be deleted"),
    username: str = Depends(get_current_user)
):
    """
    Очистка давно истекших пользователей.

    Удаляет пользователей, чей срок истек более N дней назад.
    По умолчанию в режиме dry_run - только показывает что будет удалено.
    """
    from datetime import datetime, timedelta

    try:
        conn = db._get_connection()
        cursor = conn.cursor()

        # Вычислить время отсечки
        cutoff_time = int((datetime.now() - timedelta(days=days_expired)).timestamp() * 1000)

        # Найти истекших
        cursor.execute("""
            SELECT id, email, expiry_time, inbound_id
            FROM client_traffics
            WHERE expiry_time > 0 AND expiry_time < ?
        """, (cutoff_time,))

        expired_users = cursor.fetchall()
        conn.close()

        result = {
            "dry_run": dry_run,
            "cutoff_days": days_expired,
            "found": len(expired_users),
            "users": [
                {
                    "id": u[0],
                    "email": u[1],
                    "expired_at": datetime.fromtimestamp(u[2] / 1000).isoformat() if u[2] else None
                }
                for u in expired_users[:100]  # Limit to 100 in response
            ]
        }

        if not dry_run and expired_users:
            user_ids = [str(u[0]) for u in expired_users]
            delete_result = db.bulk_delete_users(user_ids)
            result["deleted"] = delete_result.get("deleted", 0)
            result["errors"] = delete_result.get("errors", [])
            logger.info(f"Cleaned up {result['deleted']} expired users (>{days_expired} days)")

        return result

    except Exception as e:
        logger.error(f"Error cleaning expired users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SSL/CERTIFICATE MANAGEMENT ====================

@app.get("/api/ssl/status")
async def get_ssl_status(username: str = Depends(get_current_user)):
    """
    Get current SSL certificate status and information.

    Returns certificate details including expiry date, domain,
    and whether renewal is needed.
    """
    try:
        cert_info = ssl_manager.get_certificate_info()
        domain = ssl_manager.get_domain_from_config()

        return {
            "success": True,
            "domain": domain,
            "certificate": cert_info
        }
    except Exception as e:
        logger.error(f"Error getting SSL status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ssl/renew")
async def renew_ssl_certificate(
    force: bool = Query(False, description="Force renewal even if certificate is still valid"),
    domains: Optional[str] = Query(None, description="Comma-separated list of domains to renew"),
    username: str = Depends(get_current_user)
):
    """
    Renew SSL certificate using Let's Encrypt with standalone mode.

    This will:
    1. Stop nginx
    2. Renew the certificate(s) using certbot --standalone
    3. Start nginx
    4. Update 3x-ui configuration
    5. Restart 3x-ui service
    """
    try:
        # Parse domains list
        domains_list = None
        if domains:
            domains_list = [d.strip() for d in domains.split(',')]

        result = ssl_manager.full_certificate_renewal(force=force, domains=domains_list)

        if result.get("success"):
            logger.info(f"SSL certificate renewal completed: {result.get('message')}")
        else:
            logger.error(f"SSL certificate renewal failed: {result.get('message')}")

        return result
    except Exception as e:
        logger.error(f"Error renewing SSL certificate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ssl/domains")
async def get_all_ssl_domains(username: str = Depends(get_current_user)):
    """
    Get all domains with Let's Encrypt certificates.
    """
    try:
        domains = ssl_manager.get_all_domains()
        domains_info = []

        for domain in domains:
            cert_info = ssl_manager.get_certificate_info(domain)
            domains_info.append({
                "domain": domain,
                "status": cert_info.get("status"),
                "days_until_expiry": cert_info.get("days_until_expiry"),
                "needs_renewal": cert_info.get("needs_renewal"),
                "not_after": cert_info.get("not_after")
            })

        return {
            "success": True,
            "count": len(domains),
            "domains": domains_info
        }
    except Exception as e:
        logger.error(f"Error getting domains: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ssl/update-3xui")
async def update_3xui_certificate(username: str = Depends(get_current_user)):
    """
    Update 3x-ui panel to use current Let's Encrypt certificate.

    Use this if certificate was renewed externally and 3x-ui
    needs to be updated to use the new certificate.
    """
    try:
        result = ssl_manager.update_3xui_certificate()

        if result.get("success"):
            # Restart 3x-ui to apply changes
            restart_result = ssl_manager.restart_services()
            result["restart_result"] = restart_result
            logger.info("3x-ui certificate updated and services restarted")

        return result
    except Exception as e:
        logger.error(f"Error updating 3x-ui certificate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ssl/restart-services")
async def restart_ssl_services(username: str = Depends(get_current_user)):
    """
    Restart Nginx and 3x-ui services.

    Use after manual certificate changes to apply new certificate.
    """
    try:
        result = ssl_manager.restart_services()
        logger.info(f"Services restart requested: {result}")
        return {
            "success": True,
            "services": result
        }
    except Exception as e:
        logger.error(f"Error restarting services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ssl/domain")
async def get_ssl_domain(username: str = Depends(get_current_user)):
    """
    Get the configured domain for SSL certificate.
    """
    try:
        domain = ssl_manager.get_domain_from_config()
        return {
            "success": True,
            "domain": domain
        }
    except Exception as e:
        logger.error(f"Error getting domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ssl/3xui-domains")
async def get_3xui_domains(username: str = Depends(get_current_user)):
    """
    Get all domains configured in 3x-ui database.

    Returns domains from settings and inbound SNI configurations.
    """
    try:
        domains = ssl_manager.get_domains_from_3xui()
        return {
            "success": True,
            "count": len(domains),
            "domains": domains
        }
    except Exception as e:
        logger.error(f"Error getting 3x-ui domains: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SYSTEM OPTIMIZATION ====================

@app.get("/api/system/optimization/check")
async def check_system_optimization(username: str = Depends(get_current_user)):
    """Check system optimization status (BBR, TCP settings)."""
    import subprocess

    try:
        result = {
            "bbr_enabled": False,
            "bbr_version": None,
            "tcp_optimized": False,
            "kernel": None,
            "sysctl_values": ""
        }

        # Get kernel version
        kernel = subprocess.run(['uname', '-r'], capture_output=True, text=True)
        result["kernel"] = kernel.stdout.strip()

        # Check BBR
        congestion = subprocess.run(
            ['sysctl', 'net.ipv4.tcp_congestion_control'],
            capture_output=True, text=True
        )
        if 'bbr' in congestion.stdout.lower():
            result["bbr_enabled"] = True
            result["bbr_version"] = "bbr" if "bbr3" not in congestion.stdout.lower() else "bbr3"

        # Check TCP optimization
        tcp_checks = [
            'net.core.default_qdisc',
            'net.ipv4.tcp_fastopen',
            'net.ipv4.tcp_slow_start_after_idle'
        ]

        sysctl_output = []
        optimized_count = 0

        for check in tcp_checks:
            val = subprocess.run(['sysctl', check], capture_output=True, text=True)
            sysctl_output.append(val.stdout.strip())
            if 'fq' in val.stdout or 'fastopen' in val.stdout or '= 0' in val.stdout:
                optimized_count += 1

        result["tcp_optimized"] = optimized_count >= 2
        result["sysctl_values"] = '\n'.join(sysctl_output)

        return result

    except Exception as e:
        logger.error(f"Error checking optimization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/system/optimization/install-bbr")
async def install_bbr(username: str = Depends(get_current_user)):
    """Install and enable BBR congestion control."""
    import subprocess

    try:
        commands = [
            "echo 'net.core.default_qdisc=fq' >> /etc/sysctl.conf",
            "echo 'net.ipv4.tcp_congestion_control=bbr' >> /etc/sysctl.conf",
            "sysctl -p"
        ]

        for cmd in commands:
            subprocess.run(cmd, shell=True, check=True)

        return {
            "success": True,
            "message": "BBR включен. Перезагрузка может потребоваться для полной активации."
        }

    except Exception as e:
        logger.error(f"Error installing BBR: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/system/optimization/tcp")
async def optimize_tcp(username: str = Depends(get_current_user)):
    """Apply TCP optimizations."""
    import subprocess

    try:
        optimizations = [
            "net.ipv4.tcp_fastopen=3",
            "net.ipv4.tcp_slow_start_after_idle=0",
            "net.ipv4.tcp_notsent_lowat=16384",
            "net.core.rmem_max=16777216",
            "net.core.wmem_max=16777216"
        ]

        for opt in optimizations:
            subprocess.run(f"sysctl -w {opt}", shell=True)
            subprocess.run(f"echo '{opt}' >> /etc/sysctl.conf", shell=True)

        return {"success": True, "message": "TCP оптимизации применены"}

    except Exception as e:
        logger.error(f"Error optimizing TCP: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/system/optimization/install-all")
async def install_all_optimizations(username: str = Depends(get_current_user)):
    """Install all system optimizations."""
    try:
        # Install BBR
        await install_bbr(username)
        # Optimize TCP
        await optimize_tcp(username)

        return {"success": True, "message": "Все оптимизации установлены"}

    except Exception as e:
        logger.error(f"Error installing optimizations: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/system/update-dat")
async def update_dat_files(username: str = Depends(get_current_user)):
    """Update GeoIP and GeoSite dat files."""
    import subprocess
    import urllib.request

    try:
        dat_dir = "/usr/local/x-ui/bin"

        # URLs for dat files
        files = {
            "geoip.dat": "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat",
            "geosite.dat": "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat"
        }

        for filename, url in files.items():
            filepath = f"{dat_dir}/{filename}"
            logger.info(f"Downloading {filename}...")

            # Download file
            subprocess.run(
                f"curl -L -o {filepath} {url}",
                shell=True, check=True, timeout=120
            )

        # Restart x-ui to apply
        subprocess.run(['systemctl', 'restart', 'x-ui'], check=True)

        return {"success": True, "message": "GeoIP и GeoSite обновлены"}

    except Exception as e:
        logger.error(f"Error updating dat files: {e}")
        return {"success": False, "message": str(e)}


# ==================== SERVER INFO & TOOLS ====================

@app.get("/api/server/info")
async def get_server_info(username: str = Depends(get_current_user)):
    """Get comprehensive server information."""
    import psutil
    import subprocess

    info = {
        "xui_version": None,
        "xui_installed": False,
        "xray_version": None,
        "panel_url": None,
        "tcp_connections": 0,
        "online_users": 0,
        "cpu_percent": 0,
        "memory_percent": 0,
        "disk_percent": 0
    }

    try:
        # Check if x-ui is installed
        xui_installed = os.path.exists("/usr/local/x-ui") or os.path.exists("/etc/x-ui/x-ui.db")
        info["xui_installed"] = xui_installed

        if xui_installed:
            # Get x-ui version
            try:
                # Try reading version from x-ui binary
                result = subprocess.run(
                    ["/usr/local/x-ui/x-ui", "setting", "-show"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    # Parse version from output
                    import re
                    match = re.search(r'版本|version[:\s]+(\d+\.\d+\.\d+)', result.stdout, re.IGNORECASE)
                    if match:
                        info["xui_version"] = match.group(1)
                    else:
                        # Try to get from x-ui status
                        result = subprocess.run(
                            ["systemctl", "status", "x-ui"],
                            capture_output=True, text=True, timeout=5
                        )
                        # Default version if can't determine
                        if "running" in result.stdout.lower():
                            info["xui_version"] = "2.x"
            except:
                # Check if version file exists
                version_file = "/usr/local/x-ui/version"
                if os.path.exists(version_file):
                    with open(version_file) as f:
                        info["xui_version"] = f.read().strip()
                else:
                    info["xui_version"] = "установлен"

            # Get Xray version
            try:
                result = subprocess.run(
                    ["/usr/local/x-ui/bin/xray-linux-amd64", "-version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    import re
                    match = re.search(r'Xray (\d+\.\d+\.\d+)', result.stdout)
                    if match:
                        info["xray_version"] = match.group(1)
            except:
                pass

            # Get panel URL from settings
            try:
                conn = sqlite3.connect("/etc/x-ui/x-ui.db")
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = 'webPort'")
                row = cursor.fetchone()
                if row:
                    port = row[0]
                    info["panel_url"] = f":{port}/panel/"
                conn.close()
            except:
                info["panel_url"] = ":54321/panel/"

        # Get TCP connections count
        try:
            connections = psutil.net_connections(kind='tcp')
            established = [c for c in connections if c.status == 'ESTABLISHED']
            info["tcp_connections"] = len(established)
        except:
            pass

        # Get online users (from x-ui API or database)
        try:
            conn = sqlite3.connect("/etc/x-ui/x-ui.db")
            cursor = conn.cursor()
            # Count users with recent traffic
            cursor.execute("""
                SELECT COUNT(DISTINCT email) FROM client_traffics
                WHERE enable = 1
                AND (up > 0 OR down > 0)
                AND (expiry_time = 0 OR expiry_time > ?)
            """, (int(datetime.now().timestamp() * 1000),))
            info["online_users"] = cursor.fetchone()[0]
            conn.close()
        except:
            pass

        # System stats
        info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        info["memory_percent"] = psutil.virtual_memory().percent
        info["disk_percent"] = psutil.disk_usage('/').percent

    except Exception as e:
        logger.error(f"Error getting server info: {e}")

    return info


@app.post("/api/server/speedtest")
async def run_speedtest(username: str = Depends(get_current_user)):
    """Run internal speedtest."""
    try:
        # Try to import speedtest module
        try:
            import speedtest
        except ImportError:
            # Install speedtest-cli in venv
            install_result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "speedtest-cli"],
                capture_output=True, text=True, timeout=60
            )
            if install_result.returncode != 0:
                return {"success": False, "message": "Не удалось установить speedtest-cli. Установите вручную: pip install speedtest-cli"}
            import speedtest

        # Run speedtest
        st = speedtest.Speedtest()
        st.get_best_server()

        # Download test
        download = st.download() / 1_000_000  # Mbps

        # Upload test
        upload = st.upload() / 1_000_000  # Mbps

        # Get results
        results = st.results.dict()

        return {
            "success": True,
            "download": round(download, 2),
            "upload": round(upload, 2),
            "ping": round(results.get("ping", 0), 2),
            "server": results.get("server", {}).get("name", "Unknown"),
            "server_location": results.get("server", {}).get("country", ""),
            "client_ip": results.get("client", {}).get("ip", "")
        }

    except Exception as e:
        logger.error(f"Error running speedtest: {e}")
        return {"success": False, "message": str(e)}


@app.get("/api/xui/check")
async def check_xui_installation(username: str = Depends(get_current_user)):
    """Check if 3x-ui is installed and get installation status."""
    status = {
        "installed": False,
        "running": False,
        "version": None,
        "config_exists": False,
        "database_exists": False
    }

    try:
        # Check installation
        status["installed"] = os.path.exists("/usr/local/x-ui/x-ui")
        status["config_exists"] = os.path.exists("/usr/local/x-ui/bin/config.json")
        status["database_exists"] = os.path.exists("/etc/x-ui/x-ui.db")

        # Check if running
        result = subprocess.run(
            ["systemctl", "is-active", "x-ui"],
            capture_output=True, text=True
        )
        status["running"] = result.stdout.strip() == "active"

        # Get version
        if status["installed"]:
            try:
                result = subprocess.run(
                    ["/usr/local/x-ui/x-ui", "version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    status["version"] = result.stdout.strip()
            except:
                pass

    except Exception as e:
        logger.error(f"Error checking x-ui: {e}")

    return status


@app.post("/api/xui/install")
async def install_xui(username: str = Depends(get_current_user)):
    """Install 3x-ui panel."""
    try:
        # Run official install script
        result = subprocess.run(
            "bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)",
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            return {"success": True, "message": "3x-ui установлен"}
        else:
            return {"success": False, "message": result.stderr or "Installation failed"}

    except Exception as e:
        logger.error(f"Error installing x-ui: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/inbounds/apply-sni")
async def apply_sni_to_inbounds(sni: str, username: str = Depends(get_current_user)):
    """Apply SNI to all Reality inbounds."""
    try:
        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, stream_settings FROM inbounds
            WHERE protocol IN ('vless', 'trojan')
        """)

        updated = 0
        for row in cursor.fetchall():
            inbound_id, stream_settings = row
            if not stream_settings:
                continue

            try:
                settings = json.loads(stream_settings)
                security = settings.get('security', '')

                if security == 'reality' and 'realitySettings' in settings:
                    settings['realitySettings']['serverNames'] = [sni]
                    if 'dest' in settings['realitySettings']:
                        settings['realitySettings']['dest'] = f"{sni}:443"

                    cursor.execute(
                        "UPDATE inbounds SET stream_settings = ? WHERE id = ?",
                        (json.dumps(settings), inbound_id)
                    )
                    updated += 1

            except Exception as e:
                logger.error(f"Error updating inbound {inbound_id}: {e}")

        conn.commit()
        conn.close()

        if updated > 0:
            subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

        return {
            "success": True,
            "message": f"SNI применен к {updated} inbounds",
            "updated": updated,
            "sni": sni
        }

    except Exception as e:
        logger.error(f"Error applying SNI: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/users/regenerate-keys")
async def regenerate_user_keys(inbound_id: Optional[int] = None, username: str = Depends(get_current_user)):
    """Regenerate UUIDs/passwords for all users."""
    import uuid

    try:
        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        # Get inbounds
        if inbound_id:
            cursor.execute("SELECT id, settings, protocol FROM inbounds WHERE id = ?", (inbound_id,))
        else:
            cursor.execute("SELECT id, settings, protocol FROM inbounds")

        updated_total = 0

        for row in cursor.fetchall():
            ib_id, settings_json, protocol = row
            if not settings_json:
                continue

            try:
                settings = json.loads(settings_json)
                clients = settings.get('clients', [])

                for client in clients:
                    if protocol in ['vless', 'vmess']:
                        client['id'] = str(uuid.uuid4())
                    elif protocol == 'trojan':
                        client['password'] = str(uuid.uuid4())[:16]

                settings['clients'] = clients
                cursor.execute(
                    "UPDATE inbounds SET settings = ? WHERE id = ?",
                    (json.dumps(settings), ib_id)
                )
                updated_total += len(clients)

            except Exception as e:
                logger.error(f"Error updating inbound {ib_id}: {e}")

        conn.commit()
        conn.close()

        subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

        return {
            "success": True,
            "message": f"Обновлено {updated_total} ключей",
            "updated": updated_total
        }

    except Exception as e:
        logger.error(f"Error regenerating keys: {e}")
        return {"success": False, "message": str(e)}


@app.get("/api/protocols/check")
async def check_protocols(username: str = Depends(get_current_user)):
    """Check available protocols and their status."""
    try:
        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT protocol, COUNT(*) as count,
                   SUM(CASE WHEN enable = 1 THEN 1 ELSE 0 END) as enabled
            FROM inbounds
            GROUP BY protocol
        """)

        protocols = []
        for row in cursor.fetchall():
            protocol, count, enabled = row
            protocols.append({
                "protocol": protocol,
                "total": count,
                "enabled": enabled,
                "disabled": count - enabled
            })

        conn.close()

        return {"success": True, "protocols": protocols}

    except Exception as e:
        logger.error(f"Error checking protocols: {e}")
        return {"success": False, "message": str(e)}


# ==================== FINGERPRINT MANAGEMENT ====================

@app.post("/api/inbounds/fingerprints/update")
async def update_inbound_fingerprints(
    fingerprint: str = "randomized",
    inbound_ids: Optional[List[int]] = None,
    username: str = Depends(get_current_user)
):
    """Update fingerprint on all or selected inbounds."""
    try:
        valid_fingerprints = [
            "chrome", "firefox", "safari", "ios", "android",
            "edge", "360", "qq", "random", "randomized"
        ]

        if fingerprint not in valid_fingerprints:
            return {"success": False, "message": f"Invalid fingerprint. Valid: {', '.join(valid_fingerprints)}"}

        conn = sqlite3.connect("/etc/x-ui/x-ui.db")
        cursor = conn.cursor()

        # Get inbounds to update
        if inbound_ids:
            placeholders = ','.join('?' * len(inbound_ids))
            cursor.execute(f"""
                SELECT id, stream_settings
                FROM inbounds
                WHERE id IN ({placeholders}) AND protocol IN ('vless', 'trojan')
            """, inbound_ids)
        else:
            cursor.execute("""
                SELECT id, stream_settings
                FROM inbounds
                WHERE protocol IN ('vless', 'trojan')
            """)

        updated_count = 0
        for row in cursor.fetchall():
            inbound_id, stream_settings = row

            if not stream_settings:
                continue

            try:
                settings = json.loads(stream_settings)
                security = settings.get('security', 'none')
                updated = False

                # Update Reality fingerprint
                if security == 'reality' and 'realitySettings' in settings:
                    settings['realitySettings']['fingerprint'] = fingerprint
                    updated = True
                # Update TLS fingerprint
                elif security == 'tls' and 'tlsSettings' in settings:
                    settings['tlsSettings']['fingerprint'] = fingerprint
                    updated = True

                if updated:
                    cursor.execute(
                        "UPDATE inbounds SET stream_settings = ? WHERE id = ?",
                        (json.dumps(settings), inbound_id)
                    )
                    updated_count += 1

            except Exception as e:
                logger.error(f"Error updating inbound {inbound_id}: {e}")
                continue

        conn.commit()
        conn.close()

        # Restart x-ui to apply changes
        if updated_count > 0:
            subprocess.run(['systemctl', 'restart', 'x-ui'], capture_output=True)

        return {
            "success": True,
            "message": f"Обновлено {updated_count} inbounds",
            "updated_count": updated_count,
            "fingerprint": fingerprint
        }

    except Exception as e:
        logger.error(f"Error updating fingerprints: {e}")
        return {"success": False, "message": str(e)}


# ==================== SNI SCANNER ====================

@app.post("/api/sni/test")
async def test_sni_domain(domain: str, port: int = 443, username: str = Depends(get_current_user)):
    """Test a single domain for TLS 1.3 support and latency."""
    import socket
    import ssl
    import time

    result = {
        "domain": domain,
        "port": port,
        "tls_support": False,
        "tls_version": None,
        "h2_support": False,
        "latency_ms": None,
        "cert_valid": False,
        "cert_issuer": None,
        "error": None
    }

    try:
        # Measure connection latency
        start_time = time.time()

        # Create SSL context for TLS 1.3
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_alpn_protocols(['h2', 'http/1.1'])
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((domain, port))

        ssl_sock = context.wrap_socket(sock, server_hostname=domain)

        end_time = time.time()
        result["latency_ms"] = round((end_time - start_time) * 1000, 2)

        # Get TLS version
        tls_version = ssl_sock.version()
        result["tls_version"] = tls_version
        result["tls_support"] = tls_version in ['TLSv1.3', 'TLSv1.2']

        # Check H2 support
        alpn = ssl_sock.selected_alpn_protocol()
        result["h2_support"] = alpn == 'h2'

        # Get certificate info
        try:
            cert = ssl_sock.getpeercert(binary_form=False)
            if cert:
                result["cert_valid"] = True
                issuer = dict(x[0] for x in cert.get('issuer', []))
                result["cert_issuer"] = issuer.get('organizationName', issuer.get('commonName', 'Unknown'))
        except:
            # Binary cert for self-signed
            result["cert_valid"] = True

        ssl_sock.close()
        sock.close()

    except socket.timeout:
        result["error"] = "Timeout"
    except socket.gaierror:
        result["error"] = "DNS Error"
    except ssl.SSLError as e:
        result["error"] = f"SSL: {str(e)[:50]}"
    except Exception as e:
        result["error"] = str(e)[:50]

    return result


@app.post("/api/sni/scan")
async def scan_sni_domains(request: Request, port: int = 443, username: str = Depends(get_current_user)):
    """Scan multiple domains for Reality SNI suitability."""
    import socket
    import ssl
    import time
    import concurrent.futures

    data = await request.json()
    domains = data.get("domains", [])

    def test_domain(domain):
        result = {
            "domain": domain,
            "tls13": False,
            "h2": False,
            "latency": None,
            "status": "error"
        }

        try:
            start = time.time()

            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.set_alpn_protocols(['h2', 'http/1.1'])
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((domain, port))
            ssl_sock = context.wrap_socket(sock, server_hostname=domain)

            result["latency"] = round((time.time() - start) * 1000, 1)
            result["tls13"] = ssl_sock.version() == 'TLSv1.3'
            result["h2"] = ssl_sock.selected_alpn_protocol() == 'h2'
            result["status"] = "ok" if result["tls13"] and result["h2"] else "partial"

            ssl_sock.close()
            sock.close()

        except:
            result["status"] = "error"

        return result

    # Run scans in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(test_domain, d.strip()): d for d in domains if d.strip()}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # Sort by latency (valid first)
    results.sort(key=lambda x: (x["status"] != "ok", x["latency"] or 9999))

    return {"success": True, "results": results}


@app.get("/api/sni/saved")
async def get_saved_sni(username: str = Depends(get_current_user)):
    """Get saved SNI domains from config."""
    try:
        config_path = "/etc/x-ui/sni_favorites.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                data = json.load(f)
                return {"success": True, "domains": data.get("domains", [])}
        return {"success": True, "domains": []}
    except Exception as e:
        return {"success": False, "message": str(e), "domains": []}


@app.post("/api/sni/save")
async def save_sni_domain(domain: str, latency: Optional[float] = None, username: str = Depends(get_current_user)):
    """Save a favorite SNI domain."""
    try:
        config_path = "/etc/x-ui/sni_favorites.json"
        data = {"domains": []}

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                data = {"domains": []}

        # Add domain if not exists
        domains = data.get("domains", [])
        existing = [d for d in domains if d.get("domain") == domain]
        if not existing:
            domains.append({
                "domain": domain,
                "latency": latency,
                "added": datetime.now().isoformat()
            })
            data["domains"] = domains

            with open(config_path, 'w') as f:
                json.dump(data, f, indent=2)

        return {"success": True, "message": f"{domain} сохранен"}

    except Exception as e:
        return {"success": False, "message": str(e)}


@app.delete("/api/sni/saved/{domain}")
async def delete_saved_sni(domain: str, username: str = Depends(get_current_user)):
    """Delete a saved SNI domain."""
    try:
        config_path = "/etc/x-ui/sni_favorites.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                data = json.load(f)

            data["domains"] = [d for d in data.get("domains", []) if d["domain"] != domain]

            with open(config_path, 'w') as f:
                json.dump(data, f, indent=2)

        return {"success": True, "message": f"{domain} удален"}

    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/sni/discover")
async def discover_sni_domains(
    count: int = 20,
    provider: str = "cloudflare",
    username: str = Depends(get_current_user)
):
    """Auto-discover SNI domains by scanning CDN IP ranges."""
    import socket
    import ssl
    import time
    import random
    import concurrent.futures

    # CDN IP ranges (sample IPs from each provider)
    cdn_ranges = {
        "cloudflare": [
            "104.16.", "104.17.", "104.18.", "104.19.", "104.20.",
            "104.21.", "104.22.", "104.23.", "104.24.", "104.25.",
            "172.67.", "141.101."
        ],
        "google": [
            "142.250.", "172.217.", "216.58.", "74.125."
        ],
        "amazon": [
            "13.32.", "13.33.", "13.35.", "52.84.", "52.85."
        ],
        "microsoft": [
            "20.36.", "20.42.", "20.50.", "40.79.", "40.90."
        ],
        "fastly": [
            "151.101.", "199.232."
        ]
    }

    # Handle local network scan
    if provider == "local":
        # Get server's public IP and scan its /24 network
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            # Get /24 prefix
            ip_parts = local_ip.split('.')
            local_prefix = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}."
            ranges = [local_prefix]
        except:
            ranges = ["192.168.1."]
    elif provider == "all":
        # Scan all providers
        ranges = []
        for provider_ranges in cdn_ranges.values():
            ranges.extend(provider_ranges)
    else:
        ranges = cdn_ranges.get(provider, cdn_ranges["cloudflare"])

    def scan_ip(ip):
        """Scan single IP for domain and TLS support."""
        result = None
        try:
            # Reverse DNS lookup
            hostname = socket.gethostbyaddr(ip)[0]
            if not hostname or hostname == ip:
                return None

            # Test TLS
            start = time.time()
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.set_alpn_protocols(['h2', 'http/1.1'])
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((ip, 443))
            ssl_sock = context.wrap_socket(sock, server_hostname=hostname)

            latency = round((time.time() - start) * 1000, 1)
            tls13 = ssl_sock.version() == 'TLSv1.3'
            h2 = ssl_sock.selected_alpn_protocol() == 'h2'

            ssl_sock.close()
            sock.close()

            if tls13 and h2:
                return {
                    "domain": hostname,
                    "ip": ip,
                    "tls13": True,
                    "h2": True,
                    "latency": latency,
                    "status": "ok"
                }
        except:
            pass
        return None

    # Generate random IPs from ranges
    ips_to_scan = []
    for _ in range(count * 5):  # Scan more IPs to find enough results
        prefix = random.choice(ranges)
        if prefix.count('.') == 2:
            ip = f"{prefix}{random.randint(1, 254)}.{random.randint(1, 254)}"
        else:
            ip = f"{prefix}{random.randint(1, 254)}"
        ips_to_scan.append(ip)

    # Remove duplicates
    ips_to_scan = list(set(ips_to_scan))[:count * 3]

    # Scan in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(scan_ip, ip): ip for ip in ips_to_scan}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
                if len(results) >= count:
                    break

    # Sort by latency
    results.sort(key=lambda x: x["latency"])

    return {
        "success": True,
        "provider": provider,
        "scanned": len(ips_to_scan),
        "found": len(results),
        "results": results[:count]
    }


@app.get("/api/sni/suggestions")
async def get_sni_suggestions(username: str = Depends(get_current_user)):
    """Get popular SNI domain suggestions for Reality."""
    suggestions = [
        # CDN/Cloud
        "www.google.com",
        "www.microsoft.com",
        "www.apple.com",
        "www.cloudflare.com",
        "cdn.cloudflare.com",
        "www.amazon.com",
        "aws.amazon.com",
        # Tech
        "www.github.com",
        "www.gitlab.com",
        "www.npmjs.com",
        "registry.npmjs.org",
        "www.docker.com",
        # Services
        "www.paypal.com",
        "www.spotify.com",
        "www.netflix.com",
        "www.twitch.tv",
        "discord.com",
        # Regional
        "www.samsung.com",
        "www.lg.com",
        "www.sony.com",
        "www.asus.com",
        "www.lenovo.com"
    ]
    return {"success": True, "suggestions": suggestions}


@app.post("/api/system/update-3xui")
async def update_3xui(username: str = Depends(get_current_user)):
    """Update 3x-ui panel with database backup."""
    import subprocess
    import shutil
    from datetime import datetime

    try:
        # Create backup directory
        backup_dir = "/root/x-ui-backups"
        os.makedirs(backup_dir, exist_ok=True)

        # Backup database
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_path = "/etc/x-ui/x-ui.db"
        backup_path = f"{backup_dir}/x-ui_{timestamp}.db"

        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")

        # Stop x-ui
        subprocess.run(['systemctl', 'stop', 'x-ui'], check=True)

        # Run update script
        result = subprocess.run(
            "bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)",
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )

        # Start x-ui
        subprocess.run(['systemctl', 'start', 'x-ui'], check=True)

        return {
            "success": True,
            "message": "3x-ui обновлен",
            "backup_path": backup_path if os.path.exists(db_path) else None
        }

    except Exception as e:
        logger.error(f"Error updating 3x-ui: {e}")
        # Try to start x-ui in case of error
        subprocess.run(['systemctl', 'start', 'x-ui'], capture_output=True)
        return {"success": False, "message": str(e)}


@app.get("/api/system/xray-versions")
async def get_xray_versions(username: str = Depends(get_current_user)):
    """Get available Xray versions."""
    import urllib.request
    import json

    try:
        # Get releases from GitHub
        url = "https://api.github.com/repos/XTLS/Xray-core/releases?per_page=10"
        req = urllib.request.Request(url, headers={'User-Agent': 'XManager'})

        with urllib.request.urlopen(req, timeout=30) as response:
            releases = json.loads(response.read().decode())

        versions = []
        for release in releases:
            versions.append({
                "version": release["tag_name"],
                "name": release["name"],
                "published": release["published_at"],
                "prerelease": release["prerelease"]
            })

        # Get current version
        current = "unknown"
        try:
            result = subprocess.run(
                ["/usr/local/x-ui/bin/xray-linux-amd64", "-version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # Parse version from output
                import re
                match = re.search(r'Xray (\d+\.\d+\.\d+)', result.stdout)
                if match:
                    current = f"v{match.group(1)}"
        except:
            pass

        return {
            "success": True,
            "current_version": current,
            "versions": versions
        }

    except Exception as e:
        logger.error(f"Error getting Xray versions: {e}")
        return {"success": False, "message": str(e), "versions": []}


@app.post("/api/system/install-xray")
async def install_xray_version(version: str, username: str = Depends(get_current_user)):
    """Install specific Xray version."""
    import subprocess

    try:
        # Stop x-ui
        subprocess.run(['systemctl', 'stop', 'x-ui'], check=True)

        # Download and install specific version
        install_script = f"""
        cd /usr/local/x-ui/bin

        # Download specific version
        ARCH=$(uname -m)
        case $ARCH in
            x86_64) ARCH="64" ;;
            aarch64) ARCH="arm64-v8a" ;;
            *) ARCH="64" ;;
        esac

        wget -q "https://github.com/XTLS/Xray-core/releases/download/{version}/Xray-linux-$ARCH.zip" -O xray.zip
        unzip -o xray.zip xray
        mv xray xray-linux-amd64
        chmod +x xray-linux-amd64
        rm xray.zip
        """

        result = subprocess.run(
            install_script,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Start x-ui
        subprocess.run(['systemctl', 'start', 'x-ui'], check=True)

        if result.returncode == 0:
            return {"success": True, "message": f"Xray {version} установлен"}
        else:
            return {"success": False, "message": result.stderr or "Ошибка установки"}

    except Exception as e:
        logger.error(f"Error installing Xray: {e}")
        subprocess.run(['systemctl', 'start', 'x-ui'], capture_output=True)
        return {"success": False, "message": str(e)}


# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

if __name__ == "__main__":
    logger.info("Starting X-UI Manager API...")
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )