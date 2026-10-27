"""Тесты каталога видеокодеков GUI."""

from gui.models.video_codecs import (
    AVAILABLE_VIDEO_CODECS,
    DEFAULT_CODEC_ID,
    codec_id_from_display_name,
    display_name_from_codec_id,
    get_available_codec_display_names,
    get_codec_info_by_display_name,
    get_codec_info_by_id,
    get_software_fallback_codec,
    is_hardware_accelerated,
)


class TestVideoCodecsCatalog:
    """Проверки единого каталога кодеков."""

    def test_catalog_contains_expected_ids(self) -> None:
        """Каталог содержит ожидаемые идентификаторы кодеков."""
        assert [codec.codec_id for codec in AVAILABLE_VIDEO_CODECS] == [
            "libx264",
            "h264_nvenc",
            "h264_amf",
            "h264_qsv",
            "libx265",
            "hevc_nvenc",
            "hevc_amf",
            "hevc_qsv",
            "mp4v",
        ]

    def test_get_available_codec_display_names(self) -> None:
        """Каталог возвращает display-имена в UI-порядке."""
        assert get_available_codec_display_names() == [
            "libx264 (CPU)",
            "h264_nvenc (NVIDIA GPU)",
            "h264_amf (AMD GPU)",
            "h264_qsv (Intel GPU)",
            "libx265 (HEVC CPU)",
            "hevc_nvenc (NVIDIA HEVC)",
            "hevc_amf (AMD HEVC)",
            "hevc_qsv (Intel HEVC)",
            "mp4v",
        ]

    def test_get_codec_info_by_id(self) -> None:
        """Поиск по codec id возвращает ожидаемый объект."""
        codec = get_codec_info_by_id("h264_nvenc")
        assert codec is not None
        assert codec.display_name == "h264_nvenc (NVIDIA GPU)"
        assert codec.hardware_acceleration is True

        amf_codec = get_codec_info_by_id("h264_amf")
        assert amf_codec is not None
        assert amf_codec.display_name == "h264_amf (AMD GPU)"
        assert amf_codec.hardware_acceleration is True

        qsv_hevc = get_codec_info_by_id("hevc_qsv")
        assert qsv_hevc is not None
        assert qsv_hevc.hardware_acceleration is True

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

    def test_is_hardware_accelerated(self) -> None:
        """Проверка распознавания аппаратно-ускоренных кодеков."""
        assert is_hardware_accelerated("h264_nvenc") is True
        assert is_hardware_accelerated("h264_amf") is True
        assert is_hardware_accelerated("h264_qsv") is True
        assert is_hardware_accelerated("hevc_nvenc") is True
        assert is_hardware_accelerated("hevc_amf") is True
        assert is_hardware_accelerated("hevc_qsv") is True
        assert is_hardware_accelerated("libx264") is False
        assert is_hardware_accelerated("libx265") is False
        assert is_hardware_accelerated("unknown") is False

    def test_get_software_fallback_codec(self) -> None:
        """Проверка определения безопасного программного кодека для fallback."""
        assert get_software_fallback_codec("h264_nvenc") == "libx264"
        assert get_software_fallback_codec("h264_amf") == "libx264"
        assert get_software_fallback_codec("h264_qsv") == "libx264"
        assert get_software_fallback_codec("hevc_nvenc") == "libx265"
        assert get_software_fallback_codec("hevc_amf") == "libx265"
        assert get_software_fallback_codec("hevc_qsv") == "libx265"
        assert get_software_fallback_codec("libx264") == "libx264"
        assert get_software_fallback_codec("libx265") == "libx265"
