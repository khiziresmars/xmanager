#!/usr/bin/env python3
"""
Модуль для работы с базой данных 3x-ui
"""

import sqlite3
import json
import subprocess
import os
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
import uuid
import hashlib

logger = logging.getLogger(__name__)

class XUIDatabase:
    """Класс для работы с базой данных 3x-ui"""
    
    def __init__(self, db_path: str = "/etc/x-ui/x-ui.db"):
        self.db_path = db_path
        self.xui_config_path = "/usr/local/x-ui/bin/config.json"
        
    def _get_connection(self):
        """Получение соединения с БД"""
        return sqlite3.connect(self.db_path)
    
    def check_connection(self) -> bool:
        """Проверка соединения с БД"""
        try:
            conn = self._get_connection()
            conn.execute("SELECT 1")
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            return False
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    def _get_table_columns(self, table_name: str) -> List[str]:
        """Получить список колонок таблицы"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            conn.close()
            return columns
        except Exception as e:
            logger.error(f"Error getting table columns: {e}")
            return []

    # ==================== СТАТИСТИКА ====================

    def get_system_stats(self) -> Dict[str, Any]:
        """Получение статистики системы"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) FROM client_traffics")
            total_users = cursor.fetchone()[0]
            
            # Количество активных пользователей
            cursor.execute("""
                SELECT COUNT(*) FROM client_traffics 
                WHERE enable = 1
            """)
            active_users = cursor.fetchone()[0]
            
            # Общий трафик
            cursor.execute("""
                SELECT 
                    SUM(up) as total_upload,
                    SUM(down) as total_download,
                    SUM(total) as total_traffic
                FROM client_traffics
            """)
            traffic = cursor.fetchone()
            
            # Количество inbounds
            cursor.execute("SELECT COUNT(*) FROM inbounds")
            total_inbounds = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "total_upload": traffic[0] or 0,
                "total_download": traffic[1] or 0,
                "total_traffic": traffic[2] or 0,
                "total_inbounds": total_inbounds,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    # ==================== ПОЛЬЗОВАТЕЛИ ====================
    
    def get_users(self, inbound_id: Optional[int] = None,
                  limit: int = 100, offset: int = 0,
                  search: Optional[str] = None) -> Dict:
        """Получение списка пользователей с пагинацией"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Сначала подсчитаем общее количество
            count_query = "SELECT COUNT(*) FROM client_traffics ct WHERE 1=1"
            count_params = []

            if inbound_id:
                count_query += " AND ct.inbound_id = ?"
                count_params.append(inbound_id)

            if search:
                count_query += " AND ct.email LIKE ?"
                count_params.append(f"%{search}%")

            cursor.execute(count_query, count_params)
            total_count = cursor.fetchone()[0]

            # Теперь получаем пользователей с пагинацией
            query = """
                SELECT
                    ct.id, ct.inbound_id, ct.email, ct.enable,
                    ct.up, ct.down, ct.total, ct.expiry_time,
                    i.remark as inbound_name, i.port, i.protocol
                FROM client_traffics ct
                LEFT JOIN inbounds i ON ct.inbound_id = i.id
                WHERE 1=1
            """
            params = []

            if inbound_id:
                query += " AND ct.inbound_id = ?"
                params.append(inbound_id)

            if search:
                query += " AND ct.email LIKE ?"
                params.append(f"%{search}%")

            query += f" LIMIT {limit} OFFSET {offset}"

            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            users = []

            for row in cursor.fetchall():
                user = dict(zip(columns, row))
                # Добавляем расчет оставшегося трафика
                if user['total'] and user['total'] > 0:
                    used = (user['up'] or 0) + (user['down'] or 0)
                    user['remaining_traffic'] = user['total'] - used
                else:
                    user['remaining_traffic'] = None
                users.append(user)

            conn.close()
            return {'users': users, 'total': total_count}

        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return {'users': [], 'total': 0}
    
    def create_user(self, user_data: Dict) -> Dict:
        """Создание нового пользователя"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Проверяем что inbound существует
            cursor.execute("""
                SELECT id, settings, protocol FROM inbounds WHERE id = ?
            """, (user_data['inbound_id'],))

            inbound_row = cursor.fetchone()
            if not inbound_row:
                logger.error(f"Inbound {user_data['inbound_id']} not found")
                return {"success": False, "error": f"Inbound {user_data['inbound_id']} не найден"}

            inbound_id, settings_json, protocol = inbound_row
            logger.info(f"Creating user {user_data['email']} in inbound {inbound_id} (protocol: {protocol})")

            # Получаем список доступных колонок в таблице
            available_columns = self._get_table_columns('client_traffics')

            # Базовые обязательные поля
            fields = {
                'inbound_id': user_data['inbound_id'],
                'enable': 1,
                'email': user_data['email'],
                'up': 0,
                'down': 0,
                'expiry_time': user_data.get('expiry_time', 0),
                'total': user_data.get('total', 0)
            }

            # Дополнительные поля если они существуют в таблице
            optional_fields = {
                'reset': 0,
                'all_time': 0,
                'last_online': 0
            }

            # Добавляем опциональные поля только если они есть в схеме
            for field, value in optional_fields.items():
                if field in available_columns:
                    fields[field] = value

            # Формируем динамический INSERT запрос
            columns = ', '.join(fields.keys())
            placeholders = ', '.join(['?' for _ in fields])
            values = tuple(fields.values())

            cursor.execute(f"""
                INSERT INTO client_traffics ({columns})
                VALUES ({placeholders})
            """, values)

            # Получаем созданный ID
            user_id = cursor.lastrowid
            logger.info(f"Created user in client_traffics with ID: {user_id} (used columns: {list(fields.keys())})")

            # Обновляем settings в inbound
            settings = json.loads(settings_json)

            # Создаем клиента с полной структурой для x-ui
            if settings.get('clients') is None:
                settings['clients'] = []

            # Базовая структура клиента (общая для всех протоколов)
            new_client = {
                "email": user_data['email'],
                "enable": True,
                "expiryTime": user_data.get('expiry_time', 0),
                "totalGB": user_data.get('total', 0),
                "limitIp": user_data.get('limitIp', 0),
                "reset": 0
            }

            # Добавляем специфичные для протокола поля
            if protocol == 'shadowsocks':
                # Shadowsocks: использует database id, method и password
                new_client["id"] = user_id
                new_client["method"] = user_data.get('method', 'chacha20-ietf-poly1305')
                new_client["password"] = user_data.get('password', self._generate_password())
            elif protocol == 'vless':
                # VLESS: использует UUID и flow
                new_client["id"] = str(uuid.uuid4())
                new_client["flow"] = user_data.get('flow', 'xtls-rprx-vision')
            elif protocol == 'trojan':
                # Trojan: использует только password, без id/uuid
                new_client["password"] = user_data.get('password', self._generate_password())
            elif protocol == 'vmess':
                # VMess: использует UUID
                new_client["id"] = str(uuid.uuid4())
            else:
                # Fallback для неизвестных протоколов
                logger.warning(f"Unknown protocol: {protocol}, using UUID")
                new_client["id"] = str(uuid.uuid4())

            settings['clients'].append(new_client)

            # Сохраняем обновленные settings
            cursor.execute("""
                UPDATE inbounds SET settings = ? WHERE id = ?
            """, (json.dumps(settings), user_data['inbound_id']))

            conn.commit()
            conn.close()

            logger.info(f"Successfully created user {user_data['email']} with ID {user_id}")

            return {
                "success": True,
                "user": {
                    "id": user_id,
                    "email": user_data['email'],
                    "inbound_id": user_data['inbound_id']
                }
            }

        except Exception as e:
            logger.error(f"Error creating user {user_data.get('email', 'unknown')}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def delete_user(self, user_id: str) -> Dict:
        """Удаление пользователя"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Преобразуем user_id в int если нужно
            try:
                user_id_int = int(user_id)
            except (ValueError, TypeError):
                user_id_int = user_id

            # Получаем inbound_id и email пользователя
            cursor.execute("""
                SELECT inbound_id, email FROM client_traffics WHERE id = ?
            """, (user_id_int,))
            result = cursor.fetchone()

            if not result:
                return {"success": False, "error": "User not found"}

            inbound_id, email = result

            # Удаляем из client_traffics
            cursor.execute("""
                DELETE FROM client_traffics WHERE id = ?
            """, (user_id_int,))

            # Удаляем из settings inbound
            cursor.execute("""
                SELECT settings FROM inbounds WHERE id = ?
            """, (inbound_id,))

            settings_json = cursor.fetchone()[0]
            settings = json.loads(settings_json)

            if 'clients' in settings and settings['clients']:
                # Удаляем по id или по email
                settings['clients'] = [
                    c for c in settings['clients']
                    if c.get('id') != user_id_int and c.get('email') != email
                ]

            cursor.execute("""
                UPDATE inbounds SET settings = ? WHERE id = ?
            """, (json.dumps(settings, ensure_ascii=False), inbound_id))

            conn.commit()
            conn.close()

            logger.info(f"User deleted: {email} (ID: {user_id_int})")

            return {"success": True}

        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return {"success": False, "error": str(e)}
    
    def bulk_delete_users(self, user_ids: List[str] = None, 
                          filters: Dict = None) -> Dict:
        """Массовое удаление пользователей"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            deleted = 0
            failed = 0
            
            # Если указаны конкретные ID
            if user_ids:
                for user_id in user_ids:
                    result = self.delete_user(user_id)
                    if result["success"]:
                        deleted += 1
                    else:
                        failed += 1
            
            # Если указаны фильтры
            elif filters:
                # Строим запрос по фильтрам
                query = "SELECT id FROM client_traffics WHERE 1=1"
                params = []
                
                if filters.get('inbound_id'):
                    query += " AND inbound_id = ?"
                    params.append(filters['inbound_id'])
                
                if filters.get('expired'):
                    query += " AND expiry_time > 0 AND expiry_time < ?"
                    params.append(int(datetime.now().timestamp() * 1000))
                
                if filters.get('no_traffic'):
                    query += " AND (up + down) = 0"
                
                cursor.execute(query, params)
                user_ids = [row[0] for row in cursor.fetchall()]
                
                for user_id in user_ids:
                    result = self.delete_user(user_id)
                    if result["success"]:
                        deleted += 1
                    else:
                        failed += 1
            
            conn.close()
            return {"deleted": deleted, "failed": failed}
            
        except Exception as e:
            logger.error(f"Error in bulk delete: {e}")
            return {"deleted": 0, "failed": 0}
    
    def bulk_create_users(self, template: Dict, count: int,
                          inbound_id: int) -> Dict:
        """Массовое создание пользователей по шаблону"""
        try:
            created = 0
            users = []
            errors = []

            logger.info(f"Starting bulk create: {count} users for inbound {inbound_id}")

            for i in range(count):
                user_data = template.copy()
                user_data['inbound_id'] = inbound_id
                user_data['email'] = f"{template.get('prefix', 'user')}_{i+1:04d}"

                result = self.create_user(user_data)
                if result["success"]:
                    created += 1
                    users.append(result["user"])
                else:
                    error_msg = f"{user_data['email']}: {result.get('error', 'Unknown error')}"
                    errors.append(error_msg)
                    logger.error(f"Failed to create user: {error_msg}")

            # После создания всех пользователей, перезапускаем x-ui один раз
            if created > 0:
                logger.info(f"Restarting x-ui after creating {created} users")
                self._update_xui_config()

            logger.info(f"Bulk create completed: {created}/{count} users created")
            if errors:
                logger.error(f"Errors during bulk create: {errors[:5]}")  # Показываем первые 5 ошибок

            return {
                "created": created,
                "users": users,
                "errors": errors[:10] if errors else []  # Возвращаем максимум 10 ошибок
            }

        except Exception as e:
            logger.error(f"Error in bulk create: {e}", exc_info=True)
            return {"created": 0, "users": [], "errors": [str(e)]}
    
    # ==================== ТРАФИК ====================
    
    def get_low_traffic_users(self, threshold: int = 1024,
                              inbound_id: Optional[int] = None,
                              sort_by: str = "remaining",
                              order: str = "asc") -> List[Dict]:
        """Получение пользователей с низким остатком трафика"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    id, email, inbound_id,
                    total, up, down,
                    (total - up - down) as remaining,
                    enable
                FROM client_traffics
                WHERE total > 0
                AND (total - up - down) <= ?
            """
            params = [threshold]

            if inbound_id:
                query += " AND inbound_id = ?"
                params.append(inbound_id)

            # Добавляем сортировку
            valid_sort = ["remaining", "email", "total", "used"]
            if sort_by == "used":
                query += f" ORDER BY (up + down) {order.upper()}"
            elif sort_by in valid_sort:
                query += f" ORDER BY {sort_by} {order.upper()}"
            else:
                query += " ORDER BY remaining ASC"

            cursor.execute(query, params)

            columns = [description[0] for description in cursor.description]
            users = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()
            return users

        except Exception as e:
            logger.error(f"Error getting low traffic users: {e}")
            return []
    
    def get_unlimited_traffic_users(self, inbound_id: Optional[int] = None,
                                    enabled_only: bool = False,
                                    sort_by: str = "used",
                                    order: str = "desc",
                                    filter_type: str = "expiry") -> List[Dict]:
        """Получение пользователей с безлимитным трафиком или бессрочных

        filter_type:
            - 'expiry': пользователи без ограничения по времени (expiry_time = 0)
            - 'traffic': пользователи без ограничения по трафику (total = 0)
            - 'both': пользователи без обоих ограничений
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    id, email, inbound_id,
                    total, up, down,
                    enable, expiry_time
                FROM client_traffics
                WHERE 1=1
            """
            params = []

            # Фильтр по типу безлимита
            if filter_type == "expiry":
                query += " AND expiry_time = 0"
            elif filter_type == "traffic":
                query += " AND (total = 0 OR total IS NULL)"
            elif filter_type == "both":
                query += " AND expiry_time = 0 AND (total = 0 OR total IS NULL)"

            if inbound_id:
                query += " AND inbound_id = ?"
                params.append(inbound_id)

            if enabled_only:
                query += " AND enable = 1"

            # Добавляем сортировку
            if sort_by == "used":
                query += f" ORDER BY (up + down) {order.upper()}"
            elif sort_by == "email":
                query += f" ORDER BY email {order.upper()}"
            else:
                query += " ORDER BY (up + down) DESC"

            cursor.execute(query, params)

            columns = [description[0] for description in cursor.description]
            users = []

            for row in cursor.fetchall():
                user = dict(zip(columns, row))
                user['used_traffic'] = (user['up'] or 0) + (user['down'] or 0)
                users.append(user)

            conn.close()
            return users

        except Exception as e:
            logger.error(f"Error getting unlimited users: {e}")
            return []
    
    def update_user_traffic(self, user_id: str, new_limit: int) -> Dict:
        """Обновление лимита трафика пользователя"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE client_traffics
                SET total = ?
                WHERE id = ?
            """, (new_limit, user_id))

            # Синхронизируем с JSON
            self._sync_client_to_json(cursor, user_id)

            conn.commit()
            conn.close()

            return {"success": True}

        except Exception as e:
            logger.error(f"Error updating traffic: {e}")
            return {"success": False, "error": str(e)}
    
    def reset_traffic_for_users(self, user_ids: List[str],
                                new_limit: int) -> Dict:
        """Сброс трафика для группы пользователей"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            updated = 0
            for user_id in user_ids:
                cursor.execute("""
                    UPDATE client_traffics
                    SET total = ?, up = 0, down = 0
                    WHERE id = ?
                """, (new_limit, user_id))

                if cursor.rowcount > 0:
                    # Синхронизируем с JSON
                    self._sync_client_to_json(cursor, user_id)
                    updated += 1

            conn.commit()
            conn.close()

            return {"updated": updated}

        except Exception as e:
            logger.error(f"Error resetting traffic: {e}")
            return {"updated": 0}

    def add_traffic_for_users(self, user_ids: List[str],
                              additional_traffic: int) -> Dict:
        """Добавление трафика к существующему лимиту без сброса использованного"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            updated = 0
            for user_id in user_ids:
                cursor.execute("""
                    UPDATE client_traffics
                    SET total = total + ?
                    WHERE id = ?
                """, (additional_traffic, user_id))

                if cursor.rowcount > 0:
                    # Синхронизируем с JSON
                    self._sync_client_to_json(cursor, user_id)
                    updated += 1

            conn.commit()
            conn.close()

            return {"updated": updated}

        except Exception as e:
            logger.error(f"Error adding traffic: {e}")
            return {"updated": 0}

    def set_limit_for_users(self, user_ids: List[str],
                           new_limit: int) -> Dict:
        """Установка нового лимита без сброса использованного трафика"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            updated = 0
            for user_id in user_ids:
                cursor.execute("""
                    UPDATE client_traffics
                    SET total = ?
                    WHERE id = ?
                """, (new_limit, user_id))

                if cursor.rowcount > 0:
                    # Синхронизируем с JSON
                    self._sync_client_to_json(cursor, user_id)
                    updated += 1

            conn.commit()
            conn.close()

            return {"updated": updated}

        except Exception as e:
            logger.error(f"Error setting limit: {e}")
            return {"updated": 0}

    # ==================== ИНБАУНДЫ ====================
    
    def get_inbounds(self) -> List[Dict]:
        """Получение списка всех inbounds"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id, user_id, up, down, total, remark,
                    enable, expiry_time, listen, port, protocol
                FROM inbounds
                ORDER BY id
            """)
            
            columns = [description[0] for description in cursor.description]
            inbounds = []
            
            for row in cursor.fetchall():
                inbound = dict(zip(columns, row))
                
                # Подсчитываем количество пользователей
                cursor.execute("""
                    SELECT COUNT(*) FROM client_traffics 
                    WHERE inbound_id = ?
                """, (inbound['id'],))
                inbound['users_count'] = cursor.fetchone()[0]
                
                inbounds.append(inbound)
            
            conn.close()
            return inbounds
            
        except Exception as e:
            logger.error(f"Error getting inbounds: {e}")
            return []
    
    def get_inbound(self, inbound_id: int) -> Optional[Dict]:
        """Получение информации об inbound"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM inbounds WHERE id = ?
            """, (inbound_id,))
            
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                inbound = dict(zip(columns, row))
                
                # Парсим settings
                if inbound.get('settings'):
                    inbound['settings'] = json.loads(inbound['settings'])
                
                conn.close()
                return inbound
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Error getting inbound: {e}")
            return None
    
    # ==================== СИСТЕМНЫЕ ОПЕРАЦИИ ====================

    def get_server_health(self) -> Dict:
        """Получение информации о состоянии сервера"""
        try:
            import psutil

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage('/')

            # Network IO
            network = psutil.net_io_counters()

            # System uptime
            import time
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_total": memory.total,
                "memory_used": memory.used,
                "memory_percent": round(memory.percent, 2),
                "disk_total": disk.total,
                "disk_used": disk.used,
                "disk_percent": round(disk.percent, 2),
                "network_sent": network.bytes_sent,
                "network_recv": network.bytes_recv,
                "uptime_seconds": int(uptime_seconds)
            }
        except Exception as e:
            logger.error(f"Error getting server health: {e}")
            return {}

    def get_online_users_count(self) -> int:
        """Получение количества онлайн пользователей"""
        try:
            # Получаем список пользователей с недавней активностью
            # Используем поле last_online если оно доступно
            conn = self._get_connection()
            cursor = conn.cursor()

            # Проверяем наличие колонки last_online
            available_columns = self._get_table_columns('client_traffics')

            if 'last_online' in available_columns:
                # Считаем онлайн если активность была в последние 5 минут
                import time
                five_minutes_ago = int((time.time() - 300) * 1000)

                cursor.execute("""
                    SELECT COUNT(*) FROM client_traffics
                    WHERE enable = 1 AND last_online > ?
                """, (five_minutes_ago,))

                online_count = cursor.fetchone()[0]
            else:
                # Если last_online недоступен, возвращаем количество активных
                cursor.execute("""
                    SELECT COUNT(*) FROM client_traffics
                    WHERE enable = 1
                """)
                online_count = cursor.fetchone()[0]

            conn.close()
            return online_count

        except Exception as e:
            logger.error(f"Error getting online users: {e}")
            return 0

    def restart_xui_service(self) -> Dict:
        """Перезапуск сервиса x-ui"""
        try:
            subprocess.run(["systemctl", "restart", "x-ui"], check=True)
            return {"success": True, "message": "X-UI service restarted"}
        except Exception as e:
            logger.error(f"Error restarting x-ui: {e}")
            return {"success": False, "error": str(e)}

    def stop_xui_service(self) -> Dict:
        """Остановка сервиса x-ui"""
        try:
            subprocess.run(["systemctl", "stop", "x-ui"], check=True)
            return {"success": True, "message": "X-UI service stopped"}
        except Exception as e:
            logger.error(f"Error stopping x-ui: {e}")
            return {"success": False, "error": str(e)}

    def start_xui_service(self) -> Dict:
        """Запуск сервиса x-ui"""
        try:
            subprocess.run(["systemctl", "start", "x-ui"], check=True)
            return {"success": True, "message": "X-UI service started"}
        except Exception as e:
            logger.error(f"Error starting x-ui: {e}")
            return {"success": False, "error": str(e)}

    def get_xui_service_status(self) -> Dict:
        """Получение статуса сервиса x-ui"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "x-ui"],
                capture_output=True,
                text=True
            )
            is_active = result.stdout.strip() == "active"

            # Получаем детальную информацию
            status_result = subprocess.run(
                ["systemctl", "status", "x-ui", "--no-pager"],
                capture_output=True,
                text=True
            )

            return {
                "success": True,
                "active": is_active,
                "status": result.stdout.strip(),
                "details": status_result.stdout
            }
        except Exception as e:
            logger.error(f"Error getting x-ui status: {e}")
            return {"success": False, "error": str(e)}

    def update_xray_core(self) -> Dict:
        """Обновление Xray core"""
        try:
            logger.info("Starting Xray core update...")

            # Скачиваем и устанавливаем последнюю версию Xray
            result = subprocess.run(
                ["bash", "-c", "bash <(curl -Ls https://raw.githubusercontent.com/XTLS/Xray-install/main/install-release.sh) install"],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                # Перезапускаем x-ui после обновления
                self.restart_xui_service()
                return {
                    "success": True,
                    "message": "Xray core updated successfully",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "error": "Xray update failed",
                    "output": result.stderr
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Update timeout (5 minutes)"}
        except Exception as e:
            logger.error(f"Error updating Xray: {e}")
            return {"success": False, "error": str(e)}

    def get_xray_version(self) -> Dict:
        """Получение версии Xray"""
        try:
            result = subprocess.run(
                ["xray", "version"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Парсим вывод чтобы получить версию
                version_line = result.stdout.split('\n')[0]
                return {
                    "success": True,
                    "version": version_line,
                    "full_output": result.stdout
                }
            else:
                return {"success": False, "error": "Failed to get Xray version"}

        except Exception as e:
            logger.error(f"Error getting Xray version: {e}")
            return {"success": False, "error": str(e)}

    def get_xui_version(self) -> Dict:
        """Получение версии x-ui"""
        try:
            # Пытаемся получить версию из БД
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM settings WHERE key = 'xrayVersion' LIMIT 1")
            row = cursor.fetchone()

            if row:
                version = row[0]
                conn.close()
                return {"success": True, "version": version}

            conn.close()
            return {"success": False, "error": "Version not found in database"}

        except Exception as e:
            logger.error(f"Error getting x-ui version: {e}")
            return {"success": False, "error": str(e)}

    def create_backup(self) -> Dict:
        """Создание резервной копии БД"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"/opt/xui-manager/backups/xui_backup_{timestamp}.db"
            
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)
            shutil.copy2(self.db_path, backup_file)
            
            return {"success": True, "file": backup_file}
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return {"success": False, "error": str(e)}
    
    def get_system_logs(self, lines: int = 100) -> List[str]:
        """Получение логов системы"""
        try:
            result = subprocess.run(
                ["journalctl", "-u", "x-ui", "-n", str(lines), "--no-pager"],
                capture_output=True, text=True
            )
            return result.stdout.split('\n')
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return []
    
    # ==================== ШАБЛОНЫ ====================
    
    def get_user_templates(self) -> List[Dict]:
        """Получение списка шаблонов"""
        templates_file = "/opt/xui-manager/templates.json"
        try:
            if os.path.exists(templates_file):
                with open(templates_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            return []
    
    def save_user_template(self, template: Dict) -> Dict:
        """Сохранение шаблона"""
        templates_file = "/opt/xui-manager/templates.json"
        try:
            templates = self.get_user_templates()
            templates.append(template)
            
            with open(templates_file, 'w') as f:
                json.dump(templates, f, indent=2)
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error saving template: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== АНАЛИТИКА ====================
    
    def get_traffic_analytics(self) -> Dict:
        """Получение аналитики по трафику"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Топ пользователей по трафику
            cursor.execute("""
                SELECT email, (up + down) as total_used
                FROM client_traffics
                ORDER BY total_used DESC
                LIMIT 10
            """)
            top_users = [
                {"email": row[0], "traffic": row[1]} 
                for row in cursor.fetchall()
            ]
            
            # Распределение по inbounds
            cursor.execute("""
                SELECT 
                    i.remark,
                    SUM(ct.up + ct.down) as total_traffic,
                    COUNT(ct.id) as users_count
                FROM inbounds i
                LEFT JOIN client_traffics ct ON i.id = ct.inbound_id
                GROUP BY i.id
            """)
            inbound_stats = [
                {
                    "name": row[0],
                    "traffic": row[1] or 0,
                    "users": row[2]
                }
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            return {
                "top_users": top_users,
                "inbound_stats": inbound_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting traffic analytics: {e}")
            return {}
    
    def get_users_analytics(self) -> Dict:
        """Получение аналитики по пользователям"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Активные vs неактивные
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN enable = 1 THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN enable = 0 THEN 1 ELSE 0 END) as inactive
                FROM client_traffics
            """)
            status = cursor.fetchone()
            
            # Истекшие подписки
            current_time = int(datetime.now().timestamp() * 1000)
            cursor.execute("""
                SELECT COUNT(*)
                FROM client_traffics
                WHERE expiry_time > 0 AND expiry_time < ?
            """, (current_time,))
            expired = cursor.fetchone()[0]
            
            # Пользователи без трафика
            cursor.execute("""
                SELECT COUNT(*)
                FROM client_traffics
                WHERE (up + down) = 0
            """)
            no_traffic = cursor.fetchone()[0]

            conn.close()

            # Получаем реальное количество онлайн пользователей
            online = self.get_truly_online_users_count()

            return {
                "active": status[0] or 0,
                "inactive": status[1] or 0,
                "expired": expired,
                "no_traffic": no_traffic,
                "online": online
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    def _generate_password(self, length: int = 16) -> str:
        """Генерация случайного пароля"""
        import random
        import string
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def _update_xui_config(self):
        """Обновление конфигурации xray"""
        try:
            logger.info("Running x-ui migrate command...")
            # Генерируем новый config.json из БД с timeout 30 секунд
            result = subprocess.run(
                ["/usr/local/x-ui/x-ui", "migrate"],
                check=True,
                timeout=30,
                capture_output=True,
                text=True
            )
            logger.info(f"x-ui migrate completed successfully: {result.stdout}")
        except subprocess.TimeoutExpired:
            logger.error("x-ui migrate timed out after 30 seconds")
            raise
        except Exception as e:
            logger.error(f"Error updating config: {e}", exc_info=True)

    def _sync_client_to_json(self, cursor, user_id: str, email: str = None) -> bool:
        """Синхронизация данных клиента из client_traffics в inbounds.settings JSON

        Args:
            cursor: Курсор БД
            user_id: ID пользователя или email
            email: Email пользователя (если известен)

        Returns:
            True если синхронизация успешна, False иначе
        """
        try:
            # Получаем данные из client_traffics
            if email:
                cursor.execute("""
                    SELECT id, email, inbound_id, expiry_time, total, enable, up, down, reset
                    FROM client_traffics
                    WHERE email = ?
                """, (email,))
            else:
                cursor.execute("""
                    SELECT id, email, inbound_id, expiry_time, total, enable, up, down, reset
                    FROM client_traffics
                    WHERE id = ?
                """, (user_id,))

            result = cursor.fetchone()
            if not result:
                return False

            user_id, email, inbound_id, expiry_time, total, enable, up, down, reset = result

            # Получаем settings inbound
            cursor.execute("SELECT settings FROM inbounds WHERE id = ?", (inbound_id,))
            settings_result = cursor.fetchone()
            if not settings_result:
                return False

            settings = json.loads(settings_result[0])

            if 'clients' not in settings:
                return False

            # Находим и обновляем клиента в JSON
            client_updated = False
            for client in settings['clients']:
                if client.get('email') == email or client.get('id') == user_id:
                    # Обновляем поля
                    client['expiryTime'] = expiry_time
                    client['totalGB'] = total if total else 0
                    client['enable'] = bool(enable)
                    client['reset'] = reset if reset else 0

                    # Обновляем timestamp
                    client['updated_at'] = int(datetime.now().timestamp() * 1000)

                    client_updated = True
                    break

            if not client_updated:
                logger.warning(f"Client {email} not found in inbound {inbound_id} JSON")
                return False

            # Сохраняем обновленные settings
            cursor.execute("""
                UPDATE inbounds SET settings = ? WHERE id = ?
            """, (json.dumps(settings, ensure_ascii=False), inbound_id))

            return True

        except Exception as e:
            logger.error(f"Error syncing client to JSON: {e}")
            return False

    def _sync_multiple_clients_to_json(self, cursor, user_ids: List[str]) -> int:
        """Синхронизация нескольких клиентов в JSON

        Returns:
            Количество успешно синхронизированных клиентов
        """
        synced = 0
        for user_id in user_ids:
            if self._sync_client_to_json(cursor, user_id):
                synced += 1
        return synced

    # ==================== БЛОКИРОВКА ПОЛЬЗОВАТЕЛЕЙ ====================

    def toggle_user_status(self, user_id: str, enable: bool) -> Dict:
        """Блокировка/разблокировка пользователя"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE client_traffics
                SET enable = ?
                WHERE id = ?
            """, (1 if enable else 0, user_id))

            if cursor.rowcount == 0:
                return {"success": False, "error": "User not found"}

            # Синхронизируем с JSON
            self._sync_client_to_json(cursor, user_id)

            conn.commit()
            conn.close()

            return {"success": True}

        except Exception as e:
            logger.error(f"Error toggling user status: {e}")
            return {"success": False, "error": str(e)}

    def bulk_toggle_users(self, user_ids: List[str], enable: bool) -> Dict:
        """Массовая блокировка/разблокировка пользователей"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            updated = 0
            for user_id in user_ids:
                cursor.execute("""
                    UPDATE client_traffics
                    SET enable = ?
                    WHERE id = ?
                """, (1 if enable else 0, user_id))

                if cursor.rowcount > 0:
                    # Синхронизируем с JSON
                    self._sync_client_to_json(cursor, user_id)
                    updated += 1

            conn.commit()
            conn.close()

            return {"updated": updated}

        except Exception as e:
            logger.error(f"Error in bulk toggle: {e}")
            return {"updated": 0}

    # ==================== УПРАВЛЕНИЕ СРОКОМ ДЕЙСТВИЯ ====================

    def update_user_expiry(self, user_id: str, expiry_time: int) -> Dict:
        """Обновление срока действия пользователя"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE client_traffics
                SET expiry_time = ?
                WHERE id = ?
            """, (expiry_time, user_id))

            if cursor.rowcount == 0:
                return {"success": False, "error": "User not found"}

            # Синхронизируем с JSON
            self._sync_client_to_json(cursor, user_id)

            conn.commit()
            conn.close()

            return {"success": True}

        except Exception as e:
            logger.error(f"Error updating expiry: {e}")
            return {"success": False, "error": str(e)}

    def bulk_extend_expiry(self, user_ids: List[str], days: int) -> Dict:
        """Массовое продление срока действия"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Добавляем дни к текущему времени истечения
            milliseconds = days * 24 * 60 * 60 * 1000
            updated = 0

            for user_id in user_ids:
                # Получаем текущий срок
                cursor.execute("SELECT expiry_time FROM client_traffics WHERE id = ?", (user_id,))
                result = cursor.fetchone()

                if result:
                    current_expiry = result[0] or 0
                    current_time = int(datetime.now().timestamp() * 1000)

                    # Если срок уже истек или не установлен, отсчитываем от текущего времени
                    if current_expiry == 0 or current_expiry < current_time:
                        new_expiry = current_time + milliseconds
                    else:
                        new_expiry = current_expiry + milliseconds

                    cursor.execute("""
                        UPDATE client_traffics
                        SET expiry_time = ?
                        WHERE id = ?
                    """, (new_expiry, user_id))

                    if cursor.rowcount > 0:
                        # Синхронизируем с JSON
                        self._sync_client_to_json(cursor, user_id)
                        updated += 1

            conn.commit()
            conn.close()

            return {"updated": updated}

        except Exception as e:
            logger.error(f"Error extending expiry: {e}")
            return {"updated": 0}

    # ==================== РАСШИРЕННЫЙ ПОИСК И УДАЛЕНИЕ ====================

    def get_expired_users(self, inbound_id: Optional[int] = None) -> List[Dict]:
        """Получение пользователей с истекшим сроком действия"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            current_time = int(datetime.now().timestamp() * 1000)

            query = """
                SELECT
                    id, email, inbound_id,
                    expiry_time, total, up, down, enable
                FROM client_traffics
                WHERE expiry_time > 0 AND expiry_time < ?
            """
            params = [current_time]

            if inbound_id:
                query += " AND inbound_id = ?"
                params.append(inbound_id)

            query += " ORDER BY expiry_time ASC"

            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            users = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()

            logger.info(f"Found {len(users)} expired users")
            return users

        except Exception as e:
            logger.error(f"Error getting expired users: {e}", exc_info=True)
            return []

    def get_disabled_users(self, inbound_id: Optional[int] = None) -> List[Dict]:
        """Получение отключенных пользователей (enable = 0 или false)"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    id, email, inbound_id,
                    expiry_time, total, up, down, enable
                FROM client_traffics
                WHERE enable = 0 OR enable = 'false'
            """
            params = []

            if inbound_id:
                query += " AND inbound_id = ?"
                params.append(inbound_id)

            query += " ORDER BY email ASC"

            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            users = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()

            logger.info(f"Found {len(users)} disabled users")
            return users

        except Exception as e:
            logger.error(f"Error getting disabled users: {e}", exc_info=True)
            return []

    def bulk_delete_users(self, user_ids: List[int]) -> Dict:
        """Массовое удаление пользователей по списку ID

        Args:
            user_ids: Список ID пользователей для удаления

        Returns:
            Dict с количеством удаленных пользователей и ошибками
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            deleted = 0
            errors = []

            for user_id in user_ids:
                try:
                    # Получаем данные пользователя для удаления из settings
                    cursor.execute("""
                        SELECT inbound_id, email FROM client_traffics WHERE id = ?
                    """, (user_id,))
                    result = cursor.fetchone()

                    if not result:
                        errors.append(f"User ID {user_id} not found")
                        continue

                    inbound_id, email = result

                    # Удаляем из client_traffics
                    cursor.execute("DELETE FROM client_traffics WHERE id = ?", (user_id,))

                    # Удаляем из settings inbound'а
                    cursor.execute("SELECT settings FROM inbounds WHERE id = ?", (inbound_id,))
                    inbound_result = cursor.fetchone()

                    if inbound_result:
                        settings = json.loads(inbound_result[0])
                        if 'clients' in settings:
                            settings['clients'] = [
                                c for c in settings['clients']
                                if c.get('email') != email
                            ]

                            cursor.execute("""
                                UPDATE inbounds SET settings = ? WHERE id = ?
                            """, (json.dumps(settings), inbound_id))

                    deleted += 1
                    logger.info(f"Deleted user {email} (ID: {user_id}) from inbound {inbound_id}")

                except Exception as e:
                    error_msg = f"Failed to delete user ID {user_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            conn.commit()

            # Обновляем конфигурацию x-ui один раз после всех удалений
            if deleted > 0:
                logger.info(f"Updating x-ui config after deleting {deleted} users")
                self._update_xui_config()

            conn.close()

            return {
                "success": True,
                "deleted": deleted,
                "errors": errors[:10] if errors else []
            }

        except Exception as e:
            logger.error(f"Error in bulk delete: {e}", exc_info=True)
            return {
                "success": False,
                "deleted": 0,
                "errors": [str(e)]
            }

    def get_truly_online_users_count(self) -> int:
        """Получение реального количества онлайн пользователей

        Пользователь считается онлайн если last_online обновлялся в последние 2 минуты
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Проверяем есть ли колонка last_online
            available_columns = self._get_table_columns('client_traffics')

            if 'last_online' not in available_columns:
                logger.warning("Column 'last_online' not found in client_traffics")
                return 0

            # 2 минуты назад в миллисекундах
            two_minutes_ago = int((datetime.now().timestamp() - 120) * 1000)

            cursor.execute("""
                SELECT COUNT(*) FROM client_traffics
                WHERE enable = 1
                AND last_online > ?
            """, (two_minutes_ago,))

            count = cursor.fetchone()[0]
            conn.close()

            return count

        except Exception as e:
            logger.error(f"Error getting online users count: {e}", exc_info=True)
            return 0

    def bulk_create_users_all_inbounds(self, template: Dict, count: int,
                                      inbound_ids: List[int]) -> Dict:
        """Массовое создание пользователей сразу во всех указанных inbound'ах

        Создает одного пользователя сразу во всех inbound'ах с одинаковым email
        Например: user_0001 будет создан во всех inbound'ах

        Args:
            template: Шаблон пользователя (prefix, total, expiry_time, etc)
            count: Количество пользователей для создания
            inbound_ids: Список ID inbound'ов

        Returns:
            Dict с результатами создания
        """
        try:
            created_total = 0
            users_created = []
            errors = []
            batch_size = 20  # Обновляем x-ui каждые 20 пользователей

            logger.info(f"Starting multi-inbound bulk create: {count} users across {len(inbound_ids)} inbounds")

            for i in range(count):
                email = f"{template.get('prefix', 'user')}_{i+1:04d}"

                # Создаем пользователя с этим email во всех inbound'ах
                for inbound_id in inbound_ids:
                    user_data = template.copy()
                    user_data['inbound_id'] = inbound_id
                    user_data['email'] = email

                    result = self.create_user(user_data)

                    if result["success"]:
                        created_total += 1
                        users_created.append({
                            "email": email,
                            "inbound_id": inbound_id,
                            "user_id": result["user"]["id"]
                        })
                    else:
                        error_msg = f"{email} (inbound {inbound_id}): {result.get('error', 'Unknown error')}"
                        errors.append(error_msg)
                        logger.error(f"Failed to create: {error_msg}")

                # Обновляем x-ui каждые batch_size пользователей (на всех inbounds)
                if (i + 1) % batch_size == 0 and created_total > 0:
                    logger.info(f"Updating x-ui config after {i + 1} users")
                    self._update_xui_config()

            # Финальное обновление x-ui если остались пользователи
            if created_total > 0:
                logger.info(f"Final x-ui update after creating {created_total} total entries")
                self._update_xui_config()

            logger.info(f"Multi-inbound create completed: {created_total} entries created ({count} users x {len(inbound_ids)} inbounds)")

            return {
                "success": True,
                "created": created_total,
                "users": users_created,
                "total_users": count,
                "inbounds_count": len(inbound_ids),
                "errors": errors[:20] if errors else []
            }

        except Exception as e:
            logger.error(f"Error in multi-inbound bulk create: {e}", exc_info=True)
            return {
                "success": False,
                "created": 0,
                "users": [],
                "errors": [str(e)]
            }