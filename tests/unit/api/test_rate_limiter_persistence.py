
import json
import threading
import time
from pathlib import Path

from api.rate_limiter_persistence import (
    CURRENT_SCHEMA_VERSION,
    RATE_LIMITER_STATE_FILE,
    ClientState,
    PersistentRateLimiter,
    RateLimitConfig,
    RateLimiterClientState,
    RateLimiterState,
    RateLimiterStatePersistence,
)


class TestRateLimiterStatePersistence:
    def test_init_creates_file_if_not_exists(self, temp_state_file: Path):
        persistence = RateLimiterStatePersistence(state_file=temp_state_file)
        assert not temp_state_file.exists()
        state = persistence.load()
        assert state is not None
        assert state.version == CURRENT_SCHEMA_VERSION

    def test_init_default_path(self):
        persistence = RateLimiterStatePersistence()
        assert persistence.state_file == RATE_LIMITER_STATE_FILE

    def test_save_state_json_structure(self, temp_state_file: Path):
        persistence = RateLimiterStatePersistence(state_file=temp_state_file)
        state = RateLimiterState()
        client_state = RateLimiterClientState(
            minute_count=10,
            hour_count=100,
            burst_count=5,
            blocked_until=time.monotonic() + 60,
            last_activity=time.monotonic(),
        )
        state.clients["192.168.1.1"] = client_state

        result = persistence.save(state)
        assert result is True
        assert temp_state_file.exists()

        with open(temp_state_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "version" in data
        assert data["version"] == CURRENT_SCHEMA_VERSION
        assert "last_updated" in data
        assert "clients" in data
        assert "192.168.1.1" in data["clients"]
        assert data["clients"]["192.168.1.1"]["minute_count"] == 10

    def test_load_state_empty_file(self, temp_state_file: Path):
        temp_state_file.write_text("{}")
        persistence = RateLimiterStatePersistence(state_file=temp_state_file)
        state = persistence.load()
        assert state is not None
        assert state.version == CURRENT_SCHEMA_VERSION

    def test_load_state_invalid_json(self, temp_state_file: Path):
        temp_state_file.write_text("{invalid json")
        persistence = RateLimiterStatePersistence(state_file=temp_state_file)
        state = persistence.load()
        assert state is not None
        assert state.version == CURRENT_SCHEMA_VERSION

    def test_backup_existing_creates_backup(self, temp_state_file: Path):
        persistence = RateLimiterStatePersistence(state_file=temp_state_file)
        state = RateLimiterState()
        client_state = RateLimiterClientState(minute_count=5)
        state.clients["192.168.1.1"] = client_state

        persistence.save(state)

        backup_path = Path(str(temp_state_file) + ".bak")
        assert backup_path.exists()

        state.clients["192.168.1.1"].minute_count = 10
        persistence.save(state)

        assert backup_path.exists()

    def test_save_state_atomic(self, temp_state_file: Path):
        persistence = RateLimiterStatePersistence(state_file=temp_state_file)
        state = RateLimiterState()
        client_state = RateLimiterClientState(minute_count=5)
        state.clients["192.168.1.1"] = client_state

        result = persistence.save(state)
        assert result is True

        loaded_state = persistence.load()
        assert "192.168.1.1" in loaded_state.clients
        assert loaded_state.clients["192.168.1.1"].minute_count == 5

    def test_clear(self, temp_state_file: Path):
        persistence = RateLimiterStatePersistence(state_file=temp_state_file)
        state = RateLimiterState()
        client_state = RateLimiterClientState(minute_count=5)
        state.clients["192.168.1.1"] = client_state

        persistence.save(state)
        assert temp_state_file.exists()

        result = persistence.clear()
        assert result is True
        assert not temp_state_file.exists()

        backup_path = Path(str(temp_state_file) + ".bak")
        assert not backup_path.exists()


class TestRateLimiterClientState:
    def test_to_dict(self):
        state = RateLimiterClientState(
            minute_count=10,
            hour_count=100,
            burst_count=5,
            blocked_until=1234567890.0,
            last_activity=time.monotonic(),
        )

        result = state.to_dict()
        assert result["minute_count"] == 10
        assert result["hour_count"] == 100
        assert result["burst_count"] == 5
        assert result["blocked_until"] == 1234567890.0

    def test_from_dict(self):
        data = {
            "minute_count": 10,
            "hour_count": 100,
            "burst_count": 5,
            "last_minute_reset": 1000.0,
            "last_hour_reset": 1000.0,
            "last_burst_reset": 1000.0,
            "blocked_until": 1234567890.0,
            "last_activity": time.monotonic(),
        }

        state = RateLimiterClientState.from_dict(data)
        assert state.minute_count == 10
        assert state.hour_count == 100
        assert state.burst_count == 5


class TestRateLimiterState:
    def test_to_dict(self):
        state = RateLimiterState()
        client_state = RateLimiterClientState(minute_count=5)
        state.clients["192.168.1.1"] = client_state

        result = state.to_dict()
        assert result["version"] == CURRENT_SCHEMA_VERSION
        assert "clients" in result
        assert "192.168.1.1" in result["clients"]

    def test_from_dict(self):
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "last_updated": "2024-01-01T00:00:00",
            "clients": {
                "192.168.1.1": {
                    "minute_count": 10,
                    "hour_count": 100,
                    "burst_count": 5,
                    "last_minute_reset": 1000.0,
                    "last_hour_reset": 1000.0,
                    "last_burst_reset": 1000.0,
                    "blocked_until": 1234567890.0,
                    "last_activity": 1000.0,
                }
            },
        }

        state = RateLimiterState.from_dict(data)
        assert state.version == CURRENT_SCHEMA_VERSION
        assert "192.168.1.1" in state.clients
        assert state.clients["192.168.1.1"].minute_count == 10


class TestPersistentRateLimiter:
    def test_init_loads_state_from_file(self, temp_state_file: Path, persistence: RateLimiterStatePersistence):
        state = RateLimiterState()
        client_state = RateLimiterClientState(minute_count=10)
        state.clients["192.168.1.1"] = client_state
        persistence.save(state)

        config = RateLimitConfig(requests_per_minute=60)
        limiter = PersistentRateLimiter(config=config, persistence=persistence)

        limiter.load_state_on_init()

        assert "192.168.1.1" in limiter._clients

    def test_check_rate_limit_saves_state(self, temp_state_file: Path, persistence: RateLimiterStatePersistence):
        config = RateLimitConfig(requests_per_minute=60)
        limiter = PersistentRateLimiter(config=config, persistence=persistence)

        limiter.load_state_on_init()
        allowed, info = limiter.check_rate_limit("127.0.0.1")

        assert allowed is True

        loaded_state = persistence.load()
        assert loaded_state is not None
        assert loaded_state.version == CURRENT_SCHEMA_VERSION

    def test_reset_client_saves_state(self, temp_state_file: Path, persistence: RateLimiterStatePersistence):
        config = RateLimitConfig(requests_per_minute=1)
        limiter = PersistentRateLimiter(config=config, persistence=persistence)

        limiter.load_state_on_init()

        allowed, _ = limiter.check_rate_limit("127.0.0.1")
        assert allowed is True

        limiter.reset_client("127.0.0.1")

        loaded_state = persistence.load()
        assert loaded_state is not None

    def test_clear_all_saves_state(self, temp_state_file: Path, persistence: RateLimiterStatePersistence):
        config = RateLimitConfig(requests_per_minute=60)
        limiter = PersistentRateLimiter(config=config, persistence=persistence)

        limiter.load_state_on_init()

        limiter._clients["192.168.1.1"] = ClientState(minute_count=5)
        limiter._clients["192.168.1.2"] = ClientState(minute_count=10)

        limiter.clear_all()

        loaded_state = persistence.load()
        assert loaded_state is not None
        assert len(loaded_state.clients) == 0

    def test_survives_restart(self, temp_state_file: Path):
        state_file = temp_state_file
        persistence1 = RateLimiterStatePersistence(state_file=state_file)

        config = RateLimitConfig(requests_per_minute=60)
        limiter1 = PersistentRateLimiter(config=config, persistence=persistence1)

        limiter1.load_state_on_init()

        current_time = time.monotonic()
        limiter1._clients["192.168.1.1"] = ClientState(blocked_until=current_time + 100)

        limiter1._persist_state()

        persistence2 = RateLimiterStatePersistence(state_file=state_file)
        limiter2 = PersistentRateLimiter(config=config, persistence=persistence2)
        limiter2.load_state_on_init()

        assert "192.168.1.1" in limiter2._clients
        assert limiter2._clients["192.168.1.1"].blocked_until > current_time


class TestConcurrentAccess:
    def test_concurrent_load_and_save(self, temp_state_file: Path):
        persistence = RateLimiterStatePersistence(state_file=temp_state_file)

        def save_thread():
            for _ in range(10):
                state = RateLimiterState()
                client_state = RateLimiterClientState(minute_count=1)
                state.clients["192.168.1.1"] = client_state
                persistence.save(state)
                time.sleep(0.01)

        def load_thread():
            for _ in range(10):
                persistence.load()
                time.sleep(0.01)

        thread1 = threading.Thread(target=save_thread)
        thread2 = threading.Thread(target=load_thread)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        state = persistence.load()
        assert state is not None
