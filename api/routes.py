"""
Модуль маршрутов API
====================

Определяет REST API эндпоинты для видеозаписи с валидацией через Pydantic.
"""

from datetime import datetime

from flask import jsonify, request
from pydantic import ValidationError

from api.schemas import (
    CreateScheduleRequest,
    StartRecordingRequest,
    ToggleScheduleRequest,
    UpdateConfigRequest,
    UpdateScheduleRequest,
)
from logger_config import get_module_logger

logger = get_module_logger(__name__)


def handle_validation_error(error: ValidationError) -> tuple:
    """
    Обработка ошибки валидации Pydantic.
    
    Args:
        error: Ошибка валидации Pydantic
        
    Returns:
        Кортеж (JSON ответ, HTTP код)
    """
    errors = []
    for err in error.errors():
        field = '.'.join(str(loc) for loc in err['loc'])
        errors.append({
            'field': field,
            'message': err['msg'],
            'type': err['type']
        })

    return jsonify({
        'success': False,
        'error': 'Ошибка валидации данных',
        'validation_errors': errors
    }), 400


def register_routes(app, server) -> None:
    """
    Регистрация всех маршрутов API с Flask приложением.
    
    Args:
        app: Экземпляр Flask приложения
        server: Экземпляр APIServer для обратных вызовов
    """

    @app.route('/api/status', methods=['GET'])
    def get_status():
        """
        Получение текущего статуса записи.
        
        Returns:
            JSON с информацией о статусе записи
        """
        try:
            callback = server.get_callback('status')
            if callback:
                status = callback()
                return jsonify({
                    'success': True,
                    'data': status
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов статуса не установлен'
            }), 500
        except Exception as e:
            logger.error(f"Ошибка получения статуса: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/start', methods=['POST'])
    def start_recording():
        """
        Начало новой записи.
        
        Тело запроса (JSON):
            - area: "full" | "window" | "rect"
            - window_title: str (опционально, для режима окна)
            - rect: [x1, y1, x2, y2] (опционально, для режима прямоугольника)
            - audio: "mic" | "system" | "none" | "both"
            - output_path: str (опционально)
            - fps: int (опционально, 1-120)
            - codec: str (опционально)
            - bitrate: str (опционально, формат: 2M, 5000K)
            - duration: int (опционально, секунды)
            
        Returns:
            JSON с ID записи или ошибкой
        """
        try:
            data = request.get_json() or {}

            # Валидация входных данных
            try:
                validated = StartRecordingRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            # Преобразование в словарь для обратного вызова
            callback_data = validated.model_dump(exclude_none=True)

            callback = server.get_callback('start')
            if callback:
                result = callback(callback_data)
                if result.get('success'):
                    return jsonify({
                        'success': True,
                        'data': result
                    })
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Не удалось начать запись')
                }), 400

            return jsonify({
                'success': False,
                'error': 'Обратный вызов запуска не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка начала записи: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/stop', methods=['POST'])
    def stop_recording():
        """
        Остановка текущей записи.
        
        Returns:
            JSON с результатом
        """
        try:
            callback = server.get_callback('stop')
            if callback:
                result = callback()
                return jsonify({
                    'success': result.get('success', True),
                    'data': result
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов остановки не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка остановки записи: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pause', methods=['POST'])
    def pause_recording():
        """
        Пауза или возобновление текущей записи.
        
        Returns:
            JSON с новым состоянием паузы
        """
        try:
            callback = server.get_callback('pause')
            if callback:
                result = callback()
                return jsonify({
                    'success': True,
                    'data': result
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов паузы не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка паузы записи: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/recordings', methods=['GET'])
    def get_recordings():
        """
        Получение списка недавних записей.
        
        Returns:
            JSON со списком записей
        """
        try:
            callback = server.get_callback('recordings')
            if callback:
                recordings = callback()
                return jsonify({
                    'success': True,
                    'data': recordings
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов записей не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка получения записей: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/schedule', methods=['GET'])
    def get_schedule():
        """
        Получение списка запланированных задач.
        
        Returns:
            JSON со списком задач
        """
        try:
            callback = server.get_callback('get_schedule')
            if callback:
                tasks = callback()
                return jsonify({
                    'success': True,
                    'data': tasks
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов расписания не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка получения расписания: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/schedule', methods=['POST'])
    def create_schedule():
        """
        Создание новой запланированной задачи.
        
        Тело запроса (JSON):
            - name: str (название задачи)
            - trigger: "once" | "daily" | "weekly" | "interval"
            - datetime: str (формат ISO, для once)
            - time: str "HH:MM" (для daily/weekly)
            - day_of_week: str "0,1,2,3,4" (для weekly, 0=Понедельник)
            - hours: int (для interval)
            - minutes: int (для interval)
            - params: { параметры записи }
            
        Returns:
            JSON с ID задачи
        """
        try:
            data = request.get_json() or {}

            # Валидация входных данных
            try:
                validated = CreateScheduleRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            # Преобразование в словарь для обратного вызова
            callback_data = validated.model_dump(exclude_none=True)

            # Преобразование params если есть
            if validated.params:
                callback_data['params'] = validated.params.model_dump(exclude_none=True)

            callback = server.get_callback('create_schedule')
            if callback:
                result = callback(callback_data)
                if result.get('success'):
                    return jsonify({
                        'success': True,
                        'data': result
                    })
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Не удалось создать задачу')
                }), 400

            return jsonify({
                'success': False,
                'error': 'Обратный вызов создания расписания не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка создания расписания: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/schedule/<task_id>', methods=['DELETE'])
    def delete_schedule(task_id: str):
        """
        Удаление запланированной задачи.
        
        Args:
            task_id: ID задачи для удаления
            
        Returns:
            JSON с результатом
        """
        try:
            callback = server.get_callback('delete_schedule')
            if callback:
                result = callback(task_id)
                return jsonify({
                    'success': result.get('success', True),
                    'data': result
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов удаления расписания не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка удаления расписания: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/schedule/<task_id>', methods=['PUT'])
    def update_schedule(task_id: str):
        """
        Обновление запланированной задачи.
        
        Args:
            task_id: ID задачи для обновления
            
        Тело запроса (JSON):
            Поля задачи для обновления
            
        Returns:
            JSON с результатом
        """
        try:
            data = request.get_json() or {}
            data['id'] = task_id

            # Валидация входных данных
            try:
                validated = UpdateScheduleRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            callback_data = validated.model_dump(exclude_none=True)

            callback = server.get_callback('update_schedule')
            if callback:
                result = callback(callback_data)
                return jsonify({
                    'success': result.get('success', True),
                    'data': result
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов обновления расписания не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка обновления расписания: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/schedule/<task_id>/toggle', methods=['POST'])
    def toggle_schedule(task_id: str):
        """
        Включение или отключение запланированной задачи.
        
        Args:
            task_id: ID задачи для переключения
            
        Тело запроса (JSON):
            - enabled: bool
            
        Returns:
            JSON с новым состоянием включения
        """
        try:
            data = request.get_json() or {}

            # Валидация входных данных
            try:
                validated = ToggleScheduleRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            callback = server.get_callback('toggle_schedule')
            if callback:
                result = callback(task_id, validated.enabled)
                return jsonify({
                    'success': True,
                    'data': result
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов переключения расписания не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка переключения расписания: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/devices', methods=['GET'])
    def get_devices():
        """
        Получение доступных аудиоустройств.
        
        Returns:
            JSON со списком устройств ввода/вывода
        """
        try:
            callback = server.get_callback('devices')
            if callback:
                devices = callback()
                return jsonify({
                    'success': True,
                    'data': devices
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов устройств не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка получения устройств: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/windows', methods=['GET'])
    def get_windows():
        """
        Получение доступных окон для захвата.
        
        Returns:
            JSON со списком окон
        """
        try:
            callback = server.get_callback('windows')
            if callback:
                windows = callback()
                return jsonify({
                    'success': True,
                    'data': windows
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов окон не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка получения окон: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/config', methods=['GET'])
    def get_config():
        """
        Получение текущей конфигурации.
        
        Returns:
            JSON с конфигурацией
        """
        try:
            callback = server.get_callback('get_config')
            if callback:
                config = callback()
                return jsonify({
                    'success': True,
                    'data': config
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов конфигурации не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка получения конфигурации: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/config', methods=['PUT'])
    def update_config():
        """
        Обновление конфигурации.
        
        Тело запроса (JSON):
            Поля конфигурации для обновления
            
        Returns:
            JSON с результатом
        """
        try:
            data = request.get_json() or {}

            # Валидация входных данных
            try:
                validated = UpdateConfigRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            callback_data = validated.model_dump(exclude_none=True)

            callback = server.get_callback('update_config')
            if callback:
                result = callback(callback_data)
                return jsonify({
                    'success': True,
                    'data': result
                })
            return jsonify({
                'success': False,
                'error': 'Обратный вызов обновления конфигурации не установлен'
            }), 500

        except Exception as e:
            logger.error(f"Ошибка обновления конфигурации: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/health', methods=['GET'])
    def health_check():
        """Эндпоинт проверки здоровья."""
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat()
        })

    logger.info("Маршруты API зарегистрированы")
