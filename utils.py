"""
Общие утилиты для приложения.
"""

import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)


def get_app_icon_path() -> Path:
    """
    Путь к .ico приложения для брендирования окна/трея/EXE.

    В frozen-сборке (PyInstaller) ресурсы распаковываются во временный
    каталог `sys._MEIPASS`, поэтому путь относительно `__file__` там
    не работает — отсюда ветвление по `sys.frozen`, как в
    `logger_config.get_log_dir()`.

    Returns:
        Путь к `docs/assets/MIA-ScreenCapture.ico` (может не существовать —
        вызывающий код должен проверить `.exists()`).
    """
    if getattr(sys, "frozen", False):
        base_path = Path(getattr(sys, "_MEIPASS", "."))
    else:
        base_path = Path(__file__).parent
    return base_path / "docs" / "assets" / "MIA-ScreenCapture.ico"


def _windows_acl_modules() -> tuple[Any, Any, Any, Any] | None:
    """
    Ленивый импорт win32-модулей для работы с Windows ACL.

    Импорт выполняется на лету, т.к. pywin32 — тяжёлая зависимость,
    недоступная на не-Windows платформах.

    Returns:
        Кортеж (win32security, win32api, win32con, ntsecuritycon)
        или None, если модули недоступны.
    """
    try:
        import ntsecuritycon
        import win32api
        import win32con
        import win32security
    except ImportError:
        return None
    return win32security, win32api, win32con, ntsecuritycon


def _apply_windows_acl(path: Path) -> bool:
    """
    Ограничивает доступ к файлу через настоящий Windows ACL (DACL).

    В отличие от `os.chmod`, который на Windows не ограничивает доступ
    (влияет только на read-only флаг), здесь через `SetNamedSecurityInfo`
    задаётся DACL с доступом только для текущего пользователя, SYSTEM
    и группы Administrators. Наследование от родительской директории
    отключается (`PROTECTED_DACL_SECURITY_INFORMATION`), чтобы в ACL не
    попадали группы Everyone/Users.

    Args:
        path: Путь к файлу

    Returns:
        True если ACL успешно применён, False в противном случае.
    """
    modules = _windows_acl_modules()
    if modules is None:
        return False
    win32security, win32api, win32con, ntsecuritycon = modules

    try:
        # SID текущего пользователя из токена процесса
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
        )
        user_sid = win32security.GetTokenInformation(
            token, win32security.TokenUser
        )[0]
        system_sid = win32security.ConvertStringSidToSid("S-1-5-18")
        admins_sid = win32security.ConvertStringSidToSid("S-1-5-32-544")

        dacl = win32security.ACL()
        for sid in (user_sid, system_sid, admins_sid):
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                ntsecuritycon.FILE_ALL_ACCESS,
                sid,
            )

        win32security.SetNamedSecurityInfo(
            str(path),
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION
            | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            None,
            None,
            dacl,
            None,
        )
        logger.debug("Установлен Windows ACL на %s", path)
        return True
    except Exception as e:
        logger.warning("Не удалось установить Windows ACL на %s: %s", path, e)
        return False


# SID-ы групп, наличие доступа у которых считается слишком широким
_WIDE_ACCESS_SIDS: dict[str, str] = {
    "S-1-1-0": "Everyone",  # SID Everyone
    "S-1-5-32-545": "Users",  # SID BUILTIN\\Users
}


def _check_windows_acl(path: Path) -> bool:
    """
    Проверяет Windows ACL файла на наличие широкого доступа.

    Считывает текущий DACL файла и предупреждает, если доступ разрешён
    группам Everyone/Users.

    Args:
        path: Путь к файлу

    Returns:
        True если проверка выполнена (или модули недоступны — тогда
        проверка не требуется), False при ошибке чтения ACL.
    """
    modules = _windows_acl_modules()
    if modules is None:
        return True
    win32security = modules[0]

    try:
        security_info = win32security.GetNamedSecurityInfo(
            str(path),
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION,
        )
        dacl = security_info.GetSecurityDescriptorDacl()
        if dacl is None:
            logger.warning("Файл %s не имеет DACL — права не ограничены", path)
            return True

        for i in range(dacl.GetAceCount()):
            ace = dacl.GetAce(i)
            # ACE имеет вид ((ace_type, ace_flags), access_mask, sid)
            ace_type = ace[0][0]
            if ace_type != win32security.ACCESS_ALLOWED_ACE_TYPE:
                continue
            sid = win32security.ConvertSidToStringSid(ace[2])
            group_name = _WIDE_ACCESS_SIDS.get(sid)
            if group_name is not None:
                logger.warning(
                    "Файл %s доступен группе %s (%s)", path, group_name, sid
                )
        return True
    except Exception as e:
        logger.debug("Не удалось проверить Windows ACL на %s: %s", path, e)
        return False


def _restrict_file_permissions(path: Path, mode: int) -> None:
    """
    Устанавливает restricted permissions на файл.

    На Windows применяется настоящий Windows ACL (DACL) через
    win32security, поскольку `os.chmod` на Windows не ограничивает
    доступ к файлу — он лишь устанавливает read-only флаг. Если применить
    ACL не удалось (нет pywin32 или ошибка), выполняется fallback
    на `os.chmod`.

    Args:
        path: Путь к файлу
        mode: Запрашиваемые права (например, 0o600)
    """
    if sys.platform == "win32" and _apply_windows_acl(path):
        logger.debug("Права на %s установлены через Windows ACL", path)
        return

    try:
        os.chmod(path, mode)
        logger.debug("Установлены права %s на %s", oct(mode), path)
    except OSError as e:
        # На Windows без elevated rights chmod может не сработать —
        # логируем предупреждение, не падаем
        logger.warning(
            "Не удалось установить права %s на %s: %s",
            oct(mode),
            path,
            e,
        )


def _check_permissions(path: Path, expected_mode: int) -> None:
    """
    Проверяет, что права файла не шире запрошенных.

    На Windows проверяется Windows ACL (отсутствие доступа у групп
    Everyone/Users), на остальных платформах — POSIX-биты через `os.stat`.

    Args:
        path: Путь к файлу
        expected_mode: Ожидаемые права
    """
    if sys.platform == "win32" and _check_windows_acl(path):
        return

    try:
        file_stat = os.stat(path)
        actual_mode = stat.S_IMODE(file_stat.st_mode)
        # Проверяем: actual должен быть подмножеством expected
        # (т.е. не шире, чем мы запрашивали)
        if actual_mode & ~expected_mode:
            logger.warning(
                "Файл %s имеет слишком широкие права: %s (ожидается подмножество %s)",
                path,
                oct(actual_mode),
                oct(expected_mode),
            )
    except OSError:
        pass  # stat-ошибка не критична


def atomic_write_json(path: Path, data: Any, *, mode: int = 0o600) -> bool:
    """
    Атомарная запись JSON в файл через временный файл в той же директории.

    Args:
        path: Путь к целевому файлу
        data: Данные для записи (будут сериализованы в JSON)
        mode: Права на файл после записи (по умолчанию 0o600)

    Returns:
        True если запись успешна, False в противном случае
    """
    temp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        os.replace(temp_path, path)
        temp_path = None  # os.replace удалил temp, больше не нужно

        _restrict_file_permissions(path, mode)
        _check_permissions(path, mode)
        return True
    except Exception as e:
        logger.error(f"Ошибка атомарной записи в {path}: {e}")
        return False
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
