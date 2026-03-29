# Code Review Findings

## P0 — Security / cross-tenant integrity

- [x] **Untrusted feed content was rendered as trusted HTML**  
  Feed bodies and titles are sanitized with nh3 in `ft/templatetags/ft_tags.py` (allowlisted tags/attributes and URL schemes). River summaries strip tags.  
  _Previously: `mark_safe()` after weak replacements; templates used `|safe` for titles._

- [x] **Authenticated users could force server-side requests to risky URLs**  
  `addfeed` calls `_validate_feed_url()` before `requests.get` (`ft/views.py`): http/https only, blocks localhost and private/locally resolved IPs. Outbound fetch uses default TLS verification (`verify=True`).  
  _Previously: unvalidated user URLs and disabled TLS verification._

- [ ] **Feed maintenance endpoints mutate or expose global feed state without admin checks**  
  `feedthing/urls.py` exposes `/feedgarden/`, `/feed/<id>/revive/`, and `/feed/<id>/test/`.  
  `feedgarden`, `revivefeed`, and `testfeed` in `ft/views.py` only require login but operate on global `Source` rows.  
  _Impact: any logged-in user can inspect diagnostics, reset `due_poll`, and affect shared feed state._

## P1 — Security / availability

- [ ] **Anyone on the internet can trigger a full refresh cycle**  
  `/refresh/` is public; `read_request_listener` calls `update_feeds` with no auth or throttling.  
  _Impact: DoS via repeated expensive polling._

- [ ] **Several ownership and method failures fall through to 500s instead of 403/405**  
  Views such as `subscriptiondetails`, `promote`, `addto`, and `revivefeed` can return `None` when the caller is unauthorized or the method is wrong.  
  _Impact: noisy 500s and possible inference from error behaviour._

## P2 — Product behaviour / functional regressions

- [ ] **Manage Feeds refresh path calls a missing endpoint**  
  `ft/templates/manage.html` still requests `/subscription/list/`; the matching view and route remain commented out.  
  _Impact: left-hand list can drift until full page reload._

- [ ] **Save/forget actions are not idempotent**  
  `SavedPost` uniqueness and `savepost` / `forgetpost` in `ft/views.py` still assume a single save row (`[0]` on forget; duplicate insert on double save).  
  _Impact: repeated clicks can 500._

- [x] **Test suite and local test run**  
  `ft/tests.py` exercises app behaviour with pytest (`pytest.ini`, `conftest.py`). Use SQLite / configured DB for `pytest` or `manage.py test` (see project settings).  
  _Previously: placeholder tests and MySQL-only local assumptions._

## Summary

| Status | Count |
|--------|------:|
| Open   | 5     |
| Done   | 3     |
