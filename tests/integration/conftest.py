import pytest

# All integration tests require real API keys / live broker connections.
# Mark them slow so they are excluded from the default fast run.
def pytest_collection_modifyitems(items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.timeout(60))
