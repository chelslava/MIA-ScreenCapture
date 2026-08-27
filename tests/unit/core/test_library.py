"""
Unit-тесты для библиотеки записей (Issue #119).
==============================================
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.library.manager import LibraryManager
from core.library.models import RecordingMetadata
from core.library.scanner import extract_video_metadata, generate_thumbnail


def test_recording_metadata_model(tmp_path: Path) -> None:
    """Проверка свойств и сериализации модели RecordingMetadata."""
    video = tmp_path / "rec_2026.mp4"
    meta = RecordingMetadata(
        path=video,
        duration_sec=125.5,
        size_bytes=10485760,  # 10 MB
        width=1920,
        height=1080,
        fps=60.0,
        codec="h264",
        audio_codec="aac",
        created_at="2026-08-28T00:00:00",
        tags=["игры", "stream"],
    )

    assert meta.filename == "rec_2026.mp4"
    assert meta.resolution_str == "1920x1080"
    assert meta.duration_str == "02:05"
    assert "10.0 MB" in meta.size_mb_str

    data = meta.to_dict()
    assert data["filename"] == "rec_2026.mp4"
    assert data["tags"] == ["игры", "stream"]

    restored = RecordingMetadata.from_dict(data)
    assert restored.path == video
    assert restored.duration_sec == 125.5
    assert restored.tags == ["игры", "stream"]


def test_extract_video_metadata_with_ffprobe(tmp_path: Path) -> None:
    """Проверка извлечения метаданных через замоканный ffprobe."""
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"dummy")

    fake_ffprobe_out = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 2560,
                "height": 1440,
                "r_frame_rate": "60/1",
                "duration": "45.0",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
            },
        ],
        "format": {"duration": "45.0"},
    }

    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = json.dumps(fake_ffprobe_out)

    with patch("subprocess.run", return_value=mock_run):
        meta = extract_video_metadata(video)

    assert meta.width == 2560
    assert meta.height == 1440
    assert meta.fps == 60.0
    assert meta.codec == "h264"
    assert meta.audio_codec == "aac"
    assert meta.duration_sec == 45.0


def test_generate_thumbnail_success(tmp_path: Path) -> None:
    """Генерация превью-изображения через замоканный ffmpeg."""
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"dummy")
    thumbs_dir = tmp_path / "thumbs"

    def side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
        out_file = Path(cmd[-1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"fake png data")
        res = MagicMock()
        res.returncode = 0
        return res

    with patch("subprocess.run", side_effect=side_effect):
        thumb = generate_thumbnail(video, thumbs_dir)

    assert thumb is not None
    assert thumb.exists()
    assert thumb.name == "sample_thumb.png"


def test_library_manager_scan_directory(tmp_path: Path) -> None:
    """Сканирование директории и добавление записей в менеджер."""
    lib_file = tmp_path / "library.json"
    thumbs_dir = tmp_path / "thumbs"
    records_dir = tmp_path / "records"
    records_dir.mkdir()

    (records_dir / "vid1.mp4").write_bytes(b"vid1")
    (records_dir / "vid2.mkv").write_bytes(b"vid2")
    (records_dir / "other.txt").write_bytes(b"text")

    mgr = LibraryManager(library_file=lib_file, thumbs_dir=thumbs_dir)

    with (
        patch("core.library.manager.extract_video_metadata") as mock_extract,
        patch("core.library.manager.generate_thumbnail", return_value=None),
    ):
        mock_extract.side_effect = lambda p: RecordingMetadata(
            path=p, duration_sec=10.0
        )
        added = mgr.scan_directory(records_dir)

    assert added == 2
    items = mgr.get_items()
    assert len(items) == 2
    assert lib_file.exists()


def test_library_manager_filtering_and_sorting(tmp_path: Path) -> None:
    """Поиск, фильтрация по тегам и сортировка записей."""
    lib_file = tmp_path / "library.json"
    mgr = LibraryManager(library_file=lib_file)

    v1 = tmp_path / "game_play.mp4"
    v2 = tmp_path / "tutorial_python.mp4"
    v3 = tmp_path / "meeting_work.mp4"

    for v in (v1, v2, v3):
        v.write_bytes(b"data")

    with (
        patch("core.library.manager.extract_video_metadata") as mock_extract,
        patch("core.library.manager.generate_thumbnail", return_value=None),
    ):
        mock_extract.side_effect = lambda p: RecordingMetadata(
            path=p,
            duration_sec=100.0
            if "game" in p.name
            else (50.0 if "tutorial" in p.name else 200.0),
            size_bytes=1000 if "game" in p.name else 5000,
            created_at="2026-01-01" if "game" in p.name else "2026-02-01",
        )
        mgr.add_recording(v1, tags=["game", "fun"])
        mgr.add_recording(v2, tags=["work", "code"])
        mgr.add_recording(v3, tags=["work", "call"])

    # Поиск по строке
    search_res = mgr.get_items(query="tutorial")
    assert len(search_res) == 1
    assert search_res[0].filename == "tutorial_python.mp4"

    # Фильтр по тегу
    work_res = mgr.get_items(tag="work")
    assert len(work_res) == 2

    # Список всех тегов
    all_tags = mgr.get_all_tags()
    assert set(all_tags) == {"game", "fun", "work", "code", "call"}

    # Сортировка по длительности (убывание)
    sorted_dur = mgr.get_items(sort_by="duration", sort_desc=True)
    assert sorted_dur[0].filename == "meeting_work.mp4"
    assert sorted_dur[-1].filename == "tutorial_python.mp4"


def test_library_manager_tag_and_delete(tmp_path: Path) -> None:
    """Добавление/удаление тегов и удаление записи."""
    lib_file = tmp_path / "library.json"
    mgr = LibraryManager(library_file=lib_file)

    v1 = tmp_path / "test.mp4"
    v1.write_bytes(b"dummy")

    with (
        patch(
            "core.library.manager.extract_video_metadata",
            return_value=RecordingMetadata(path=v1),
        ),
        patch("core.library.manager.generate_thumbnail", return_value=None),
    ):
        mgr.add_recording(v1)

    assert mgr.add_tag(v1, "newtag") is True
    item = mgr.get_item_by_path(v1)
    assert item is not None and "newtag" in item.tags

    assert mgr.remove_tag(v1, "newtag") is True
    assert "newtag" not in item.tags

    # Удаление записи
    assert mgr.delete_recording(v1, delete_file=True) is True
    assert not v1.exists()
    assert mgr.get_item_by_path(v1) is None
