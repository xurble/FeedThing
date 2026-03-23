# Code Review Findings

## P0 - Security / Cross-Tenant Integrity

### Untrusted feed content is rendered as trusted HTML
- `ft/templatetags/ft_tags.py:47-56` returns feed bodies with `mark_safe()` after only string replacements, so scripts, inline event handlers, `javascript:` URLs, and other active content survive unchanged.
- `ft/templatetags/ft_tags.py:21-39` also returns the river summary via `mark_safe()`, and `ft/templates/feed.html:43`, `ft/templates/river.html:26`, and `ft/templates/savedposts.html:66` render post titles with `|safe`.
- Impact: any subscribed feed can execute JavaScript in a logged-in reader’s browser, which enables account takeover, CSRF bypass against same-origin endpoints, and stored XSS across every user who subscribes to that feed.

### Authenticated users can force server-side requests to arbitrary URLs
- `ft/views.py:201-248` fetches the user-supplied `feed` URL directly with `requests.get(...)` before validating ownership, destination, or scheme.
- `verify=False` at `ft/views.py:206` disables TLS verification on top of that.
- Impact: this is an SSRF primitive against internal services and metadata endpoints, and it also makes outbound HTTPS fetches vulnerable to man-in-the-middle tampering.

### Feed maintenance endpoints mutate or expose global feed state without admin checks
- `feedthing/urls.py:25,47,49` exposes `/feedgarden/`, `/feed/<id>/revive/`, and `/feed/<id>/test/`.
- `ft/views.py:183-186`, `ft/views.py:503-517`, and `ft/views.py:521-531` only require login, but they operate on global `Source` rows instead of the caller’s own subscriptions.
- Impact: any regular user can inspect feed diagnostics for sources they do not own, force re-polls by resetting `due_poll`, and interfere with feed-processing state for every tenant.

## P1 - Security / Availability

### Anyone on the internet can trigger a full refresh cycle
- `feedthing/urls.py:17` exposes `/refresh/` publicly, and `ft/views.py:617-625` calls `update_feeds(3, response)` with no authentication, throttling, or method restriction.
- `ft/templates/feedgarden.html:12` links to this as “Manual Refresh”, but the server does not enforce that it is an admin-only operation.
- Impact: external callers can repeatedly trigger expensive polling work and turn feed refresh into a denial-of-service vector.

### Several ownership and method failures fall through to 500s instead of returning 403/405
- `ft/views.py:359-370`, `ft/views.py:373-396`, `ft/views.py:399-447`, `ft/views.py:502-517`, and `ft/views.py:534-559` all have execution paths where unauthorized users or unexpected methods return `None`.
- Examples: requesting another user’s subscription details, calling `promote`/`addto` on someone else’s subscription, or hitting `revivefeed` with `GET`.
- Impact: callers get 500s instead of clean permission errors, and object existence can be inferred from different failure behavior.

## P2 - Product Behavior / Functional Regressions

### Manage Feeds refresh path is wired to an endpoint that no longer exists
- The client calls `/subscription/list/` in `ft/templates/manage.html:287-293`.
- The only matching view is commented out in `ft/views.py:157-165`, and the route is also commented out in `feedthing/urls.py:39`.
- Impact: after rename, regroup, or unsubscribe operations, the management pane cannot refresh its left-hand feed list and will drift out of sync until the page is reloaded.

### Save/forget actions are not idempotent and will 500 on normal repeated clicks
- `ft/models.py:69-70` enforces uniqueness of `(post, user)` for saved posts.
- `ft/views.py:562-572` always inserts a new `SavedPost`, while `ft/views.py:575-583` blindly indexes `[0]` when removing one.
- Impact: double-clicking save, replaying the request, or forgetting an already-forgotten post raises server errors instead of returning a stable success response.

### The checked-in test suite does not cover app behavior, and the current setup is not self-testing
- `ft/tests.py:1-16` is still the default `1 + 1 == 2` placeholder, and `web/tests.py:1-3` is empty.
- Running `python manage.py test` currently fails before executing any tests because the project expects a live MySQL server (`django.db.utils.OperationalError: Can't connect to local MySQL server through socket '/tmp/mysql.sock'`).
- Impact: the risky areas above have no automated regression coverage, and contributors cannot rely on CI-like feedback from a fresh checkout.
