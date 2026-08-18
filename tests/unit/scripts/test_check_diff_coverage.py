"""Unit-тесты для scripts/check_diff_coverage.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_diff_coverage import (
    _get_changed_python_files,
    _is_production_python_file,
    _load_coverage_map,
    _normalize_path,
    _resolve_base_sha,
    main,
)


class TestNormalizePath:
    """Тесты нормализации путей."""

    def test_replaces_backslashes(self) -> None:
        assert (
            _normalize_path("gui\\views\\main_view.py")
            == "gui/views/main_view.py"
        )

    def test_strips_leading_dot_slash(self) -> None:
        assert _normalize_path("./core/profiles.py") == "core/profiles.py"
        assert (
            _normalize_path(".\\recorder\\video_recorder.py")
            == "recorder/video_recorder.py"
        )


class TestIsProductionPythonFile:
    """Тесты фильтрации production Python файлов."""

    def test_matches_production_prefixes(self) -> None:
        assert _is_production_python_file("api/routes.py") is True
        assert _is_production_python_file("cli/parser.py") is True
        assert _is_production_python_file("core/profiles.py") is True
        assert _is_production_python_file("gui/main_window.py") is True
        assert _is_production_python_file("recorder/encoder.py") is True
        assert (
            _is_production_python_file("scheduler/task_scheduler.py") is True
        )

    def test_matches_production_single_files(self) -> None:
        assert _is_production_python_file("main.py") is True
        assert _is_production_python_file("config.py") is True
        assert _is_production_python_file("logger_config.py") is True
        assert _is_production_python_file("exceptions.py") is True
        assert _is_production_python_file("utils.py") is True

    def test_ignores_non_python_and_test_files(self) -> None:
        assert _is_production_python_file("README.md") is False
        assert _is_production_python_file("tests/unit/test_config.py") is False
        assert (
            _is_production_python_file("scripts/check_diff_coverage.py")
            is False
        )
        assert _is_production_python_file("pyproject.toml") is False
        assert _is_production_python_file("gui/views/__init__.py") is False
        assert _is_production_python_file("__init__.py") is False


class TestResolveBaseSha:
    """Тесты разрешения base SHA."""

    def test_uses_provided_base_sha(self) -> None:
        assert _resolve_base_sha("abc1234", "HEAD") == "abc1234"

    def test_ignores_zero_sha_and_calls_git(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="fedcba9\n")
            result = _resolve_base_sha(
                "0000000000000000000000000000000000000000", "HEAD"
            )
            assert result == "fedcba9"
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "HEAD~1"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_raises_when_git_fails(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            with pytest.raises(
                RuntimeError, match="Не удалось определить base SHA"
            ):
                _resolve_base_sha("", "HEAD")

    def test_raises_when_git_returns_empty(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="  \n")
            with pytest.raises(RuntimeError, match="Получен пустой base SHA"):
                _resolve_base_sha("", "HEAD")


class TestGetChangedPythonFiles:
    """Тесты получения списка изменённых Python-файлов."""

    def test_returns_filtered_production_files(self) -> None:
        diff_output = "core/profiles.py\ntests/unit/test_profiles.py\nREADME.md\nmain.py\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=diff_output)
            changed = _get_changed_python_files("base", "head")
            assert changed == ["core/profiles.py", "main.py"]

    def test_fallback_when_first_git_fails(self) -> None:
        with patch("subprocess.run") as mock_run:
            # First diff fails, rev-parse succeeds, fallback diff succeeds
            mock_run.side_effect = [
                subprocess.CalledProcessError(1, "git diff"),
                MagicMock(stdout="fallback_base\n"),
                MagicMock(stdout="api/routes.py\n"),
            ]
            changed = _get_changed_python_files("invalid_base", "head")
            assert changed == ["api/routes.py"]

    def test_raises_when_fallback_also_fails(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CalledProcessError(1, "git diff"),
                subprocess.CalledProcessError(1, "git rev-parse"),
            ]
            with pytest.raises(
                RuntimeError, match="Не удалось получить список"
            ):
                _get_changed_python_files("invalid_base", "head")


class TestLoadCoverageMap:
    """Тесты загрузки coverage.json."""

    def test_loads_percent_covered_map(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(
            json.dumps(
                {
                    "files": {
                        "core\\profiles.py": {
                            "summary": {"percent_covered": 85.5}
                        },
                        "api/routes.py": {
                            "summary": {"percent_covered": 92.0}
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        cov_map = _load_coverage_map(cov_file)
        assert cov_map["core/profiles.py"] == 85.5
        assert cov_map["api/routes.py"] == 92.0


class TestMain:
    """Тесты функции main."""

    def test_returns_2_when_coverage_file_missing(
        self, tmp_path: Path
    ) -> None:
        missing_file = str(tmp_path / "non_existent.json")
        with patch(
            "sys.argv",
            ["check_diff_coverage.py", "--coverage-json", missing_file],
        ):
            assert main() == 2

    def test_returns_2_when_base_sha_error(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text("{}", encoding="utf-8")
        with (
            patch(
                "sys.argv",
                ["check_diff_coverage.py", "--coverage-json", str(cov_file)],
            ),
            patch(
                "scripts.check_diff_coverage._resolve_base_sha",
                side_effect=RuntimeError("base error"),
            ),
        ):
            assert main() == 2

    def test_returns_0_when_no_changed_files(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text("{}", encoding="utf-8")
        with (
            patch(
                "sys.argv",
                ["check_diff_coverage.py", "--coverage-json", str(cov_file)],
            ),
            patch(
                "scripts.check_diff_coverage._resolve_base_sha",
                return_value="base",
            ),
            patch(
                "scripts.check_diff_coverage._get_changed_python_files",
                return_value=[],
            ),
        ):
            assert main() == 0

    def test_returns_0_when_all_files_pass_threshold(
        self, tmp_path: Path
    ) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(
            json.dumps(
                {
                    "files": {
                        "core/profiles.py": {
                            "summary": {"percent_covered": 75.0}
                        },
                        "main.py": {"summary": {"percent_covered": 65.0}},
                    }
                }
            ),
            encoding="utf-8",
        )
        with (
            patch(
                "sys.argv",
                [
                    "check_diff_coverage.py",
                    "--coverage-json",
                    str(cov_file),
                    "--min-file-coverage",
                    "60",
                ],
            ),
            patch(
                "scripts.check_diff_coverage._resolve_base_sha",
                return_value="base",
            ),
            patch(
                "scripts.check_diff_coverage._get_changed_python_files",
                return_value=["core/profiles.py", "main.py"],
            ),
        ):
            assert main() == 0

    def test_returns_1_when_file_below_threshold(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(
            json.dumps(
                {
                    "files": {
                        "core/profiles.py": {
                            "summary": {"percent_covered": 55.0}
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        with (
            patch(
                "sys.argv",
                [
                    "check_diff_coverage.py",
                    "--coverage-json",
                    str(cov_file),
                    "--min-file-coverage",
                    "60",
                ],
            ),
            patch(
                "scripts.check_diff_coverage._resolve_base_sha",
                return_value="base",
            ),
            patch(
                "scripts.check_diff_coverage._get_changed_python_files",
                return_value=["core/profiles.py"],
            ),
        ):
            assert main() == 1
