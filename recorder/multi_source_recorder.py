"""
Мультиисточниковая запись (#51).

Запускает несколько независимых `VideoRecorder` (один на каждый источник —
монитор/окно/прямоугольник), каждый со своим файлом и своим
`_WindowsCaptureSession`/`FFmpegVideoWriter`. Источники не синхронизируются
по кадрам друг с другом — каждый идёт по своим таймингам, что надёжнее, чем
зависимость от самого медленного источника.

Поддерживает опциональное аудио-наложение (один общий audio track для всех
сегментов) с использованием `AudioRecorder` и `RecordingEncoder`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from logger_config import get_module_logger
from recorder.audio_recorder import AudioRecorder, SystemAudioRecorder
from recorder.video_recorder import CaptureArea, VideoRecorder

logger = get_module_logger(__name__)


@dataclass(frozen=True)
class MultiCaptureSourceSpec:
    """Спецификация одного источника для мультиисточниковой записи."""

    label: str
    area_type: Literal["full", "window", "rect"] = "full"
    monitor_index: int = 0
    window_title: str = ""
    rect_coords: tuple[int, int, int, int] = (0, 0, 1920, 1080)

    def build_capture_area(self) -> CaptureArea:
        """Строит `CaptureArea` для этого источника."""
        if self.area_type == "window":
            return CaptureArea.from_window(
                self.window_title, raise_if_not_found=True
            )
        if self.area_type == "rect":
            return CaptureArea.from_rect(*self.rect_coords)
        return CaptureArea.full_screen(monitor_index=self.monitor_index)


@dataclass
class _ActiveSource:
    """Запущенный источник с привязанными рекордером и путём вывода."""

    recorder: VideoRecorder
    output_path: Path


class MultiSourceRecorder:
    """
    Управляет N независимыми `VideoRecorder` как одной логической сессией.

    При неудаче запуска любого источника откатывает уже запущенные —
    ничего не остаётся в наполовину запущенном состоянии.

    Поддерживает опциональное аудио: один общий audio track записывается
    параллельно и добавляется ко всем видео-сегментам после записи.
    """

    def __init__(
        self,
        fps: int = 30,
        codec: str = "libx264",
        bitrate: str = "2M",
        preset: str = "medium",
    ) -> None:
        self._fps = fps
        self._codec = codec
        self._bitrate = bitrate
        self._preset = preset
        self._sources: dict[str, _ActiveSource] = {}
        self._audio_recorder: AudioRecorder | SystemAudioRecorder | None = None
        self._audio_temp_path: Path | None = None

    @property
    def is_active(self) -> bool:
        """Признак, что хотя бы один источник запущен."""
        return bool(self._sources)

    def _build_output_path(self, base_output_path: Path, label: str) -> Path:
        """Строит путь вывода для источника на основе базового пути."""
        return base_output_path.with_name(
            f"{base_output_path.stem}_{label}{base_output_path.suffix}"
        )

    def start(
        self,
        sources: list[MultiCaptureSourceSpec],
        base_output_path: Path,
        duration: float | None = None,
        audio_type: str = "none",
    ) -> tuple[bool, dict[str, Path] | None, str | None]:
        """
        Запускает запись всех источников с опциональным аудио.

        При неудаче любого источника останавливает уже запущенные и
        возвращает понятную ошибку — частично запущенной сессии не
        остаётся.

        Args:
            sources: Источники захвата (минимум 2, уникальные `label`).
            base_output_path: Базовый путь вывода — каждый источник
                получает свой файл `{stem}_{label}{suffix}`.
            duration: Опциональная длительность записи в секундах.
            audio_type: Тип аудио ("none", "mic", "system", "both").

        Returns:
            Кортеж `(success, {label: output_path}, error_message)`.
        """
        if self.is_active:
            return False, None, "Мультиисточниковая запись уже активна"

        if len(sources) < 2:
            return False, None, "Нужно минимум 2 источника"

        labels = [s.label for s in sources]
        if len(labels) != len(set(labels)):
            return False, None, "Метки источников должны быть уникальными"

        started: dict[str, _ActiveSource] = {}
        audio_started = False
        try:
            # Запуск аудиозаписи если требуется
            if audio_type in ("mic", "system", "both"):
                try:
                    if audio_type == "system":
                        self._audio_recorder = SystemAudioRecorder()
                    else:
                        self._audio_recorder = AudioRecorder()

                    # Временный файл для аудио
                    self._audio_temp_path = base_output_path.with_stem(
                        f"{base_output_path.stem}_audio_temp"
                    ).with_suffix(".wav")

                    if not self._audio_recorder.start(self._audio_temp_path):
                        raise RuntimeError("Не удалось запустить аудиозапись")
                    audio_started = True
                    logger.debug(
                        "Аудиозапись для мультиисточниковой записи запущена"
                    )
                except (ValueError, RuntimeError, OSError) as e:
                    if audio_type == "both":
                        # Для "both" можно продолжить без системного аудио
                        logger.warning(
                            "Не удалось запустить системное аудио, продолжаем без него: %s",
                            e,
                        )
                        self._audio_recorder = None
                        self._audio_temp_path = None
                    else:
                        raise RuntimeError(
                            f"Ошибка запуска аудиозаписи ({audio_type}): {e}"
                        )

            for source in sources:
                capture_area = source.build_capture_area()
                output_path = self._build_output_path(
                    base_output_path, source.label
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)

                recorder = VideoRecorder(
                    fps=self._fps,
                    codec=self._codec,
                    bitrate=self._bitrate,
                    use_ffmpeg=True,
                    preset=self._preset,
                )
                if not recorder.start(output_path, capture_area, duration):
                    raise RuntimeError(
                        f"Не удалось запустить запись источника '{source.label}'"
                    )
                started[source.label] = _ActiveSource(
                    recorder=recorder, output_path=output_path
                )
        except (ValueError, RuntimeError) as e:
            logger.error(
                "Ошибка запуска мультиисточниковой записи, откат: %s", e
            )
            # Откат аудио
            if audio_started and self._audio_recorder:
                try:
                    self._audio_recorder.stop()
                except (OSError, RuntimeError) as stop_error:
                    logger.warning(
                        "Ошибка остановки аудиозаписи при откате: %s",
                        stop_error,
                    )
            self._audio_recorder = None
            self._audio_temp_path = None

            # Откат видео
            for active in started.values():
                try:
                    active.recorder.stop()
                except (OSError, RuntimeError) as stop_error:
                    logger.warning(
                        "Ошибка остановки источника при откате: %s",
                        stop_error,
                    )
            return False, None, str(e)

        self._sources = started
        logger.info(
            "Мультиисточниковая запись запущена: %s", list(started.keys())
        )
        return (
            True,
            {label: active.output_path for label, active in started.items()},
            None,
        )

    def stop(self) -> dict[str, dict[str, Any]]:
        """
        Останавливает все источники и опциональное аудио.

        Если аудио записывалось, объединяет его со всеми видеофайлами.

        Returns:
            `{label: {"success": bool, "output_path": str | None}}`.
        """
        results: dict[str, dict[str, Any]] = {}

        # Остановка видео
        for label, active in self._sources.items():
            success = active.recorder.stop()
            results[label] = {
                "success": success,
                "output_path": str(active.output_path) if success else None,
            }

        # Остановка аудио и микширование
        if (
            self._audio_recorder is not None
            and self._audio_temp_path is not None
        ):
            try:
                self._audio_recorder.stop()
                logger.debug(
                    "Аудиозапись для мультиисточниковой записи остановлена"
                )

                # Микширование аудио со всеми видеофайлами
                if all(results[label]["success"] for label in results):
                    self._merge_audio_with_videos(results)
            except (OSError, RuntimeError) as e:
                logger.warning(
                    "Ошибка остановки аудиозаписи при остановке мультиисточниковой "
                    "записи: %s",
                    e,
                )
            finally:
                self._audio_recorder = None
                self._audio_temp_path = None

        self._sources = {}
        logger.info("Мультиисточниковая запись остановлена: %s", results)
        return results

    def _merge_audio_with_videos(
        self, results: dict[str, dict[str, Any]]
    ) -> None:
        """Микширует временный аудиофайл со всеми видеофайлами."""
        from recorder.encoder import Encoder, EncodingSettings

        if self._audio_temp_path is None or not self._audio_temp_path.exists():
            logger.warning(
                "Временный аудиофайл не найден, микширование пропущено"
            )
            return

        encoder = Encoder(
            EncodingSettings(codec=self._codec, bitrate=self._bitrate)
        )

        for label, result in results.items():
            if not result["success"] or result["output_path"] is None:
                continue

            original_path = Path(result["output_path"])
            temp_path = original_path.with_stem(
                f"{original_path.stem}_no_audio"
            )

            try:
                # Переименование исходного файла (без аудио)
                original_path.rename(temp_path)

                # Микширование аудио с видео
                success, error = encoder.merge_video_audio(
                    video_path=temp_path,
                    audio_path=self._audio_temp_path,
                    output_path=original_path,
                    keep_originals=False,
                )

                if success:
                    logger.debug("Аудио добавлено к видеосегменту '%s'", label)
                    # Удаление временного видеофайла (без аудио)
                    try:
                        temp_path.unlink()
                    except OSError as e:
                        logger.warning(
                            "Не удалось удалить временный видеофайл %s: %s",
                            temp_path,
                            e,
                        )
                else:
                    # Откат: переименование обратно
                    logger.warning(
                        "Ошибка микширования аудио для '%s': %s, откат",
                        label,
                        error,
                    )
                    temp_path.rename(original_path)
            except OSError as e:
                logger.warning(
                    "Ошибка обработки файла при микшировании аудио для '%s': %s",
                    label,
                    e,
                )

        # Удаление временного аудиофайла
        try:
            self._audio_temp_path.unlink()
        except OSError as e:
            logger.warning("Не удалось удалить временный аудиофайл: %s", e)

    def get_status(self) -> dict[str, Any]:
        """Возвращает агрегированный статус по всем источникам."""
        return {
            "active": self.is_active,
            "sources": {
                label: {
                    "state": active.recorder.state.value,
                    "elapsed_time": active.recorder.elapsed_time,
                    "output_path": str(active.output_path),
                }
                for label, active in self._sources.items()
            },
        }
