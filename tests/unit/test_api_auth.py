"""
Тесты для модуля аутентификации API
====================================

Проверяет функциональность API Key аутентификации.
"""

import os
from unittest.mock import patch

import pytest
from flask import Flask

from api.auth import (
    API_KEY_CONFIG_KEY,
    API_KEY_ENV_VAR,
    API_KEY_HEADER,
    AUTH_DISABLED_CONFIG_KEY,
    check_api_key,
    generate_api_key,
    get_api_key,
    get_stored_api_key,
    init_api_auth,
    optional_api_key,
    require_api_key,
    set_stored_api_key,
)


@pytest.fixture(autouse=True)
def disable_credential_manager(monkeypatch: pytest.MonkeyPatch):
    """Отключает реальный Credential Manager в unit-тестах."""
    monkeypatch.setattr(
        "api.auth._get_api_key_from_credential_manager", lambda: None
    )
    monkeypatch.setattr(
        "api.auth._set_api_key_in_credential_manager",
        lambda _api_key: False,
    )


class TestGenerateApiKey:
    """Тесты генерации API ключа."""

    def test_generate_key_length(self):
        """Проверка длины сгенерированного ключа."""
        key = generate_api_key()
        # token_urlsafe(32) генерирует ~43 символа
        assert len(key) >= 40
        assert len(key) <= 50

    def test_generate_key_uniqueness(self):
        """Проверка уникальности ключей."""
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100

    def test_generate_key_url_safe(self):
        """Проверка URL-безопасности ключа."""
        key = generate_api_key()
        # Ключ должен содержать только URL-безопасные символы
        import string

        allowed = string.ascii_letters + string.digits + "-_"
        assert all(c in allowed for c in key)


class TestGetStoredApiKey:
    """Тесты получения сохранённого ключа."""

    def test_get_from_env(self):
        """Проверка получения ключа из переменной окружения."""
        test_key = "test-api-key-12345"
        with patch.dict(os.environ, {API_KEY_ENV_VAR: test_key}):
            result = get_stored_api_key()
            assert result == test_key

    def test_get_when_not_set(self):
        """Проверка когда ключ не установлен."""
        with patch.dict(os.environ, {}, clear=True):
            # Удаляем переменную если она есть
            os.environ.pop(API_KEY_ENV_VAR, None)
            result = get_stored_api_key()
            assert result is None

    def test_get_ignores_masked_env_value(self):
        """Маскированное значение в env не должно использоваться."""
        with patch.dict(os.environ, {API_KEY_ENV_VAR: "test****1234"}):
            result = get_stored_api_key()
            assert result is None


class TestSetStoredApiKey:
    """Тесты сохранения API ключа в постоянное хранилище."""

    def test_set_stored_api_key_uses_env_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При недоступном Credential Manager ключ НЕ сохраняется в env."""
        monkeypatch.setenv(API_KEY_ENV_VAR, "old-value")
        set_stored_api_key("new-value")
        # Новое поведение: env НЕ используется как fallback
        assert os.environ[API_KEY_ENV_VAR] == "old-value"
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)

    def test_set_stored_api_key_clears_env_on_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Пустое значение должно очищать env."""
        monkeypatch.setenv(API_KEY_ENV_VAR, "old-value")
        set_stored_api_key("")
        assert API_KEY_ENV_VAR not in os.environ

    def test_set_stored_api_key_calls_credential_manager(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Проверка вызова Credential Manager при доступности."""
        calls: list[str | None] = []

        def _store(key: str | None) -> bool:
            calls.append(key)
            return True

        monkeypatch.setattr(
            "api.auth._set_api_key_in_credential_manager",
            _store,
        )
        set_stored_api_key("stored-value")

        assert calls == ["stored-value"]
        # Новое поведение: при успешном сохранении в Credential Manager
        # ключ НЕ записывается в env
        assert API_KEY_ENV_VAR not in os.environ

    def test_set_stored_api_key_rejects_masked_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Маскированный ключ должен очищать хранилище и env."""
        monkeypatch.setenv(API_KEY_ENV_VAR, "old-value")
        set_stored_api_key("test****1234")
        assert API_KEY_ENV_VAR not in os.environ


class TestInitApiAuth:
    """Тесты инициализации аутентификации."""

    def test_init_with_provided_key(self):
        """Проверка инициализации с предоставленным ключом."""
        app = Flask(__name__)
        test_key = "my-secret-key-12345"

        result = init_api_auth(app, api_key=test_key)

        assert result == test_key
        assert app.config[API_KEY_CONFIG_KEY] == test_key

    def test_init_generates_key_if_none(self):
        """Проверка генерации ключа если не предоставлен."""
        app = Flask(__name__)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop(API_KEY_ENV_VAR, None)
            result = init_api_auth(app)

            assert result is not None
            assert len(result) >= 40
            assert app.config[API_KEY_CONFIG_KEY] == result

    def test_init_uses_env_key(self):
        """Проверка использования ключа из переменной окружения."""
        app = Flask(__name__)
        env_key = "env-api-key-67890"

        with patch.dict(os.environ, {API_KEY_ENV_VAR: env_key}):
            result = init_api_auth(app)

            assert result == env_key
            assert app.config[API_KEY_CONFIG_KEY] == env_key


class TestRequireApiKey:
    """Тесты декоратора require_api_key."""

    @pytest.fixture
    def app(self):
        """Создание тестового Flask приложения."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def client(self, app):
        """Создание тестового клиента."""
        return app.test_client()

    def test_no_key_returns_401(self, app, client):
        """Проверка возврата 401 без ключа."""
        init_api_auth(app, api_key="test-key")

        @app.route("/protected")
        @require_api_key
        def protected():
            return {"success": True}

        response = client.get("/protected")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert "API ключ" in data["error"]

    def test_invalid_key_returns_401(self, app, client):
        """Проверка возврата 401 с неверным ключом."""
        init_api_auth(app, api_key="correct-key")

        @app.route("/protected")
        @require_api_key
        def protected():
            return {"success": True}

        response = client.get(
            "/protected", headers={API_KEY_HEADER: "wrong-key"}
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    def test_valid_key_allows_access(self, app, client):
        """Проверка доступа с правильным ключом."""
        test_key = "correct-api-key"
        init_api_auth(app, api_key=test_key)

        @app.route("/protected")
        @require_api_key
        def protected():
            return {"success": True}

        response = client.get("/protected", headers={API_KEY_HEADER: test_key})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_no_auth_in_testing_mode_requires_explicit_disable(
        self, app, client
    ):
        """Проверка что в TESTING режиме требуется явное отключение аутентификации."""
        # Не вызываем init_api_auth, TESTING=True, но AUTH_DISABLED не установлен
        app.config[API_KEY_CONFIG_KEY] = None
        app.config["TESTING"] = True
        app.config[AUTH_DISABLED_CONFIG_KEY] = False

        @app.route("/protected")
        @require_api_key
        def protected():
            return {"success": True}

        response = client.get("/protected")

        # Без явного отключения - ошибка 500
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "не настроен" in data["error"].lower()

    def test_auth_explicitly_disabled_in_testing_mode(self, app, client):
        """Проверка доступа при явном отключении аутентификации в TESTING режиме."""
        app.config[API_KEY_CONFIG_KEY] = None
        app.config["TESTING"] = True
        app.config[AUTH_DISABLED_CONFIG_KEY] = True

        @app.route("/protected")
        @require_api_key
        def protected():
            return {"success": True}

        response = client.get("/protected")

        # С явным отключением - доступ разрешён
        assert response.status_code == 200

    def test_no_auth_in_production_returns_error(self, app):
        """Проверка ошибки без аутентификации в production режиме."""
        app.config[API_KEY_CONFIG_KEY] = None
        app.config["TESTING"] = False  # Production mode

        @app.route("/protected")
        @require_api_key
        def protected():
            return {"success": True}

        client = app.test_client()
        response = client.get("/protected")

        # В production режиме возвращается ошибка 500
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "не настроен" in data["error"].lower()

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Timing tests are unstable in CI environment",
    )
    def test_timing_attack_protection(self, app, client):
        """Проверка защиты от timing attacks."""
        import statistics
        import time

        test_key = "a" * 32  # Длинный ключ
        init_api_auth(app, api_key=test_key)

        @app.route("/protected")
        @require_api_key
        def protected():
            return {"success": True}

        def _measure(different_key: str, samples: int) -> list[float]:
            durations: list[float] = []
            for _ in range(samples):
                start = time.perf_counter()
                client.get(
                    "/protected", headers={API_KEY_HEADER: different_key}
                )
                durations.append(time.perf_counter() - start)
            return durations

        # Прогрев, чтобы снизить влияние холодного кэша.
        with patch("api.auth.logger.warning"):
            _measure("x" * 32, samples=5)
            _measure("a" * 31 + "x", samples=5)

            times_wrong = _measure("x" * 32, samples=30)
            times_almost = _measure("a" * 31 + "x", samples=30)

        median_wrong = statistics.median(times_wrong)
        median_almost = statistics.median(times_almost)

        # Время не должно сильно отличаться (медиана устойчива к шуму).
        if min(median_wrong, median_almost) > 0:
            ratio = max(median_wrong, median_almost) / min(
                median_wrong, median_almost
            )
            assert ratio < 4.0, (
                f"Timing attack vulnerability detected: ratio={ratio}"
            )


class TestOptionalApiKey:
    """Тесты декоратора optional_api_key."""

    @pytest.fixture
    def app(self):
        """Создание тестового Flask приложения."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def client(self, app):
        """Создание тестового клиента."""
        return app.test_client()

    def test_no_key_still_allows_access(self, app, client):
        """Проверка доступа без ключа."""
        init_api_auth(app, api_key="test-key")

        @app.route("/optional")
        @optional_api_key
        def optional():
            from flask import g

            return {"authenticated": getattr(g, "is_authenticated", False)}

        response = client.get("/optional")

        assert response.status_code == 200
        data = response.get_json()
        assert data["authenticated"] is False

    def test_valid_key_sets_authenticated(self, app, client):
        """Проверка установки флага аутентификации."""
        test_key = "test-key"
        init_api_auth(app, api_key=test_key)

        @app.route("/optional")
        @optional_api_key
        def optional():
            from flask import g

            return {"authenticated": g.is_authenticated}

        response = client.get("/optional", headers={API_KEY_HEADER: test_key})

        assert response.status_code == 200
        data = response.get_json()
        assert data["authenticated"] is True

    def test_invalid_key_not_authenticated(self, app, client):
        """Проверка с неверным ключом."""
        init_api_auth(app, api_key="correct-key")

        @app.route("/optional")
        @optional_api_key
        def optional():
            from flask import g

            return {"authenticated": g.is_authenticated}

        response = client.get(
            "/optional", headers={API_KEY_HEADER: "wrong-key"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["authenticated"] is False


class TestCheckApiKey:
    """Тесты функции check_api_key."""

    def test_check_valid_key(self):
        """Проверка валидного ключа."""
        app = Flask(__name__)
        test_key = "test-key"
        init_api_auth(app, api_key=test_key)

        result = check_api_key(test_key, app)
        assert result is True

    def test_check_invalid_key(self):
        """Проверка невалидного ключа."""
        app = Flask(__name__)
        init_api_auth(app, api_key="correct-key")

        result = check_api_key("wrong-key", app)
        assert result is False

    def test_check_none_key(self):
        """Проверка None ключа."""
        app = Flask(__name__)
        init_api_auth(app, api_key="test-key")

        result = check_api_key(None, app)
        assert result is False

    def test_check_empty_key(self):
        """Проверка пустого ключа."""
        app = Flask(__name__)
        init_api_auth(app, api_key="test-key")

        result = check_api_key("", app)
        assert result is False

    def test_check_no_auth_configured_raises(self):
        """Проверка что без настройки аутентификации выбрасывается ошибка."""
        app = Flask(__name__)
        app.config[API_KEY_CONFIG_KEY] = None

        with pytest.raises(
            ValueError, match="API аутентификация не инициализирована"
        ):
            check_api_key("any-key", app)

    def test_check_with_current_app(self):
        """Проверка с current_app."""
        app = Flask(__name__)
        test_key = "test-key"
        init_api_auth(app, api_key=test_key)

        with app.app_context():
            result = check_api_key(test_key)
            assert result is True


class TestIntegration:
    """Интеграционные тесты."""

    def test_full_flow(self):
        """Проверка полного цикла аутентификации."""
        app = Flask(__name__)
        app.config["TESTING"] = True

        # Инициализация
        api_key = init_api_auth(app)

        # Защищённый эндпоинт
        @app.route("/api/status")
        @require_api_key
        def status():
            return {"status": "ok"}

        # Публичный эндпоинт
        @app.route("/api/public")
        def public():
            return {"public": True}

        client = app.test_client()

        # Публичный доступен без ключа
        response = client.get("/api/public")
        assert response.status_code == 200

        # Защищённый требует ключ
        response = client.get("/api/status")
        assert response.status_code == 401

        # С правильным ключом доступен
        response = client.get("/api/status", headers={API_KEY_HEADER: api_key})
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"


class TestGetApiKey:
    """Тесты для функции get_api_key."""

    def test_get_api_key_from_app_config(self):
        """Проверка маскирования ключа из конфигурации приложения."""
        app = Flask(__name__)
        test_key = "test-key-from-config"
        app.config[API_KEY_CONFIG_KEY] = test_key

        result = get_api_key(app)

        assert result == "test****nfig"

    def test_get_api_key_from_env_when_no_app(self):
        """Проверка маскирования ключа из переменной окружения."""
        test_key = "env-api-key"
        with patch.dict(os.environ, {API_KEY_ENV_VAR: test_key}):
            result = get_api_key()  # Без app
            assert result == "env-****-key"

    def test_get_api_key_returns_none_when_not_set(self):
        """Проверка возврата None когда ключ не установлен."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop(API_KEY_ENV_VAR, None)
            result = get_api_key()
            assert result is None

    def test_get_api_key_masks_short_value(self):
        """Проверка маскирования короткого ключа."""
        app = Flask(__name__)
        app.config[API_KEY_CONFIG_KEY] = "short"

        result = get_api_key(app)

        assert result == "*****"

    def test_get_api_key_returns_none_for_empty_value(self):
        """Проверка обработки пустого ключа."""
        app = Flask(__name__)
        app.config[API_KEY_CONFIG_KEY] = ""

        result = get_api_key(app)

        assert result is None

    def test_get_api_key_with_current_app_context(self):
        """Проверка маскирования ключа через current_app context."""
        app = Flask(__name__)
        test_key = "context-api-key"
        app.config[API_KEY_CONFIG_KEY] = test_key

        with app.app_context():
            result = get_api_key()
            assert result == "cont****-key"

    def test_get_api_key_runtime_error_fallback_to_env(self):
        """Проверка маскирования fallback на переменную окружения."""
        test_key = "fallback-env-key"
        with patch.dict(os.environ, {API_KEY_ENV_VAR: test_key}):
            # Вызываем без app и без контекста - должен быть fallback на env
            result = get_api_key()
            assert result == "fall****-key"


class TestAPIServerGetApiKey:
    """Тесты для метода APIServer.get_api_key."""

    def test_server_get_api_key_returns_key(self):
        """Проверка что метод возвращает установленный ключ."""
        from api.server import APIServer

        # Создаём сервер с предустановленным ключом через env
        test_key = "server-test-key"
        with patch.dict(os.environ, {API_KEY_ENV_VAR: test_key}):
            server = APIServer()
            result = server.get_api_key()

            assert result == "serv****-key"

    def test_server_get_api_key_returns_none_when_not_set(self):
        """Проверка что метод возвращает None если ключ не установлен."""
        from api.server import APIServer

        # Создаём сервер без ключа в env
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop(API_KEY_ENV_VAR, None)
            # Патчим generate_api_key чтобы вернуть None
            with patch("api.auth.generate_api_key", return_value=None):
                # Пересоздаём сервер чтобы init_api_auth не сгенерировал ключ
                server = APIServer.__new__(APIServer)
                server.app = Flask(__name__)
                server.app.config[API_KEY_CONFIG_KEY] = None
                server.host = "127.0.0.1"
                server.port = 5000
                server._server_thread = None
                server._running = False
                server._callbacks = {}

                result = server.get_api_key()

                assert result is None
