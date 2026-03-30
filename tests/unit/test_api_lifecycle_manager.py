"""Тесты stateful lifecycle-менеджера API."""

from core.api_lifecycle_manager import ApiLifecycleManager


class TestApiLifecycleManager:
    """Проверки переходов lifecycle-состояний API."""

    def test_default_state_created(self) -> None:
        """Менеджер стартует в состоянии created."""
        manager = ApiLifecycleManager()
        assert manager.get_state() == "created"

    def test_try_begin_start_success(self) -> None:
        """Переход в starting должен быть разрешён из стабильных состояний."""
        manager = ApiLifecycleManager()

        assert manager.try_begin_start() is True
        assert manager.get_state() == "starting"

    def test_try_begin_start_denied_during_transition(self) -> None:
        """Повторный start во время перехода должен быть отклонён."""
        manager = ApiLifecycleManager()
        manager.set_state("stopping")

        assert manager.try_begin_start() is False
        assert manager.get_state() == "stopping"

    def test_try_begin_stop_denied_while_starting(self) -> None:
        """Остановка во время starting должна быть отклонена."""
        manager = ApiLifecycleManager()
        manager.set_state("starting")

        assert manager.try_begin_stop() is False
        assert manager.get_state() == "starting"

    def test_try_begin_stop_success(self) -> None:
        """Остановка из running должна переводить в stopping."""
        manager = ApiLifecycleManager()
        manager.set_state("running")

        assert manager.try_begin_stop() is True
        assert manager.get_state() == "stopping"
