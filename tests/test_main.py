from src.main import hello_world


def test_hello_world() -> None:
    """Test that hello_world returns the expected greeting."""
    assert hello_world() == "Hello, World!"
