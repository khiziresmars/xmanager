#!/usr/bin/env python3
"""
X-UI Manager API - Управление пользователями 3x-ui
Универсальный инструмент для управления базой пользователей 3x-ui
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
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
from config import settings

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

# Подключение статических файлов
if os.path.exists("/opt/xui-manager/static"):
    app.mount("/static", StaticFiles(directory="/opt/xui-manager/static"), name="static")

# Инициализация базы данных
db = XUIDatabase()

# ========================= API ENDPOINTS =========================

@app.get("/", response_class=HTMLResponse)
async def web_interface():
    """Веб-интерфейс для управления"""
    with open("/opt/xui-manager/templates/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db.check_connection()
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
    """Массовое создание пользователей по шаблону"""
    try:
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
    filter_type: str = Query("expiry", description="Тип фильтра: expiry (бессрочные), traffic (без лимита трафика), both (оба)")
):
    """Получение пользователей с безлимитным трафиком или бессрочных"""
    try:
        users = db.get_unlimited_traffic_users(inbound_id, enabled_only, sort_by, order, filter_type)
        return {
            "users": users,
            "count": len(users),
            "filter_type": filter_type
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

# ==================== СИСТЕМНЫЕ ОПЕРАЦИИ ====================

@app.post("/api/system/restart-xui")
async def restart_xui():
    """Перезапуск сервиса x-ui"""
    try:
        result = db.restart_xui_service()
        if result["success"]:
            return {"message": "X-UI service restarted successfully"}
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        logger.error(f"Error restarting x-ui: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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