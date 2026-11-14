"""
Отчёты о падениях процесса (#192)
=================================

Глобальные хуки необработанных исключений (sys.excepthook,
threading.excepthook), faulthandler для хард-падений (segfault/abort)
и мини-дамп процесса. Отчёты складываются в logs/crash/ — стека
и дампа достаточно для воспроизведения невидимых ранее падений
GUI/headless-процесса.

Повторный старт уведомляет пользователя о падении через
`consume_pending_crash_report` (диалог в GUI, предупреждение в логе
в headless).
"""

import ctypes
import faulthandler
import os
import sys
import threading
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import TracebackType

from logger_config import get_log_dir, get_module_logger

logger = get_module_logger(__name__)

# Имя под-директории отчётов внутри logs/
CRASH_DIR_NAME = "crash"
# Маркер последнего показанного пользователю отчёта
SEEN_MARKER_FILE = ".last_seen_crash"
# Хард-падения (segfault/abort): faulthandler пишет стеки всех потоков
FAULTHANDLER_LOG_PREFIX = "faulthandler"

# ctypes.HANDLE не типизируется в mypy-стабах
_Handle = ctypes.c_void_p

# Ссылку держим на уровне модуля: faulthandler пишет в открытый файл,
# а файловый объект не должен собрать GC до конца процесса
_faulthandler_file = None


def get_crash_dir() -> Path:
    """Директория отчётов о падениях: logs/crash.

    Returns:
        Путь к директории (создаётся при отсутствии).
    """
    crash_dir = get_log_dir() / CRASH_DIR_NAME
    crash_dir.mkdir(parents=True, exist_ok=True)
    return crash_dir


def _format_all_thread_stacks() -> str:
    """Стеки всех живых потоков (кроме текущего) для контекста падения.

    Returns:
        Текстовый дамп стеков; при сбое — строка-извинение.
    """
    current_id = threading.get_ident()
    frames = sys._current_frames()  # noqa: SLF001 — штатный introspection API
    threads = {thread.ident: thread.name for thread in threading.enumerate()}

    sections: list[str] = []
    for thread_id, frame in frames.items():
        if thread_id == current_id:
            continue
        name = threads.get(thread_id, f"thread-{thread_id}")
        stack = "".join(traceback.format_stack(frame))
        sections.append(f"--- Поток {name} ({thread_id}) ---\n{stack}")
    if not sections:
        return "(единственный поток)"
    return "\n".join(sections)


def _write_crash_report(
    crash_dir: Path,
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> Path:
    """Записать текстовый отчёт о необработанном исключении.

    Args:
        crash_dir: Директория отчётов.
        exc_type: Класс исключения.
        exc_value: Значение исключения.
        exc_traceback: Трейсбэк.

    Returns:
        Путь к записанному отчёту.
    """
    # Директория может исчезнуть между установкой хуков и падением
    crash_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    report_path = crash_dir / f"crash_{now:%Y%m%d_%H%M%S}.txt"
    report_path.write_text(
        f"Время: {now:%Y-%m-%d %H:%M:%S}\n"
        f"Процесс: PID {os.getpid()}, Python {sys.version.split()[0]}\n"
        f"Аргументы: {' '.join(sys.argv)}\n\n"
        f"Исключение: {exc_type.__name__}: {exc_value}\n\n"
        f"{traceback.format_exception(exc_type, exc_value, exc_traceback)}"
        f"\n\nСтеки потоков:\n{_format_all_thread_stacks()}\n",
        encoding="utf-8",
    )
    return report_path


def _write_minidump(report_path: Path) -> Path | None:
    """Мини-дамп процесса через MiniDumpWriteDump (best effort).

    Дамп живого процесса в момент необработанного исключения —
    не полный аналог дампа от WER, но фиксирует состояние памяти
    для диагностики нативных структур.

    Args:
        report_path: Путь к текстовому отчёту — имя дампа наследуется.

    Returns:
        Путь к записанному .dmp или None (не Windows / сбой API).
    """
    if sys.platform != "win32":
        return None
    dump_path = report_path.with_suffix(".dmp")
    try:
        kernel32 = ctypes.WinDLL("kernel32")
        dbghelp = ctypes.WinDLL("dbghelp")

        generic_write = 0x40000000
        create_always = 2
        file_attribute_normal = 0x80
        minidump_normal = 0
        handle = kernel32.CreateFileW(
            str(dump_path),
            generic_write,
            0,
            None,
            create_always,
            file_attribute_normal,
            None,
        )
        if handle == _Handle(-1):  # INVALID_HANDLE_VALUE
            logger.debug("Не удалось создать файл дампа %s", dump_path)
            return None

        try:
            ok = dbghelp.MiniDumpWriteDump(
                kernel32.GetCurrentProcess(),
                kernel32.GetCurrentProcessId(),
                handle,
                minidump_normal,
                None,
                None,
                None,
            )
        finally:
            kernel32.CloseHandle(handle)
        if not ok:
            logger.debug("MiniDumpWriteDump вернул ошибку")
            return None
        return dump_path
    except (AttributeError, OSError) as e:
        logger.debug("Мини-дамп недоступен: %s", e)
        return None


def _invoke_previous_hook(
    previous_hook: Callable[..., object],
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    """Вызвать предыдущий хук, если он не системный.

    Цепочка сохраняется, чтобы не потерять поведение, установленное
    другими библиотеками (например pytest).
    """
    if previous_hook is None or previous_hook is sys.__excepthook__:
        return
    try:
        previous_hook(exc_type, exc_value, exc_traceback)
    except Exception:  # noqa: BLE001 — хук не должен мешать своему преемнику
        logger.debug("Предыдущий excepthook упал", exc_info=True)


def _make_excepthook(
    previous_hook: Callable[..., object],
    crash_dir: Path,
) -> Callable[
    [type[BaseException], BaseException, TracebackType | None], None
]:
    """Создать sys.excepthook с записью отчёта и дампа.

    Args:
        previous_hook: Предыдущий хук (вызывается после записи отчёта).
        crash_dir: Директория отчётов.

    Returns:
        Новый excepthook.
    """

    def _hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        try:
            report_path = _write_crash_report(
                crash_dir, exc_type, exc_value, exc_traceback
            )
            _write_minidump(report_path)
            logger.error(
                "Необработанное исключение, отчёт сохранён: %s", report_path
            )
        except Exception:  # noqa: BLE001 — хук обязан пережить любой сбой
            logger.exception("Не удалось сохранить отчёт о падении")
        _invoke_previous_hook(
            previous_hook, exc_type, exc_value, exc_traceback
        )

    return _hook


def _make_threading_excepthook(
    previous_hook: Callable[..., object],
    crash_dir: Path,
) -> Callable[[threading.ExceptHookArgs], None]:
    """Создать threading.excepthook с записью отчёта.

    Args:
        previous_hook: Предыдущий хук (может отсутствовать).
        crash_dir: Директория отчётов.

    Returns:
        Новый threading excepthook.
    """

    def _hook(args: threading.ExceptHookArgs) -> None:
        thread_name = args.thread.name if args.thread else "unknown"
        exc_value = args.exc_value or Exception("неизвестная ошибка потока")
        try:
            report_path = _write_crash_report(
                crash_dir, args.exc_type, exc_value, args.exc_traceback
            )
            logger.error(
                "Необработанное исключение в потоке %s, отчёт: %s",
                thread_name,
                report_path,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Не удалось сохранить отчёт о падении в потоке %s",
                thread_name,
            )
        if (
            previous_hook is not None
            and previous_hook is not threading.__excepthook__
        ):
            try:
                previous_hook(args)
            except Exception:  # noqa: BLE001
                logger.debug("Предыдущий threading.excepthook упал")

    return _hook


def install_crash_handlers(crash_dir: Path | None = None) -> Path:
    """Установить глобальные хуки падений процесса (#192).

    Вызывается один раз при старте приложения до создания окон и
    потоков: sys.excepthook (в PyQt6 исключения слотов доходят до
    него), threading.excepthook, faulthandler для хард-падений.

    Args:
        crash_dir: Директория отчётов; по умолчанию logs/crash.

    Returns:
        Использованная директория отчётов.
    """
    crash_dir = crash_dir if crash_dir is not None else get_crash_dir()
    crash_dir.mkdir(parents=True, exist_ok=True)

    sys.excepthook = _make_excepthook(sys.excepthook, crash_dir)
    threading.excepthook = _make_threading_excepthook(
        threading.excepthook,
        crash_dir,
    )

    global _faulthandler_file
    if not faulthandler.is_enabled():
        try:
            log_path = (
                crash_dir / f"{FAULTHANDLER_LOG_PREFIX}_{os.getpid()}.log"
            )
            _faulthandler_file = open(  # noqa: SIM115 — живёт весь процесс
                log_path, "w", encoding="utf-8"
            )
            faulthandler.enable(file=_faulthandler_file)
        except OSError as e:
            logger.debug("faulthandler не включён: %s", e)

    logger.info("Хуки падений установлены: %s", crash_dir)
    return crash_dir


def consume_pending_crash_report(crash_dir: Path | None = None) -> Path | None:
    """Найти новый (ещё не показанный пользователю) отчёт о падении.

    Видимость отслеживается маркером `.last_seen_crash` с именем
    последнего показанного отчёта. Повторный вызов с тем же
    содержимым директории вернёт None — отчёт «показан» самим фактом
    возврата, маркер обновляется здесь же.

    Args:
        crash_dir: Директория отчётов; по умолчанию logs/crash.

    Returns:
        Путь к свежему отчёту или None.
    """
    crash_dir = crash_dir if crash_dir is not None else get_crash_dir()
    reports = sorted(crash_dir.glob("crash_*.txt"))
    if not reports:
        return None

    latest = reports[-1]
    marker_path = crash_dir / SEEN_MARKER_FILE
    seen_name = ""
    if marker_path.exists():
        try:
            seen_name = marker_path.read_text(encoding="ascii").strip()
        except OSError as e:
            logger.debug("Маркер показанных отчётов не читается: %s", e)
    if latest.name == seen_name:
        return None

    try:
        marker_path.write_text(latest.name, encoding="ascii")
    except OSError as e:
        logger.debug("Маркер показанных отчётов не записан: %s", e)
    return latest
