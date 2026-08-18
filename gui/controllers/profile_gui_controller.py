"""
Контроллер управления профилями записи в GUI
===========================================

Отвечает за:
- инициализацию и синхронизацию выпадающего списка профилей;
- открытие диалога настройки профилей (ProfileDialog);
- применение настроек выбранного профиля к представлениям захвата, аудио, видео и состоянию.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core.profiles import get_profile_storage
from core.recording_types import AudioMode, CaptureMode

if TYPE_CHECKING:
    from collections.abc import Callable

    from PyQt6.QtWidgets import QComboBox, QStatusBar, QWidget

    from gui.models.recording_state import RecordingState
    from gui.views.audio_view import AudioView
    from gui.views.capture_view import CaptureView
    from gui.views.video_view import VideoView


class ProfileGUIController:
    """Контроллер интерфейса профилей записи."""

    def __init__(self) -> None:
        pass

    def init_profiles(self, combo: QComboBox) -> None:
        """Инициализация списка профилей в выпадающем списке."""
        storage = get_profile_storage()
        profiles = storage.list_profiles()

        combo.blockSignals(True)
        combo.clear()

        default_index = 0
        for i, profile in enumerate(profiles):
            display_text = f"{profile.icon} {profile.name}"
            combo.addItem(display_text, profile.id)
            if profile.is_default:
                default_index = i

        if profiles:
            combo.setCurrentIndex(default_index)

        combo.blockSignals(False)

    def on_profile_combo_changed(
        self,
        index: int,
        combo: QComboBox,
        apply_callback: Callable[[Any], None],
    ) -> None:
        """Обработка выбора профиля в выпадающем списке."""
        if index < 0:
            return

        profile_id = combo.itemData(index)
        if not profile_id:
            return

        storage = get_profile_storage()
        profile = storage.get_profile(profile_id)
        if profile:
            apply_callback(profile)

    def open_profile_dialog(
        self,
        parent: QWidget,
        combo: QComboBox,
        apply_callback: Callable[[Any], None],
    ) -> None:
        """Открытие диалога управления профилями."""
        from gui.views.profile_dialog import ProfileDialog

        def on_applied(profile_id: str) -> None:
            storage = get_profile_storage()
            profile = storage.get_profile(profile_id)
            if profile:
                apply_callback(profile)
                self.init_profiles(combo)

        dialog = ProfileDialog(parent=parent)
        dialog.profiles_changed.connect(lambda: self.init_profiles(combo))
        dialog.profile_applied.connect(on_applied)
        dialog.exec()

    def apply_profile_settings(
        self,
        profile: Any,
        video_view: VideoView | None = None,
        audio_view: AudioView | None = None,
        capture_view: CaptureView | None = None,
        state: RecordingState | None = None,
        combo: QComboBox | None = None,
        status_bar: QStatusBar | None = None,
    ) -> None:
        """Применяет параметры профиля к активным представлениям и состоянию."""
        if hasattr(profile, "video") and video_view is not None:
            v = profile.video
            video_view.set_fps(v.fps)
            video_view.set_codec(v.codec)
            video_view.set_bitrate(v.bitrate)
            video_view.set_format(v.format)
            video_view.set_preset(v.preset)

        if hasattr(profile, "audio"):
            a = profile.audio
            rec_mic = getattr(a, "record_mic", True)
            rec_sys = getattr(a, "record_system", False)
            if rec_mic and rec_sys:
                audio_mode = AudioMode.BOTH
            elif rec_mic:
                audio_mode = AudioMode.MIC
            elif rec_sys:
                audio_mode = AudioMode.SYSTEM
            else:
                audio_mode = AudioMode.NONE

            if state is not None:
                state.set_audio_type(audio_mode)
            if audio_view is not None:
                audio_view.set_audio_type(audio_mode)

        if hasattr(profile, "capture") and capture_view is not None:
            c = profile.capture
            area_type_str = getattr(c, "area_type", "full")
            if area_type_str == "window":
                mode = CaptureMode.WINDOW
            elif area_type_str == "rect":
                mode = CaptureMode.RECT
            else:
                mode = CaptureMode.FULL

            capture_view.set_capture_type(mode)
            if getattr(c, "window_title", None):
                capture_view.set_window_title(c.window_title)
            if getattr(c, "rect_coords", None):
                capture_view.set_rect_coords(tuple(c.rect_coords))

        if combo is not None:
            combo.blockSignals(True)
            for i in range(combo.count()):
                if combo.itemData(i) == getattr(profile, "id", None):
                    combo.setCurrentIndex(i)
                    break
            combo.blockSignals(False)

        if status_bar is not None:
            name = getattr(profile, "name", "Профиль")
            status_bar.showMessage(f"Применен профиль: {name}", 4000)
