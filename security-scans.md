# Security Scanning

This document describes the automated security scanning setup for this project and records the reasoning behind all false-positive suppressions.

## Tools

Run these from the project root. Install once with `pip install pip-audit bandit semgrep`.
Gitleaks is a standalone binary; download it from https://github.com/gitleaks/gitleaks/releases.

| Tool | Scope | Command |
|---|---|---|
| `pip-audit` | Python dependency CVEs | `pip-audit .` |
| `yarn audit` | JS dependency CVEs | `cd browsing_platform/client && yarn audit` |
| `bandit` | Python SAST | `bandit -r browsing_platform/server/ --configfile pyproject.toml` |
| `semgrep` | Python + TS SAST | `semgrep scan --config "p/python" --config "p/fastapi" --config "p/secrets" browsing_platform/server/` |
| `gitleaks` | Secret scanning in git history | `./gitleaks.exe detect --source .` |
| OWASP ZAP | DAST (dynamic scan of running app) | Import `http://localhost:4444/openapi.json`, active scan with auth header injected via Replacer |

## False Positives

### Bandit B608 — "Possible SQL injection via f-string" (9 locations)

Files: `media.py`, `post.py`, `media_part.py`, `enriched_entities.py`, `tag.py`, `search.py`

**Why it's a false positive:** Bandit flags any f-string inside a SQL query. In all these cases the f-string only interpolates two kinds of values, both safe:

1. **Parameterized placeholder lists** — e.g. `query_in_clause = ', '.join([f"%(id_{i})s" for i in range(len(ids))])`. The resulting string is `%(id_0)s, %(id_1)s, ...` — pure placeholders, no user data. MySQL's driver handles the actual substitution.

2. **Hardcoded column/table names** — in `tag.py`, `{table_name}` and `{id_column}` come from `ENTITY_TAG_TABLES`, a hardcoded dict in the same file, never touched by user input. In `search.py`, column names go through `sanitize_column()` which validates them against the `ALLOWED_COLUMNS` allowlist before interpolation.

Suppressed with `# nosec B608` on each affected line.

---

### Bandit B105 — "Possible hardcoded password" (`file_tokens.py:16`)

```python
FILE_TOKEN_SECRET_ENV = "FILE_TOKEN_SECRET"  # nosec B105
```

**Why it's a false positive:** This is a string containing the *name* of an environment variable, not a credential value. The actual secret is read at runtime via `os.getenv("FILE_TOKEN_SECRET")` and is never committed to the repository.

---

### Bandit B110 — "Try/Except/Pass" (2 locations)

**`file_tokens.py` — hex decode fallback:**
```python
try:
    return bytes.fromhex(s)
except Exception:  # nosec B110
    pass
return s.encode("utf-8")
```
Intentional: if the secret string is not valid hex, fall back to treating it as raw UTF-8 bytes. Both are valid ways to supply the secret; the exception is an expected control-flow branch, not an error being silently swallowed.

**`permissions.py` — request logger enrichment:**
```python
try:
    token_permissions = check_token(token)
    user_id = token_permissions.user_id
except Exception:  # nosec B110
    pass
```
Intentional: this is optional user-ID enrichment for audit logging. If it fails (e.g. token is malformed), the log entry is still written without a user_id. The failure is non-fatal and non-security-relevant.

---

### Semgrep `python-logger-credential-disclosure` (`file_tokens.py:60`)

```python
logger.debug("Generating file token for path: %s", file_path)  # nosemgrep: ...
```

**Why it's a false positive:** Semgrep detects the word "token" in a logger call and assumes a credential is being leaked. `file_path` is the HTTP request path (e.g. `/archives/session-123/video.mp4`), not a secret. The actual token (the encrypted blob) is never logged.

---

---

### OWASP ZAP — `CSP: style-src unsafe-inline` (Medium)

**Why it's accepted:** Material UI uses the emotion CSS-in-JS library which injects styles at runtime via `<style>` tags. Removing `'unsafe-inline'` from `style-src` breaks the entire UI. Eliminating this would require migrating to emotion's CSP nonce mode, which is a significant frontend refactor. Accepted as a known trade-off.

### OWASP ZAP — `HTTP Only Site` (Medium)

**Why it's a false positive:** ZAP scanned the local development server (HTTP only). In production the server runs behind an nginx reverse proxy that handles TLS termination; the HSTS header is already set in the CSP for production (`ENVIRONMENT=production`). Not applicable to the dev scan target.

### OWASP ZAP — `Modern Web Application` / `User Agent Fuzzer` (Informational)

No action required — informational only.

---

### Gitleaks `generic-api-key` (`.env.sample:39`)

Fingerprint: `9650f344cf1415dca70f3d76bf74789988162db8:.env.sample:generic-api-key:39`
Suppressed in `.gitleaksignore`.

**Why it's a false positive:** `.env.sample` is a committed template that documents required environment variables with example placeholder values (e.g. `FILE_TOKEN_SECRET=a1b2c3d4e5f6...`). These are not real secrets. The actual `.env` file with real values is listed in `.gitignore`.
