# Contributing

[🇩🇪 Deutsche Version](CONTRIBUTING.de.md)

Thank you for your interest in this project! Contributions are welcome. This
server is part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide).

## How can I contribute?

**Report bugs:** Create an [Issue](../../issues) with a clear description,
reproduction steps, and expected vs. actual output. Please include your Python
version and OS.

**Suggest features:** Describe the use case, ideally with a reference to the
Swiss energy context (site planning, solar cadastre, Energiestadt label, grid
infrastructure, etc.).

**Contribute code:**

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Write tests for your changes
5. Run linter: `ruff check src/ tests/`
6. Ensure all tests pass: `PYTHONPATH=src pytest tests/ -m "not live"`
7. Commit with a clear message (see [Conventional Commits](https://www.conventionalcommits.org/)): `git commit -m "feat: extend wind turbine details"`
8. Create a Pull Request against `main`

## Code Standards

- Python 3.11+, Ruff for linting and formatting
- Type hints required for all public functions
- Docstrings in English (for international compatibility)
- Comments and error messages may be in German or English
- All MCP tools must set `readOnlyHint: True` (read-only access)
- Pydantic v2 models for all tool inputs
- Follow the existing FastMCP patterns in the source modules

## Data Source Policy

This project uses only open, publicly accessible data sources (OGD). New tools
may only integrate data that is accessible without registration or paid
licensing — in line with the portfolio's **No-Auth-First** principle.

| Source | Documentation |
|--------|--------------|
| GeoAdmin REST API (swisstopo) | [api3.geo.admin.ch](https://api3.geo.admin.ch/) |
| opendata.swiss CKAN API | [opendata.swiss](https://opendata.swiss/) |
| SFOE/BFE | [bfe.admin.ch](https://www.bfe.admin.ch/) |

## Tests

```bash
# Unit tests (no network access required)
PYTHONPATH=src pytest tests/ -m "not live"

# Live tests (require network access)
PYTHONPATH=src pytest tests/ -m "live"
```

**Never** commit API keys or personal credentials.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
