#!/usr/bin/env python3
"""
Pydantic модели для API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ==================== USER MODELS ====================

class UserCreate(BaseModel):
    """Модель для создания пользователя"""
    inbound_id: int = Field(..., description="ID инбаунда")
    email: str = Field(..., description="Email/имя пользователя")
    total: Optional[int] = Field(0, description="Лимит трафика в байтах")
    expiry_time: Optional[int] = Field(0, description="Время истечения в миллисекундах")
    method: Optional[str] = Field("chacha20-ietf-poly1305", description="Метод шифрования для Shadowsocks")
    flow: Optional[str] = Field(None, description="Flow для VLESS (например: xtls-rprx-vision)")
    password: Optional[str] = Field(None, description="Пароль для Shadowsocks")
    limitIp: Optional[int] = Field(0, description="Лимит IP адресов")

class UserTemplate(BaseModel):
    """Шаблон пользователя"""
    name: str = Field(..., description="Название шаблона")
    prefix: str = Field("user", description="Префикс для имени")
    total: int = Field(0, description="Лимит трафика")
    expiry_time: int = Field(0, description="Время истечения")
    method: Optional[str] = Field("chacha20-ietf-poly1305", description="Метод для Shadowsocks")
    flow: Optional[str] = Field(None, description="Flow для VLESS (например: xtls-rprx-vision)")
    limitIp: Optional[int] = Field(0)

class BulkCreateRequest(BaseModel):
    """Запрос на массовое создание пользователей (до 100)"""
    template: UserTemplate
    count: int = Field(..., ge=1, le=100, description="Количество пользователей")
    inbound_id: int = Field(..., description="ID инбаунда")

class QueueBulkCreateRequest(BaseModel):
    """Запрос на массовое создание через систему очередей (101-5000)"""
    template: UserTemplate
    count: int = Field(..., ge=1, le=5000, description="Количество пользователей (макс. 5000)")
    inbound_id: int = Field(..., description="ID инбаунда")

class BulkDeleteRequest(BaseModel):
    """Запрос на массовое удаление"""
    user_ids: Optional[List[str]] = Field(None, description="Список ID пользователей")
    filters: Optional[Dict[str, Any]] = Field(None, description="Фильтры для удаления")

# ==================== TRAFFIC MODELS ====================

class UpdateTrafficRequest(BaseModel):
    """Запрос на обновление трафика"""
    traffic_limit: int = Field(..., ge=0, description="Новый лимит трафика в байтах")

class ResetTrafficRequest(BaseModel):
    """Запрос на сброс трафика"""
    user_ids: List[str] = Field(..., description="Список ID пользователей")
    new_limit: int = Field(..., ge=0, description="Новый лимит трафика")

class AddTrafficRequest(BaseModel):
    """Запрос на добавление трафика"""
    user_ids: List[str] = Field(..., description="Список ID пользователей")
    additional_traffic: int = Field(..., ge=0, description="Дополнительный трафик в байтах")

class SetLimitRequest(BaseModel):
    """Запрос на установку лимита"""
    user_ids: List[str] = Field(..., description="Список ID пользователей")
    new_limit: int = Field(..., ge=0, description="Новый лимит трафика в байтах")

class ToggleStatusRequest(BaseModel):
    """Запрос на блокировку/разблокировку"""
    user_ids: List[str] = Field(..., description="Список ID пользователей")
    enable: bool = Field(..., description="True - разблокировать, False - заблокировать")

class ExtendExpiryRequest(BaseModel):
    """Запрос на продление срока"""
    user_ids: List[str] = Field(..., description="Список ID пользователей")
    days: int = Field(..., ge=1, le=365, description="Количество дней для продления")

# ==================== INBOUND MODELS ====================

class InboundCreate(BaseModel):
    """Модель для создания инбаунда"""
    port: int = Field(..., ge=1, le=65535)
    protocol: str = Field(..., description="Протокол: vmess, vless, trojan, shadowsocks")
    remark: str = Field(..., description="Название инбаунда")
    settings: Dict[str, Any] = Field({}, description="Настройки протокола")

# ==================== RESPONSE MODELS ====================

class UserResponse(BaseModel):
    """Ответ с информацией о пользователе"""
    id: str
    email: str
    inbound_id: int
    enable: bool
    up: int
    down: int
    total: int
    remaining_traffic: Optional[int]
    expiry_time: int
    inbound_name: Optional[str]
    port: Optional[int]
    protocol: Optional[str]

class InboundResponse(BaseModel):
    """Ответ с информацией об инбаунде"""
    id: int
    port: int
    protocol: str
    remark: str
    enable: bool
    users_count: int
    up: int
    down: int
    total: int

class StatsResponse(BaseModel):
    """Ответ со статистикой"""
    total_users: int
    active_users: int
    total_upload: int
    total_download: int
    total_traffic: int
    total_inbounds: int
    timestamp: str

class AnalyticsResponse(BaseModel):
    """Ответ с аналитикой"""
    top_users: List[Dict[str, Any]]
    inbound_stats: List[Dict[str, Any]]
    user_status: Dict[str, int]

# ==================== ERROR MODELS ====================

class ErrorResponse(BaseModel):
    """Модель ошибки"""
    error: str
    detail: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())