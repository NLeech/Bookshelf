# AGENTS.md - Guidelines for Agentic Coding

## Project Overview
Bookshelf is a Django-based online library application supporting EPUB books, OPDS interface, user authentication, 
download history, and reading lists.

**Tech Stack:** Django 6+, DRF, PostgreSQL, Celery/Redis, Bootstrap, HTMX, Docker, uv 

---

## Build/Lint/Test Commands

### Running Tests
- **Run all tests:** `python manage.py test`
- **Run specific app tests:** `python manage.py test library` or `python manage.py test authentication`
- **Run single test file:** `python manage.py test bookshelf.library.tests.test_models`
- **Run single test method:** `python manage.py test bookshelf.library.tests.test_models.LoopHierarchyTest.test_wrong_parent`

### Database Operations
- **Create migrations:** `python manage.py makemigrations`
- **Apply migrations:** `python manage.py migrate`
- **Reset database:** `python manage.py flush` (use with caution)

### Development Server
- **Start server:** `python manage.py runserver`
- Default URL: http://127.0.0.1:8000

---

## Code Style Guidelines

### Imports & Dependencies
- Use standard library imports first, then third-party (Django, DRF), then local app imports
- Organize imports alphabetically within each group
- Import specific models from apps: `from library.models import Book`
- Never use wildcard imports (`from module import *`)

### Type Hints & Annotations
- Use type hints for all function parameters and return values (Python 3.12+ required)
- Prefer explicit types over `Any`: `def get_books() -> list[Book]:`
- Use `Optional[X]` or `X | None` for nullable returns
- Type hint class attributes that are used externally

### Naming Conventions
- **Classes:** PascalCase (e.g., `BookService`, `DownloadHistory`)
- **Functions/Methods:** snake_case (e.g., `get_user_books`, `calculate_statistics`)
- **Constants:** UPPER_SNAKE_CASE (e.g., `MAX_DOWNLOADS_PER_DAY`)
- **Private methods:** prefix with single underscore (`_internal_helper`)

### Error Handling
- Use Django's `ValidationError` for model validation errors
- Raise specific exceptions rather than generic `Exception`
- Wrap external API calls in try/except blocks with proper error logging
- Always call `full_clean()` before saving models when custom validation exists

### Testing Standards
- All new features require corresponding tests
- Use `django.test.TestCase` for integration tests
- Leverage `parameterized_class` for testing multiple scenarios (see existing tests)
- Test both valid and invalid input cases
- Mock external services (Celery, Redis, OPDS servers) in unit tests

### Django-Specific Guidelines
- Keep views thin; delegate logic to services or business logic classes
- Use Django's ORM efficiently (avoid N+1 queries with `select_related`, `prefetch_related`)
- Models should have clear `__str__` methods returning meaningful identifiers
- Use Django's built-in authentication system (`allauth`) rather than custom auth
- Apply database indexes on frequently queried fields

### Code Organization
- Place models in `models.py`, views in `views.py`, services in dedicated service modules
- Tests should mirror the structure of the code being tested
- Keep settings modular; use environment variables via `django-environ`
- Document complex business logic with inline comments explaining the "why"

### Formatting & Style
- Follow PEP 8 style guide strictly
- Use 4-space indentation (Django default)
- Limit lines to 79 characters for code, 100 for docstrings/comments
- Use double quotes for strings; single quotes for short identifiers
- Add blank lines between major logical sections in files

---

## Additional Notes
- **No Cursor/Copilot rules exist** - follow these guidelines instead
- **Docker:** Setup planned but not yet implemented (see GEMINI.md)
- **Background Tasks:** Celery integration exists; use `@shared_task` decorator for async operations
- **OPDS Support:** Third-party library integration requires careful error handling for network failures
