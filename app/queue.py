#!/usr/bin/env python3
"""
Модуль управления очередями для массовых операций
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Файл для хранения очередей
QUEUE_FILE = "/opt/xui-manager/queues.json"

class QueueStatus:
    """Статусы очереди"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class QueueManager:
    """Управление очередями массовых операций"""

    def __init__(self):
        self.queues = {}
        self.processing_threads = {}
        self._load_queues()

    def _load_queues(self):
        """Загрузка очередей из файла"""
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, 'r') as f:
                    self.queues = json.load(f)
            except Exception as e:
                logger.error(f"Error loading queues: {e}")
                self.queues = {}

    def _save_queues(self):
        """Сохранение очередей в файл"""
        try:
            os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
            with open(QUEUE_FILE, 'w') as f:
                json.dump(self.queues, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving queues: {e}")

    def create_queue(self, queue_type: str, params: Dict) -> str:
        """Создание новой очереди"""
        import uuid
        queue_id = str(uuid.uuid4())

        self.queues[queue_id] = {
            "id": queue_id,
            "type": queue_type,
            "status": QueueStatus.PENDING,
            "params": params,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "progress": {
                "total": params.get("count", 0),
                "completed": 0,
                "failed": 0,
                "current_batch": 0,
                "total_batches": 0
            },
            "results": [],
            "errors": []
        }

        self._save_queues()
        logger.info(f"Queue created: {queue_id} ({queue_type})")

        return queue_id

    def get_queue(self, queue_id: str) -> Optional[Dict]:
        """Получение информации об очереди"""
        return self.queues.get(queue_id)

    def list_queues(self, status: Optional[str] = None) -> List[Dict]:
        """Получение списка очередей"""
        queues = list(self.queues.values())

        if status:
            queues = [q for q in queues if q["status"] == status]

        # Сортируем по дате создания (новые первые)
        queues.sort(key=lambda x: x["created_at"], reverse=True)

        return queues

    def update_queue_status(self, queue_id: str, status: str):
        """Обновление статуса очереди"""
        if queue_id in self.queues:
            self.queues[queue_id]["status"] = status

            if status == QueueStatus.PROCESSING:
                self.queues[queue_id]["started_at"] = datetime.now().isoformat()
            elif status in [QueueStatus.COMPLETED, QueueStatus.FAILED, QueueStatus.CANCELLED]:
                self.queues[queue_id]["completed_at"] = datetime.now().isoformat()

            self._save_queues()

    def update_queue_progress(self, queue_id: str, completed: int, failed: int, current_batch: int):
        """Обновление прогресса очереди"""
        if queue_id in self.queues:
            self.queues[queue_id]["progress"]["completed"] = completed
            self.queues[queue_id]["progress"]["failed"] = failed
            self.queues[queue_id]["progress"]["current_batch"] = current_batch
            self._save_queues()

    def add_queue_result(self, queue_id: str, result: Dict):
        """Добавление результата в очередь"""
        if queue_id in self.queues:
            self.queues[queue_id]["results"].append(result)
            self._save_queues()

    def add_queue_error(self, queue_id: str, error: str):
        """Добавление ошибки в очередь"""
        if queue_id in self.queues:
            self.queues[queue_id]["errors"].append(error)
            # Ограничиваем количество сохраненных ошибок
            if len(self.queues[queue_id]["errors"]) > 50:
                self.queues[queue_id]["errors"] = self.queues[queue_id]["errors"][-50:]
            self._save_queues()

    def cancel_queue(self, queue_id: str) -> bool:
        """Отмена очереди"""
        if queue_id in self.queues:
            queue = self.queues[queue_id]

            if queue["status"] in [QueueStatus.PENDING, QueueStatus.PROCESSING]:
                self.update_queue_status(queue_id, QueueStatus.CANCELLED)
                logger.info(f"Queue cancelled: {queue_id}")
                return True

        return False

    def delete_queue(self, queue_id: str) -> bool:
        """Удаление очереди"""
        if queue_id in self.queues:
            # Нельзя удалить обрабатываемую очередь
            if self.queues[queue_id]["status"] == QueueStatus.PROCESSING:
                return False

            del self.queues[queue_id]
            self._save_queues()
            logger.info(f"Queue deleted: {queue_id}")
            return True

        return False

    def process_bulk_create_queue(self, queue_id: str, db):
        """Обработка очереди массового создания пользователей"""
        from database import XUIDatabase

        try:
            queue = self.queues[queue_id]

            # Проверяем, не была ли отменена очередь
            if queue["status"] == QueueStatus.CANCELLED:
                return

            self.update_queue_status(queue_id, QueueStatus.PROCESSING)

            params = queue["params"]
            total_count = params["count"]
            batch_size = 100
            total_batches = (total_count + batch_size - 1) // batch_size
            start_index = params.get("start_index", 0)  # Начальный индекс для multi-inbound

            self.queues[queue_id]["progress"]["total_batches"] = total_batches
            self._save_queues()

            completed = 0
            failed = 0

            logger.info(f"Processing queue {queue_id}: {total_count} users in {total_batches} batches (start_index: {start_index})")

            for batch_num in range(total_batches):
                # Проверяем отмену
                if self.queues[queue_id]["status"] == QueueStatus.CANCELLED:
                    logger.info(f"Queue {queue_id} was cancelled")
                    return

                batch_start = batch_num * batch_size
                batch_count = min(batch_size, total_count - batch_start)

                logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({batch_count} users)")

                # Создаем пользователей в батче
                for i in range(batch_count):
                    # Проверяем отмену перед каждым пользователем
                    if self.queues[queue_id]["status"] == QueueStatus.CANCELLED:
                        logger.info(f"Queue {queue_id} was cancelled during batch processing")
                        return

                    user_index = batch_start + i
                    user_data = params["template"].copy()
                    user_data['inbound_id'] = params['inbound_id']
                    # Используем start_index для правильной нумерации в multi-inbound сценариях
                    user_data['email'] = f"{params['template'].get('prefix', 'user')}_{start_index + user_index + 1:04d}"

                    result = db.create_user(user_data)

                    if result["success"]:
                        completed += 1
                    else:
                        failed += 1
                        error_msg = f"{user_data['email']}: {result.get('error', 'Unknown error')}"
                        self.add_queue_error(queue_id, error_msg)

                    # Обновляем прогресс
                    self.update_queue_progress(queue_id, completed, failed, batch_num + 1)

                # Перезапускаем x-ui после каждого батча
                logger.info(f"Restarting x-ui after batch {batch_num + 1}")
                db._update_xui_config()

                # Небольшая пауза между батчами
                time.sleep(2)

            # Финальное обновление
            self.update_queue_status(queue_id, QueueStatus.COMPLETED)
            logger.info(f"Queue {queue_id} completed: {completed} created, {failed} failed")

        except Exception as e:
            logger.error(f"Error processing queue {queue_id}: {e}", exc_info=True)
            self.update_queue_status(queue_id, QueueStatus.FAILED)
            self.add_queue_error(queue_id, str(e))

    def start_queue_processing(self, queue_id: str, db):
        """Запуск обработки очереди в отдельном потоке"""
        if queue_id not in self.queues:
            return False

        queue = self.queues[queue_id]

        if queue["status"] != QueueStatus.PENDING:
            return False

        # Все очереди теперь используют bulk_create метод
        # Multi-inbound разбивается на несколько параллельных bulk очередей
        thread = threading.Thread(
            target=self.process_bulk_create_queue,
            args=(queue_id, db),
            daemon=True
        )
        thread.start()

        self.processing_threads[queue_id] = thread

        return True

# Глобальный экземпляр менеджера очередей
queue_manager = QueueManager()
