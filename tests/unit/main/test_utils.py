"""
Unit-тесты для utils.py
========================
"""

from pathlib import Path

import pytest

from utils import (
    _apply_windows_acl,
    _check_permissions,
    _check_windows_acl,
    _restrict_file_permissions,
    atomic_write_json,
    get_app_icon_path,
)


class TestGetAppIconPath:
    """Тесты резолва пути к .ico приложения."""

    def test_dev_mode_resolves_relative_to_repo_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """В dev-режиме (не frozen) путь строится от каталога repo root."""
        monkeypatch.delattr("sys.frozen", raising=False)

        path = get_app_icon_path()

        assert path == (
            Path(__file__).parent.parent.parent.parent
            / "docs"
            / "assets"
            / "MIA-ScreenCapture.ico"
        )

    def test_frozen_mode_resolves_relative_to_meipass(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """В frozen-сборке путь строится от sys._MEIPASS."""
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)

        path = get_app_icon_path()

        assert path == tmp_path / "docs" / "assets" / "MIA-ScreenCapture.ico"

    def test_returns_path_even_if_file_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Функция не проверяет существование файла — это забота вызывающего."""
        monkeypatch.delattr("sys.frozen", raising=False)

        path = get_app_icon_path()

        assert isinstance(path, Path)


class FakeACL:
    """Заглушка win32security.ACL для unit-тестов."""

    def __init__(self) -> None:
        self.aces: list[tuple[int, int, object]] = []

    def AddAccessAllowedAce(
        self, revision: int, mask: int, sid: object
    ) -> None:
        """Добавляет ACE в список (заглушка)."""
        self.aces.append((revision, mask, sid))


def _make_fake_win32_modules() -> tuple[object, object, object, object]:
    """Возвращает набор фейковых win32-модулей для тестов ACL."""
    import types

    fake_ws = types.SimpleNamespace(
        OpenProcessToken=lambda *_a: "token",
        GetTokenInformation=lambda *_a: ["user-sid"],
        ConvertStringSidToSid=lambda s: f"sid:{s}",
        ACL=FakeACL,
        ACL_REVISION=2,
        SE_FILE_OBJECT=1,
        DACL_SECURITY_INFORMATION=4,
        PROTECTED_DACL_SECURITY_INFORMATION=0x80000000,
        ACCESS_ALLOWED_ACE_TYPE=0,
        TokenUser="TokenUser",
        SetNamedSecurityInfo=lambda *_a, **_k: None,
        GetNamedSecurityInfo=lambda *_a: _FakeSecurityInfo(),
    )
    fake_api = types.SimpleNamespace(GetCurrentProcess=lambda: "proc")
    fake_con = types.SimpleNamespace(TOKEN_QUERY=0x0008)
    fake_nt = types.SimpleNamespace(FILE_ALL_ACCESS=0x001F01FF)
    return fake_ws, fake_api, fake_con, fake_nt


class _FakeDacl:
    """Заглушка DACL с заданным списком ACE."""

    def __init__(self, aces: list[tuple[object, ...]] | None = None) -> None:
        self._aces: list[tuple[object, ...]] = aces or []

    def GetAceCount(self) -> int:
        """Количество ACE."""
        return len(self._aces)

    def GetAce(self, index: int) -> tuple[object, ...]:
        """ACE по индексу."""
        return self._aces[index]


class _FakeSecurityInfo:
    """Заглушка результата GetNamedSecurityInfo."""

    def __init__(self, dacl: _FakeDacl | None = None) -> None:
        self._dacl = dacl

    def GetSecurityDescriptorDacl(self) -> _FakeDacl | None:
        """DACL из дескриптора безопасности."""
        return self._dacl


class TestRestrictFilePermissions:
    """Тесты ограничения прав через _restrict_file_permissions."""

    def test_skips_chmod_when_windows_acl_applied(
        self, mocker, tmp_path: Path
    ) -> None:
        """Если Windows ACL применён — os.chmod не вызывается."""
        target = tmp_path / "config.json"
        target.write_text("{}", encoding="utf-8")
        apply_acl = mocker.patch("utils._apply_windows_acl", return_value=True)
        chmod = mocker.patch("utils.os.chmod")

        _restrict_file_permissions(target, 0o600)

        apply_acl.assert_called_once_with(target)
        chmod.assert_not_called()

    def test_falls_back_to_chmod_when_acl_unavailable(
        self, mocker, tmp_path: Path
    ) -> None:
        """Без win32security (или при ошибке) — fallback на os.chmod."""
        target = tmp_path / "config.json"
        target.write_text("{}", encoding="utf-8")
        mocker.patch("utils._apply_windows_acl", return_value=False)
        chmod = mocker.patch("utils.os.chmod")

        _restrict_file_permissions(target, 0o600)

        chmod.assert_called_once_with(target, 0o600)

    def test_apply_windows_acl_returns_false_without_win32security(
        self, mocker
    ) -> None:
        """На платформе без win32security ACL не применяется."""
        mocker.patch("utils._windows_acl_modules", return_value=None)

        result = _apply_windows_acl(Path("config.json"))

        assert result is False

    def test_apply_windows_acl_sets_restricted_dacl(self, mocker) -> None:
        """DACL содержит текущего пользователя, SYSTEM и Administrators."""
        fake_ws, fake_api, fake_con, fake_nt = _make_fake_win32_modules()
        mocker.patch(
            "utils._windows_acl_modules",
            return_value=(fake_ws, fake_api, fake_con, fake_nt),
        )
        fake_ws.SetNamedSecurityInfo = mocker.MagicMock()  # type: ignore[attr-defined]

        result = _apply_windows_acl(Path("config.json"))

        assert result is True
        fake_ws.SetNamedSecurityInfo.assert_called_once()  # type: ignore[attr-defined]
        args = fake_ws.SetNamedSecurityInfo.call_args.args  # type: ignore[attr-defined]
        assert args[0] == "config.json"
        dacl = args[5]
        assert isinstance(dacl, FakeACL)
        sids = {ace[2] for ace in dacl.aces}
        assert "user-sid" in sids
        assert "sid:S-1-5-18" in sids  # SYSTEM
        assert "sid:S-1-5-32-544" in sids  # Administrators
        # Наследование отключено (PROTECTED_DACL)
        assert args[2] & fake_ws.PROTECTED_DACL_SECURITY_INFORMATION

    def test_apply_windows_acl_logs_warning_on_error(
        self, mocker, caplog
    ) -> None:
        """Ошибка SetNamedSecurityInfo логируется, ACL не применяется."""
        fake_ws, fake_api, fake_con, fake_nt = _make_fake_win32_modules()
        mocker.patch(
            "utils._windows_acl_modules",
            return_value=(fake_ws, fake_api, fake_con, fake_nt),
        )
        fake_ws.SetNamedSecurityInfo = mocker.MagicMock(  # type: ignore[attr-defined]
            side_effect=OSError("access denied")
        )

        result = _apply_windows_acl(Path("config.json"))

        assert result is False
        assert "access denied" in caplog.text


class TestCheckPermissions:
    """Тесты проверки прав через _check_permissions."""

    def test_uses_stat_check_when_windows_acl_unavailable(
        self, mocker, tmp_path: Path
    ) -> None:
        """Без win32security — проверка через os.stat (POSIX-ветка)."""
        target = tmp_path / "config.json"
        target.write_text("{}", encoding="utf-8")
        mocker.patch("utils._check_windows_acl", return_value=False)
        mocker.patch("utils.sys.platform", "linux")

        # Не должно упасть: файл существует, прав "шире" нет
        _check_permissions(target, 0o600)

    def test_windows_acl_check_detects_everyone_access(
        self, mocker, caplog
    ) -> None:
        """Доступ Everyone в DACL — предупреждение в лог."""
        fake_ws, fake_api, fake_con, fake_nt = _make_fake_win32_modules()
        mocker.patch(
            "utils._windows_acl_modules",
            return_value=(fake_ws, fake_api, fake_con, fake_nt),
        )
        # ACE: ((type=ACCESS_ALLOWED, flags=0), mask, SID Everyone)
        fake_dacl = _FakeDacl(
            [((fake_ws.ACCESS_ALLOWED_ACE_TYPE, 0), 0x001F01FF, "S-1-1-0")]
        )
        fake_ws.GetNamedSecurityInfo = mocker.MagicMock(  # type: ignore[attr-defined]
            return_value=_FakeSecurityInfo(fake_dacl)
        )
        fake_ws.ConvertSidToStringSid = lambda sid: sid  # type: ignore[attr-defined]

        result = _check_windows_acl(Path("config.json"))

        assert result is True
        assert "Everyone" in caplog.text

    def test_windows_acl_check_silent_when_restricted(
        self, mocker, caplog
    ) -> None:
        """Только user/SYSTEM/Admins в DACL — без предупреждений."""
        fake_ws, fake_api, fake_con, fake_nt = _make_fake_win32_modules()
        mocker.patch(
            "utils._windows_acl_modules",
            return_value=(fake_ws, fake_api, fake_con, fake_nt),
        )
        fake_dacl = _FakeDacl(
            [
                ((fake_ws.ACCESS_ALLOWED_ACE_TYPE, 0), 0x001F01FF, "user-sid"),
                ((fake_ws.ACCESS_ALLOWED_ACE_TYPE, 0), 0x001F01FF, "S-1-5-18"),
            ]
        )
        fake_ws.GetNamedSecurityInfo = mocker.MagicMock(  # type: ignore[attr-defined]
            return_value=_FakeSecurityInfo(fake_dacl)
        )
        fake_ws.ConvertSidToStringSid = lambda sid: sid  # type: ignore[attr-defined]

        result = _check_windows_acl(Path("config.json"))

        assert result is True
        assert "Everyone" not in caplog.text


class TestAtomicWriteJsonPermissions:
    """Тесты атомарной записи JSON с правами доступа."""

    def test_restricts_file_permissions_after_write(
        self, mocker, tmp_path: Path
    ) -> None:
        """После записи файла применяются restricted permissions."""
        target = tmp_path / "config.json"
        mocker.patch("utils._apply_windows_acl", return_value=True)
        mocker.patch("utils._check_windows_acl", return_value=True)

        result = atomic_write_json(target, {"a": 1})

        assert result is True
        assert target.exists()
        assert '{\n  "a": 1\n}' in target.read_text(encoding="utf-8")

    def test_returns_false_on_write_error(
        self, mocker, tmp_path: Path
    ) -> None:
        """Ошибка записи — False, без исключения наружу."""
        target = tmp_path / "config.json"
        mocker.patch("utils.json.dump", side_effect=OSError("disk full"))

        result = atomic_write_json(target, {"a": 1})

        assert result is False
        assert not target.exists()
