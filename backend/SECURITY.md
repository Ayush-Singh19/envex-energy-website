# Security controls

How the backend meets *Envex Energy Backend — Security* (4 Oct 2026). Each control names
where it lives and the test that proves it. Items marked **deploy** can only be done on
the live hosting and are listed again in the pre-launch checklist at the end.

## Authentication and sessions

| Control | Implementation | Test |
| --- | --- | --- |
| No public sign-up; CLI only | `app/scripts/create_admin.py` | `test_auth.py::test_create_admin_cli` |
| bcrypt, cost 12 | `app/core/security.py` (`BCRYPT_ROUNDS = 12`) | login tests |
| Password policy: 12+ chars, common-password list, no company name / email / sequences | `app/core/passwords.py` | `test_change_password_rejects_weak_passwords` |
| Seed password must be changed at first sign-in | `admin_users.must_change_password`; `get_current_admin` returns 403 until changed; admin UI forces the change | `test_seed_admin_must_change_password…`, `test_every_admin_route_blocks_a_seed_password` |
| Lockout 15 min after 5 failures; one generic message for every failure (incl. locked/inactive) | `app/services/auth_service.py` | `test_lockout_after_5_failures…`, `test_bad_credentials_get_the_same_generic_error` |
| Unknown emails cost the same time as real ones | dummy bcrypt check | live check (timing ratio 1.00) |
| JWT HS256, 64-byte secret, 8 h, admin id only | `create_access_token`; production refuses a secret under 86 chars | `test_session_token_carries_only_the_admin_id`, `test_production_refuses_weak_configuration` |
| `alg: none` and algorithm swaps rejected | `algorithms=["HS256"]` pinned | `test_invalid_tokens_are_rejected[alg_none]` |
| Cookie `HttpOnly`, `Secure` (prod), `SameSite=Strict`, `Path=/` | `app/api/v1/auth.py` | `test_login_sets_hardened_session_cookie`, `test_cookie_is_secure_in_production` |
| Password change / reset invalidates older sessions (token version) | `admin_users.token_version` in every token | `test_change_password_signs_out_every_other_session` |
| One guard on every `/admin` route | router-level `Depends(get_current_admin)` | `test_every_admin_route_requires_a_session` (routes discovered from the app, so new routes are covered automatically) |

## Input validation and abuse

| Control | Implementation | Test |
| --- | --- | --- |
| Max length on every string; unknown fields rejected; consent must be JSON `true` | `extra="forbid"`, `StrictBool` in `app/schemas/` | `test_unknown_enquiry_fields_are_rejected`, `test_consent_must_be_a_real_boolean` |
| Phone regex then E.164; 11 project types; email check | `app/schemas/enquiry.py`, `app/core/phone.py` | `test_enquiries.py`, `test_phone.py` |
| Parameterised queries only; LIKE wildcards escaped | SQLAlchemy throughout | `test_sql_injection_is_stored_as_plain_text`, `test_search[%]` |
| WhatsApp link built and encoded server-side | `app/services/whatsapp_service.py` | `test_whatsapp.py` |
| Requests over 16 KB rejected (declared or streamed) | `BodySizeLimitMiddleware` | `test_bodies_over_16kb_are_rejected`, `test_streamed_body_without_length_is_also_capped` |
| Rate limits: enquiries 5/10 min (429 offers the phone number), events 60/min, login 10/min | `app/core/rate_limit.py` | `test_rate_limit_is_five_per_ten_minutes_per_ip`, `test_enquiry_rate_limit_message_offers_the_phone_number`, `test_login_is_rate_limited_per_ip` |
| Rate limits can't be dodged with a forged `X-Forwarded-For` | `app/core/client_ip.py` (`TRUSTED_PROXY_HOPS`) | `test_client_ip.py` |
| Honeypot: fake 201, nothing stored | `enquiry_service.submit_enquiry` | `test_honeypot_returns_fake_success_and_stores_nothing` |

## Browser protections

| Control | Implementation | Test |
| --- | --- | --- |
| CORS: production site only (localhost in development); never credentials | `Settings.cors_origins` | `test_cors_never_allows_credentials_or_foreign_origins`, `test_dev_origins_are_not_allowed_in_production` |
| HSTS (prod), `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` | `SecurityHeadersMiddleware` | `test_security_headers_on_every_response` |
| CSP on `/admin`: scripts from itself only (stricter than the doc: Chart.js was dropped) | `ADMIN_CSP` | `test_admin_csp_allows_only_its_own_scripts` |
| Enquiry text never rendered as HTML | admin UI builds text nodes only | browser check: `<script>` / `<img onerror>` leads show as text, nothing runs |

## Data protection

| Control | Implementation | Test |
| --- | --- | --- |
| Consent checkbox, stored with each enquiry | site form + `enquiries.consent` | `test_invalid_field_is_rejected[consent]` |
| Delete on request, audit-logged without personal data | `DELETE /api/v1/admin/enquiries/{id}`; admin UI "Delete this enquiry" | `test_delete_on_request_removes_the_record_and_audits_without_personal_data` |
| Retention: enquiries 24 months after last activity, audit and clicks 12 months | `app/services/retention_service.py`; run `python -m app.scripts.purge_old_data` daily (**deploy**: schedule it) | `test_retention_purge` |
| Exports audit-logged; CSV formula injection neutralised | `export_service` | `test_csv_export` |
| Alert email: details to call back only, no admin links | `templates/email/new_enquiry.html` | `test_alert_email_sent_via_smtp_with_escaped_html` |

## Logging and errors

| Control | Implementation | Test |
| --- | --- | --- |
| Request log: id, method, path, status, duration, truncated IP; never query strings or bodies | `RequestContextMiddleware` | `test_request_log_has_truncated_ip_and_no_query_string` |
| Never log passwords, phones, emails, messages | services log ids only | `test_passwords_never_reach_the_logs`, `test_admin_actions_never_log_personal_data`, `test_alert_is_logged_not_sent_without_smtp_and_logs_hold_no_pii` |
| Login failures, lockouts and rate-limit hits are logged | `login_failed`, `login_locked`, `rate_limited` events | `test_enquiry_rate_limit_message_offers_the_phone_number` |
| No stack traces to clients; `/docs` off in production | error handlers; `create_app` | `test_production_hides_docs_adds_hsts_and_hides_errors` |
| Sentry: no PII, no request bodies, cookies or user | `_scrub_event`, `max_request_body_size="never"` | `test_sentry_scrubber_drops_bodies_cookies_and_user` |

## Supply chain

- Dependencies pinned in `uv.lock`; Dependabot weekly (`.github/dependabot.yml`).
- CI (`.github/workflows/backend-ci.yml`): ruff (incl. security rules), pip-audit `--strict`,
  migration drift check, full test suite on Postgres 16, gitleaks over the full history.
- Container runs as a non-root user on `python:3.12-slim`.

## Pre-launch checklist status

| Item | Status |
| --- | --- |
| Every `/admin` route returns 401 without a session | Done (automated) |
| Lockout after 5 failed logins | Done (automated + live) |
| Cookie HttpOnly, Secure, SameSite=Strict | Done (automated) |
| Seed password changed; policy enforced | Done in code. The local admin is flagged to change at next sign-in |
| `<script>` in an enquiry shows as plain text | Done (browser check) |
| No secrets in the repo; `.env` not committed | Done (gitleaks: full history clean) |
| `/docs` disabled in production | Done (automated + production container) |
| Logs hold no phones, emails or messages | Done (automated) |
| pip-audit: no critical vulnerabilities | Done (no known vulnerabilities) |
| Consent checkbox on the form | Done |
| Privacy notice linked from the form | **Open**: needs the notice text (legal review per the doc) |
| HTTPS on site and API; HTTP redirects | **deploy** |
| CORS allows only the production URL | **deploy**: set `FRONTEND_URL` (code enforces https in production) |
| Security headers on the live URL (securityheaders.com) | **deploy** |
| Rate limits and honeypot verified on the live URL | **deploy** (set `TRUSTED_PROXY_HOPS=1` on Render/Railway) |
| Sentry and UptimeRobot alerts tested | **deploy** |
| Daily backups on; one restore tested | **deploy** |
| Retention job scheduled daily | **deploy** |
| Hosting dashboards with two-factor login; separate prod/dev databases and secrets | **deploy** |
