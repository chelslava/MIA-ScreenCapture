"""
Модуль аудиозаписи
==================

Обрабатывает захват аудио с микрофона и системного аудио (где поддерживается).
Записывает в WAV файл для последующего объединения с видео.
"""

import queue
import threading
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from logger_config import get_module_logger
from recorder.utils import get_audio_devices, get_platform

logger = get_module_logger(__name__)

_AUDIO_QUEUE_MAX_CHUNKS = 256
_AUDIO_QUEUE_GET_TIMEOUT_SECONDS = 0.1


class AudioState(Enum):
    """Перечисление состояний аудиозаписи."""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"


@dataclass
class AudioConfig:
    """Конфигурация аудиозаписи."""

    sample_rate: int = 44100
    channels: int = 2
    chunk_size: int = 1024
    device_index: int | None = None


class AudioRecorder:
    """
    Класс аудиозаписи для захвата аудио с микрофона.

    Поддерживает запись с микрофонного входа. Захват системного аудио
    зависит от платформы и может потребовать дополнительной настройки.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        channels: int = 2,
        chunk_size: int = 1024,
    ):
        """
        Инициализация аудиозаписи.

        Args:
            sample_rate: Частота дискретизации аудио в Гц
            channels: Количество аудиоканалов (1=моно, 2=стерео)
            chunk_size: Размер чанка аудио для буферизации
        """
        self.config = AudioConfig(
            sample_rate=sample_rate, channels=channels, chunk_size=chunk_size
        )

        # Состояние
        self._state = AudioState.IDLE
        self._lock = threading.Lock()
        self._audio_queue: queue.Queue[tuple[bytes, int] | None] = queue.Queue(
            maxsize=_AUDIO_QUEUE_MAX_CHUNKS
        )
        self._record_thread: threading.Thread | None = None
        self._writer_thread: threading.Thread | None = None
        self._writer_stop_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._dropped_chunks = 0

        # Информация о записи
        self._output_path: Path | None = None
        self._audio_interface = None
        self._audio_stream = None
        self._wave_file: wave.Wave_write | None = None

        # Статистика
        self._start_time: float = 0
        self._paused_time: float = 0
        self._total_paused: float = 0
        self._frames_recorded: int = 0

        # Обратные вызовы
        self._on_error: Callable | None = None
        self._on_chunks_dropped: Callable | None = None

        # Информация о платформе
        self._platform = get_platform()
        self._last_dropped_notification = 0

    @property
    def state(self) -> AudioState:
        """Получение текущего состояния записи."""
        return self._state

    @property
    def is_recording(self) -> bool:
        """Проверка активности записи."""
        return self._state == AudioState.RECORDING

    @property
    def is_paused(self) -> bool:
        """Проверка паузы записи."""
        return self._state == AudioState.PAUSED

    @property
    def elapsed_time(self) -> float:
        """Получение времени записи в секундах."""
        if self._start_time == 0:
            return 0
        elapsed = time.time() - self._start_time - self._total_paused
        if self._state == AudioState.PAUSED:
            elapsed -= time.time() - self._paused_time
        return max(0, elapsed)

    @property
    def output_path(self) -> Path | None:
        """Получение текущего пути вывода."""
        return self._output_path

    @property
    def dropped_chunks(self) -> int:
        """Получение количества пропущенных аудио-чанков."""
        return self._dropped_chunks

    def set_callbacks(
        self,
        on_error: Callable | None = None,
        on_chunks_dropped: Callable | None = None,
    ) -> None:
        """
        Установка функций обратного вызова.

        Args:
            on_error: Вызывается при ошибке (получает сообщение об ошибке)
            on_chunks_dropped: Вызывается при потере аудио-чанков
                (получает количество потерянных чанков)
        """
        self._on_error = on_error
        self._on_chunks_dropped = on_chunks_dropped

    @staticmethod
    def get_available_devices() -> list[dict[str, Any]]:
        """
        Получение списка доступных устройств ввода аудио.

        Returns:
            Список словарей с информацией об устройствах
        """
        devices = get_audio_devices()
        return devices.get("input", [])

    def start(
        self,
        output_path: Path,
        device_index: int | None = None,
        duration: float | None = None,
    ) -> bool:
        """
        Начало аудиозаписи.

        Args:
            output_path: Путь для сохранения аудиофайла (формат WAV)
            device_index: Опциональный индекс аудиоустройства
            duration: Опциональная длительность записи в секундах

        Returns:
            True если запись успешно началась
        """
        with self._lock:
            if self._state != AudioState.IDLE:
                logger.warning(
                    f"Невозможно начать: текущее состояние {self._state}"
                )
                return False

            try:
                self._output_path = Path(output_path)
                self._duration = duration
                self.config.device_index = device_index

                # Убедиться, что директория вывода существует
                self._output_path.parent.mkdir(parents=True, exist_ok=True)

                # Инициализация аудио
                self._init_audio()

                # Создание WAV файла
                self._wave_file = wave.open(str(self._output_path), "wb")
                self._wave_file.setnchannels(self.config.channels)
                self._wave_file.setsampwidth(2)  # 16-бит
                self._wave_file.setframerate(self.config.sample_rate)

                # Сброс статистики
                self._start_time = time.time()
                self._paused_time = 0
                self._total_paused = 0
                self._frames_recorded = 0
                self._dropped_chunks = 0
                self._reset_audio_queue()
                self._writer_stop_event.clear()
                self._shutdown_event.clear()

                # Запуск потока записи
                self._state = AudioState.RECORDING
                self._writer_thread = threading.Thread(
                    target=self._writer_loop, daemon=False
                )
                self._writer_thread.start()
                self._record_thread = threading.Thread(
                    target=self._record_loop, daemon=False
                )
                self._record_thread.start()

                logger.info(f"Аудиозапись начата: {output_path}")
                return True

            except Exception as e:
                logger.error(f"Не удалось начать аудиозапись: {e}")
                self._cleanup()
                if self._on_error:
                    self._on_error(str(e))
                return False

    def _init_audio(self) -> None:
        """Инициализация аудиоинтерфейса и потока."""
        try:
            import sounddevice as sd

            # Получение информации об устройстве
            if self.config.device_index is not None:
                device_info = sd.query_devices(self.config.device_index)
            else:
                device_info = sd.query_devices(kind="input")

            logger.info(f"Используется аудиоустройство: {device_info['name']}")

            # Корректировка каналов при необходимости
            max_channels = device_info.get("max_input_channels", 2)
            if self.config.channels > max_channels:
                self.config.channels = max_channels

        except ImportError:
            # Возврат к pyaudio
            self._init_pyaudio()

    def _init_pyaudio(self) -> None:
        """Инициализация PyAudio как запасного варианта."""
        try:
            import pyaudio

            self._audio_interface = pyaudio.PyAudio()

            # Открытие потока
            self._audio_stream = self._audio_interface.open(  # type: ignore[attr-defined]
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                input_device_index=self.config.device_index,
                frames_per_buffer=self.config.chunk_size,
            )

        except ImportError:
            raise RuntimeError("Ни sounddevice, ни pyaudio недоступны")

    def pause(self) -> bool:
        """
        Пауза записи.

        Returns:
            True если пауза успешно установлена
        """
        with self._lock:
            if self._state != AudioState.RECORDING:
                return False

            self._state = AudioState.PAUSED
            self._paused_time = time.time()
            logger.info("Аудиозапись приостановлена")
            return True

    def resume(self) -> bool:
        """
        Возобновление приостановленной записи.

        Returns:
            True если запись успешно возобновлена
        """
        with self._lock:
            if self._state != AudioState.PAUSED:
                return False

            self._total_paused += time.time() - self._paused_time
            self._state = AudioState.RECORDING
            logger.info("Аудиозапись возобновлена")
            return True

    def stop(self) -> bool:
        """
        Остановка записи и сохранение файла.

        Returns:
            True если запись успешно остановлена
        """
        with self._lock:
            if self._state == AudioState.IDLE:
                return False

            self._state = AudioState.STOPPING
            self._shutdown_event.set()

        # Ожидание завершения потока записи
        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=5)

        self._writer_stop_event.set()
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=5)

        self._cleanup()

        logger.info(f"Аудиозапись остановлена: {self._output_path}")
        return True

    def _record_loop(self) -> None:
        """Основной цикл записи в отдельном потоке."""
        try:
            import sounddevice as sd

            def audio_callback(indata, frames, time_info, status):
                _ = time_info
                if status:
                    logger.warning(f"Проблема аудиозахвата: {status}")
                if self._state == AudioState.RECORDING:
                    # Callback не должен блокироваться дисковым I/O.
                    audio_data = indata.tobytes()
                    self._enqueue_audio_chunk(audio_data, int(frames))

            # Запуск потоковой передачи
            with sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype="int16",
                device=self.config.device_index,
                blocksize=self.config.chunk_size,
                callback=audio_callback,
            ):
                while (
                    not self._shutdown_event.is_set()
                    and self._state
                    not in (
                        AudioState.IDLE,
                        AudioState.STOPPING,
                    )
                ):
                    if self._state == AudioState.PAUSED:
                        time.sleep(0.1)
                        continue

                    # Проверка лимита длительности
                    if self._duration and self.elapsed_time >= self._duration:
                        logger.info("Достигнут лимит длительности аудио")
                        break

                    time.sleep(0.01)

        except ImportError:
            # Возврат к циклу pyaudio
            self._record_loop_pyaudio()

    def _record_loop_pyaudio(self) -> None:
        """Цикл записи с использованием PyAudio."""
        if not self._audio_stream:
            return

        try:
            while not self._shutdown_event.is_set() and self._state not in (
                AudioState.IDLE,
                AudioState.STOPPING,
            ):
                if self._state == AudioState.PAUSED:
                    time.sleep(0.1)
                    continue

                try:
                    data = self._audio_stream.read(
                        self.config.chunk_size, exception_on_overflow=False
                    )
                    self._enqueue_audio_chunk(data, self.config.chunk_size)

                except Exception as e:
                    logger.error(f"Ошибка чтения аудио: {e}")

                # Проверка лимита длительности
                if self._duration and self.elapsed_time >= self._duration:
                    break

        except Exception as e:
            logger.error(f"Ошибка цикла записи PyAudio: {e}")
            if self._on_error:
                self._on_error(str(e))

    def _enqueue_audio_chunk(self, audio_data: bytes, frames: int) -> None:
        """
        Неблокирующее помещение аудио-чанка в очередь writer-потока.

        Args:
            audio_data: Байты PCM чанка.
            frames: Количество кадров в чанке.
        """
        try:
            self._audio_queue.put_nowait((audio_data, frames))
        except queue.Full:
            self._dropped_chunks += 1

            # Уведомление при первой потере и далее каждые 10
            should_notify = (
                self._dropped_chunks == 1 or self._dropped_chunks % 10 == 0
            )

            if should_notify and self._on_chunks_dropped:
                try:
                    self._on_chunks_dropped(self._dropped_chunks)
                except Exception as e:
                    logger.error(f"Ошибка в on_chunks_dropped callback: {e}")

            if self._dropped_chunks == 1 or self._dropped_chunks % 50 == 0:
                logger.warning(
                    "Очередь аудио переполнена, пропущено чанков: %s",
                    self._dropped_chunks,
                )

    def _writer_loop(self) -> None:
        """Фоновая запись WAV из очереди audio-чанков."""
        while True:
            if self._writer_stop_event.is_set() and self._audio_queue.empty():
                return

            try:
                chunk = self._audio_queue.get(
                    timeout=_AUDIO_QUEUE_GET_TIMEOUT_SECONDS
                )
            except queue.Empty:
                continue

            if chunk is None:
                continue

            audio_data, frames = chunk
            try:
                if self._wave_file is not None:
                    self._wave_file.writeframes(audio_data)
                    self._frames_recorded += frames
            except Exception as e:
                logger.error(f"Ошибка записи WAV чанка: {e}")
                if self._on_error:
                    self._on_error(str(e))
                self._writer_stop_event.set()

    def _reset_audio_queue(self) -> None:
        """Очистка очереди аудио перед запуском новой записи."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    def _cleanup(self) -> None:
        """Очистка ресурсов."""
        try:
            self._writer_stop_event.set()

            # Закрытие WAV файла
            if self._wave_file:
                self._wave_file.close()
                self._wave_file = None

            # Закрытие ресурсов PyAudio если использовались
            if self._audio_stream:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
                self._audio_stream = None

            if self._audio_interface:
                self._audio_interface.terminate()
                self._audio_interface = None

        except Exception as e:
            logger.error(f"Ошибка при очистке аудио: {e}")

        self._writer_thread = None
        self._state = AudioState.IDLE


class SystemAudioRecorder(AudioRecorder):
    """
    Класс записи системного аудио для захвата общесистемного вывода аудио.

    Примечание: Зависит от платформы и может потребовать дополнительной настройки:
    - Windows: Использует WASAPI loopback (требует pycaw)
    - Linux: Требует устройство мониторинга PulseAudio
    - macOS: Требует виртуальное устройство BlackHole или Soundflower
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_system_audio = True

    def _init_audio(self) -> None:
        """Инициализация захвата системного аудио."""
        if self._platform == "windows":
            self._init_windows_system_audio()
        elif self._platform == "linux":
            self._init_linux_system_audio()
        elif self._platform == "darwin":
            self._init_macos_system_audio()
        else:
            raise RuntimeError(
                f"Системное аудио не поддерживается на {self._platform}"
            )

    def _init_windows_system_audio(self) -> None:
        """Инициализация захвата системного аудио Windows с использованием WASAPI loopback."""
        try:
            import sounddevice as sd

            # Поиск устройства loopback
            devices = sd.query_devices()
            loopback_device = None

            for i, dev in enumerate(devices):
                # Поиск устройства loopback или стерео микшера
                if (
                    "loopback" in dev["name"].lower()
                    or "stereo mix" in dev["name"].lower()
                ):
                    if dev["max_input_channels"] > 0:
                        loopback_device = i
                        break

            if loopback_device is None:
                logger.warning(
                    "Устройство loopback для системного аудио не найдено, используется вход по умолчанию"
                )
                super()._init_audio()
                return

            self.config.device_index = loopback_device
            logger.info(
                f"Используется устройство системного аудио: {devices[loopback_device]['name']}"
            )

        except Exception as e:
            logger.error(
                f"Не удалось инициализировать системное аудио Windows: {e}"
            )
            raise

    def _init_linux_system_audio(self) -> None:
        """Инициализация захвата системного аудио Linux с использованием монитора PulseAudio."""
        try:
            import sounddevice as sd

            # Поиск устройства монитора PulseAudio
            devices = sd.query_devices()
            monitor_device = None

            for i, dev in enumerate(devices):
                if "monitor" in dev["name"].lower():
                    monitor_device = i
                    break

            if monitor_device is None:
                logger.warning("Устройство монитора PulseAudio не найдено")
                raise RuntimeError("Монитор системного аудио недоступен")

            self.config.device_index = monitor_device
            logger.info(
                f"Используется устройство системного аудио: {devices[monitor_device]['name']}"
            )

        except Exception as e:
            logger.error(
                f"Не удалось инициализировать системное аудио Linux: {e}"
            )
            raise

    def _init_macos_system_audio(self) -> None:
        """Инициализация захвата системного аудио macOS."""
        # macOS требует виртуальное аудиоустройство вроде BlackHole или Soundflower
        logger.warning(
            "Системное аудио macOS требует виртуальное аудиоустройство "
            "(BlackHole, Soundflower или аналогичное). "
            "Пожалуйста, установите и настройте виртуальное аудиоустройство."
        )

        try:
            import sounddevice as sd

            devices = sd.query_devices()
            virtual_device = None

            for i, dev in enumerate(devices):
                name_lower = dev["name"].lower()
                if "blackhole" in name_lower or "soundflower" in name_lower:
                    virtual_device = i
                    break

            if virtual_device is None:
                raise RuntimeError(
                    "Виртуальное аудиоустройство не найдено. "
                    "Установите BlackHole или Soundflower для захвата системного аудио."
                )

            self.config.device_index = virtual_device
            logger.info(
                f"Используется устройство системного аудио: {devices[virtual_device]['name']}"
            )

        except Exception as e:
            logger.error(
                f"Не удалось инициализировать системное аудио macOS: {e}"
            )
            raise
