"""Тесты soak-скрипта: чистая логика отчёта и оценки (#174)."""

import importlib.util
from pathlib import Path
from typing import Any

import numpy as np
import pytest


@pytest.fixture
def soak_module() -> Any:
    """Загрузить scripts/soak_test.py как модуль."""
    spec = importlib.util.spec_from_file_location(
        "soak_test", Path("scripts") / "soak_test.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBuildFrame:
    """Синтетические кадры soak-записи (#174)."""

    def test_frame_shape_and_dtype(self, soak_module: Any) -> None:
        """Кадр имеет форму (H, W, 3) и тип uint8."""
        frame = soak_module.build_frame(0, 320, 200)

        assert frame.shape == (200, 320, 3)
        assert frame.dtype == np.uint8

    def test_frames_differ_over_time(self, soak_module: Any) -> None:
        """Кадры со временем сдвигаются — поток не «застревает»."""
        first = soak_module.build_frame(0, 320, 200)
        later = soak_module.build_frame(160, 320, 200)

        assert not np.array_equal(first, later)

    def test_frame_wraps_around(self, soak_module: Any) -> None:
        """Сдвиг периодичен: кадр 0 и кадр W совпадают."""
        first = soak_module.build_frame(0, 320, 200)
        wrapped = soak_module.build_frame(320, 320, 200)

        assert np.array_equal(first, wrapped)


class TestRssGrowth:
    """Оценка роста RSS по замерам (#174)."""

    def test_growth_mb_per_min(self, soak_module: Any) -> None:
        """50 МБ за минуту — 50 МБ/мин."""
        samples = [(0.0, 100.0), (60.0, 150.0)]

        assert soak_module.rss_growth_mb_per_min(samples) == 50.0

    def test_negative_growth(self, soak_module: Any) -> None:
        """Уменьшение RSS даёт отрицательную скорость."""
        samples = [(0.0, 200.0), (120.0, 150.0)]

        assert soak_module.rss_growth_mb_per_min(samples) == -25.0

    def test_insufficient_samples(self, soak_module: Any) -> None:
        """Меньше двух замеров — оценка невозможна."""
        assert soak_module.rss_growth_mb_per_min([]) is None
        assert soak_module.rss_growth_mb_per_min([(0.0, 100.0)]) is None

    def test_zero_interval(self, soak_module: Any) -> None:
        """Нулевой интервал времени — оценка невозможна."""
        samples = [(10.0, 100.0), (10.0, 150.0)]

        assert soak_module.rss_growth_mb_per_min(samples) is None


class TestEvaluateSoakChecks:
    """Проверка отчёта soak-теста на деградацию (#174)."""

    def _good_report(self, soak_module: Any) -> dict[str, Any]:
        """Валидный отчёт без деградации."""
        return {
            "closed_ok": True,
            "expected_duration_s": 60.0,
            "frames_written": 1800,
            "target_frames": 1800,
            "integrity": {"valid": True, "duration_s": 60.2},
            "rss_growth_mb_per_min": 1.5,
        }

    def test_clean_report_passes(self, soak_module: Any) -> None:
        """Валидный отчёт не даёт нарушений."""
        assert (
            soak_module.evaluate_soak_checks(self._good_report(soak_module))
            == []
        )

    def test_broken_finalization_detected(self, soak_module: Any) -> None:
        """Ошибка финализации обнаруживается."""
        report = self._good_report(soak_module)
        report["closed_ok"] = False

        failures = soak_module.evaluate_soak_checks(report)

        assert any("Финализация" in f for f in failures)

    def test_integrity_failure_detected(self, soak_module: Any) -> None:
        """Провал проверки целостности обнаруживается."""
        report = self._good_report(soak_module)
        report["integrity"] = {"valid": False, "error": "moov not found"}

        failures = soak_module.evaluate_soak_checks(report)

        assert any("целостности" in f for f in failures)

    def test_duration_drift_detected(self, soak_module: Any) -> None:
        """Дрейф длительности сверх допуска обнаруживается."""
        report = self._good_report(soak_module)
        report["integrity"] = {"valid": True, "duration_s": 45.0}

        failures = soak_module.evaluate_soak_checks(report)

        assert any("Дрейф" in f for f in failures)

    def test_frame_loss_detected(self, soak_module: Any) -> None:
        """Потеря кадров сверх 2% обнаруживается."""
        report = self._good_report(soak_module)
        report["frames_written"] = 1700

        failures = soak_module.evaluate_soak_checks(report)

        assert any("кадров" in f for f in failures)

    def test_rss_leak_detected(self, soak_module: Any) -> None:
        """Рост RSS выше порога обнаруживается."""
        report = self._good_report(soak_module)
        report["rss_growth_mb_per_min"] = 25.0

        failures = soak_module.evaluate_soak_checks(report)

        assert any("RSS" in f for f in failures)

    def test_missing_duration_detected(self, soak_module: Any) -> None:
        """Отсутствие длительности от ffprobe обнаруживается."""
        report = self._good_report(soak_module)
        report["integrity"] = {"valid": True, "duration_s": None}

        failures = soak_module.evaluate_soak_checks(report)

        assert any("длительность" in f for f in failures)


class TestBenchmarkPercentile:
    """Персентили и пороги бенчмарка hot-path (#173)."""

    def test_percentile_basic(self, soak_module: Any) -> None:
        """Персентиль отсортированного списка."""
        import importlib.util
        from pathlib import Path as PathLib

        spec = importlib.util.spec_from_file_location(
            "benchmark_hot_path", PathLib("scripts") / "benchmark_hot_path.py"
        )
        assert spec is not None and spec.loader is not None
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)

        assert bench.percentile([], 0.99) == 0.0
        assert bench.percentile([1.0, 2.0, 3.0], 0.5) == 2.0
        assert bench.percentile([1.0, 2.0, 3.0, 4.0], 0.99) == 4.0

    def test_evaluate_clean_report_passes(self, soak_module: Any) -> None:
        """Отчёт в пределах порогов не даёт нарушений."""
        import importlib.util
        from pathlib import Path as PathLib

        spec = importlib.util.spec_from_file_location(
            "benchmark_hot_path", PathLib("scripts") / "benchmark_hot_path.py"
        )
        assert spec is not None and spec.loader is not None
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)

        report = {
            "fps": 30,
            "elapsed_s": 60.0,
            "frames_written": 1800,
            "write_p99_ms": 12.0,
            "slow_write_ratio": 0.01,
            "rss_peak_mb": 300.0,
        }
        assert bench.evaluate_benchmark(report) == []

    def test_evaluate_fps_regression_detected(self, soak_module: Any) -> None:
        """Просадка FPS обнаруживается."""
        import importlib.util
        from pathlib import Path as PathLib

        spec = importlib.util.spec_from_file_location(
            "benchmark_hot_path", PathLib("scripts") / "benchmark_hot_path.py"
        )
        assert spec is not None and spec.loader is not None
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)

        report = {"fps": 30, "elapsed_s": 60.0, "frames_written": 1500}
        failures = bench.evaluate_benchmark(report)
        assert any("FPS" in f for f in failures)

    def test_evaluate_p99_and_rss_detected(self, soak_module: Any) -> None:
        """Превышение p99 и RSS обнаруживается."""
        import importlib.util
        from pathlib import Path as PathLib

        spec = importlib.util.spec_from_file_location(
            "benchmark_hot_path", PathLib("scripts") / "benchmark_hot_path.py"
        )
        assert spec is not None and spec.loader is not None
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)

        report = {
            "fps": 30,
            "elapsed_s": 60.0,
            "frames_written": 1800,
            "write_p99_ms": 40.0,
            "slow_write_ratio": 0.10,
            "rss_peak_mb": 900.0,
        }
        failures = bench.evaluate_benchmark(report)
        assert len(failures) == 3
