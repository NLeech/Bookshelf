# Bookshelf — Project Reference

- Project: 'Bookshelf' — a Django-based online library for EPUB/FB2 books, featuring an OPDS interface, a web reader, and a read-only Flibusta database mirror
- OS: Linux
- Shell: bash
- Environment management: `uv`
- Do not manually activate `.venv`
- Backend: Python, Django 6+, DRF, PostgreSQL, Celery/Redis with `shared_task`
- Frontend: Bootstrap, HTMX
- Auth: Django `allauth`
- Core requirements are defined in `PRD.md`

Do not introduce React, Vue, or SPA-style architecture unless the user explicitly requests that change.
