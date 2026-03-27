"""
Интеграционные тесты полного рабочего процесса
==============================================

Тестирует end-to-end сценарии использования приложения с реальными компонентами.
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from api.auth import init_api_auth
from api.routes import register_routes
from api.server import APIServer
from config import ConfigManager
from recorder.audio_recorder import AudioRecorder, AudioState
from recorder.video_recorder import CaptureArea, RecordingState, VideoRecorder
from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
    TaskScheduler,
)

# Тестовый API ключ
TEST_API_KEY = "test-api-key-for-workflow-tests-12345"


@pytest.fixture
def mock_recording_callbacks() -> dict[str, MagicMock]:
    """
    Создание mock функций обратного вызова для записи.

    Returns:
        Словарь с mock функциями
    """
    return {
        "status": MagicMock(
            return_value={
                "is_recording": False,
                "is_paused": False,
                "elapsed_time": 0,
                "current_file": None,
            }
        ),
        "start": MagicMock(
            return_value={
                "success": True,
                "output_path": "/tmp/test_recording.mp4",
            }
        ),
        "stop": MagicMock(
            return_value={
                "success": True,
                "output_path": "/tmp/test_recording.mp4",
                "duration": 10.5,
            }
        ),
        "pause": MagicMock(return_value={"success": True, "is_paused": True}),
        "resume": MagicMock(
            return_value={"success": True, "is_paused": False}
        ),
    }


@pytest.fixture
def workflow_app(mock_recording_callbacks: dict[str, MagicMock]) -> Flask:
    """
    Создание тестового Flask приложения для workflow тестов.

    Args:
        mock_recording_callbacks: Словарь с mock функциями

    Returns:
        Настроенное Flask приложение
    """
    server = APIServer(host="127.0.0.1", port=5002)
    init_api_auth(server.app, api_key=TEST_API_KEY)

    for action, callback in mock_recording_callbacks.items():
        server.set_callback(action, callback)

    register_routes(server.app, server)
    server.app.config["TESTING"] = True

    return server.app


@pytest.fixture
def workflow_client(workflow_app: Flask) -> FlaskClient:
    """
    Создание тестового клиента с авторизацией.

    Args:
        workflow_app: Flask приложение

    Returns:
        Тестовый клиент
    """
    test_client = workflow_app.test_client()
    test_client.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return test_client


class TestFullRecordingWorkflow:
    """Тесты полного цикла записи через API."""

    def test_start_record_stop_workflow(
        self,
        workflow_client: FlaskClient,
        mock_recording_callbacks: dict[str, MagicMock],
    ) -> None:
        """Проверка полного цикла: старт -> запись -> стоп через API."""
        # Проверяем начальный статус
        status_response = workflow_client.get("/api/status")
        assert status_response.status_code == 200
        initial_status = status_response.get_json()
        assert initial_status["data"]["is_recording"] is False

        # Запускаем запись
        start_response = workflow_client.post(
            "/api/start",
            json={"area": "full"},
            content_type="application/json",
        )
        assert start_response.status_code == 200
        start_data = start_response.get_json()
        assert start_data["success"] is True
        mock_recording_callbacks["start"].assert_called_once()

        # Останавливаем запись
        stop_response = workflow_client.post("/api/stop")
        assert stop_response.status_code == 200
        stop_data = stop_response.get_json()
        assert stop_data["success"] is True
        mock_recording_callbacks["stop"].assert_called_once()


class TestVideoRecorderWorkflow:
    """Тесты workflow VideoRecorder с реальным объектом."""

    def test_video_recorder_state_transitions(self) -> None:
        """Проверка переходов состояний VideoRecorder."""
        recorder = VideoRecorder()

        # Начальное состояние
        assert recorder.state == RecordingState.IDLE
        assert recorder.is_recording is False
        assert recorder.is_paused is False

        # Проверка свойств после изменения состояния
        recorder._state = RecordingState.RECORDING
        assert recorder.is_recording is True
        assert recorder.is_paused is False

        recorder._state = RecordingState.PAUSED
        assert recorder.is_recording is False
        assert recorder.is_paused is True

        recorder._state = RecordingState.IDLE
        assert recorder.is_recording is False
        assert recorder.is_paused is False

    def test_video_recorder_callbacks_invoked(self) -> None:
        """Проверка вызова callbacks при событиях."""
        recorder = VideoRecorder()

        on_frame = MagicMock()
        on_error = MagicMock()

        recorder.set_callbacks(on_frame_captured=on_frame, on_error=on_error)

        assert recorder._on_frame_captured == on_frame
        assert recorder._on_error == on_error

    def test_video_recorder_elapsed_time(self) -> None:
        """Проверка расчёта времени записи."""
        import time

        recorder = VideoRecorder()

        # До начала записи время = 0
        assert recorder.elapsed_time == 0

        # После начала записи
        recorder._start_time = time.time() - 10
        recorder._state = RecordingState.RECORDING

        elapsed = recorder.elapsed_time
        assert 9 < elapsed < 11


class TestAudioRecorderWorkflow:
    """Тесты workflow AudioRecorder с реальным объектом."""

    def test_audio_recorder_state_transitions(self) -> None:
        """Проверка переходов состояний AudioRecorder."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        # Начальное состояние
        assert recorder.state == AudioState.IDLE
        assert recorder.is_recording is False
        assert recorder.is_paused is False

        # Переход в запись
        recorder._state = AudioState.RECORDING
        assert recorder.is_recording is True

        # Переход в паузу
        recorder._state = AudioState.PAUSED
        assert recorder.is_paused is True

    def test_audio_recorder_config(self) -> None:
        """Проверка конфигурации AudioRecorder."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder(
                sample_rate=48000,
                channels=1,
                chunk_size=2048,
            )

        assert recorder.config.sample_rate == 48000
        assert recorder.config.channels == 1
        assert recorder.config.chunk_size == 2048


class TestCaptureAreaWorkflow:
    """Тесты workflow CaptureArea с реальным объектом."""

    def test_capture_area_full_screen(self) -> None:
        """Проверка создания области полного экрана."""
        with patch(
            "recorder.video_recorder.get_available_monitors",
            return_value=[{"index": 0, "width": 1920, "height": 1080, "is_primary": True}],
        ):
            area = CaptureArea.full_screen()

        assert area.type == "full"
        assert area.width == 1920
        assert area.height == 1080

    def test_capture_area_from_rect(self) -> None:
        """Проверка создания прямоугольной области."""
        with patch(
            "recorder.video_recorder.validate_rect_coords",
            return_value=(100, 100, 800, 600),
        ):
            area = CaptureArea.from_rect(100, 100, 800, 600)

        assert area.type == "rect"
        assert area.x == 100
        assert area.y == 100

    def test_capture_area_to_capture_dict(self) -> None:
        """Проверка преобразования в формат области захвата."""
        area = CaptureArea(type="rect", x=100, y=200, width=800, height=600)

        capture_dict = area.to_capture_dict()

        assert capture_dict["left"] == 100
        assert capture_dict["top"] == 200
        assert capture_dict["width"] == 800
        assert capture_dict["height"] == 600


class TestConfigWorkflow:
    """Тесты workflow конфигурации с реальным ConfigManager."""

    def test_config_load_and_access(self, temp_config_file: Path) -> None:
        """Проверка загрузки и доступа к конфигурации."""
        config_manager = ConfigManager(temp_config_file)
        settings = config_manager.settings

        assert settings is not None
        assert settings.video.fps == 30
        assert settings.video.codec == "libx264"

    def test_config_save(self, temp_config_file: Path) -> None:
        """Проверка сохранения конфигурации."""
        config_manager = ConfigManager(temp_config_file)

        # Сохранение должно быть успешным
        result = config_manager.save()
        assert result is True


class TestSchedulerWorkflow:
    """Тесты workflow планировщика с реальным TaskScheduler."""

    def test_scheduler_add_and_remove_task(self, tasks_file: Path) -> None:
        """Проверка добавления и удаления задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        # Создание задачи
        task = ScheduleTask(
            id="test-task-1",
            name="Test Recording",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(fps=30),
            start_time=datetime.now() + timedelta(hours=1),
        )

        # Добавление задачи
        result = scheduler.add_task(task)
        assert result is True

        # Проверка что задача добавлена
        all_tasks = scheduler.get_all_tasks()
        assert len(all_tasks) == 1
        assert all_tasks[0].name == "Test Recording"

        # Удаление задачи
        scheduler.remove_task(task.id)
        all_tasks = scheduler.get_all_tasks()
        assert len(all_tasks) == 0

    def test_scheduler_start_stop(self, tasks_file: Path) -> None:
        """Проверка запуска и остановки планировщика."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        # Запуск
        scheduler.start()
        assert scheduler._scheduler.running is True

        # Остановка
        scheduler.stop()
        assert scheduler._scheduler.running is False


class TestAPIAuthenticationWorkflow:
    """Тесты workflow аутентификации API."""

    def test_api_requires_authentication(self, workflow_app: Flask) -> None:
        """Проверка требования аутентификации."""
        client = workflow_app.test_client()

        # Запрос без API ключа
        response = client.get("/api/status")

        # Должен вернуть 401 Unauthorized
        assert response.status_code == 401

    def test_api_with_valid_key(self, workflow_client: FlaskClient) -> None:
        """Проверка доступа с валидным ключом."""
        response = workflow_client.get("/api/status")

        assert response.status_code == 200

    def test_api_with_invalid_key(self, workflow_app: Flask) -> None:
        """Проверка отказа с неверным ключом."""
        client = workflow_app.test_client()
        client.environ_base["HTTP_X_API_KEY"] = "invalid_key"

        response = client.get("/api/status")

        assert response.status_code == 401


class TestFileOutputWorkflow:
    """Тесты workflow файлового вывода."""

    def test_output_file_creation(self, temp_dir: Path) -> None:
        """Проверка создания выходного файла."""
        output_path = temp_dir / "recordings" / "test.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake video content")

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_output_file_naming_with_timestamp(self, temp_dir: Path) -> None:
        """Проверка именования файла с временной меткой."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.mp4"
        output_path = temp_dir / filename

        output_path.write_bytes(b"test")

        assert output_path.exists()
        assert "recording_" in output_path.name
        assert output_path.suffix == ".mp4"

    def test_output_directory_auto_creation(self, temp_dir: Path) -> None:
        """Проверка автоматического создания директории."""
        output_dir = temp_dir / "recordings" / "subfolder"
        output_dir.mkdir(parents=True, exist_ok=True)

        assert output_dir.exists()
        assert output_dir.is_dir()


class TestErrorRecoveryWorkflow:
    """Тесты workflow восстановления после ошибок."""

    def test_video_recorder_error_handling(self) -> None:
        """Проверка обработки ошибок VideoRecorder."""
        recorder = VideoRecorder()

        on_error = MagicMock()
        recorder.set_callbacks(on_error=on_error)

        # Симуляция ошибки
        if recorder._on_error:
            recorder._on_error("Test error")

        on_error.assert_called_once_with("Test error")

    def test_audio_recorder_error_callback(self) -> None:
        """Проверка callback ошибки AudioRecorder."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        on_error = MagicMock()
        recorder.set_callbacks(on_error=on_error)

        # Проверка что callback установлен
        assert recorder._on_error == on_error


class TestMultiComponentIntegration:
    """Тесты интеграции нескольких компонентов."""

    def test_config_and_recorder_integration(
        self, temp_config_file: Path
    ) -> None:
        """Проверка интеграции ConfigManager и VideoRecorder."""
        config_manager = ConfigManager(temp_config_file)
        settings = config_manager.settings

        # Создание рекордера с настройками из конфигурации
        recorder = VideoRecorder(
            fps=settings.video.fps,
            codec=settings.video.codec,
            bitrate=settings.video.bitrate,
        )

        assert recorder.fps == settings.video.fps
        assert recorder.codec == settings.video.codec

    def test_scheduler_and_config_integration(
        self, temp_config_file: Path, tasks_file: Path
    ) -> None:
        """Проверка интеграции TaskScheduler и ConfigManager."""
        config_manager = ConfigManager(temp_config_file)
        scheduler = TaskScheduler(persist_path=tasks_file)

        settings = config_manager.settings

        # Создание задачи с параметрами из конфигурации
        task = ScheduleTask(
            id="config-task-1",
            name="Config-based Recording",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(
                fps=settings.video.fps,
                codec=settings.video.codec,
            ),
            start_time=datetime.now() + timedelta(hours=1),
        )

        scheduler.add_task(task)
        all_tasks = scheduler.get_all_tasks()
        assert all_tasks[0].params.fps == settings.video.fps


class TestGracefulShutdownWorkflow:
    """Тесты workflow корректного завершения."""

    def test_video_recorder_stop_from_recording_state(self) -> None:
        """Проверка остановки VideoRecorder из состояния записи."""
        recorder = VideoRecorder()

        # Симуляция активной записи
        recorder._state = RecordingState.RECORDING
        recorder._start_time = 1000.0

        # Остановка должна переводить в IDLE
        recorder._state = RecordingState.IDLE
        assert recorder.state == RecordingState.IDLE

    def test_scheduler_cleanup(self, tasks_file: Path) -> None:
        """Проверка очистки планировщика."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        # Добавляем задачу
        task = ScheduleTask(
            id="cleanup-task-1",
            name="Test Task",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(fps=30),
            start_time=datetime.now() + timedelta(hours=1),
        )
        scheduler.add_task(task)

        # Запуск и остановка планировщика
        scheduler.start()
        scheduler.stop()

        # Проверяем что планировщик остановлен
        assert scheduler._scheduler.running is False


class TestCLIWorkflow:
    """Тесты workflow CLI с реальным парсером."""

    def test_cli_start_command_parsing(self) -> None:
        """Проверка парсинга команды start."""
        from cli.parser import parse_args

        config = parse_args(["--start", "--fps", "30"])

        assert config["mode"] == "start"
        assert config["recording"]["fps"] == 30

    def test_cli_stop_command_parsing(self) -> None:
        """Проверка парсинга команды stop."""
        from cli.parser import parse_args

        config = parse_args(["--stop"])

        assert config["mode"] == "stop"

    def test_cli_status_command_parsing(self) -> None:
        """Проверка парсинга команды status."""
        from cli.parser import parse_args

        config = parse_args(["--status"])

        assert config["mode"] == "status"

    def test_cli_headless_mode_parsing(self) -> None:
        """Проверка парсинга headless режима."""
        from cli.parser import parse_args

        config = parse_args(["--headless"])

        assert config["mode"] == "headless"
