"""
Интеграционные тесты для API
============================

Тестирует REST API эндпоинты с реальным Flask сервером.
"""

from datetime import datetime, timedelta
from typing import Dict
from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient

from api.routes import register_routes
from api.server import APIServer


@pytest.fixture
def mock_callbacks() -> Dict[str, MagicMock]:
    """
    Создание mock функций обратного вызова.
    
    Returns:
        Словарь с mock функциями для каждого действия
    """
    return {
        'status': MagicMock(return_value={
            'is_recording': False,
            'is_paused': False,
            'elapsed_time': 0,
            'current_file': None
        }),
        'start': MagicMock(return_value={
            'success': True,
            'output_path': '/tmp/test_recording.mp4'
        }),
        'stop': MagicMock(return_value={
            'success': True,
            'output_path': '/tmp/test_recording.mp4',
            'duration': 10.5
        }),
        'pause': MagicMock(return_value={
            'success': True,
            'is_paused': True
        }),
        'resume': MagicMock(return_value={
            'success': True,
            'is_paused': False
        }),
        'recordings': MagicMock(return_value={
            'recordings': [
                {
                    'path': '/tmp/recording1.mp4',
                    'date': '2026-03-18T10:00:00',
                    'size': 1024000
                }
            ]
        }),
        # Исправленные имена callbacks в соответствии с api/routes.py
        'get_schedule': MagicMock(return_value={
            'tasks': []
        }),
        'create_schedule': MagicMock(return_value={
            'success': True,
            'task_id': 'test-task-001'
        }),
        'delete_schedule': MagicMock(return_value={
            'success': True
        }),
        'update_schedule': MagicMock(return_value={
            'success': True
        }),
        'toggle_schedule': MagicMock(return_value={
            'success': True
        }),
        'devices': MagicMock(return_value={
            'input': [
                {'index': 0, 'name': 'Microphone'},
                {'index': 1, 'name': 'Headset'}
            ],
            'output': [
                {'index': 0, 'name': 'Speakers'}
            ]
        }),
        'windows': MagicMock(return_value={
            'windows': [
                {'title': 'Browser', 'x': 0, 'y': 0, 'width': 1920, 'height': 1080}
            ]
        }),
        'get_config': MagicMock(return_value={
            'video': {'fps': 30, 'codec': 'libx264'},
            'audio': {'sample_rate': 44100}
        }),
        'update_config': MagicMock(return_value={
            'success': True
        }),
    }


@pytest.fixture
def test_app(mock_callbacks: Dict[str, MagicMock]) -> Flask:
    """
    Создание тестового Flask приложения.

    Args:
        mock_callbacks: Словарь с mock функциями
        
    Returns:
        Настроенное Flask приложение
    """
    server = APIServer(host='127.0.0.1', port=5001)
    
    # Установка mock callbacks
    for action, callback in mock_callbacks.items():
        server.set_callback(action, callback)
    
    # Регистрация маршрутов
    register_routes(server.app, server)
    
    server.app.config['TESTING'] = True
    
    return server.app


@pytest.fixture
def client(test_app: Flask) -> FlaskClient:
    """
    Создание тестового клиента.
    
    Args:
        test_app: Flask приложение
        
    Returns:
        Тестовый клиент
    """
    return test_app.test_client()


class TestAPIStatusEndpoint:
    """Тесты для эндпоинта /api/status."""

    def test_get_status_success(self, client: FlaskClient, mock_callbacks: Dict[str, MagicMock]):
        """Проверка успешного получения статуса."""
        response = client.get('/api/status')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'is_recording' in data['data']
        mock_callbacks['status'].assert_called_once()

    def test_get_status_recording(self, client: FlaskClient, mock_callbacks: Dict[str, MagicMock]):
        """Проверка статуса во время записи."""
        mock_callbacks['status'].return_value = {
            'is_recording': True,
            'is_paused': False,
            'elapsed_time': 45.2,
            'current_file': '/tmp/recording.mp4'
        }
        
        response = client.get('/api/status')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['is_recording'] is True
        assert data['data']['elapsed_time'] == 45.2


class TestAPIStartEndpoint:
    """Тесты для эндпоинта /api/start."""

    def test_start_recording_default_params(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка запуска записи с параметрами по умолчанию."""
        response = client.post(
            '/api/start',
            json={},
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_callbacks['start'].assert_called_once()

    def test_start_recording_with_params(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка запуска записи с пользовательскими параметрами."""
        request_data = {
            'area': 'rect',
            'rect': [100, 100, 800, 600],
            'audio': 'mic',
            'fps': 60,
            'codec': 'libx264',
            'bitrate': '5M',
            'duration': 300
        }
        
        response = client.post(
            '/api/start',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Проверка переданных параметров
        call_args = mock_callbacks['start'].call_args[0][0]
        assert call_args['area'] == 'rect'
        assert call_args['fps'] == 60

    def test_start_recording_invalid_fps(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка валидации некорректного FPS."""
        request_data = {
            'fps': 150  # Превышает максимум 120
        }
        
        response = client.post(
            '/api/start',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'validation_errors' in data

    def test_start_recording_invalid_area(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка валидации некорректной области."""
        request_data = {
            'area': 'window'  # Требуется window_title
        }
        
        response = client.post(
            '/api/start',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_start_recording_invalid_rect(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка валидации некорректных координат прямоугольника."""
        request_data = {
            'area': 'rect',
            'rect': [100, 100, 50, 200]  # x2 < x1
        }
        
        response = client.post(
            '/api/start',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_start_recording_invalid_bitrate(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка валидации некорректного битрейта."""
        request_data = {
            'bitrate': 'invalid'
        }
        
        response = client.post(
            '/api/start',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False


class TestAPIStopEndpoint:
    """Тесты для эндпоинта /api/stop."""

    def test_stop_recording_success(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка успешной остановки записи."""
        response = client.post('/api/stop')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_callbacks['stop'].assert_called_once()

    def test_stop_recording_not_recording(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка остановки когда запись не активна."""
        # Примечание: API возвращает 200 даже при неудаче, проверяем success=False
        mock_callbacks['stop'].return_value = {
            'success': False,
            'error': 'Нет активной записи'
        }
        
        response = client.post('/api/stop')
        
        # API возвращает 200 с success=False в данных
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False


class TestAPIPauseEndpoint:
    """Тесты для эндпоинта /api/pause."""

    def test_pause_recording_success(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка успешной паузы записи."""
        response = client.post('/api/pause')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_callbacks['pause'].assert_called_once()


class TestAPIRecordingsEndpoint:
    """Тесты для эндпоинта /api/recordings."""

    def test_get_recordings_success(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка получения списка записей."""
        response = client.get('/api/recordings')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        mock_callbacks['recordings'].assert_called_once()

    def test_get_recordings_empty(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка пустого списка записей."""
        mock_callbacks['recordings'].return_value = {'recordings': []}
        
        response = client.get('/api/recordings')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['recordings'] == []


class TestAPIScheduleEndpoints:
    """Тесты для эндпоинтов планировщика."""

    def test_get_schedule_list(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка получения списка задач."""
        response = client.get('/api/schedule')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_callbacks['get_schedule'].assert_called_once()

    def test_create_schedule_task_once(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка создания разовой задачи."""
        # Используем будущую дату (через 1 час от текущего времени)
        future_datetime = (datetime.now() + timedelta(hours=1)).isoformat()
        
        request_data = {
            'name': 'Test Once Task',
            'trigger': 'once',
            'datetime': future_datetime,
            'params': {
                'area': 'full',
                'fps': 30
            }
        }
        
        response = client.post(
            '/api/schedule',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_callbacks['create_schedule'].assert_called_once()

    def test_create_schedule_task_daily(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка создания ежедневной задачи."""
        request_data = {
            'name': 'Test Daily Task',
            'trigger': 'daily',
            'time': '09:00',
            'params': {
                'area_type': 'window',
                'window_title': 'Browser'
            }
        }
        
        response = client.post(
            '/api/schedule',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_create_schedule_task_weekly(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка создания еженедельной задачи."""
        request_data = {
            'name': 'Test Weekly Task',
            'trigger': 'weekly',
            'time': '10:00',
            'day_of_week': '0,2,4',
            'params': {}
        }
        
        response = client.post(
            '/api/schedule',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_create_schedule_task_interval(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка создания интервальной задачи."""
        request_data = {
            'name': 'Test Interval Task',
            'trigger': 'interval',
            'hours': 2,
            'minutes': 30,
            'params': {}
        }
        
        response = client.post(
            '/api/schedule',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_delete_schedule_task(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка удаления задачи."""
        response = client.delete('/api/schedule/test-task-001')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_callbacks['delete_schedule'].assert_called_once()

    def test_toggle_schedule_task(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка переключения активности задачи."""
        request_data = {
            'enabled': False
        }
        
        response = client.post(
            '/api/schedule/test-task-001/toggle',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True


class TestAPIDevicesEndpoint:
    """Тесты для эндпоинта /api/devices."""

    def test_get_devices_success(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка получения списка устройств."""
        response = client.get('/api/devices')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'input' in data['data']
        assert 'output' in data['data']
        mock_callbacks['devices'].assert_called_once()


class TestAPIWindowsEndpoint:
    """Тесты для эндпоинта /api/windows."""

    def test_get_windows_success(
        self, 
        client: FlaskClient, 
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка получения списка окон."""
        response = client.get('/api/windows')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'windows' in data['data']
        mock_callbacks['windows'].assert_called_once()


class TestAPIConfigEndpoint:
    """Тесты для эндпоинтов конфигурации."""

    def test_get_config_success(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка получения конфигурации."""
        response = client.get('/api/config')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_callbacks['get_config'].assert_called_once()

    def test_update_config_success(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка обновления конфигурации."""
        request_data = {
            'video': {
                'fps': 60
            }
        }
        
        response = client.put(
            '/api/config',
            json=request_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_callbacks['update_config'].assert_called_once()


class TestAPIErrorHandling:
    """Тесты обработки ошибок API."""

    def test_404_error(self, client: FlaskClient):
        """Проверка обработки 404 ошибки."""
        response = client.get('/api/nonexistent')
        
        assert response.status_code == 404

    def test_invalid_json(self, client: FlaskClient):
        """Проверка обработки некорректного JSON."""
        # Flask возвращает 500 при ошибке парсинга JSON
        response = client.post(
            '/api/start',
            data='invalid json',
            content_type='application/json'
        )
        
        # API возвращает 500 при ошибке парсинга JSON
        assert response.status_code == 500

    def test_callback_returns_error(
        self,
        client: FlaskClient,
        mock_callbacks: Dict[str, MagicMock]
    ):
        """Проверка обработки ошибки от callback."""
        mock_callbacks['start'].return_value = {
            'success': False,
            'error': 'Ошибка запуска записи'
        }
        
        response = client.post(
            '/api/start',
            json={},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False


class TestAPIServerIntegration:
    """Интеграционные тесты APIServer."""

    def test_server_creation(self):
        """Проверка создания сервера."""
        server = APIServer(host='127.0.0.1', port=5002)
        
        assert server.host == '127.0.0.1'
        assert server.port == 5002
        assert server.app is not None

    def test_set_and_get_callback(self):
        """Проверка установки и получения callback."""
        server = APIServer(host='127.0.0.1', port=5003)
        
        def test_callback():
            return {'status': 'ok'}
        
        server.set_callback('test', test_callback)
        
        assert server.get_callback('test') == test_callback
        assert server.get_callback('nonexistent') is None

    def test_multiple_callbacks(self):
        """Проверка установки нескольких callbacks."""
        server = APIServer(host='127.0.0.1', port=5004)
        
        callbacks = {
            'start': lambda: {'started': True},
            'stop': lambda: {'stopped': True},
            'status': lambda: {'recording': False}
        }
        
        for action, callback in callbacks.items():
            server.set_callback(action, callback)
        
        for action, callback in callbacks.items():
            assert server.get_callback(action) == callback
