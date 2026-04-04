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
