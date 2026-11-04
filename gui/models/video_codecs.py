"""Единый источник данных о доступных видеокодеках GUI."""

from dataclasses import dataclass

DEFAULT_CODEC_ID = "libx264"


@dataclass(frozen=True, slots=True)
class CodecInfo:
    """Описание доступного видеокодека."""

    codec_id: str
    display_name: str
    description: str
    hardware_acceleration: bool = False


AVAILABLE_VIDEO_CODECS: tuple[CodecInfo, ...] = (
    CodecInfo(
        codec_id="libx264",
        display_name="libx264 (CPU)",
        description="Программный кодек H.264.",
    ),
    CodecInfo(
        codec_id="h264_nvenc",
        display_name="h264_nvenc (NVIDIA GPU)",
        description="Аппаратное кодирование NVIDIA H.264.",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="h264_amf",
        display_name="h264_amf (AMD GPU)",
        description="Аппаратное кодирование AMD AMF H.264.",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="h264_qsv",
        display_name="h264_qsv (Intel GPU)",
        description="Аппаратное кодирование Intel Quick Sync H.264.",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="libx265",
        display_name="libx265 (HEVC CPU)",
        description="Программный кодек H.265/HEVC.",
    ),
    CodecInfo(
        codec_id="hevc_nvenc",
        display_name="hevc_nvenc (NVIDIA HEVC)",
        description="Аппаратное кодирование NVIDIA HEVC.",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="hevc_amf",
        display_name="hevc_amf (AMD HEVC)",
        description="Аппаратное кодирование AMD AMF HEVC.",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="hevc_qsv",
        display_name="hevc_qsv (Intel HEVC)",
        description="Аппаратное кодирование Intel Quick Sync HEVC.",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="av1_nvenc",
        display_name="av1_nvenc (NVIDIA AV1)",
        description="Аппаратное кодирование NVIDIA AV1 (RTX 40xx+).",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="av1_amf",
        display_name="av1_amf (AMD AV1)",
        description="Аппаратное кодирование AMD AV1 (RX 7000+).",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="av1_qsv",
        display_name="av1_qsv (Intel AV1)",
        description="Аппаратное кодирование Intel Quick Sync AV1 (Arc+).",
        hardware_acceleration=True,
    ),
    CodecInfo(
        codec_id="mp4v",
        display_name="mp4v",
        description="MPEG-4 Visual.",
    ),
)

_CODEC_BY_ID = {codec.codec_id: codec for codec in AVAILABLE_VIDEO_CODECS}
_CODEC_BY_DISPLAY_NAME = {
    codec.display_name: codec for codec in AVAILABLE_VIDEO_CODECS
}


def get_available_codec_display_names() -> list[str]:
    """Вернуть display-имена кодеков в порядке показа в UI."""

    return [codec.display_name for codec in AVAILABLE_VIDEO_CODECS]


def get_codec_info_by_id(codec_id: str) -> CodecInfo | None:
    """Найти описание кодека по идентификатору."""

    return _CODEC_BY_ID.get(codec_id)


def get_codec_info_by_display_name(display_name: str) -> CodecInfo | None:
    """Найти описание кодека по display-имени."""

    return _CODEC_BY_DISPLAY_NAME.get(display_name)


def codec_id_from_display_name(display_name: str) -> str:
    """Преобразовать display-имя в идентификатор кодека."""

    codec = get_codec_info_by_display_name(display_name)
    if codec is None:
        return DEFAULT_CODEC_ID
    return codec.codec_id


def display_name_from_codec_id(codec_id: str) -> str:
    """Преобразовать идентификатор кодека в display-имя."""

    codec = get_codec_info_by_id(codec_id)
    if codec is None:
        return _CODEC_BY_ID[DEFAULT_CODEC_ID].display_name
    return codec.display_name


def is_hardware_accelerated(codec_id: str) -> bool:
    """Проверить, является ли кодек аппаратно-ускоренным (GPU)."""

    info = get_codec_info_by_id(codec_id)
    return bool(info and info.hardware_acceleration)


def get_software_fallback_codec(codec_id: str) -> str:
    """Получить безопасный программный аналог (fallback) для кодека."""

    if "hevc" in codec_id or "265" in codec_id:
        return "libx265"
    return "libx264"


# Программные кодеки, доступные без проверки железа (#168)
SOFTWARE_CODEC_IDS: frozenset[str] = frozenset({"libx264", "libx265", "mp4v"})


def filter_codec_display_names(
    supported_codec_ids: set[str] | None,
) -> list[str]:
    """Отфильтровать display-имена по реально доступным энкодерам (#168).

    Args:
        supported_codec_ids: Множество энкодеров из `ffmpeg -encoders`;
            `None` — проверка не удалась, вернуть полный список.

    Returns:
        Display-имена для UI: программные кодеки всегда, аппаратные —
        только при наличии в проверке.
    """
    names = get_available_codec_display_names()
    if supported_codec_ids is None:
        return names

    filtered = [
        codec.display_name
        for codec in AVAILABLE_VIDEO_CODECS
        if codec.codec_id in supported_codec_ids
        or codec.codec_id in SOFTWARE_CODEC_IDS
    ]
    return filtered or names
