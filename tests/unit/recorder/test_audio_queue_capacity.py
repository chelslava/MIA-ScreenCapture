"""Тесты настройки audio queue capacity (#86)."""

import queue

from recorder.audio_recorder import (
    _AUDIO_QUEUE_MAX_CHUNKS,
    AudioRecorder,
)


class TestAudioQueueCapacity:
    """Проверка параметризации максимального размера очереди (#86)."""

    def test_default_capacity_increased_to_2048(self) -> None:
        """Дефолт очереди поднят с 256 до 2048 чанков (~23с буфера)."""
        assert _AUDIO_QUEUE_MAX_CHUNKS == 2048

    def test_default_queue_capacity_is_2048(self) -> None:
        """`AudioRecorder()` без параметров создаёт очередь на 2048 чанков."""
        rec = AudioRecorder()
        assert rec._audio_queue_max_chunks == 2048
        assert rec._audio_queue.maxsize == 2048

    def test_custom_queue_capacity(self) -> None:
        """Явное значение `audio_queue_max_chunks` уважается."""
        rec = AudioRecorder(audio_queue_max_chunks=512)
        assert rec._audio_queue_max_chunks == 512
        assert rec._audio_queue.maxsize == 512

    def test_min_capacity_clamped(self) -> None:
        """Слишком малое значение (>0) clampится до 8."""
        rec = AudioRecorder(audio_queue_max_chunks=1)
        assert rec._audio_queue_max_chunks == 8
        assert rec._audio_queue.maxsize == 8

    def test_queue_capacity_round_trip(self) -> None:
        """Очередь действительно использует кастомное значение maxsize."""
        rec = AudioRecorder(audio_queue_max_chunks=64)
        # Проверяем, что очередь принимает ровно 64 чанка до Full
        for _ in range(64):
            rec._audio_queue.put_nowait((b"x" * 64, 16))
        try:
            rec._audio_queue.put_nowait((b"y" * 64, 16))
            raise AssertionError("Должен быть queue.Full на 65-м чанке")
        except queue.Full:
            pass
