#!/usr/bin/env python3
"""
X-UI Manager API - Управление пользователями 3x-ui
Универсальный инструмент для управления базой пользователей 3x-ui
"""

from fastapi import FastAPI, HTTPException, Depends, Query, Response, Cookie
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

# Добавляем путь для импорта локальных модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import XUIDatabase
from models import *
from config import settings, SERVER_ID
from auth import SessionManager, TokenManager, authenticate_user, get_current_user, optional_user, ADMIN_USERNAME
from app.queue import queue_manager, QueueStatus

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
    version="1.0.0",
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
    public_paths = ["/login", "/api/auth/login", "/api/health"]

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

# Инициализация базы данных
db = XUIDatabase()

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
        return RedirectResponse(url="/login", status_code=302)

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

@app.get("/api/server/info")
async def get_server_info():
    """Получение информации о сервере"""
    return {
        "server_id": SERVER_ID,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION
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
    """Получение количества онлайн пользователей"""
    try:
        online_count = db.get_online_users_count()
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

@app.post("/api/users/bulk-delete")
async def bulk_delete_users(request: BulkDeleteRequest):
    """Массовое удаление пользователей"""
    try:
        result = db.bulk_delete_users(request.user_ids, request.filters)
        return {
            "message": f"Deleted {result['deleted']} users",
            "deleted": result['deleted'],
            "failed": result['failed']
        }
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}")
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

# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

if __name__ == "__main__":
    logger.info("Starting X-UI Manager API...")
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )