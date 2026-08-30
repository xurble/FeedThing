# Code Review Findings

## P0 — Security / cross-tenant integrity

- [x] **Untrusted feed content was rendered as trusted HTML**  
  Feed bodies and titles are sanitized with nh3 in `ft/templatetags/ft_tags.py` (allowlisted tags/attributes and URL schemes). River summaries strip tags.  
  _Previously: `mark_safe()` after weak replacements; templates used `|safe` for titles._

- [x] **Authenticated users could force server-side requests to risky URLs**  
  `addfeed` calls `_validate_feed_url()` before `requests.get` (`ft/views.py`): http/https only, blocks localhost and private/locally resolved IPs. Outbound fetch uses default TLS verification (`verify=True`).  
  _Previously: unvalidated user URLs and disabled TLS verification._

- [x] **Feed maintenance endpoints mutate or expose global feed state without admin checks**  
  `feedgarden`, `revivefeed`, and `testfeed` now require a superuser. Feed revival also requires POST.  
  _Previously: any logged-in user could inspect diagnostics, reset `due_poll`, and affect shared feed state._

## P1 — Security / availability

- [x] **Anyone on the internet can trigger a full refresh cycle**  
  `/refresh/` now requires a superuser and a CSRF-protected POST. Scheduled polling uses the management command.  
  _Previously: anonymous callers could repeatedly trigger expensive polling._

- [x] **Several ownership and method failures fall through to 500s instead of 403/405**  
  Subscription-management views now return 403 for cross-user access and 405 for unsupported methods.  
  _Previously: several failure paths returned `None` and became noisy 500 responses._

## P2 — Product behaviour / functional regressions

- [x] **Manage Feeds refresh path calls a missing endpoint**  
  `/subscription/list/` is restored as an authenticated, user-scoped HTML fragment endpoint.  
  _Previously: the left-hand list could drift until a full page reload._

- [x] **Save/forget actions are not idempotent**  
  `savepost` uses `get_or_create` and `forgetpost` deletes a filtered queryset, so repeated calls succeed.  
  _Previously: repeated clicks could violate uniqueness or index an empty queryset and return 500._

- [x] **Test suite and local test run**  
  `ft/tests.py` exercises app behaviour with pytest (`pytest.ini`, `conftest.py`). Use SQLite / configured DB for `pytest` or `manage.py test` (see project settings).  
  _Previously: placeholder tests and MySQL-only local assumptions._

## Summary

| Status | Count |
|--------|------:|
| Open   | 0     |
| Done   | 8     |
