# BOOK-45 auth: OPDS Authentication & Permissions — Implementation Plan

## 1. Context & Architecture

### Problem being solved

The Phase 1 OPDS catalog (BOOK-45) is fully public: every feed is browsable by
anyone and acquisition links are always rendered. This phase adds:

1. **`BasicAuthentication`** on all OPDS views (auth is *attempted* everywhere so
   `request.user` is populated; browse stays public).
2. A root-menu **`Login`** entry that triggers the reader's Basic credential
   prompt (`401`) and, once authenticated, **`302`-redirects to the OPDS root**.
   The entry is shown only to anonymous users — it disappears after login.
3. The **`/opds/v1/books/<pk>/download/`** endpoint with proper auth semantics:
   `401` for unauthenticated users, `403` for authenticated users lacking
   `library.view_book`.
4. A **`can_view_book(user, book)`** helper in `library/services.py` that
   encapsulates the per-book download authorization check. It currently gates on
   the `library.view_book` permission, but takes the `book` so forthcoming
   per-book rules (e.g. **public-domain books downloadable by anyone**) can be
   added without touching any call site.

### Codebase state at plan time (verified on `BOOK-45-initial-opds-implementation`)

- **The OPDS download endpoint does not exist yet.** `OPDSBookDownloadView` and
  its URL pattern were never implemented in `library/opds/`. The serializers
  already emit a `/opds/v1/books/<pk>/download/` acquisition `href`, but it
  currently resolves to nothing in the `opds` namespace. This phase **creates**
  the endpoint. (`library:book_download` at `library/views.py` is the separate
  **web** download view — a Django `PermissionRequiredMixin` view, not OPDS.)
- **Acquisition links are always rendered**, with no `has_perm` gating in
  `serializers.py`. This is the committed, documented, and tested contract
  (`test_*_acquisition_link_always_rendered`). **It is kept** (see Decision B).
- `OPDSBaseView` sets only `permission_classes = [AllowAny]`; it does not set
  `authentication_classes`, so it inherits DRF defaults today.
- `settings.REST_FRAMEWORK` has throttle rates only — no
  `DEFAULT_AUTHENTICATION_CLASSES`.
- The `library.view_book` permission and the `Book access` group already exist
  (`library/migrations/0007_create_book_access_group.py`).

### Target app

`library` — all changes are in `bookshelf/library/opds/` and
`bookshelf/library/services.py`. No new app.

### Schema change required: no  •  Celery required: no  •  UI mode: API only

---

### Decision A — where BasicAuth lives

Set `authentication_classes = [BasicAuthentication]` (**Basic only**, not
Session) on `OPDSBaseView`. Every OPDS view then *attempts* Basic auth — this
populates `request.user` (so the root feed can drop the `Login` entry once a
reader sends cached credentials) — while browse views keep
`permission_classes = [AllowAny]`. Enforcement (`IsAuthenticated`) is added only
on the login and download views.

**Do not** set a global `DEFAULT_AUTHENTICATION_CLASSES` — keep auth per-package
so the rest of the project is unaffected.

**Why Basic-only, not Session-first.** DRF derives the `WWW-Authenticate` header
from the **first** authenticator's `authenticate_header`. `SessionAuthentication`
returns `None` there, which would make anonymous requests yield `403` instead of
`401`. Basic-only guarantees `401 + WWW-Authenticate: Basic`, which is what makes
a reader show its credential prompt.

**Side effect (documented):** a request carrying *invalid* Basic credentials now
gets `401` on *any* OPDS view (DRF raises `AuthenticationFailed` during
authentication, before `AllowAny` runs). Requests with **no** `Authorization`
header still browse anonymously.

### Decision B — feed acquisition-link gating (resolved: always-rendered)

Acquisition (`rel="…/acquisition"`) links in book feed entries **remain always
rendered**; security is enforced only at the `/download/` endpoint (`401`/`403`).
Confirmed by the user.

Rationale: (1) it is the committed, tested, documented "fully browsable"
contract; (2) keeping the link visible is what lets a reader tap *download* on a
book and trigger the Basic credential prompt (a `401`) — the intended UX in
requirement #3; hiding it would force every download through the `Login` entry
first; (3) the real boundary is the endpoint, not the feed.

### Data flows

**Download:**
```
GET /opds/v1/books/<pk>/download/
  → OPDSBookDownloadView (BasicAuthentication attempts auth → request.user)
      → IsAuthenticated: anonymous → NotAuthenticated → 401 + WWW-Authenticate: Basic
      → can_view_book(request.user, book) is False → 403
      → get_book_file_content(book): content is None → 404
      → HttpResponse(content, Content-Disposition=…)            → 200
```

**Login:**
```
GET /opds/v1/login/
  → OPDSLoginView (IsAuthenticated)
      → anonymous → 401 + WWW-Authenticate: Basic   (reader shows credential prompt)
      → authenticated → 302 redirect to opds:root
```

**Root feed:** `build_root_feed(request)` appends the `Login` entry only when
`not request.user.is_authenticated` → 5 entries for anonymous, 4 for
authenticated.

---

## 2. File Modifications

### MODIFY `bookshelf/library/services.py`

Add next to the other service helpers:

```python
def can_view_book(user, book) -> bool:
    """Return True if the user may download this book.

    Currently gates on the ``library.view_book`` permission. The ``book`` is
    accepted so per-book rules (e.g. public-domain books downloadable by anyone)
    can be added later without changing the call sites. Handles ``AnonymousUser``
    gracefully (its ``has_perm`` returns ``False``).
    """
    return bool(user and user.has_perm('library.view_book'))
```

No other change to `services.py`. **`book` is intentionally unused in the body**
— it is part of the public API contract for the public-domain follow-up. Keep
the name `book` (not `_book`) so call sites and the future per-book logic read
naturally; if the linter flags the unused argument, suppress it locally
(`# noqa: ARG001` or equivalent) rather than renaming the parameter. The
docstring already documents why the argument exists, so the suppression is
self-explanatory.

### MODIFY `bookshelf/library/opds/views.py`

- Imports: add `from rest_framework.authentication import BasicAuthentication`,
  `from rest_framework.permissions import IsAuthenticated`,
  `from rest_framework.renderers import JSONRenderer`,
  `from rest_framework.exceptions import PermissionDenied`,
  `from django.http import HttpResponse`, `from django.shortcuts import redirect`,
  and extend the `library.services` import with `can_view_book`,
  `get_book_file_content`.
- `OPDSBaseView`: add `authentication_classes = [BasicAuthentication]`
  (Decision A). Leave `permission_classes = [AllowAny]`, renderer/throttle/
  pagination unchanged.
- **CREATE `OPDSLoginView(OPDSBaseView)`**: `permission_classes = [IsAuthenticated]`;
  `renderer_classes = [JSONRenderer]` (so DRF can render the `401` exception body
  — `OPDSRenderer` expects a feed dict and would raise on `{'detail': …}`; the
  success path returns a redirect that bypasses rendering). `get(self, request)`
  returns `redirect('opds:root')`.
- **CREATE `OPDSBookDownloadView(OPDSBaseView)`**: `permission_classes =
  [IsAuthenticated]`; `renderer_classes = [JSONRenderer]` (same reason; the
  success body is a plain `HttpResponse`, passed through unrendered).
  `get(self, request, pk)`:
  - `book = get_object_or_404(Book, pk=pk)`
  - `if not can_view_book(request.user, book): raise PermissionDenied` → `403`
  - `filename, content, content_type = get_book_file_content(book)`
  - `if content is None: return HttpResponse(status=404)`
  - else `HttpResponse(content, content_type=content_type)` with
    `Content-Disposition: attachment; filename*=…` (reuse the RFC 6266 pattern
    used by the web `BookDownloadView`).

  Inherits `BasicAuthentication` + throttles from `OPDSBaseView`.

### MODIFY `bookshelf/library/opds/urls.py`

Add two patterns (`<int:pk>` never matches the literal `login`, so no ordering
hazard):

```python
path('login/', views.OPDSLoginView.as_view(), name='login'),
path('books/<int:pk>/download/', views.OPDSBookDownloadView.as_view(), name='book_download'),
```

The `book_download` route is the target the serializers' acquisition `href`
already emits.

### MODIFY `bookshelf/library/opds/serializers.py`

In `build_root_feed`, after the four browse entries, append a `Login` nav entry
**only when** `not request.user.is_authenticated`:

```python
'tag:bookshelf:login', title='Login',
href = _with_sticky_params(opds_base + 'login/', request),
content = 'Sign in to download books'
```

(Built with the same nav-entry helper / logo-thumbnail rule as the other root
entries.) Update the docstring to note the conditional `Login` entry. **No
change** to acquisition-link logic (Decision B).

### MODIFY `bookshelf/library/tests/tests_opds.py`

- Update `OPDSRootFeedTest`: anonymous root now has **5** entries (`Authors,
  Genres, Series, Books, Login`); add an authenticated case asserting **4**.
- Add `CanViewBookTest` and `OPDSLoginViewTest`; fold the download auth
  assertions into the existing `OPDSBookDownloadTest` (the `anon → 403` case
  becomes `anon → 401`). See §4. The `*_acquisition_link_always_rendered` tests
  remain unchanged (Decision B). These edits are mirrored in `BOOK-45.md` §4 and
  `docs/TDD_OPDS.md` §10.

### MODIFY `docs/TDD_OPDS.md` (surgical) and `BOOK-45.md` (surgical)

Edits enumerated in the parent change set: TDD §1, §4 table, §6.1, §6.5/§6.5a
(always-rendered wording), §6.6, §9, §10.2; BOOK-45 Data flow, Permission model,
`BookDownloadView` row, `build_root_feed` note, settings note.

---

## 3. Execution Steps

1. Add `can_view_book(user, book)` to `bookshelf/library/services.py`.
2. Add `authentication_classes = [BasicAuthentication]` to `OPDSBaseView`; add the
   imports.
3. Add `OPDSLoginView` (`IsAuthenticated`, `JSONRenderer`, `get` →
   `redirect('opds:root')`).
4. Add `OPDSBookDownloadView` (`IsAuthenticated`, `JSONRenderer`,
   `can_view_book(request.user, book)` → `403`, `get_book_file_content` →
   `404`/`200`, `Content-Disposition`).
5. Add the `login` and `book_download` URL patterns.
6. In `build_root_feed`: append the anonymous-only `Login` entry; update docstring.
7. `uv run python bookshelf/manage.py check`.
8. Update the root-feed tests (5/4 counts) and add the new auth test classes.
9. Apply the surgical doc edits to `docs/TDD_OPDS.md` and `BOOK-45.md`.
10. `uv run python bookshelf/manage.py test library.tests.tests_opds`.

No new dependencies; no migrations; no dev-server/browser steps.

---

## 4. Test Cases

All in `bookshelf/library/tests/tests_opds.py`, reusing the existing
throttle-reset mixin, `_parse`, `OPDS_BASE`, `NS`, and `create_test_dataset`.
Add a `_basic(username, password)` helper returning
`'Basic ' + base64('user:pass')`, passed via `HTTP_AUTHORIZATION=` (session login
does **not** authenticate Basic-only OPDS views). Download tests need
`BaseTestCase` (real file) and a user in the `Book access` group.

**`CanViewBookTest(TestCase)`** (each call passes a `book` instance)
1. `test_can_view_book_true_with_perm` — user in `Book access` group (re-fetch to
   reset perm cache) → `can_view_book(user, book)` is `True`.
2. `test_can_view_book_false_without_perm` — plain authenticated user →
   `can_view_book(user, book)` is `False`.
3. `test_can_view_book_false_for_anonymous` — `can_view_book(AnonymousUser(), book)`
   → `False`, no exception.

**`OPDSRootFeedTest` (extend)**
4. `test_root_feed_anonymous_has_login_entry` — GET `/opds/v1/` no auth → 5
   entries; titles include `Login`; the `Login` `subsection` href ends
   `/opds/v1/login/`.
5. `test_root_feed_authenticated_omits_login_entry` — GET with valid Basic creds →
   4 entries; `Login` absent. (Also retarget the existing 4-entry tests to the
   anonymous-5 case.)

**`OPDSLoginViewTest`**
6. `test_login_anonymous_returns_401` — GET `/opds/v1/login/` no auth → `401`.
7. `test_login_anonymous_sets_www_authenticate_basic` — `WWW-Authenticate` header
   starts with `Basic`.
8. `test_login_authenticated_redirects_to_root` — GET with valid Basic creds,
   `follow=False` → `302`; `Location` ends `/opds/v1/`.
9. `test_login_invalid_credentials_returns_401` — wrong-password Basic header →
   `401`.

**`OPDSBookDownloadTest(BaseTestCase)`** (existing class, updated for the auth
phase — book with a real EPUB file; `user_with_perm` in `Book access`,
`user_no_perm` plain; Basic creds via `HTTP_AUTHORIZATION`)
10. `test_download_anon_returns_401` — no auth → `401`; `WWW-Authenticate` starts
    with `Basic` (was `test_download_anon_returns_403` in the pre-auth plan).
11. `test_download_user_no_perm_returns_403` — `user_no_perm` creds → `403` (via
    `can_view_book(user, book)`).
12. `test_download_user_with_perm_epub_returns_200` — `user_with_perm` creds →
    `200`; `Content-Disposition` contains `attachment`; body non-empty.
13. `test_download_no_file_returns_404` — `user_with_perm`, book with no file →
    `404`. (The remaining `OPDSBookDownloadTest` rows — fb2-zip, disposition,
    content-matches — are unchanged except for sending Basic creds.)

---

## 5. Key Decisions (summary)

- **Auth placement:** `[BasicAuthentication]` (Basic-only) on `OPDSBaseView`; auth
  attempted on every OPDS view; browse stays `AllowAny`; only `OPDSLoginView` and
  `OPDSBookDownloadView` set `IsAuthenticated`. No global
  `DEFAULT_AUTHENTICATION_CLASSES`. Basic-only guarantees `401 + WWW-Authenticate:
  Basic` (Session-first would yield `403`).
- **Login endpoint:** new `OPDSLoginView` at `opds:login` (`login/`) → `401` for
  anonymous, `302` to `opds:root` once authenticated. `build_root_feed` shows the
  `Login` entry only when anonymous (5 / 4 entries).
- **Download endpoint:** **created** (did not exist) — `OPDSBookDownloadView` at
  `opds:book_download`, `IsAuthenticated` → `401`, `can_view_book(user, book)` →
  `403`, `get_book_file_content` → `404`/`200`.
- **Services helper:** `can_view_book(user, book) -> bool`, anonymous-safe; the
  `book` arg is forward-looking for per-book public-domain rules.
- **Acquisition links:** kept **always-rendered** (Decision B, user-confirmed);
  the three existing always-rendered tests are unchanged.
- **Renderer caveat:** login/download use `JSONRenderer` so DRF can render the
  `401`/`403` exception bodies; success paths (redirect / `HttpResponse`) bypass
  rendering.
