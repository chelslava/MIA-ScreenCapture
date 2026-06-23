"""
Тесты DI контейнера
===================
"""

import pytest

from core.container import (
    Container,
    get_container,
    reset_container,
)


class TestContainer:
    """Тесты контейнера зависимостей."""

    def test_register_instance(self) -> None:
        """Тест регистрации экземпляра."""
        container = Container()
        obj = {"key": "value"}
        container.register_instance("test", obj)

        assert container.get("test") is obj

    def test_register_factory(self) -> None:
        """Тест регистрации фабрики."""
        container = Container()
        call_count = 0

        def factory() -> dict[str, int]:
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        container.register_factory("test", factory)

        # Каждый вызов создаёт новый экземпляр
        result1 = container.get("test")
        result2 = container.get("test")

        assert result1["count"] == 1
        assert result2["count"] == 2
        assert result1 is not result2

    def test_register_singleton(self) -> None:
        """Тест регистрации синглтона."""
        container = Container()
        call_count = 0

        def factory() -> dict[str, int]:
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        container.register_singleton("test", factory)

        # Все вызовы возвращают один экземпляр
        result1 = container.get("test")
        result2 = container.get("test")

        assert result1["count"] == 1
        assert result2["count"] == 1
        assert result1 is result2

    def test_has_dependency(self) -> None:
        """Тест проверки наличия зависимости."""
        container = Container()
        container.register_instance("test", {})

        assert container.has("test") is True
        assert container.has("nonexistent") is False

    def test_remove_dependency(self) -> None:
        """Тест удаления зависимости."""
        container = Container()
        container.register_instance("test", {})

        assert container.remove("test") is True
        assert container.has("test") is False
        assert container.remove("test") is False

    def test_get_nonexistent_raises(self) -> None:
        """Тест получения несуществующей зависимости."""
        container = Container()

        with pytest.raises(KeyError, match="nonexistent"):
            container.get("nonexistent")

    def test_get_instance_with_default(self) -> None:
        """Тест получения с значением по умолчанию."""
        container = Container()
        default = {"default": True}

        result = container.get_instance("nonexistent", default)
        assert result is default

    def test_get_instance_existing(self) -> None:
        """Тест получения существующей зависимости через get_instance."""
        container = Container()
        obj = {"key": "value"}
        container.register_instance("test", obj)

        result = container.get_instance("test", None)
        assert result is obj

    def test_get_typed_success(self) -> None:
        """Тест получения с проверкой типа."""
        container = Container()
        container.register_instance("test", [1, 2, 3])

        result = container.get_typed("test", list)
        assert result == [1, 2, 3]

    def test_get_typed_wrong_type(self) -> None:
        """Тест ошибки типа при получении."""
        container = Container()
        container.register_instance("test", "string")

        with pytest.raises(TypeError, match="ожидался int"):
            container.get_typed("test", int)

    def test_clear(self) -> None:
        """Тест очистки контейнера."""
        container = Container()
        container.register_instance("test1", {})
        container.register_factory("test2", lambda: {})
        container.register_singleton("test3", lambda: {})

        container.clear()

        assert container.has("test1") is False
        assert container.has("test2") is False
        assert container.has("test3") is False

    def test_list_dependencies(self) -> None:
        """Тест списка зависимостей."""
        container = Container()
        container.register_instance("a", 1)
        container.register_factory("b", lambda: 2)
        container.register_singleton("c", lambda: 3)

        deps = container.list_dependencies()

        assert deps == ["a", "b", "c"]

    def test_priority_instance_over_factory(self) -> None:
        """Тест приоритета экземпляра над фабрикой."""
        container = Container()
        container.register_factory("test", lambda: "from_factory")
        container.register_instance("test", "from_instance")

        assert container.get("test") == "from_instance"

    def test_priority_instance_over_singleton(self) -> None:
        """Тест приоритета экземпляра над синглтоном."""
        container = Container()
        container.register_singleton("test", lambda: "from_singleton")
        container.register_instance("test", "from_instance")

        assert container.get("test") == "from_instance"

    def test_singleton_cache_cleared_on_remove(self) -> None:
        """Тест очистки кэша синглтона при удалении."""
        container = Container()
        call_count = 0

        def factory() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        container.register_singleton("test", factory)
        result1 = container.get("test")

        container.remove("test")
        container.register_singleton("test", factory)
        result2 = container.get("test")

        # После удаления и повторной регистрации счётчик продолжается
        assert result1 == 1
        assert result2 == 2


class TestGlobalContainer:
    """Тесты глобального контейнера."""

    def test_get_container_creates_singleton(self) -> None:
        """Тест создания глобального контейнера."""
        reset_container()
        container1 = get_container()
        container2 = get_container()

        assert container1 is container2

    def test_reset_container(self) -> None:
        """Тест сброса глобального контейнера."""
        container1 = get_container()
        container1.register_instance("test", {})

        reset_container()
        container2 = get_container()

        assert container1 is not container2
        assert not container2.has("test")

    def teardown_method(self) -> None:
        """Очистка после каждого теста."""
        reset_container()
