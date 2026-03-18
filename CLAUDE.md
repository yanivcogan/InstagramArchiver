# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a three-component system: a **data capture mechanism**, a **data ingestion pipeline**, and a **browsing platform**.

### Data Capture (`archiver/`)

`archiver/archive.py` is the entry point. It launches a Playwright-controlled Firefox browser, records the screen, captures a HAR file, and saves everything to `archives/` in the project root. Each archive folder contains a screen recording, HAR file, hashes, an affidavit, and metadata JSON.

Supporting modules in `archiver/`:
- `profile_registration.py` / `profile_selection.py` — manage Playwright browser profiles stored in `archiver/profiles/`
- `dialogs.py` — Toga-based GUI dialog forms used during the archiving session
- `summarizers/` — post-session processing: parses the HAR and downloads media
- `executable/` — PyInstaller packaging: `archive.spec`, `build_exe.py`, and build artifacts

`root_anchor.py` (project root) defines `ROOT_DIR` as an absolute path to the project root; all archiver modules import from it for path resolution.

### Data Ingestion Pipeline (`db_loaders/`, `extractors/`)

`db_loaders/archives_db_loader.py` processes archives in 4 stages:
- **A - REGISTER**: Scans `archives/` and creates DB records for new folders
- **B - PARSE**: Parses HAR files via `extractors/` into structured data
- **C - EXTRACT**: Normalizes entities (accounts, posts, media) into MySQL tables
- **D - THUMBNAILS**: Generates preview images for media files

The extraction logic lives in `extractors/` — HAR files contain raw Instagram API responses (GraphQL and API v1 formats), parsed by `structures_extraction*.py` files into Pydantic models (`models.py`, `models_graphql.py`, `models_api_v1.py`), then inserted into MySQL via `db_loaders/db_intake.py`.

### Browsing Platform (`browsing_platform/`)

**Backend** (`browsing_platform/server/server.py`): FastAPI app on port 4444. Uses a routes/services pattern — `routes/` handles HTTP and `services/` contains business logic. File access is secured with ChaCha20-Poly1305 encrypted tokens (`FILE_TOKEN_SECRET`). Authentication uses `BROWSING_PLATFORM_DEV=1` bypass for local dev.

**Frontend** (`browsing_platform/client/`): React 18 + TypeScript + Material-UI + React Router app. Source in `src/` with `pages/`, `services/`, `UIComponents/`, `lib/`, and `types/`. The API endpoint (`REACT_APP_SERVER_ENDPOINT`) is baked into the build at compile time.

### Database

MySQL schema defined in `infra/create_db.sql`. Key entities: `accounts`, `posts`, `media`, `media_parts`, `archiving_sessions`.

### Utilities (`utils/`)

- `db.py` — MySQL connection helper
- `misc.py` — general helpers (IP, system info)
- `ffmpeg_installer.py` / `ffmpeg/` — local FFmpeg management
- `commit_tracker/` — embeds git commit ID into builds
- `opentimestamps/` — OpenTimestamps integration for HAR hash timestamping
- `data_transfers/` — tools for packaging and transferring archives

### Environment

Copy `.env.sample` to `.env`. Key variables:
- `DB_*` — MySQL connection credentials
- `FILE_TOKEN_SECRET` — 32-byte hex secret for file access token generation
- `BROWSING_PLATFORM_DEV=1` — bypasses all authentication; blocked when `ENVIRONMENT=production`
- `DEFAULT_SIGNATURE` — signature attached to archiving records

### No Tests

There are no automated tests in this project.
