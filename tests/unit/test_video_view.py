"""Тесты VideoView на моках PyQt6."""

from typing import Any

from PyQt6.QtWidgets import QApplication

from gui.models.recording_state import VideoSettings
from gui.views.video_view import VideoView


def _patch_combo_runtime(combo: Any) -> None:
    """Добавить недостающие методы mock combobox для тестов."""

    def find_text(text: str) -> int:
        items = getattr(combo, "_items", [])
        return items.index(text) if text in items else -1

    def set_current_index(index: int) -> None:
        combo._current_index = index
        items = getattr(combo, "_items", [])
        if 0 <= index < len(items):
            combo._current_text = items[index]

    def set_edit_text(text: str) -> None:
        combo._current_text = text

    combo.findText = find_text
    combo.setCurrentIndex = set_current_index
    combo.setEditText = set_edit_text


def _patch_view_runtime(view: VideoView) -> VideoView:
    """Подготовить моковый VideoView к unit-проверкам."""

    _patch_combo_runtime(view._codec_combo)
    _patch_combo_runtime(view._bitrate_combo)
    _patch_combo_runtime(view._format_combo)
    _patch_combo_runtime(view._preset_combo)
    return view


class TestVideoView:
    """Проверки VideoView с мокированным PyQt6."""

    def test_init_populates_codec_combo(self, qapp: QApplication) -> None:
        """Список кодеков заполняется при инициализации."""
        view = _patch_view_runtime(VideoView())

        assert view._codec_combo.count() == 6
        assert view._codec_combo.itemText(0) == "libx264 (CPU)"
        assert view._codec_combo.itemText(5) == "mp4v"

    def test_get_codec_uses_catalog_mapping(self, qapp: QApplication) -> None:
        """Геттер кодека возвращает codec id, а не display text."""
        view = _patch_view_runtime(VideoView())
        view._codec_combo.setCurrentText("h264_nvenc (NVIDIA GPU)")

        assert view.get_codec() == "h264_nvenc"

    def test_get_settings_returns_codec_id(self, qapp: QApplication) -> None:
        """Текущие настройки возвращают codec id из каталога."""
        view = _patch_view_runtime(VideoView())
        view.set_fps(60)
        view._codec_combo.setCurrentText("mp4v")
        view._bitrate_combo.setCurrentText("8M")
        view._format_combo.setCurrentText("avi")
        view.set_preset("slow")

        settings = view.get_settings()

        assert settings == VideoSettings(
            fps=60,
            codec="mp4v",
            bitrate="8M",
            format="avi",
            preset="slow",
        )

    def test_emit_settings_uses_codec_id(self, qapp: QApplication) -> None:
        """Сигнал настроек эмитит codec id, а не display text."""
        view = _patch_view_runtime(VideoView())
        received: list[VideoSettings] = []
        view.settings_changed.disconnect()
        view.settings_changed.connect(received.append)

        view._codec_combo.setCurrentText("h264_qsv (Intel GPU)")
        view._emit_settings()

        assert received
        assert received[-1].codec == "h264_qsv"

    def test_set_codec_selects_expected_display_name(
        self, qapp: QApplication
    ) -> None:
        """set_codec выбирает нужный display text по codec id."""
        view = _patch_view_runtime(VideoView())

        view.set_codec("hevc_nvenc")

        assert view._codec_combo.currentText() == "hevc_nvenc (NVIDIA HEVC)"

    def test_set_codec_unknown_falls_back_to_default(
        self, qapp: QApplication
    ) -> None:
        """Неизвестный codec id откатывается на дефолтный display text."""
        view = _patch_view_runtime(VideoView())

        view.set_codec("unknown_codec")

        assert view._codec_combo.currentText() == "libx264 (CPU)"

    def test_set_bitrate_supports_existing_and_custom_values(
        self, qapp: QApplication
    ) -> None:
        """set_bitrate работает и для списка, и для custom значения."""
        view = _patch_view_runtime(VideoView())

        view.set_bitrate("4M")
        assert view.get_bitrate() == "4M"

        view.set_bitrate("5M")
        assert view.get_bitrate() == "5M"

    def test_set_format_and_preset(self, qapp: QApplication) -> None:
        """set_format и set_preset обновляют соответствующие значения."""
        view = _patch_view_runtime(VideoView())

        view.set_format("mkv")
        view.set_preset("veryslow")

        assert view.get_format() == "mkv"
        assert view.get_preset() == "veryslow"

    def test_set_settings_applies_all_video_values(
        self, qapp: QApplication
    ) -> None:
        """set_settings применяет полный набор видеонастроек."""
        view = _patch_view_runtime(VideoView())

        view.set_settings(
            VideoSettings(
                fps=48,
                codec="libx265",
                bitrate="10M",
                format="mkv",
                preset="fast",
            )
        )

        assert view.get_settings() == VideoSettings(
            fps=48,
            codec="libx265",
            bitrate="10M",
            format="mkv",
            preset="fast",
        )

    def test_change_handlers_emit_signals(self, qapp: QApplication) -> None:
        """Обработчики изменений пробрасывают сигналы наружу."""
        view = _patch_view_runtime(VideoView())
        fps_values: list[int] = []
        codec_values: list[str] = []
        bitrate_values: list[str] = []
        format_values: list[str] = []
        preset_values: list[str] = []

        view.fps_changed.disconnect()
        view.codec_changed.disconnect()
        view.bitrate_changed.disconnect()
        view.format_changed.disconnect()
        view.preset_changed.disconnect()

        view.fps_changed.connect(fps_values.append)
        view.codec_changed.connect(codec_values.append)
        view.bitrate_changed.connect(bitrate_values.append)
        view.format_changed.connect(format_values.append)
        view.preset_changed.connect(preset_values.append)

        view._on_fps_changed(75)
        view._on_codec_changed("mp4v")
        view._on_bitrate_changed("6M")
        view._on_format_changed("avi")
        view.set_preset("slow")
        view._on_preset_changed(6)

        assert fps_values[-1] == 75
        assert codec_values[-1] == "mp4v"
        assert bitrate_values[-1] == "6M"
        assert format_values[-1] == "avi"
        assert preset_values[-1] == "slow"
