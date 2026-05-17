"""Тесты каталога видеокодеков GUI."""

from gui.models.video_codecs import (
    AVAILABLE_VIDEO_CODECS,
    DEFAULT_CODEC_ID,
    codec_id_from_display_name,
    display_name_from_codec_id,
    get_available_codec_display_names,
    get_codec_info_by_display_name,
    get_codec_info_by_id,
)


class TestVideoCodecsCatalog:
    """Проверки единого каталога кодеков."""

    def test_catalog_contains_expected_ids(self) -> None:
        """Каталог содержит ожидаемые идентификаторы кодеков."""
        assert [codec.codec_id for codec in AVAILABLE_VIDEO_CODECS] == [
            "libx264",
            "h264_nvenc",
            "h264_qsv",
            "libx265",
            "hevc_nvenc",
            "mp4v",
        ]

    def test_get_available_codec_display_names(self) -> None:
        """Каталог возвращает display-имена в UI-порядке."""
        assert get_available_codec_display_names() == [
            "libx264 (CPU)",
            "h264_nvenc (NVIDIA GPU)",
            "h264_qsv (Intel GPU)",
            "libx265 (HEVC CPU)",
            "hevc_nvenc (NVIDIA HEVC)",
            "mp4v",
        ]

    def test_get_codec_info_by_id(self) -> None:
        """Поиск по codec id возвращает ожидаемый объект."""
        codec = get_codec_info_by_id("h264_nvenc")

        assert codec is not None
        assert codec.display_name == "h264_nvenc (NVIDIA GPU)"
        assert codec.hardware_acceleration is True

    def test_get_codec_info_by_display_name(self) -> None:
        """Поиск по display-имени возвращает ожидаемый объект."""
        codec = get_codec_info_by_display_name("libx265 (HEVC CPU)")

        assert codec is not None
        assert codec.codec_id == "libx265"

    def test_codec_id_from_display_name_returns_default_for_unknown(
        self,
    ) -> None:
        """Неизвестное display-имя откатывается к дефолтному codec id."""
        assert codec_id_from_display_name("unknown") == DEFAULT_CODEC_ID

    def test_display_name_from_codec_id_returns_default_for_unknown(
        self,
    ) -> None:
        """Неизвестный codec id откатывается к дефолтному display text."""
        assert display_name_from_codec_id("unknown") == "libx264 (CPU)"
