"""Модель и сервис pre-start readiness для сценариев записи."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from core.recording_state import AudioSettings, CaptureSettings
from core.recording_types import AudioMode, CaptureMode
from recorder.utils import (
    check_disk_space,
    check_ffmpeg,
    get_audio_devices,
    get_available_windows,
    is_valid_output_path,
)

ReadinessSeverity = Literal["blocking", "warning"]
ReadinessCheckStatus = Literal[
    "ready",
    "warning",
    "blocking",
    "not_required",
]
_MIN_FREE_SPACE_MB = 100


@dataclass(frozen=True, slots=True)
class ReadinessIssue:
    """Описание одной проблемы готовности к старту."""

    code: str
    severity: ReadinessSeverity
    title: str
    message: str
    next_step: str | None = None


@dataclass(frozen=True, slots=True)
class ReadinessAction:
    """Действие, помогающее исправить readiness-проблему."""

    key: str
    label: str


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    """Статус одного пункта readiness-checklist."""

    key: str
    title: str
    status: ReadinessCheckStatus
    message: str
    next_step: str | None = None
    action: ReadinessAction | None = None


@dataclass(frozen=True, slots=True)
class ReadinessSnapshot:
    """Снимок готовности сценария записи."""

    issues: tuple[ReadinessIssue, ...] = ()

    @property
    def blocking_issues(self) -> tuple[ReadinessIssue, ...]:
        """Вернуть только блокирующие проблемы."""
        return tuple(
            issue for issue in self.issues if issue.severity == "blocking"
        )

    @property
    def warning_issues(self) -> tuple[ReadinessIssue, ...]:
        """Вернуть предупреждения, не блокирующие старт."""
        return tuple(
            issue for issue in self.issues if issue.severity == "warning"
        )

    @property
    def is_ready(self) -> bool:
        """Признак отсутствия блокирующих проблем."""
        return not self.blocking_issues

    def find_issue(self, *codes: str) -> ReadinessIssue | None:
        """Найти первую проблему по одному из переданных кодов."""
        issue_codes = set(codes)
        for issue in self.issues:
            if issue.code in issue_codes:
                return issue
        return None

    def summary_text(self, max_items: int = 2) -> str:
        """Сформировать короткое summary по проблемам."""
        if not self.issues:
            return "Система готова к записи."

        titles = [issue.title for issue in self.issues[:max_items]]
        summary = "; ".join(titles)
        remaining = len(self.issues) - len(titles)
        if remaining > 0:
            summary = f"{summary}; ещё проблем: {remaining}"
        return summary


class RecordingReadinessService:
    """Сервис предварительной проверки готовности записи."""

    def __init__(self) -> None:
        self._ffmpeg_checker = check_ffmpeg
        self._window_provider = get_available_windows
        self._audio_devices_provider = get_audio_devices

    def evaluate(
        self,
        capture: CaptureSettings,
        audio: AudioSettings,
        output_path: Path,
    ) -> ReadinessSnapshot:
        """
        Собрать readiness snapshot для текущего сценария записи.

        Args:
            capture: Настройки области захвата.
            audio: Настройки аудио.
            output_path: Итоговый путь вывода.

        Returns:
            Снимок готовности с blocking/warning issues.
        """
        issues: list[ReadinessIssue] = []

        ffmpeg_available, _version = self._ffmpeg_checker()
        if not ffmpeg_available:
            issues.append(
                ReadinessIssue(
                    code="ffmpeg_missing",
                    severity="blocking",
                    title="FFmpeg недоступен",
                    message=(
                        "Приложение не нашло FFmpeg в PATH, поэтому "
                        "старт записи сейчас невозможен."
                    ),
                    next_step="Установите FFmpeg или проверьте PATH.",
                )
            )

        output_path_str = str(output_path)
        if not is_valid_output_path(output_path_str):
            issues.append(
                ReadinessIssue(
                    code="output_path_invalid",
                    severity="blocking",
                    title="Путь вывода недоступен",
                    message=(
                        "Текущий путь вывода нельзя использовать для записи."
                    ),
                    next_step="Выберите другую папку вывода.",
                )
            )
        else:
            has_space, _free_bytes, disk_error = check_disk_space(
                output_path,
                min_space_mb=_MIN_FREE_SPACE_MB,
            )
            if not has_space:
                issues.append(
                    ReadinessIssue(
                        code="disk_space_low",
                        severity="blocking",
                        title="Недостаточно места на диске",
                        message=(
                            disk_error
                            or "Для записи не хватает свободного места."
                        ),
                        next_step="Освободите место или смените папку вывода.",
                    )
                )

        if capture.capture_type == CaptureMode.WINDOW:
            self._append_window_issues(issues, capture)

        if audio.audio_type in (AudioMode.MIC, AudioMode.BOTH):
            self._append_microphone_issues(issues, audio)

        return ReadinessSnapshot(tuple(issues))

    def _append_window_issues(
        self,
        issues: list[ReadinessIssue],
        capture: CaptureSettings,
    ) -> None:
        """Добавить readiness-проблемы, связанные с выбором окна."""
        if not capture.window_title:
            issues.append(
                ReadinessIssue(
                    code="window_not_selected",
                    severity="blocking",
                    title="Не выбрано окно захвата",
                    message="Для режима захвата окна нужно выбрать окно.",
                    next_step="Откройте список окон и выберите нужное окно.",
                )
            )
            return

        window_titles = {
            str(window.get("title", ""))
            for window in self._window_provider()
            if isinstance(window, dict)
        }
        if capture.window_title not in window_titles:
            issues.append(
                ReadinessIssue(
                    code="window_missing",
                    severity="blocking",
                    title="Окно захвата недоступно",
                    message=(
                        f"Окно '{capture.window_title}' сейчас не найдено."
                    ),
                    next_step="Обновите список окон и выберите доступное окно.",
                )
            )

    def _append_microphone_issues(
        self,
        issues: list[ReadinessIssue],
        audio: AudioSettings,
    ) -> None:
        """Добавить readiness-проблемы, связанные с микрофоном."""
        input_devices = [
            device
            for device in self._audio_devices_provider().get("input", [])
            if isinstance(device, dict)
        ]

        if not input_devices:
            issues.append(
                ReadinessIssue(
                    code="microphone_missing",
                    severity="blocking",
                    title="Нет доступных микрофонов",
                    message="Система не вернула ни одного устройства ввода.",
                    next_step="Подключите микрофон и обновите список устройств.",
                )
            )
            return

        if audio.mic_device_index is None and not audio.mic_device_name:
            issues.append(
                ReadinessIssue(
                    code="microphone_default",
                    severity="warning",
                    title="Будет использован системный микрофон по умолчанию",
                    message=(
                        "Явное устройство микрофона не выбрано, будет "
                        "использован системный default input."
                    ),
                    next_step="При необходимости выберите конкретный микрофон.",
                )
            )
            return

        if audio.mic_device_index is not None:
            for device in input_devices:
                if device.get("id") == audio.mic_device_index:
                    return
            issues.append(
                ReadinessIssue(
                    code="microphone_selected_missing",
                    severity="blocking",
                    title="Выбранный микрофон недоступен",
                    message="Ранее выбранный микрофон больше не найден.",
                    next_step="Обновите список устройств и выберите микрофон.",
                )
            )
            return

        available_names = {
            str(device.get("name", "")) for device in input_devices
        }
        if (
            audio.mic_device_name
            and audio.mic_device_name not in available_names
        ):
            issues.append(
                ReadinessIssue(
                    code="microphone_name_missing",
                    severity="blocking",
                    title="Выбранный микрофон недоступен",
                    message=(
                        f"Микрофон '{audio.mic_device_name}' сейчас не найден."
                    ),
                    next_step="Обновите список устройств и выберите микрофон.",
                )
            )


def resolve_readiness_action(issue_code: str) -> ReadinessAction | None:
    """
    Вернуть рекомендуемое remediation-action для readiness-проблемы.

    Args:
        issue_code: Код проблемы из readiness snapshot.

    Returns:
        Описание быстрого действия или `None`, если action не нужен.
    """
    action_map = {
        "ffmpeg_missing": ReadinessAction(
            key="open_ffmpeg_docs",
            label="Открыть инструкцию",
        ),
        "output_path_invalid": ReadinessAction(
            key="choose_output_path",
            label="Выбрать папку",
        ),
        "disk_space_low": ReadinessAction(
            key="choose_output_path",
            label="Сменить папку",
        ),
        "window_not_selected": ReadinessAction(
            key="focus_capture_window",
            label="Выбрать окно",
        ),
        "window_missing": ReadinessAction(
            key="refresh_windows",
            label="Обновить окна",
        ),
        "microphone_missing": ReadinessAction(
            key="refresh_audio_devices",
            label="Обновить микрофоны",
        ),
        "microphone_selected_missing": ReadinessAction(
            key="refresh_audio_devices",
            label="Обновить микрофоны",
        ),
        "microphone_name_missing": ReadinessAction(
            key="refresh_audio_devices",
            label="Обновить микрофоны",
        ),
        "microphone_default": ReadinessAction(
            key="focus_microphone_selection",
            label="Выбрать микрофон",
        ),
    }
    return action_map.get(issue_code)


def build_readiness_checks(
    snapshot: ReadinessSnapshot,
    capture: CaptureSettings,
    audio: AudioSettings,
) -> tuple[ReadinessCheck, ...]:
    """
    Построить компактный checklist для GUI из readiness snapshot.

    Args:
        snapshot: Результат preflight-проверки.
        capture: Текущие настройки захвата.
        audio: Текущие настройки аудио.

    Returns:
        Упорядоченный набор check-элементов для inline readiness UI.
    """
    ffmpeg_issue = snapshot.find_issue("ffmpeg_missing")
    output_issue = snapshot.find_issue(
        "output_path_invalid",
        "disk_space_low",
    )
    capture_issue = snapshot.find_issue(
        "window_not_selected",
        "window_missing",
    )
    audio_issue = snapshot.find_issue(
        "microphone_missing",
        "microphone_selected_missing",
        "microphone_name_missing",
        "microphone_default",
    )

    ffmpeg_check = ReadinessCheck(
        key="ffmpeg",
        title="FFmpeg",
        status="blocking" if ffmpeg_issue is not None else "ready",
        message=(
            ffmpeg_issue.message
            if ffmpeg_issue is not None
            else "FFmpeg найден и готов к кодированию."
        ),
        next_step=ffmpeg_issue.next_step if ffmpeg_issue is not None else None,
        action=(
            resolve_readiness_action(ffmpeg_issue.code)
            if ffmpeg_issue is not None
            else None
        ),
    )

    output_check = ReadinessCheck(
        key="output",
        title="Путь вывода",
        status="blocking" if output_issue is not None else "ready",
        message=(
            output_issue.message
            if output_issue is not None
            else "Путь вывода доступен, свободного места достаточно."
        ),
        next_step=output_issue.next_step if output_issue is not None else None,
        action=(
            resolve_readiness_action(output_issue.code)
            if output_issue is not None
            else None
        ),
    )

    if capture.capture_type != CaptureMode.WINDOW:
        capture_check = ReadinessCheck(
            key="capture",
            title="Окно захвата",
            status="not_required",
            message="Для текущего режима записи отдельное окно не требуется.",
        )
    else:
        capture_check = ReadinessCheck(
            key="capture",
            title="Окно захвата",
            status="blocking" if capture_issue is not None else "ready",
            message=(
                capture_issue.message
                if capture_issue is not None
                else "Выбранное окно доступно для захвата."
            ),
            next_step=(
                capture_issue.next_step if capture_issue is not None else None
            ),
            action=(
                resolve_readiness_action(capture_issue.code)
                if capture_issue is not None
                else None
            ),
        )

    if audio.audio_type in (AudioMode.NONE, AudioMode.SYSTEM):
        audio_check = ReadinessCheck(
            key="audio",
            title="Микрофон",
            status="not_required",
            message="Для текущего аудиорежима микрофон не обязателен.",
        )
    elif audio_issue is None:
        audio_check = ReadinessCheck(
            key="audio",
            title="Микрофон",
            status="ready",
            message="Микрофон готов к записи.",
        )
    else:
        audio_check = ReadinessCheck(
            key="audio",
            title="Микрофон",
            status=audio_issue.severity,
            message=audio_issue.message,
            next_step=audio_issue.next_step,
            action=resolve_readiness_action(audio_issue.code),
        )

    return (
        ffmpeg_check,
        output_check,
        capture_check,
        audio_check,
    )


def summarize_readiness_checks(
    checks: tuple[ReadinessCheck, ...],
) -> tuple[ReadinessCheckStatus, str]:
    """
    Сформировать общий статус и summary по readiness checklist.

    Args:
        checks: Набор check-элементов readiness.

    Returns:
        Кортеж `(status, summary_text)`.
    """
    blocking_checks = [check for check in checks if check.status == "blocking"]
    warning_checks = [check for check in checks if check.status == "warning"]

    if blocking_checks:
        titles = ", ".join(check.title for check in blocking_checks[:2])
        return "blocking", f"Старт заблокирован: {titles}"

    if warning_checks:
        titles = ", ".join(check.title for check in warning_checks[:2])
        return "warning", f"Есть предупреждения: {titles}"

    return "ready", "Система готова к записи."
