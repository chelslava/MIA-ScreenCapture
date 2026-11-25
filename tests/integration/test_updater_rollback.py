"""
Интеграционные тесты установщика обновлений с реальным PowerShell (#191)
========================================================================

Smoke-тест updater по issue #191: фиктивные "релизы" (zip-архивы) и
фиктивные "установки" во временных директориях, применение через
настоящий powershell.exe. Проверяются три сценария:

1. Успех: backup -> распаковка -> приложение подтверждает запуск ->
   backup удаляется.
2. Битый архив (нет обязательных файлов): откат, старая версия цела.
3. Провал health-check (приложение не подтверждает запуск): откат
   по таймауту, зависший процесс убивается.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from core.updater.patcher import UpdatePatcher
from core.updater.rollback import (
    confirm_pending_update,
    read_rollback_notice,
    read_update_state,
)

PS_SCRIPT_TIMEOUT_S = 120


def _powershell_available() -> bool:
    """Проверяет доступность powershell.exe (есть на всех Windows)."""
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "$null"],
            capture_output=True,
            timeout=30,
            check=True,
        )
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(
        sys.platform != "win32",
        reason="Установщик обновлений работает только на Windows",
    ),
    pytest.mark.skipif(
        not _powershell_available(), reason="powershell.exe недоступен"
    ),
]


def _make_archive(path: Path, files: dict[str, str]) -> None:
    """Создаёт фиктивный архив обновления («релиз» на fixture-сервере)."""
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)


def _make_healthy_helper(directory: Path) -> Path:
    """Скрипт «здорового приложения»: подтверждает запуск и завершается.

    Имитирует поведение main.py после успешной инициализации ядра:
    confirm_pending_update удаляет маркер (сигнал health-check) и
    backup предыдущей версии.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    helper = directory / "healthy_app.py"
    helper.write_text(
        "import sys\n"
        f"sys.path.insert(0, r'{repo_root}')\n"
        "from pathlib import Path\n"
        "from core.updater.rollback import confirm_pending_update\n"
        "confirm_pending_update(Path(sys.argv[1]))\n",
        encoding="utf-8",
    )
    return helper


def _run_script(script: Path) -> subprocess.CompletedProcess[str]:
    """Запускает сгенерированный PS-скрипт как реальный установщик."""
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        text=True,
        encoding="cp866",
        errors="replace",
        timeout=PS_SCRIPT_TIMEOUT_S,
    )


class TestUpdaterRollbackIntegration:
    """End-to-end сценарии установщика обновлений (#191)."""

    def test_successful_update_confirmed_by_app(self, tmp_path: Path) -> None:
        """Успешный путь: новая версия применяется, backup чистится."""
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        app = tmp_path / "app"
        app.mkdir()
        (app / "main.py").write_text("# версия 1.0", encoding="utf-8")
        patcher = UpdatePatcher(download_dir=download_dir)

        archive = download_dir / "mia_update_2.1.0.zip"
        _make_archive(
            archive,
            {"main.py": "# версия 2.1.0", "новый_модуль.py": "X = 42"},
        )

        helper = _make_healthy_helper(download_dir)
        backup = tmp_path / "app.backup-t"
        script = patcher.generate_powershell_updater(
            archive_path=archive,
            target_dir=app,
            current_pid=999_999,  # процесса нет — Wait-Process уйдёт по таймауту
            restart_command=[sys.executable, str(helper), str(app)],
            restart_command_backup=[sys.executable, "-c", "pass"],
            version="2.1.0",
            verify_paths=["main.py", "новый_модуль.py"],
            health_timeout_s=30,
            backup_dir=backup,
        )

        result = _run_script(script)

        assert result.returncode == 0, result.stdout + result.stderr
        # Новая версия применена, кириллица в файлах не пострадала
        assert (app / "main.py").read_text(encoding="utf-8") == (
            "# версия 2.1.0"
        )
        assert (app / "новый_модуль.py").exists()
        # Приложение подтвердило запуск: маркер и backup удалены
        assert read_update_state(app) is None
        assert not backup.exists()

    def test_corrupt_archive_triggers_rollback(self, tmp_path: Path) -> None:
        """Архив без обязательных файлов откатывается, старая версия цела."""
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        app = tmp_path / "app"
        app.mkdir()
        (app / "main.py").write_text("# рабочая версия 1.0", encoding="utf-8")
        (app / "config.json").write_text("{}", encoding="utf-8")
        patcher = UpdatePatcher(download_dir=download_dir)

        archive = download_dir / "broken.zip"
        _make_archive(archive, {"посторонний_файл.txt": "битое обновление"})

        backup = tmp_path / "app.backup-t"
        script = patcher.generate_powershell_updater(
            archive_path=archive,
            target_dir=app,
            current_pid=999_999,
            restart_command=[sys.executable, "-c", "pass"],
            restart_command_backup=[sys.executable, "-c", "pass"],
            version="2.1.0",
            verify_paths=["main.py"],
            health_timeout_s=10,
            backup_dir=backup,
        )

        result = _run_script(script)

        assert result.returncode == 2, result.stdout + result.stderr
        # Инвариант #191: приложение остаётся рабочим на старой версии
        assert (app / "main.py").read_text(encoding="utf-8") == (
            "# рабочая версия 1.0"
        )
        assert (app / "config.json").exists()
        assert (app / "посторонний_файл.txt").exists() is False
        notice = read_rollback_notice(app)
        assert notice is not None
        assert "main.py" in notice["reason"]
        # Backup вернулся на место
        assert not backup.exists()

    def test_failed_health_check_triggers_rollback_and_kill(
        self, tmp_path: Path
    ) -> None:
        """Приложение не подтверждает запуск: откат и kill зависшего."""
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        app = tmp_path / "app"
        app.mkdir()
        (app / "main.py").write_text("# рабочая версия 1.0", encoding="utf-8")
        patcher = UpdatePatcher(download_dir=download_dir)

        archive = download_dir / "mia_update_2.1.0.zip"
        _make_archive(archive, {"main.py": "# битая версия 2.1.0"})

        # «Зависшее» приложение: не удаляет маркер
        stuck = download_dir / "stuck_app.py"
        stuck.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")

        backup = tmp_path / "app.backup-t"
        script = patcher.generate_powershell_updater(
            archive_path=archive,
            target_dir=app,
            current_pid=999_999,
            restart_command=[sys.executable, str(stuck)],
            restart_command_backup=[sys.executable, "-c", "pass"],
            version="2.1.0",
            verify_paths=["main.py"],
            health_timeout_s=6,
            backup_dir=backup,
        )

        result = _run_script(script)

        assert result.returncode == 2, result.stdout + result.stderr
        notice = read_rollback_notice(app)
        assert notice is not None
        assert "health-check" in notice["reason"]
        assert (app / "main.py").read_text(encoding="utf-8") == (
            "# рабочая версия 1.0"
        )
        assert read_update_state(app) is None
        # Зависший процесс новой версии убит установщиком
        assert stuck.exists()

    def test_confirm_after_rollback_scenario_is_noop(
        self, tmp_path: Path
    ) -> None:
        """После отката маркер подтверждения отсутствует — запуск тихий."""
        # Откат не оставляет update_state.json, приложение стартует
        # без подтверждения обновления
        assert confirm_pending_update(tmp_path / "app") is None
