"""Unit-тесты для scripts/check_diff_coverage.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_diff_coverage import (
    _diff_coverage_percent,
    _is_production_python_file,
    _load_coverage_map,
    _normalize_path,
    _parse_changed_lines,
    _resolve_base_sha,
    _run_git_diff,
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


class TestRunGitDiff:
    """Тесты получения unified diff."""

    def test_returns_diff_stdout(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="diff text")
            assert _run_git_diff("base", "head") == "diff text"
            args = mock_run.call_args.args[0]
            assert args[:3] == ["git", "diff", "-U0"]
            assert "--no-color" in args
            assert args[-1] == "*.py"

    def test_raises_on_git_error(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            with pytest.raises(RuntimeError, match="Не удалось получить diff"):
                _run_git_diff("base", "head")


class TestParseChangedLines:
    """Тесты разбора добавленных строк из unified diff."""

    DIFF = (
        "diff --git a/core/profiles.py b/core/profiles.py\n"
        "index 111..222 100644\n"
        "--- a/core/profiles.py\n"
        "+++ b/core/profiles.py\n"
        "@@ -10,0 +11,3 @@ def foo():\n"
        "+line1\n"
        "+line2\n"
        "+line3\n"
        "diff --git a/tests/unit/test_x.py b/tests/unit/test_x.py\n"
        "index 333..444 100644\n"
        "--- a/tests/unit/test_x.py\n"
        "+++ b/tests/unit/test_x.py\n"
        "@@ -1,0 +2 @@\n"
        "+import os\n"
        "diff --git a/gui/old.py b/gui/old.py\n"
        "deleted file mode 100644\n"
        "--- a/gui/old.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-old1\n"
        "-old2\n"
    )

    def test_parses_added_lines_of_production_files(self) -> None:
        changed = _parse_changed_lines(self.DIFF)
        assert changed == {"core/profiles.py": {11, 12, 13}}

    def test_empty_diff_gives_no_files(self) -> None:
        assert _parse_changed_lines("") == {}

    def test_filters_non_production_files(self) -> None:
        diff = (
            "diff --git a/tests/unit/test_x.py b/tests/unit/test_x.py\n"
            "--- a/tests/unit/test_x.py\n"
            "+++ b/tests/unit/test_x.py\n"
            "@@ -1,0 +2 @@\n"
            "+import os\n"
        )
        assert _parse_changed_lines(diff) == {}

    def test_skips_deleted_files(self) -> None:
        diff = (
            "diff --git a/gui/old.py b/gui/old.py\n"
            "--- a/gui/old.py\n"
            "+++ /dev/null\n"
            "@@ -1,2 +0,0 @@\n"
            "-old1\n"
        )
        assert _parse_changed_lines(diff) == {}

    def test_single_line_hunk_without_count(self) -> None:
        diff = (
            "diff --git a/config.py b/config.py\n"
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -5,0 +6 @@\n"
            "+VALUE = 1\n"
        )
        assert _parse_changed_lines(diff) == {"config.py": {6}}


class TestLoadCoverageMap:
    """Тесты загрузки coverage.json."""

    def test_loads_line_sets(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(
            json.dumps(
                {
                    "files": {
                        "core\\profiles.py": {
                            "executed_lines": [1, 2, 11, 12],
                            "missing_lines": [13],
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        cov_map = _load_coverage_map(cov_file)
        assert cov_map["core/profiles.py"] == ({1, 2, 11, 12}, {13})

    def test_raises_when_no_line_data(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(
            json.dumps(
                {
                    "files": {
                        "core/profiles.py": {
                            "summary": {"percent_covered": 85.5}
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="построчных данных"):
            _load_coverage_map(cov_file)


class TestDiffCoveragePercent:
    """Расчёт покрытия изменённых строк."""

    def test_fully_covered(self) -> None:
        percent = _diff_coverage_percent({11, 12}, {11, 12}, set())
        assert percent == 100.0

    def test_partially_covered(self) -> None:
        percent = _diff_coverage_percent({11, 12, 13}, {11}, {12, 13})
        assert percent == pytest.approx(100 / 3)

    def test_no_executable_lines_returns_none(self) -> None:
        # Изменены только docstring/комментарии — их нет в coverage
        assert _diff_coverage_percent({11}, set(), set()) is None


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

    def test_returns_2_when_coverage_has_no_line_data(
        self, tmp_path: Path
    ) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(
            json.dumps(
                {
                    "files": {
                        "core/profiles.py": {
                            "summary": {"percent_covered": 85.5}
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        diff = (
            "diff --git a/core/profiles.py b/core/profiles.py\n"
            "--- a/core/profiles.py\n"
            "+++ b/core/profiles.py\n"
            "@@ -10,0 +11 @@\n"
            "+a\n"
        )
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
                "scripts.check_diff_coverage._run_git_diff",
                return_value=diff,
            ),
        ):
            assert main() == 2

    def test_returns_0_when_no_changed_lines(self, tmp_path: Path) -> None:
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
                "scripts.check_diff_coverage._run_git_diff",
                return_value="",
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
                            "executed_lines": [11, 12],
                            "missing_lines": [],
                        },
                        "main.py": {
                            "executed_lines": [20],
                            "missing_lines": [21, 22],
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        diff = (
            "diff --git a/core/profiles.py b/core/profiles.py\n"
            "--- a/core/profiles.py\n"
            "+++ b/core/profiles.py\n"
            "@@ -10,0 +11,2 @@\n"
            "+a\n"
            "+b\n"
            "diff --git a/main.py b/main.py\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -19,0 +20,3 @@\n"
            "+x\n"
            "+y\n"
            "+z\n"
        )
        with (
            patch(
                "sys.argv",
                [
                    "check_diff_coverage.py",
                    "--coverage-json",
                    str(cov_file),
                    "--min-file-coverage",
                    "30",
                ],
            ),
            patch(
                "scripts.check_diff_coverage._resolve_base_sha",
                return_value="base",
            ),
            patch(
                "scripts.check_diff_coverage._run_git_diff",
                return_value=diff,
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
                            "executed_lines": [11],
                            "missing_lines": [12],
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        diff = (
            "diff --git a/core/profiles.py b/core/profiles.py\n"
            "--- a/core/profiles.py\n"
            "+++ b/core/profiles.py\n"
            "@@ -10,0 +11,2 @@\n"
            "+a\n"
            "+b\n"
        )
        with (
            patch(
                "sys.argv",
                [
                    "check_diff_coverage.py",
                    "--coverage-json",
                    str(cov_file),
                    "--min-file-coverage",
                    "70",
                ],
            ),
            patch(
                "scripts.check_diff_coverage._resolve_base_sha",
                return_value="base",
            ),
            patch(
                "scripts.check_diff_coverage._run_git_diff",
                return_value=diff,
            ),
        ):
            assert main() == 1

    def test_returns_1_when_file_missing_from_coverage(
        self, tmp_path: Path
    ) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(json.dumps({"files": {}}), encoding="utf-8")
        diff = (
            "diff --git a/core/profiles.py b/core/profiles.py\n"
            "--- a/core/profiles.py\n"
            "+++ b/core/profiles.py\n"
            "@@ -10,0 +11 @@\n"
            "+a\n"
        )
        with (
            patch(
                "sys.argv",
                [
                    "check_diff_coverage.py",
                    "--coverage-json",
                    str(cov_file),
                    "--min-file-coverage",
                    "70",
                ],
            ),
            patch(
                "scripts.check_diff_coverage._resolve_base_sha",
                return_value="base",
            ),
            patch(
                "scripts.check_diff_coverage._run_git_diff",
                return_value=diff,
            ),
        ):
            assert main() == 1

    def test_returns_0_when_only_non_executable_lines_changed(
        self, tmp_path: Path
    ) -> None:
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(
            json.dumps(
                {
                    "files": {
                        "core/profiles.py": {
                            "executed_lines": [1],
                            "missing_lines": [],
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        diff = (
            "diff --git a/core/profiles.py b/core/profiles.py\n"
            "--- a/core/profiles.py\n"
            "+++ b/core/profiles.py\n"
            "@@ -10,0 +11 @@\n"
            "+# только комментарий\n"
        )
        with (
            patch(
                "sys.argv",
                [
                    "check_diff_coverage.py",
                    "--coverage-json",
                    str(cov_file),
                    "--min-file-coverage",
                    "70",
                ],
            ),
            patch(
                "scripts.check_diff_coverage._resolve_base_sha",
                return_value="base",
            ),
            patch(
                "scripts.check_diff_coverage._run_git_diff",
                return_value=diff,
            ),
        ):
            assert main() == 0
