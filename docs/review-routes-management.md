# Navigation recovery, operator deletion and routes

The previous browser worker treated a JavaScript execution context destroyed during school navigation as a terminal error. A network-disabled real-Chromium reproduction failed five of five times on the old worker. It passes five of five with navigation-aware frame retries and a loading state. Client polling retries transient frame failures in the same owner-bound session, preserves an existing frame where possible and provides a manual reconnect button. It never resubmits the school password when fetching a frame.

Browser result collection now uses the User-Agent captured before submitting the login form, rather than evaluating JavaScript during a potentially changing final page. Read-only school inputs are not covered by editable input overlays. Safe error categories distinguish expired sessions, busy workers, changing fields and unavailable connections; logs contain action, category and exception class only.

Students use `/login`, `/app`, `/app/history`, `/app/settings`. Operators use `/admin/login`, `/admin`, `/admin/accounts`, `/admin/users`, `/admin/history`. Root redirects to the appropriate entry. Every application path can be loaded directly; the client returns to a validated internal deep link after login. Navigation uses real links and History API with browser back/forward support and per-page titles. Unknown paths remain 404; student requests for operator pages remain forbidden.

The operator can delete school accounts from the account action menu and delete ordinary users from the user list. Both require an explicit confirmation. Account deletion removes encrypted credentials, the trusted browser binding, encrypted cookies and cascading run records. Bound student sessions are revoked so the student can complete verification again. User deletion also cascades owned accounts and local sessions. Running/queued jobs block deletion; the current/last administrator remains protected.

Deleting an account does not reset daily school authentication counters or durable per-day check-in claims. This permits reconnect testing without accidentally enabling repeated submissions. A separate deletion of the ordinary user is available when a complete local student-profile reset is intended.

UI deletion acceptance runs only against explicitly synthetic, isolated local fixtures. No production school account or user is deleted by deployment verification. Real school MFA success remains a separate owner-operated verification step.
