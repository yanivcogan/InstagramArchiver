# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a three-component system: a **data capture mechanism** a **data ingestion pipeline** and a **browsing platform**.

### Data Capture
The `archive.py` script captures HAR files of browsing sessions on Playwright, and stores them alongside screen recordings and metadata in the `archives/` directory. Each archive is hashed and timestamped.

### Data Ingestion Pipeline
Stored archived are processed under the assumption that the HAR file contain data obtained while browsing Instagram. The data is parsed to reconstruct the underlying entities (accounts, posts, media, etc.)

The `db_loaders/archives_db_loader.py` pipeline processes archives in 4 stages:
- **A - REGISTER**: Scans `archives/` and creates DB records for new folders
- **B - PARSE**: Parses HAR files via `extractors/` modules into structured data
- **C - EXTRACT**: Normalizes entities (accounts, posts, media) into MySQL tables
- **D - THUMBNAILS**: Generates preview images for media files

The extraction logic lives in `extractors/` — HAR files contain raw Instagram API responses (GraphQL and API v1 formats), which are parsed by `structures_extraction*.py` files and converted to Pydantic models in `models.py`, then inserted into MySQL via `db_loaders/db_intake.py`.

### Browsing Platform
**Backend** (`browsing_platform/server/browse.py`): FastAPI app on port 4444. Uses a routes/services pattern — `routes/` handles HTTP and `services/` contains business logic. File access is secured with ChaCha20-Poly1305 encrypted tokens (`FILE_TOKEN_SECRET`). Authentication uses `BROWSING_PLATFORM_DEV=1` bypass for local dev.

**Frontend** (`browsing_platform/client/`): React 18 + TypeScript + Material-UI app. The API endpoint (`REACT_APP_SERVER_ENDPOINT`) is baked into the build at compile time.

### Database
MySQL schema defined in `infra/create_db.sql`. Key entities: `accounts`, `posts`, `media`, `media_parts`, `archiving_sessions`.

### Environment
Copy `.env.sample` to `.env`. Key variables:
- `DB_*` — MySQL connection credentials
- `FILE_TOKEN_SECRET` — 32-byte hex secret for file access token generation
- `BROWSING_PLATFORM_DEV=1` — bypasses all authentication; blocked when `ENVIRONMENT=production`
- `DEFAULT_SIGNATURE` — signature attached to archiving records

### No Tests
There are no automated tests in this project.
