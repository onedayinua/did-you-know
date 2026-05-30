Lint and format check the service.

Activate the virtual environment first: `source cenv/bin/activate`

```bash
ruff check <service>/
ruff format --check <service>/
mypy <service>/
```

Report violations. Fix auto-fixable issues. Flag the rest for the developer.