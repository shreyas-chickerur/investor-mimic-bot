import pytest

# All functional tests load full training_data.csv or run end-to-end flows.
# Mark them slow so they are excluded from the default fast run.
def pytest_collection_modifyitems(items):
    for item in items:
        if "functional" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.timeout(120))
