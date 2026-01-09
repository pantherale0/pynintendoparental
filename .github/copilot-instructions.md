# GitHub Copilot Instructions for pynintendoparental

## Project Overview

This is a Python library that provides an API client for Nintendo Switch Parental Controls. The library is built with asyncio and uses aiohttp for HTTP requests. It allows users to authenticate with Nintendo's servers and manage parental control settings for Nintendo Switch devices.

## Code Style and Formatting

### Python Version
- Target Python 3.8+ (as specified in setup.py: `python_requires='>=3.8, <4'`)

### Code Formatting
- **Black**: Use Black formatter with 120 character line length (`line-length = 120`)
- **String quotes**: Skip string normalization (use single quotes: `skip-string-normalization = true`)
- **Import sorting**: Use isort with Black profile (`profile = "black"`)
- **Line length**: Maximum 120 characters (enforced by flake8 and Black)

### Linting Rules
- **flake8**: Follow flake8 rules with extended ignore for E203 (whitespace before ':')
- **mypy**: Type hints are required (project uses `py.typed` marker)
- **pylint**: Some files use `# pylint: disable=` comments for specific exceptions

### Running Code Quality Tools
Use the justfile commands for all code quality operations:
```bash
just lint          # Run all linters (black-check, isort-check, flake8, mypy, bandit)
just lint-fix      # Auto-fix formatting issues (black, isort)
just black         # Format code with Black
just isort         # Sort imports
just flake8        # Run flake8 linter
just mypy          # Run type checking
just bandit        # Security vulnerability scanning
```

## Testing

### Test Framework
- **pytest**: Main testing framework
- **pytest-asyncio**: For async tests (asyncio_mode = auto)
- **pytest-cov**: For coverage reporting
- **syrupy**: For snapshot testing

### Coverage Requirements
- Minimum coverage: 90% (`--cov-fail-under=90`)
- Coverage measured with branch coverage enabled

### Running Tests
```bash
just test          # Run tests
just coverage      # Run tests with HTML coverage report
```

### Test Structure
- Tests are located in the `tests/` directory
- Test files follow the pattern `test_*.py`
- Use fixtures defined in `tests/conftest.py` for common setup
- Mock external dependencies (especially HTTP requests)
- Use `unittest.mock` for mocking (AsyncMock, MagicMock, Mock, PropertyMock)
- Async tests should use `async def` and are automatically handled by pytest-asyncio

### Test Naming and Patterns
- Test functions start with `test_`
- Use descriptive test names: `test_<function>_<scenario>` (e.g., `test_send_request_invalid_endpoint`)
- Use `pytest.mark.parametrize` for testing multiple scenarios
- Mock authenticator and HTTP responses in tests

## Project Structure

```
pynintendoparental/
├── __init__.py          # Main entry point with NintendoParental class
├── api.py               # API request handler
├── authenticator.py     # Nintendo authentication handler
├── const.py             # Constants (endpoints, headers, etc.)
├── device.py            # Device model and operations
├── player.py            # Player model
├── application.py       # Application model
├── enum.py              # Enumerations
├── exceptions.py        # Custom exceptions
├── utils.py             # Utility functions
├── _version.py          # Version string
└── py.typed             # PEP 561 type marker
```

## Coding Conventions

### Async/Await
- All API operations are async and should use `async def` and `await`
- HTTP operations use aiohttp.ClientSession
- Use `asyncio.run()` for entry points in examples

### Authentication
- Authentication is handled by the `Authenticator` class from `pynintendoauth` library
- Two authentication methods: session token or interactive login
- Always refresh tokens when expired

### API Requests
- Use the `Api` class for making requests to Nintendo's servers
- Endpoints are defined in `ENDPOINTS` dict in `const.py`
- All requests go through `send_request()` method
- Headers include Nintendo-specific fields (X-Moon-* headers)

### Logging
- Use the module logger: `from .const import _LOGGER`
- Log debug information for API requests and responses
- Follow format: `_LOGGER.debug("message with %s", variable)`

### Error Handling
- Custom exceptions are defined in `exceptions.py`
- Use `HttpException` from pynintendoauth for HTTP errors
- Handle problem+json error responses from Nintendo API
- Raise descriptive errors with meaningful messages

### Type Hints
- Use type hints for all function signatures
- Import types from `typing` module when needed
- The project uses mypy for type checking

### Docstrings
- Use docstrings for classes and public methods
- Format: Triple-quoted strings on the line after definition
- Keep docstrings concise and descriptive

## Dependencies

### Production Dependencies
- `pynintendoauth==1.0.2`: Nintendo authentication library
- Python standard library for most operations

### Development Dependencies
See `setup.py` DEV_REQUIREMENTS for the complete list, including:
- Testing: pytest, pytest-cov, pytest-asyncio, syrupy
- Code quality: black, isort, flake8, mypy, bandit
- Build tools: build, twine

## Development Workflow

### Initial Setup
```bash
just install        # Create venv and install with dev dependencies
```

### Making Changes
1. Write code following the style guidelines
2. Add/update tests in `tests/` directory
3. Run `just lint-fix` to auto-format code
4. Run `just lint` to check code quality
5. Run `just test` to verify tests pass
6. Run `just coverage` to check coverage meets 90% requirement

### Building
```bash
just build          # Build distribution packages
```

### Cleaning
```bash
just clean          # Remove venv, dist, cache files
```

## Common Patterns

### Creating the Main API Object
```python
async with aiohttp.ClientSession() as session:
    auth = Authenticator(session_token, session)
    await auth.async_complete_login(use_session_token=True)
    nintendo = await NintendoParental.create(auth, timezone="Europe/London", lang="en-GB")
```

### API Request Pattern
```python
response = await self._api.send_request("endpoint_name", body=data, **kwargs)
```

### Device Operations
- Devices are accessed via `nintendo.devices` dict
- Device updates use async methods (e.g., `await device.update_max_daily_playtime()`)

## Security Considerations
- Never hardcode session tokens or credentials
- Use the bandit security scanner before committing
- Handle authentication errors appropriately
- Validate all inputs from API responses

## Additional Notes
- The library mimics the official Nintendo mobile app (Android)
- API endpoints are reverse-engineered from the mobile app
- User-Agent and headers must match mobile app to work correctly
- All times/dates should respect timezone settings
