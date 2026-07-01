import threading
import time
from pathlib import Path

from api.rate_limiter_persistence import (
    RateLimiterClientState,
    RateLimiterState,
    RateLimiterStatePersistence,
)


class TestPersistenceStateFile:
    def test_state_dir_creation(self, temp_dir: Path):
        state_file = temp_dir / "subdir" / "rate_limiter_state.json"
        persistence = RateLimiterStatePersistence(state_file=state_file)
        state = RateLimiterState()
        client_state = RateLimiterClientState(minute_count=5)
        state.clients["192.168.1.1"] = client_state

        result = persistence.save(state)
        assert result is True
        assert state_file.parent.exists()
        assert state_file.exists()


class TestPersistenceAcrossRestarts:
    def test_persistence_across_restarts(self, temp_dir: Path):
        state_file = temp_dir / "rate_limiter_state.json"

        persistence1 = RateLimiterStatePersistence(state_file=state_file)

        state1 = RateLimiterState()
        client1 = RateLimiterClientState(
            minute_count=10,
            hour_count=100,
            burst_count=5,
            blocked_until=time.monotonic() + 60,
            last_activity=time.monotonic(),
        )
        state1.clients["192.168.1.1"] = client1

        persistence1.save(state1)

        persistence2 = RateLimiterStatePersistence(state_file=state_file)
        state2 = persistence2.load()

        assert len(state2.clients) == 1
        assert "192.168.1.1" in state2.clients
        assert state2.clients["192.168.1.1"].minute_count == 10
        assert state2.clients["192.168.1.1"].hour_count == 100
        assert state2.clients["192.168.1.1"].burst_count == 5
        assert state2.clients["192.168.1.1"].blocked_until > time.monotonic()


class TestConcurrentWrites:
    def test_concurrent_writes_no_corruption(self, temp_dir: Path):
        state_file = temp_dir / "rate_limiter_state.json"
        persistence = RateLimiterStatePersistence(state_file=state_file)

        errors = []

        def write_thread(client_ip, count):
            try:
                for i in range(count):
                    state = RateLimiterState()
                    client_state = RateLimiterClientState(
                        minute_count=i + 1,
                    )
                    state.clients[client_ip] = client_state
                    persistence.save_merge(state)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(5):
            client_ip = f"192.168.1.{i}"
            t = threading.Thread(target=write_thread, args=(client_ip, 10))
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0

        final_state = persistence.load()
        assert final_state is not None
        assert final_state.version > 0

        for i in range(5):
            assert f"192.168.1.{i}" in final_state.clients

    def test_concurrent_load_and_save(self, temp_dir: Path):
        state_file = temp_dir / "rate_limiter_state.json"
        persistence = RateLimiterStatePersistence(state_file=state_file)

        state = RateLimiterState()
        client_state = RateLimiterClientState(minute_count=1)
        state.clients["192.168.1.1"] = client_state
        persistence.save(state)

        errors = []

        def load_thread():
            try:
                for _ in range(20):
                    state = persistence.load()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        def save_thread():
            try:
                for i in range(20):
                    state = RateLimiterState()
                    client_state = RateLimiterClientState(
                        minute_count=i + 1,
                    )
                    state.clients["192.168.1.1"] = client_state
                    persistence.save(state)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        load_t = threading.Thread(target=load_thread)
        save_t = threading.Thread(target=save_thread)

        load_t.start()
        save_t.start()

        load_t.join()
        save_t.join()

        assert len(errors) == 0

        final_state = persistence.load()
        assert final_state is not None
        assert "192.168.1.1" in final_state.clients


class TestDataIntegrity:
    def test_invalid_json_recovery(self, temp_dir: Path):
        state_file = temp_dir / "rate_limiter_state.json"

        persistence = RateLimiterStatePersistence(state_file=state_file)

        state = RateLimiterState()
        client_state = RateLimiterClientState(minute_count=5)
        state.clients["192.168.1.1"] = client_state

        persistence.save(state)

        with open(state_file, "w", encoding="utf-8") as f:
            f.write("{invalid json}")

        restored_state = persistence.load()

        assert restored_state is not None
        assert restored_state.version > 0

    def test_backup_restore_on_error(self, temp_dir: Path):
        state_file = temp_dir / "rate_limiter_state.json"

        persistence = RateLimiterStatePersistence(state_file=state_file)

        state1 = RateLimiterState()
        client1 = RateLimiterClientState(minute_count=10)
        state1.clients["192.168.1.1"] = client1
        persistence.save(state1)

        backup_path = Path(str(state_file) + ".bak")
        assert backup_path.exists()

        with open(state_file, "w", encoding="utf-8") as f:
            f.write("{corrupted}")

        restored = persistence.load()
        assert restored is not None
        assert restored.version > 0

    def test_load_from_backup(self, temp_dir: Path):
        state_file = temp_dir / "rate_limiter_state.json"

        persistence = RateLimiterStatePersistence(state_file=state_file)

        state1 = RateLimiterState()
        client1 = RateLimiterClientState(minute_count=20)
        state1.clients["192.168.1.1"] = client1
        persistence.save(state1)

        backup_path = Path(str(state_file) + ".bak")

        current_state = persistence.load()
        assert current_state is not None
