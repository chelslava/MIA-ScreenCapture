import threading
import time
from pathlib import Path

from flask import Response, jsonify

from api.rate_limiter import rate_limit
from api.rate_limiter_persistence import (
    ClientState,
    PersistentRateLimiter,
    RateLimitConfig,
    RateLimiterClientState,
    RateLimiterState,
    RateLimiterStatePersistence,
)
from api.server import APIServer


def _register_limited_route(server: APIServer) -> None:
    """Регистрирует маршрут, использующий общий API rate limiter."""
    assert server.app is not None

    @server.app.get("/limited")
    @rate_limit
    def limited_route() -> Response:
        return jsonify({"success": True})


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

    def test_api_server_route_observes_persisted_quota(
        self, temp_dir: Path
    ) -> None:
        state_file = temp_dir / "api_server_rate_limiter_state.json"
        first_persistence = RateLimiterStatePersistence(state_file=state_file)
        first_server = APIServer(
            api_key="test-api-key",
            state_persistence=first_persistence,
        )
        _register_limited_route(first_server)

        assert first_server.app is not None
        first_response = first_server.app.test_client().get("/limited")

        assert first_response.status_code == 200
        assert first_response.headers["X-RateLimit-Remaining-Minute"] == "59"
        first_state = first_persistence.load()
        assert first_state.clients["127.0.0.1"].minute_count == 1

        second_persistence = RateLimiterStatePersistence(state_file=state_file)
        second_server = APIServer(
            api_key="test-api-key",
            state_persistence=second_persistence,
        )
        _register_limited_route(second_server)

        assert second_server.app is not None
        assert (
            second_server.app.config["RATE_LIMITER"]
            is second_server._rate_limiter
        )
        second_response = second_server.app.test_client().get("/limited")

        assert second_response.status_code == 200
        assert second_response.headers["X-RateLimit-Remaining-Minute"] == "58"
        assert (
            second_server._rate_limiter._clients["127.0.0.1"].minute_count == 2
        )

    def test_reset_client_does_not_resurrect_after_restart(
        self, temp_dir: Path
    ) -> None:
        state_file = temp_dir / "reset_rate_limiter_state.json"
        config = RateLimitConfig(requests_per_minute=60)
        limiter = PersistentRateLimiter(
            config=config,
            persistence=RateLimiterStatePersistence(state_file),
        )
        limiter.load_state_on_init()
        limiter._clients["192.168.1.1"] = ClientState(minute_count=4)
        limiter._clients["192.168.1.2"] = ClientState(minute_count=9)
        limiter._persist_state()

        limiter.reset_client("192.168.1.1")

        restarted_limiter = PersistentRateLimiter(
            config=config,
            persistence=RateLimiterStatePersistence(state_file),
        )
        restarted_limiter.load_state_on_init()
        assert set(restarted_limiter._clients) == {"192.168.1.2"}
        assert restarted_limiter._clients["192.168.1.2"].minute_count == 9

    def test_clear_all_persists_empty_state_across_restart(
        self, temp_dir: Path
    ) -> None:
        state_file = temp_dir / "clear_rate_limiter_state.json"
        config = RateLimitConfig(requests_per_minute=60)
        limiter = PersistentRateLimiter(
            config=config,
            persistence=RateLimiterStatePersistence(state_file),
        )
        limiter.load_state_on_init()
        limiter._clients["192.168.1.1"] = ClientState(minute_count=4)
        limiter._clients["192.168.1.2"] = ClientState(minute_count=9)
        limiter._persist_state()

        limiter.clear_all()

        restarted_limiter = PersistentRateLimiter(
            config=config,
            persistence=RateLimiterStatePersistence(state_file),
        )
        restarted_limiter.load_state_on_init()
        assert not restarted_limiter._clients


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
                    persistence.load()
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

        current_state = persistence.load()
        assert current_state is not None
