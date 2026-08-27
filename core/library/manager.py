"""
Менеджер библиотеки медиазаписей MIA-ScreenCapture (Issue #119).
===============================================================

Предоставляет:
- сканирование директорий и обнаружение новых записей;
- извлечение метаданных и генерацию превью-изображений;
- фильтрацию, поиск в реальном времени и сортировку записей;
- управление тегами и коллекциями;
- персистентное хранение базы библиотеки в JSON.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from core.event_bus import EventBus
from core.library.models import RecordingMetadata
from core.library.scanner import extract_video_metadata, generate_thumbnail
from logger_config import get_module_logger

logger = get_module_logger(__name__)

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".avi", ".mov"}


class LibraryManager:
    """Централизованный менеджер библиотеки медиафайлов."""

    def __init__(
        self,
        library_file: Path | None = None,
        thumbs_dir: Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._library_file = library_file or Path("config/library.json")
        self._thumbs_dir = thumbs_dir or Path("config/thumbs")
        self._event_bus = event_bus
        self._items: dict[str, RecordingMetadata] = {}
        self._lock = threading.RLock()
        self._load()

    @property
    def library_file(self) -> Path:
        """Путь к файлу базы данных библиотеки."""
        return self._library_file

    @property
    def thumbs_dir(self) -> Path:
        """Директория хранения превью."""
        return self._thumbs_dir

    def scan_directory(self, directory: Path) -> int:
        """
        Сканирует указанную директорию на наличие видеозаписей и обновляет базу.

        Args:
            directory: Директория с записями.

        Returns:
            Количество добавленных или обновлённых записей.
        """
        if not directory.exists() or not directory.is_dir():
            return 0

        updated_count = 0
        with self._lock:
            for file_path in directory.iterdir():
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
                ):
                    key = str(file_path.resolve())
                    existing = self._items.get(key)
                    if existing is None:
                        meta = extract_video_metadata(file_path)
                        thumb = generate_thumbnail(file_path, self._thumbs_dir)
                        meta.thumbnail_path = thumb
                        self._items[key] = meta
                        updated_count += 1
                    elif (
                        existing.thumbnail_path is None
                        or not existing.thumbnail_path.exists()
                    ):
                        existing.thumbnail_path = generate_thumbnail(
                            file_path, self._thumbs_dir
                        )
            if updated_count > 0:
                self._save()
        return updated_count

    def add_recording(
        self,
        video_path: Path,
        tags: list[str] | None = None,
    ) -> RecordingMetadata:
        """
        Добавляет одну видеозапись в библиотеку (вызывается после завершения записи).

        Args:
            video_path: Путь к видеозаписи.
            tags: Начальный список тегов.

        Returns:
            Созданный объект RecordingMetadata.
        """
        resolved = video_path.resolve()
        key = str(resolved)
        with self._lock:
            meta = extract_video_metadata(video_path)
            if tags:
                meta.tags = list(set(tags))
            meta.thumbnail_path = generate_thumbnail(
                video_path, self._thumbs_dir
            )
            self._items[key] = meta
            self._save()
            logger.info("Запись %s добавлена в библиотеку", video_path.name)
            return meta

    def get_items(
        self,
        query: str | None = None,
        tag: str | None = None,
        sort_by: str = "date",
        sort_desc: bool = True,
    ) -> list[RecordingMetadata]:
        """
        Возвращает список записей с фильтрацией и поиском.

        Args:
            query: Строка поиска по имени файла.
            tag: Фильтр по тегу.
            sort_by: Поле сортировки ('date', 'name', 'duration', 'size').
            sort_desc: Направление сортировки (True — по убыванию).

        Returns:
            Отфильтрованный и отсортированный список RecordingMetadata.
        """
        with self._lock:
            items = list(self._items.values())

            # Фильтрация по поисковому запросу
            if query:
                q_clean = query.strip().lower()
                items = [
                    it
                    for it in items
                    if q_clean in it.filename.lower()
                    or any(q_clean in t.lower() for t in it.tags)
                ]

            # Фильтрация по тегу
            if tag:
                t_clean = tag.strip().lower()
                items = [
                    it
                    for it in items
                    if any(t.lower() == t_clean for t in it.tags)
                ]

            # Сортировка
            if sort_by == "name":
                items.sort(
                    key=lambda it: it.filename.lower(), reverse=sort_desc
                )
            elif sort_by == "duration":
                items.sort(key=lambda it: it.duration_sec, reverse=sort_desc)
            elif sort_by == "size":
                items.sort(key=lambda it: it.size_bytes, reverse=sort_desc)
            else:  # date
                items.sort(key=lambda it: it.created_at, reverse=sort_desc)

            return items

    def get_item_by_path(self, path: Path | str) -> RecordingMetadata | None:
        """Возвращает метаданные записи по пути к файлу."""
        key = str(Path(path).resolve())
        with self._lock:
            return self._items.get(key)

    def add_tag(self, path: Path | str, tag: str) -> bool:
        """Добавляет тег к записи."""
        clean_tag = tag.strip()
        if not clean_tag:
            return False
        with self._lock:
            item = self.get_item_by_path(path)
            if not item:
                return False
            if clean_tag not in item.tags:
                item.tags.append(clean_tag)
                self._save()
            return True

    def remove_tag(self, path: Path | str, tag: str) -> bool:
        """Удаляет тег из записи."""
        clean_tag = tag.strip()
        with self._lock:
            item = self.get_item_by_path(path)
            if not item or clean_tag not in item.tags:
                return False
            item.tags.remove(clean_tag)
            self._save()
            return True

    def get_all_tags(self) -> list[str]:
        """Возвращает список всех уникальных тегов в библиотеке."""
        with self._lock:
            all_tags: set[str] = set()
            for it in self._items.values():
                all_tags.update(it.tags)
            return sorted(all_tags)

    def delete_recording(
        self,
        path: Path | str,
        delete_file: bool = True,
    ) -> bool:
        """
        Удаляет запись из библиотеки и опционально физический файл с диска.

        Args:
            path: Путь к файлу.
            delete_file: Удалять ли физический видеофайл и превью.

        Returns:
            True при успешном удалении.
        """
        p = Path(path).resolve()
        key = str(p)
        with self._lock:
            item = self._items.pop(key, None)
            if delete_file:
                if p.exists():
                    try:
                        p.unlink()
                    except OSError as e:
                        logger.error("Не удалось удалить файл %s: %s", p, e)
                if (
                    item
                    and item.thumbnail_path
                    and item.thumbnail_path.exists()
                ):
                    try:
                        item.thumbnail_path.unlink()
                    except OSError:
                        pass
            self._save()
            return True

    def _load(self) -> None:
        """Загрузка базы из JSON."""
        if not self._library_file.exists():
            return
        try:
            with open(self._library_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and "path" in entry:
                        meta = RecordingMetadata.from_dict(entry)
                        self._items[str(meta.path.resolve())] = meta
        except Exception as e:
            logger.warning("Не удалось загрузить библиотеку записей: %s", e)

    def _save(self) -> None:
        """Сохранение базы в JSON."""
        try:
            self._library_file.parent.mkdir(parents=True, exist_ok=True)
            payload = [it.to_dict() for it in self._items.values()]
            with open(self._library_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Не удалось сохранить библиотеку записей: %s", e)
