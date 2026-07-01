"""
Модуль постоянного хранения состояния rate limiter
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from logger_config import get_module_logger
from utils import atomic_write_json

from .rate_limiter import ClientState, InMemoryRateLimiter, RateLimitConfig

logger = get_module_logger(__name__)

RATE_LIMITER_STATE_DIR = Path(__file__).parent / "config"
RATE_LIMITER_STATE_FILE = RATE_LIMITER_STATE_DIR / "rate_limiter_state.json"
CURRENT_SCHEMA_VERSION = 1


class RateLimiterClientStateSchema(BaseModel):
    """Схема валидации состояния клиента для rate limiter."""

    minute_count: int = Field(default=0, ge=0)
    hour_count: int = Field(default=0, ge=0)
    burst_count: int = Field(default=0, ge=0)
    last_minute_reset: float = Field(default=0.0)
    last_hour_reset: float = Field(default=0.0)
    last_burst_reset: float = Field(default=0.0)
    blocked_until: float = Field(default=0.0)
    last_activity: float = Field(default=0.0)


class RateLimiterStateSchema(BaseModel):
    """Схема валидации общего состояния rate limiter."""

    version: int = Field(default=CURRENT_SCHEMA_VERSION, ge=1)
    last_updated: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    clients: dict[str, RateLimiterClientStateSchema] = Field(
        default_factory=dict
    )


class RateLimiterClientState:
    """Состояние клиента для отслеживания запросов."""

    def __init__(
        self,
        minute_count: int = 0,
        hour_count: int = 0,
        burst_count: int = 0,
        last_minute_reset: float = 0.0,
        last_hour_reset: float = 0.0,
        last_burst_reset: float = 0.0,
        blocked_until: float = 0.0,
        last_activity: float = 0.0,
    ):
        self.minute_count = minute_count
        self.hour_count = hour_count
        self.burst_count = burst_count
        self.last_minute_reset = last_minute_reset
        self.last_hour_reset = last_hour_reset
        self.last_burst_reset = last_burst_reset
        self.blocked_until = blocked_until
        self.last_activity = last_activity

    def to_dict(self) -> dict[str, Any]:
        return {
            "minute_count": self.minute_count,
            "hour_count": self.hour_count,
            "burst_count": self.burst_count,
            "last_minute_reset": self.last_minute_reset,
            "last_hour_reset": self.last_hour_reset,
            "last_burst_reset": self.last_burst_reset,
            "blocked_until": self.blocked_until,
            "last_activity": self.last_activity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RateLimiterClientState":
        return cls(
            minute_count=data.get("minute_count", 0),
            hour_count=data.get("hour_count", 0),
            burst_count=data.get("burst_count", 0),
            last_minute_reset=data.get("last_minute_reset", 0.0),
            last_hour_reset=data.get("last_hour_reset", 0.0),
            last_burst_reset=data.get("last_burst_reset", 0.0),
            blocked_until=data.get("blocked_until", 0.0),
            last_activity=data.get("last_activity", 0.0),
        )


class RateLimiterState:
    """Общее состояние ограничителя частоты запросов."""

    def __init__(
        self,
        version: int = CURRENT_SCHEMA_VERSION,
        last_updated: str = "",
        clients: dict[str, "RateLimiterClientState"] | None = None,
    ):
        self.version = version
        self.last_updated = last_updated or datetime.now().isoformat()
        self.clients = clients if clients is not None else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "clients": {
                ip: state.to_dict() for ip, state in self.clients.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RateLimiterState":
        clients_data = data.get("clients", {})
        clients = {
            ip: RateLimiterClientState.from_dict(client_data)
            for ip, client_data in clients_data.items()
        }

        return cls(
            version=data.get("version", CURRENT_SCHEMA_VERSION),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            clients=clients,
        )


class RateLimiterStatePersistence:
    """Менеджер сохранения состояния rate limiter в JSON файл."""

    def __init__(self, state_file: Path | None = None):
        self.state_file = state_file or RATE_LIMITER_STATE_FILE
        self._lock = threading.RLock()
        self._save_lock = threading.Lock()

    def _create_default_state(self) -> RateLimiterState:
        return RateLimiterState()

    def _get_backup_path(self) -> Path:
        return Path(str(self.state_file) + ".bak")

    def load(self) -> RateLimiterState:
        with self._lock:
            if not self.state_file.exists():
                logger.info(
                    "Файл состояния rate limiter не найден, используем default"
                )
                return self._create_default_state()

            data: dict[str, Any] | None = None

            try:
                with open(self.state_file, encoding="utf-8") as f:
                    data = json.load(f)

                validated = RateLimiterStateSchema.model_validate(data)
                state = RateLimiterState.from_dict(validated.model_dump())

                logger.info(
                    f"Состояние rate limiter загружено из {self.state_file}, "
                    f"клиентов: {len(state.clients)}"
                )
                return state
            except Exception as e:
                logger.error(f"Ошибка загрузки состояния rate limiter: {e}")
                if data is not None:
                    logger.debug(
                        "Проблемная структура состояния: %s",
                        json.dumps(data, ensure_ascii=False, indent=2)[:2000],
                    )

                backup_path = self._get_backup_path()
                if backup_path.exists():
                    logger.info(
                        "Попытка восстановления из backup файла: %s",
                        backup_path,
                    )
                    return self._load_backup(backup_path)

                return self._create_default_state()

    def _load_backup(self, backup_path: Path) -> RateLimiterState:
        try:
            with open(backup_path, encoding="utf-8") as f:
                data = json.load(f)

            validated = RateLimiterStateSchema.model_validate(data)
            state = RateLimiterState.from_dict(validated.model_dump())

            logger.info(f"Состояние восстановлено из backup: {backup_path}")
            return state
        except Exception as e:
            logger.error(f"Ошибка загрузки backup файла: {e}")
            return self._create_default_state()

    def save(self, state: RateLimiterState) -> bool:
        with self._lock:
            try:
                schema = RateLimiterStateSchema(
                    version=state.version,
                    last_updated=state.last_updated,
                    clients={
                        ip: RateLimiterClientStateSchema(**state.clients[ip].to_dict())
                        for ip in state.clients
                    },
                )

                data = schema.model_dump()
                RateLimiterStateSchema.model_validate(data)
            except Exception as e:
                logger.error(
                    f"Ошибка валидации состояния перед сохранением: {e}"
                )
                return False

        with self._save_lock:
            try:
                result = atomic_write_json(self.state_file, data)

                if result:
                    backup_path = self._get_backup_path()
                    try:
                        backup_path.write_text(
                            self.state_file.read_text(encoding="utf-8"),
                            encoding="utf-8",
                        )
                    except Exception as e:
                        logger.warning(
                            f"Ошибка сохранения backup файла: {e}"
                        )

                    logger.info(
                        f"Состояние rate limiter сохранено в "
                        f"{self.state_file}, клиентов: {len(state.clients)}"
                    )
                return bool(result)
            except Exception as e:
                logger.error(
                    f"Ошибка сохранения состояния rate limiter: {e}"
                )
                return False

    def save_merge(self, state: RateLimiterState) -> bool:
        with self._save_lock:
            return self._save_merge_impl(state)

    def _save_merge_impl(self, state: RateLimiterState) -> bool:
        """
        Атомарная операция merge и сохранения состояния.

        Загружает текущее состояние из файла, обновляет клиентов из state,
        сохраняет результат. Гарантирует atomicity при конкурентных записях.
        """
        with self._lock:
            current_state = self.load()

            if current_state.clients is None:
                current_state.clients = {}

            for ip, client_state in state.clients.items():
                if ip in current_state.clients:
                    existing = current_state.clients[ip]
                    existing.minute_count = client_state.minute_count
                    existing.hour_count = client_state.hour_count
                    existing.burst_count = client_state.burst_count
                    existing.last_minute_reset = client_state.last_minute_reset
                    existing.hour_count = client_state.hour_count
                    existing.last_hour_reset = client_state.last_hour_reset
                    existing.last_burst_reset = client_state.last_burst_reset
                    existing.blocked_until = client_state.blocked_until
                    existing.last_activity = client_state.last_activity
                else:
                    current_state.clients[ip] = client_state

            current_state.version = state.version
            current_state.last_updated = state.last_updated

            try:
                schema = RateLimiterStateSchema(
                    version=current_state.version,
                    last_updated=current_state.last_updated,
                    clients={
                        ip: RateLimiterClientStateSchema(**cs.to_dict())
                        for ip, cs in current_state.clients.items()
                    },
                )

                data = schema.model_dump()
                RateLimiterStateSchema.model_validate(data)

                result = atomic_write_json(self.state_file, data)

                if result:
                    backup_path = self._get_backup_path()
                    try:
                        backup_path.write_text(
                            self.state_file.read_text(encoding="utf-8"),
                            encoding="utf-8",
                        )
                    except Exception as e:
                        logger.warning(
                            f"Ошибка сохранения backup файла: {e}"
                        )

                    logger.info(
                        f"Состояние rate limiter сохранено (merge) в "
                        f"{self.state_file}, клиентов: {len(current_state.clients)}"
                    )
                return bool(result)
            except Exception as e:
                logger.error(
                    f"Ошибка сохранения состояния rate limiter (merge): {e}"
                )
                return False

    def clear(self) -> bool:
        with self._lock:
            try:
                if self.state_file.exists():
                    self.state_file.unlink()

                backup_path = self._get_backup_path()
                if backup_path.exists():
                    backup_path.unlink()

                logger.info("Состояние rate limiter очищено")
                return True
            except Exception as e:
                logger.error(f"Ошибка очистки состояния rate limiter: {e}")
                return False


class PersistentRateLimiter(InMemoryRateLimiter):
    """Rate limiter с постоянным хранением состояния."""

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        persistence: RateLimiterStatePersistence | None = None,
    ):
        super().__init__(config)
        self._persistence = persistence or get_persistence()
        self._state: RateLimiterState | None = None
        self._load_state_on_init = True
        self._concurrent_lock = threading.RLock()

    def _ensure_state_loaded(self) -> None:
        with self._concurrent_lock:
            if self._state is None:
                with self._persistence._lock:
                    self._state = self._persistence.load()

    def _persist_state(self) -> None:
        with self._concurrent_lock:
            if self._state is None:
                with self._persistence._lock:
                    self._state = self._persistence.load()

            if self._state is None:
                self._state = RateLimiterState()

            try:
                for ip, client_state in self._clients.items():
                    if ip in self._state.clients:
                        rate_client_state = self._state.clients[ip]
                        rate_client_state.minute_count = client_state.minute_count
                        rate_client_state.hour_count = client_state.hour_count
                        rate_client_state.burst_count = client_state.burst_count
                        rate_client_state.last_minute_reset = (
                            client_state.last_minute_reset
                        )
                        rate_client_state.last_hour_reset = (
                            client_state.last_hour_reset
                        )
                        rate_client_state.last_burst_reset = (
                            client_state.last_burst_reset
                        )
                        rate_client_state.blocked_until = (
                            client_state.blocked_until
                        )
                        rate_client_state.last_activity = (
                            client_state.last_activity
                        )
                    else:
                        rate_client_state = RateLimiterClientState()
                        rate_client_state.minute_count = client_state.minute_count
                        rate_client_state.hour_count = client_state.hour_count
                        rate_client_state.burst_count = client_state.burst_count
                        rate_client_state.last_minute_reset = (
                            client_state.last_minute_reset
                        )
                        rate_client_state.last_hour_reset = (
                            client_state.last_hour_reset
                        )
                        rate_client_state.last_burst_reset = (
                            client_state.last_burst_reset
                        )
                        rate_client_state.blocked_until = (
                            client_state.blocked_until
                        )
                        rate_client_state.last_activity = (
                            client_state.last_activity
                        )
                        self._state.clients[ip] = rate_client_state

                self._state.version = CURRENT_SCHEMA_VERSION
                self._state.last_updated = datetime.now().isoformat()

                with self._persistence._save_lock:
                    result = self._persistence.save(self._state)
                    if not result:
                        logger.error("Не удалось сохранить состояние rate limiter")
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния rate limiter: {e}")

    def load_state_on_init(self) -> None:
        with self._lock:
            self._ensure_state_loaded()

            if self._state is not None and self._state.clients:
                for ip, state in self._state.clients.items():
                    client_state = ClientState()
                    client_state.minute_count = state.minute_count
                    client_state.hour_count = state.hour_count
                    client_state.burst_count = state.burst_count
                    client_state.last_minute_reset = state.last_minute_reset
                    client_state.last_hour_reset = state.last_hour_reset
                    client_state.last_burst_reset = state.last_burst_reset
                    client_state.blocked_until = state.blocked_until
                    client_state.last_activity = state.last_activity
                    self._clients[ip] = client_state

                logger.info(
                    f"Загружено состояний клиентов: {len(self._state.clients)}"
                )

    def check_rate_limit(
        self, client_ip: str | None = None
    ) -> tuple[bool, dict | None]:
        """
        Проверка ограничения частоты.

        Args:
            client_ip: IP-адрес клиента (если None, используется _get_client_ip())

        Returns:
            Кортеж (разрешён ли запрос, информация об ограничении)
        """
        if not self.config.enabled:
            return True, None

        ip = client_ip if client_ip is not None else self._get_client_ip()

        if self._is_whitelisted(ip):
            return True, None

        with self._lock:
            if self._load_state_on_init:
                self._ensure_state_loaded()
                self._load_state_on_init = False

            try:
                self._cleanup_inactive_clients()

                state = self._clients[ip]
                current_time = time.monotonic()

                state.last_activity = current_time

                if current_time < state.blocked_until:
                    remaining = int(state.blocked_until - current_time)
                    result = (
                        False,
                        {
                            "error": "Too Many Requests",
                            "retry_after": remaining,
                            "limit_type": "blocked",
                        },
                    )
                else:
                    self._reset_counters_if_needed(state)

                    if state.burst_count >= self.config.burst_limit:
                        block_duration = self.config.block_duration
                        state.blocked_until = current_time + block_duration
                        logger.warning(
                            f"Burst rate limit exceeded for {ip}: "
                            f"{state.burst_count} requests/second"
                        )
                        result = (
                            False,
                            {
                                "error": "Too Many Requests",
                                "retry_after": block_duration,
                                "limit_type": "burst",
                            },
                        )
                    elif state.minute_count >= self.config.requests_per_minute:
                        result = (
                            False,
                            {
                                "error": "Too Many Requests",
                                "retry_after": 60,
                                "limit_type": "minute",
                            },
                        )
                    elif state.hour_count >= self.config.requests_per_hour:
                        result = (
                            False,
                            {
                                "error": "Too Many Requests",
                                "retry_after": 3600,
                                "limit_type": "hour",
                            },
                        )
                    else:
                        state.burst_count += 1
                        state.minute_count += 1
                        state.hour_count += 1

                        result = (
                            True,
                            {
                                "limit_type": "request",
                                "minute_count": state.minute_count,
                                "hour_count": state.hour_count,
                                "burst_count": state.burst_count,
                            },
                        )

                self._persist_state()
                return result
            except Exception:
                raise

    def reset_client(self, client_ip: str) -> None:
        with self._lock:
            super().reset_client(client_ip)
            self._persist_state()

    def clear_all(self) -> None:
        with self._lock:
            super().clear_all()
            self._persist_state()


STATE_FILE = RATE_LIMITER_STATE_FILE


def _init_persistence() -> RateLimiterStatePersistence:
    RATE_LIMITER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return RateLimiterStatePersistence()


_persistence: RateLimiterStatePersistence | None = None


def get_persistence() -> RateLimiterStatePersistence:
    global _persistence
    if _persistence is None:
        _persistence = _init_persistence()
    return _persistence


def init_persistence(
    state_file: Path | None = None,
) -> RateLimiterStatePersistence:
    global _persistence
    _persistence = RateLimiterStatePersistence(state_file)
    return _persistence
