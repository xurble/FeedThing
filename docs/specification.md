# FeedThing Current-State Specification

## Status and scope

This document specifies the externally observable behavior of FeedThing as it
exists today. It covers account access, feed subscription, organization,
reading, saved posts, feed polling, and deployment boundaries.

Known defects and proposed features are recorded separately and are not
requirements. Feed parsing and polling behavior supplied by the pinned
`django-feed-reader` dependency is included where FeedThing exposes or relies on
that behavior.

## Purpose

FeedThing is a self-hosted, multi-user Django feed reader supporting RSS, Atom,
and JSON Feed. It combines chronological unread catch-up with
reverse-chronological river reading, allowing users to follow some feeds without
missing a post while consuming high-volume feeds as a stream.

## Actors

- **Reader:** Manages and reads their own subscriptions.
- **Administrator:** Provisions users and operates the installation.
- **Scheduler/operator:** Periodically triggers feed polling.
- **Feed publisher:** Provides external feed metadata and posts.

## Terminology

- **Source:** A globally shared external feed and its fetched posts.
- **Subscription:** A user's relationship to a source, including its display
  name, read position, folder, and reading mode.
- **Folder:** A source-less subscription that groups subscriptions.
- **Tracked mode:** Unread posts are presented chronologically and marked read
  when opened.
- **River mode:** Posts are presented reverse-chronologically without advancing
  read state.
- **Personal river:** A reverse-chronological view across all sources subscribed
  to by one user.

## Functional requirements

### Accounts and access

- **FT-AUTH-001:** Users authenticate by email and password.
- **FT-AUTH-002:** Public self-registration is disabled. Accounts are
  provisioned by an administrator.
- **FT-AUTH-003:** Administrators can create the initial account through Django's
  `createsuperuser` command and manage accounts through Django administration.
- **FT-AUTH-004:** Users can reset and change passwords through django-allauth.
- **FT-AUTH-005:** Each user has a name, optional salutation, and a preference
  controlling whether their authenticated home page opens the feed list or
  personal river.
- **FT-AUTH-006:** A user's subscriptions, read positions, settings, and saved
  posts are private to that user.

### Feed subscription

- **FT-SUB-001:** An authenticated user can subscribe using an HTTP or HTTPS feed
  URL.
- **FT-SUB-002:** Before the initial fetch, FeedThing rejects URLs using other
  schemes, URLs without a hostname, localhost names, direct private or local IP
  addresses, and hostnames resolving to private, loopback, link-local,
  multicast, reserved, or unspecified addresses.
- **FT-SUB-003:** FeedThing accepts RSS or Atom XML and JSON Feed documents that
  contain entries.
- **FT-SUB-004:** When a supplied URL returns HTML, FeedThing discovers linked
  RSS, Atom, and JSON feeds. One discovered feed may be selected for
  subscription.
- **FT-SUB-005:** A source is shared globally between users. Each user receives
  an independent subscription and read position.
- **FT-SUB-006:** A user cannot hold two subscriptions to the same source.
- **FT-SUB-007:** When subscribing to an existing source with more than ten
  indexed posts, the new subscription initially exposes only the latest ten as
  unread.
- **FT-SUB-008:** A user can import an OPML file. Existing sources are reused and
  missing subscriptions are created; OPML folder structure is not preserved.
- **FT-SUB-009:** A superuser can export all global sources as OPML.

### Organization

- **FT-ORG-001:** A subscription can exist at the root or inside a folder.
- **FT-ORG-002:** The supported hierarchy is exactly one folder level: folders
  contain feeds and cannot contain folders. Deeper structures represent invalid
  legacy data and are not supported behavior.
- **FT-ORG-003:** A user can rename their subscriptions and folders.
- **FT-ORG-004:** A user can move a feed into an existing folder, combine two
  feeds into a new folder, or promote a feed from a folder to the root.
- **FT-ORG-005:** An empty folder is deleted after its final child is removed.
- **FT-ORG-006:** A feed or folder can use tracked mode or river mode.
- **FT-ORG-007:** Unsubscribing the final user from a source deletes the global
  source and its associated posts.

### Reading

- **FT-READ-001:** The default feed list contains root subscriptions with unread
  items. River subscriptions remain visible regardless of unread count.
- **FT-READ-002:** A user can switch to an all-feeds list that includes
  read-up-to-date subscriptions.
- **FT-READ-003:** Opening a tracked subscription displays all unread posts in
  chronological order.
- **FT-READ-004:** Opening a tracked subscription marks all currently available
  posts in that subscription as read. For a folder, the operation applies to its
  child feed subscriptions.
- **FT-READ-005:** When a tracked subscription has no unread posts, its historical
  posts appear reverse-chronologically, ten per page.
- **FT-READ-006:** A river subscription displays posts from its source or folder
  reverse-chronologically, forty per page, without advancing read positions.
- **FT-READ-007:** The personal river combines every source subscribed to by the
  user, reverse-chronologically, at 100 posts per page.
- **FT-READ-008:** The personal river supports case-insensitive search across post
  titles and bodies.
- **FT-READ-009:** A user can make the personal river their default authenticated
  landing page.
- **FT-READ-010:** Feed post bodies and titles are sanitized before rendering.
  River summaries contain plain text and are truncated to approximately 500
  characters.
- **FT-READ-011:** A user can follow a post link to the publisher's original URL.

### Saved posts

- **FT-SAVE-001:** A user can save a post associated with the subscription through
  which they encountered it.
- **FT-SAVE-002:** A user can save a given post at most once.
- **FT-SAVE-003:** Saved posts are ordered by most recent save and displayed ten
  per page.
- **FT-SAVE-004:** Saved posts support case-insensitive search across post titles
  and bodies.
- **FT-SAVE-005:** A user can remove a post from their saved collection.

### Feed polling and health

- **FT-POLL-001:** A polling cycle selects live sources whose next-poll time has
  arrived, processing the oldest-due sources first.
- **FT-POLL-002:** A normal FeedThing refresh cycle processes at most three
  sources.
- **FT-POLL-003:** A deployment is expected to trigger polling periodically,
  approximately every five minutes. The management command is the preferred
  trigger.
- **FT-POLL-004:** Polling uses ETag and Last-Modified validators when available.
- **FT-POLL-005:** Polling frequency adapts according to changes and failures and
  is bounded between 60 minutes and 24 hours.
- **FT-POLL-006:** A permanent redirect updates the source URL. A stable temporary
  redirect may be adopted as permanent after 60 days.
- **FT-POLL-007:** Unsafe redirect targets are rejected.
- **FT-POLL-008:** HTTP failures update source health, delay later polling, and
  may mark a source inactive.
- **FT-POLL-009:** Administrators can inspect the global polling queue, test a
  source fetch, and revive an inactive source.
- **FT-POLL-010:** Feed models, parsing, adaptive scheduling, redirect handling,
  and polling mechanics are supplied by the pinned `django-feed-reader`
  dependency.

## Data rules and invariants

- A user email address is required and unique.
- A source feed URL is globally unique.
- A source owns its posts; deleting the source cascades to its posts.
- A subscription belongs to exactly one user and optionally one source.
- A source-less subscription represents a folder.
- A user's source subscription is unique for the user/source pair.
- Each source maintains a monotonically increasing post index used for per-user
  read positions.
- A saved post is unique for the user/post pair.
- Deleting a user cascades to their subscriptions and saved posts.
- Removing the last subscription to a source through the unsubscribe workflow
  deletes that source.

## Validation, errors, and recovery

- Anonymous requests to reader functionality redirect to authentication.
- Access to another user's readable subscription is forbidden.
- A malformed or unsafe manual feed URL produces an escaped error response and
  is not fetched.
- Initial feed fetches use a 15-second timeout and normal TLS verification.
- Invalid or out-of-range reading pages fall back to the first page.
- Feed polling records status, last result, scheduling, and validator metadata so
  failed sources can be diagnosed or revived.
- Reviving a source marks it live, clears cached validators, and makes it
  immediately due for polling.

## Security and permissions

- Reader workflows require authentication.
- Subscription ownership is the authorization boundary for user-specific
  reading and organization.
- Queue inspection, source testing, source revival, and global OPML export are
  administrator functions.
- Untrusted feed bodies and titles are sanitized using explicit tag, attribute,
  and URL-scheme allowlists.
- Embedded iframes are sandboxed without same-origin permission.
- Manual subscription blocks server-side requests to local and private network
  targets.
- Deployment secrets and installation-specific settings must not be checked into
  version control.

## Installation and compatibility

- **FT-OPS-001:** Deployment-specific database, email, host, secret, logging, and
  feed-service settings live in an ignored `feedthing/settings_server.py` based
  on the supplied example.
- **FT-OPS-002:** The application supports a standard Django WSGI deployment;
  Gunicorn is included as a production server dependency.
- **FT-OPS-003:** Static assets are collected for separate production serving.
- **FT-OPS-004:** Continuous integration runs on Python 3.13 with SQLite.
  Production database selection is deployment-specific.
- **FT-OPS-005:** Outbound feed requests identify FeedThing using its configured
  application user agent.
- **FT-OPS-006:** The current application version reported to feed servers is
  3.7.

## Non-goals and excluded behavior

- Public account registration is not supported.
- Folders deeper than one level are not supported.
- OPML import does not recreate folder organization.
- FeedThing does not expose a public application API.
- Social login providers are not active.
- XMPP, Gemini Feed, and twtxt support are prospective features rather than
  current behavior.
- Parser internals that do not affect FeedThing's observable behavior are outside
  this specification.

## Known defects and contradictions

The following observed behaviors conflict with the approved product intent and
must not be treated as requirements:

- The public `/refresh/` endpoint allows unauthenticated callers to start polling
  work. Scheduled refresh is intended to be an operator function.
- `/feedgarden/`, source revival, and source testing currently accept any
  authenticated user even though they are administrator functions.
- Several ownership and HTTP-method failure paths return server errors instead of
  explicit 403 or 405 responses.
- Manage Feeds attempts to refresh its list through the removed
  `/subscription/list/` endpoint.
- Save and forget operations are not idempotent even though saved-post uniqueness
  is enforced by the database.
- The public landing page says sign-ups are open while the active account adapter
  disables registration.
- The OPML export interface says "your feeds" although it exports all global
  sources and is restricted to superusers.
- The data model can represent nested folders even though supported product
  behavior permits only one level.
- OPML import does not apply all manual-subscription URL safety validation.

## Approved interpretation decisions

- **D-001:** Public registration remains closed; contrary landing-page copy is a
  defect.
- **D-002:** Queue inspection, source revival, and feed-test operations are
  administrator-only functions; broader current access is a defect.
- **D-003:** Public refresh access is a legacy defect. Scheduled polling is an
  operator responsibility.
- **D-004:** Folder depth is exactly one level. Deeper structures are invalid
  legacy data, not supported behavior.
- **D-005:** Deleting a source when its final subscription is removed is
  intentional current behavior.
- **D-006:** Observable polling behavior from the pinned `django-feed-reader`
  dependency is part of this product specification.

## Evidence and traceability

Primary repository evidence:

- `README.md` and `ft/templates/help.html`: product purpose and documented user
  workflows.
- `feedthing/urls.py`: public and authenticated route surface.
- `ft/views.py`: request behavior, authorization, feed addition, organization,
  reading, saved posts, OPML, and refresh behavior.
- `ft/models.py` and migrations: user and saved-post invariants.
- `ft/templates/` and `web/templates/`: visible workflows and client-side
  interactions.
- `ft/templatetags/ft_tags.py`: sanitization and display behavior.
- `ft/tests.py` and `conftest.py`: executable behavior evidence.
- `.github/workflows/tests.yml`: supported CI runtime and canonical test command.
- Pinned `django-feed-reader` models and utilities: sources, posts,
  subscriptions, read tracking, scheduling, fetching, and redirects.
- `TODO.md`: known defects, kept separate from intended behavior.
- GitHub issues 53 through 55: prospective protocol support excluded from the
  current state.

## Coverage gaps

- There are no browser-level acceptance tests for the JavaScript-driven reading
  and feed-management workflows.
- Deployment-specific production database and email behavior cannot be derived
  from the ignored `settings_server.py`.
- The repository does not contain an executable acceptance test for the intended
  administrator-only feed-health boundary because the implementation currently
  contradicts that intent.
- Runtime behavior of remote feed publishers, Cloudflare bypass services, and
  production scheduling depends on external systems.
