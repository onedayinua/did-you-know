Run tests for the service.

Activate the virtual environment first: `source cenv/bin/activate`

```bash
pytest <service>/tests/                               # all tests
pytest <service>/tests/test_file.py                   # single file
pytest <service>/tests/test_file.py::test_name        # single test
pytest <service>/tests/ -v                            # verbose
pytest -v -m integration <service>/tests/integration/ # integration only
```

Run unit tests first. Run integration tests only if the ticket has a Root Cause
section or unit tests pass but real behavior is still broken.
Report counts, failures, and any mocking gaps.