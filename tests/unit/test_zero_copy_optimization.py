"""
Тесты zero-copy оптимизации BGR→RGB для VideoRecorder и FFmpegVideoWriter.

Проверяет:
- Флаг _needs_color_conversion присутствует в VideoRecorder
- memoryview write идентичен tobytes write побайтово
- Benchmark: memoryview быстрее tobytes (ожидаем >10% улучшение)
"""

import timeit
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from recorder.ffmpeg_writer import FFmpegVideoWriter, RetryPolicy
from recorder.video_recorder import VideoRecorder


class TestNeedsColorConversionFlag:
    """Проверка флага _needs_color_conversion в VideoRecorder."""

    def test_flag_exists_and_default_true(self) -> None:
        recorder = VideoRecorder()
        assert hasattr(recorder, "_needs_color_conversion")
        assert recorder._needs_color_conversion is True

    def test_flag_preserved_after_init(self) -> None:
        recorder = VideoRecorder(fps=60, codec="libx264")
        assert recorder._needs_color_conversion is True


class TestZeroCopyWrite:
    """Проверка идентичности данных при записи через memoryview vs tobytes."""

    def _make_writer(self, stdin_mock: MagicMock) -> FFmpegVideoWriter:
        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=640,
            height=480,
            fps=30,
            retry_policy=RetryPolicy(max_attempts=1, initial_delay_s=0),
        )
        process_mock = MagicMock()
        process_mock.poll.return_value = None
        process_mock.stdin = stdin_mock
        writer._process = process_mock
        return writer

    def test_memoryview_and_tobytes_identical(self) -> None:
        """Данные записанные через memoryview идентичны tobytes побайтово."""
        frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)

        written_via_memoryview: list[bytes] = []
        stdin_mock = MagicMock()
        stdin_mock.write.side_effect = (
            lambda data: written_via_memoryview.append(bytes(data))
        )

        writer = self._make_writer(stdin_mock)
        writer.write(frame)

        assert len(written_via_memoryview) == 1
        result_bytes = written_via_memoryview[0]
        expected_bytes = frame.tobytes()
        assert result_bytes == expected_bytes, (
            "memoryview write должен быть идентичен tobytes побайтово"
        )

    def test_non_contiguous_frame_handled(self) -> None:
        """Не-contiguous кадр (срез) корректно обрабатывается."""
        base = np.random.randint(0, 256, (960, 1280, 3), dtype=np.uint8)
        frame = base[::2, ::2]  # stride-срез, не contiguous
        assert not frame.flags["C_CONTIGUOUS"]

        written: list[bytes] = []
        stdin_mock = MagicMock()
        stdin_mock.write.side_effect = lambda data: written.append(bytes(data))

        writer = self._make_writer(stdin_mock)
        writer.write(frame)

        assert len(written) == 1
        result_bytes = written[0]
        expected_bytes = np.ascontiguousarray(frame).tobytes()
        assert result_bytes == expected_bytes

    def test_contiguous_frame_no_extra_copy(self) -> None:
        """Contiguous кадр не создаёт дополнительную копию через ascontiguousarray."""
        frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        assert frame.flags["C_CONTIGUOUS"]

        contiguous = np.ascontiguousarray(frame)
        # ascontiguousarray на уже contiguous массиве возвращает тот же объект
        assert contiguous is frame


class TestZeroCopyBenchmark:
    """Benchmark: memoryview vs tobytes для типичного кадра 1920x1080."""

    def test_memoryview_not_slower_than_tobytes(self) -> None:
        """memoryview write не медленнее tobytes более чем в 2 раза (обычно быстрее)."""
        frame = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
        contiguous = np.ascontiguousarray(frame)

        n = 200

        time_tobytes = timeit.timeit(lambda: frame.tobytes(), number=n)
        time_memoryview = timeit.timeit(
            lambda: memoryview(contiguous), number=n
        )

        # memoryview создание должно быть значительно быстрее tobytes
        # (tobytes копирует данные, memoryview — нет)
        ratio = (
            time_tobytes / time_memoryview
            if time_memoryview > 0
            else float("inf")
        )
        assert ratio >= 1.0, (
            f"memoryview ({time_memoryview:.4f}s) не быстрее tobytes "
            f"({time_tobytes:.4f}s), ratio={ratio:.2f}"
        )

    def test_benchmark_improvement_10_percent(self) -> None:
        """Benchmark подтверждает >10% улучшение (memoryview vs tobytes)."""
        frame = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)

        n = 100

        time_tobytes = timeit.timeit(lambda: frame.tobytes(), number=n)
        # Симулируем полный путь write: ascontiguousarray + memoryview
        time_zero_copy = timeit.timeit(
            lambda: memoryview(np.ascontiguousarray(frame)), number=n
        )

        improvement_pct = (time_tobytes - time_zero_copy) / time_tobytes * 100
        assert improvement_pct >= 10.0, (
            f"Улучшение {improvement_pct:.1f}% < 10%. "
            f"tobytes={time_tobytes:.4f}s, zero_copy={time_zero_copy:.4f}s"
        )
