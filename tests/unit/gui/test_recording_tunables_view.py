"""Unit-тесты представления тонких параметров записи (#155)."""

from __future__ import annotations

from config import RecordingTunables
from gui.views.recording_tunables_view import RecordingTunablesView


class TestRecordingTunablesView:
    """Тестирование виджета RecordingTunablesView."""

    def test_get_and_set_settings_roundtrip(self) -> None:
        """set_settings → get_settings возвращает те же значения."""
        view = RecordingTunablesView()
        settings = RecordingTunables(
            enable_frame_skip=True,
            max_recovery_attempts=6,
            audio_max_recovery_attempts=8,
            disk_warning_mb=4096.0,
            disk_critical_mb=256.0,
            disk_check_interval_s=15.0,
            max_segment_size_mb=128.0,
            max_segment_duration_s=600.0,
            health_check_interval_s=2.5,
        )

        view.set_settings(settings)
        result = view.get_settings()

        assert result == settings

    def test_defaults_match_config_defaults(self) -> None:
        """Свежий виджет отдаёт дефолты конфигурации."""
        view = RecordingTunablesView()

        result = view.get_settings()

        assert result == RecordingTunables()

    def test_zero_segment_limits_map_to_none(self) -> None:
        """0 в полях сегментов означает «без лимита» (None)."""
        view = RecordingTunablesView()

        view.set_settings(
            RecordingTunables(
                max_segment_size_mb=100.0,
                max_segment_duration_s=60.0,
            )
        )
        view._segment_size_spin.setValue(0)
        view._segment_duration_spin.setValue(0)

        result = view.get_settings()

        assert result.max_segment_size_mb is None
        assert result.max_segment_duration_s is None

    def test_critical_threshold_clamped_to_warning(self) -> None:
        """Критический порог диска не превышает предупреждение."""
        view = RecordingTunablesView()

        view.set_settings(RecordingTunables(disk_warning_mb=500.0))
        view._disk_critical_spin.setValue(1000.0)

        result = view.get_settings()

        assert result.disk_critical_mb <= result.disk_warning_mb

    def test_settings_changed_emitted_on_edit(self) -> None:
        """Изменение поля тянет сигнал settings_changed (проводка)."""
        from unittest.mock import MagicMock

        view = RecordingTunablesView()

        signal_mock = MagicMock()
        view.settings_changed.connect(signal_mock)

        # Мок-спин не эмитит valueChanged на setValue (в отличие от Qt),
        # поэтому эмулируем событие изменения поля
        view._recovery_spin.valueChanged.emit(5)

        assert signal_mock.called
