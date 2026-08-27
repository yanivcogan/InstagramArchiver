# Presentation Service — public static snapshots, isolated from the browsing platform

Status: **design approved, not implemented.** One decision is deliberately left open
(see [Open decision: transport](#open-decision-transport)).

---

## Context

The browsing platform (BP) holds the entire archive and is a valuable target. Its
current defence is largely obscurity: we do not publicise it and we do not hand out
links. But some archived material is genuinely of public interest and needs to be
shareable, and today the only sharing mechanism (`entity_share_link`) still points a
stranger at BP's hostname. Every share therefore erodes the thing keeping BP safe.

The fix is to stop sharing *access to BP* and start sharing *copies*. A separate,
deliberately dumb, static host — the **presentation service (PS)** — accumulates
frozen HTML + media snapshots. An admin viewing an item in BP clicks "Publish
publicly"; BP builds a redacted static bundle and pushes it to PS; the admin gets a
public URL. PS runs no application code, holds no database, has no credentials for BP,
and does not know BP exists.

The second, non-negotiable requirement is **archiver anonymity**. The people who
captured this material use real platform accounts, and exposing which accounts those
are puts them at risk. Nothing that identifies them may reach PS.

A secondary goal is to fix video over-fetching. Today no `<video>` element in BP sets
`preload`, so opening a page with ten videos starts ten downloads nobody asked for.

---

## Ownership

This work splits cleanly into two tracks that share only the bundle format
([Component 2](#component-2--bundle-format)) and can otherwise proceed in parallel.

**Track A — infrastructure.** [Open decision: transport](#open-decision-transport),
[Component 1](#component-1--the-presentation-service) (PS host, nginx, hardening,
hosting choice, IaC), and the optional `X-Accel-Redirect` work in
[Component 7](#component-7--streaming).

**Track B — application.** [Components 3–6](#component-3--redaction-the-allowlist)
(redaction, assets and provenance, publisher API, UI) and the client-side half of
[Component 7](#component-7--streaming).

Track B can be built and tested end to end against `LocalDirTarget` without any of
Track A existing yet. Track A is not blocked by Track B either — the bundle format is
specified below and PS only ever serves static files.

---

## Decisions already made

| Question | Decision |
|---|---|
| Publishable entities | account, post, media, media_part. **Never** archiving_session. |
| Bundle contents | Publisher chooses per item, minimal defaults |
| Lifecycle | Immutable snapshots; every publish gets a new slug; nothing auto-retracts |
| URL shape | Unguessable random slug (`/p/<22 chars>/`) |
| Indexing | Never — `noindex` everywhere |
| Redaction | Strict allowlist, never a denylist |
| Session identifiers | Omitted from public pages entirely |
| Streaming | `preload="none"` + poster on both platforms; no HLS for now |
| Who may publish | Admins only (`auth_admin_access`) |
| Attribution | Generic project attribution; no individual named |
| Verification | Best available proof per asset, degrading gracefully |
| Hosting | Undecided — build for portability |
| **Transport** | **Open — Track A owns this** |

---

## Open decision: transport

**Do not implement the transport until this is settled.** Everything else can be built
without it, behind the `PublishTarget` interface below.

### Why this is a real problem

Isolation is the entire point of PS. But the moment BP pushes bytes to PS, a link
between the two hosts exists somewhere. An attacker with root on PS can read:

- `/var/log/auth.log` — the source IP of every SSH/SFTP/rsync session. That is BP's
  egress address.
- `~/.ssh/authorized_keys` — the pushing key's comment field, conventionally
  `user@hostname`.
- File mtimes correlated against the public pages, giving away a publishing rhythm.

None of this is exotic. If someone compromises PS specifically in order to find BP,
the logs are the first place they look.

Note also the vectors that no transport choice fixes: both hosts are likely billed to
the same entity, and may sit behind the same registrar or provider ASN. Transport
choice narrows the technical channel; it does not make the two hosts unrelatable to a
determined investigator with legal process.

### Options

**A. SSH push egressing through a VPN or jump host.** BP rsyncs to PS, but the
connection leaves through the VPN the archiver already requires, or through a cheap
jump VPS. PS logs the exit IP, never BP's. One extra hop, no third party sees content.
*Cost: one VPS, or an existing VPN. Residual risk: the jump host becomes a target of
its own, and its logs point at BP.*

**B. Blind drop through object storage.** BP writes the bundle to a write-only bucket;
PS polls and pulls. The two hosts never exchange a packet and PS accepts no inbound
connections at all. *Cost: a third-party provider sees both sides and is subject to
legal process; PS now needs a credential and a poll loop, which is application code on
a host that was supposed to have none.*

**C. Direct SSH push.** Simplest, cheapest, no moving parts. *Accepts that root on PS
yields BP's IP address.*

**D. Human in the loop.** The button builds a bundle and offers it as a download; a
person uploads it from a workstation. No automated path exists to find. *Costs the
one-click workflow, and puts the workstation's IP in the logs instead.*

### How to keep this from blocking

Model the target as an interface and decide later:

```python
class PublishTarget(Protocol):
    def push(self, bundle_dir: Path, slug: str) -> str: ...   # returns public URL
```

with `LocalDirTarget` (dev and tests), `RsyncSshTarget` (A and C — they differ only in
network routing, not in code), and `ObjectStoreTarget` (B). Selected by a
`PUBLISH_TARGET` environment variable. Option D needs no target at all: it is
`LocalDirTarget` plus a download link in the UI.

**Invariant under every option:** the channel is one-directional and append-only. PS
never holds a hostname, key, or credential for BP. Retraction is a manual act
performed on PS by a human over SSH.

### Hygiene on PS that applies regardless

- `access_log off` (or IP-anonymised), sshd logging minimised, no remote log shipping.
- `server_tokens off`, `autoindex off`.
- No source maps, no build metadata, no commit SHA, no author strings in published
  CSS/JS. The published assets must be free of anything identifying the build host or
  the people who built it.
- `Referrer-Policy: no-referrer`, so a reader clicking an outbound link from a
  published page does not leak the slug to the destination.

---

## Threat model — what must never reach PS

Archiver identity is present in more places than expected. The concrete inventory:

| Source | Leak |
|---|---|
| `media.local_url` | `local_archive_har/<profile>_<YYYYMMDD>_<HHMMSS>/videos/....mp4` — the folder name is the capture profile |
| `archiver/profiles/map.json` | maps profile directory name to the real platform account handle |
| `archive_session.metadata` | `profile_name`, `my_ip`, `har_archive` (absolute path including the OS user name), `platform` (hostname, LAN IP, **MAC address**), `signature`, `commit_id`, `branch`, `domain_resolutions` |
| `archive_session.archive_location`, `.external_id` | contain the profile name |
| `affidavit.txt` | names the signatory, public IP, hostname, MAC |
| `media.thumbnail_path` | on failure stores `error: <exception text>` truncated to 200 chars, which can contain the full archive path (`db_loaders/thumbnail_generator.py:224-230`) |
| `account_relation` (followers / following) | frequently contains the archiving accounts |
| `post_like`, `tagged_account` | can contain an archiving account |
| `*.data` JSON blobs | raw platform API responses; may carry viewer-relative fields (`friendship_status`, `has_liked`) computed **for the archiving account** |
| `archiver_account`, `archiver_account_access` | the operators' own social graph |

The existing share-link censor list (`browsing_platform/server/routes/fast_api_request_processor.py:52`)
covers only four of these — `signature`, `profile_name`, `har_archive`, `my_ip`. It is
a denylist and it is already incomplete. **Do not extend it and do not reuse it.** The
publisher gets its own allowlist.

---

## Component 1 — The presentation service

New top-level directory `presentation_service/`. Nothing in it runs on PS except
nginx; the templates and CSS live here because BP renders with them, and only the
*output* is pushed.

```
presentation_service/
  templates/                 # Jinja2 — rendered by BP, never shipped to PS
    base.html.j2
    account.html.j2
    post.html.j2
    media.html.j2
    verification.html.j2     # included partial
  static/
    site.css
    site.js                  # optional, tiny: lightbox only. Pages work without it.
  deploy/
    nginx.conf
    bootstrap.md             # provisioning and hardening runbook
```

On the server, the document root is flat and disconnected:

```
/srv/presentation/
  robots.txt                        # User-agent: *  /  Disallow: /
  index.html                        # neutral landing page; reveals nothing, links nowhere
  static/site.<hash>.css            # content-hashed, immutable, shared by all pages
  static/site.<hash>.js
  p/<slug>/index.html
  p/<slug>/bundle.json              # machine-readable copy of the page's data
  p/<slug>/assets/<sha256[:32]>.<ext>
```

No database, no index, no cross-links between snapshots. A snapshot is reachable only
if you were given its slug.

### nginx requirements (`deploy/nginx.conf`)

- `add_header X-Robots-Tag "noindex, nofollow, noarchive" always;`
- `add_header Referrer-Policy "no-referrer" always;`
- `add_header Content-Security-Policy "default-src 'none'; img-src 'self'; media-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'" always;`
  — with `default-src 'none'`, a published page physically cannot phone home.
- `add_header X-Content-Type-Options nosniff always;`
- `location` for `/p/*/assets/` → `Cache-Control: public, max-age=31536000, immutable`.
  Safe because filenames are content hashes.
- `sendfile on; tcp_nopush on;` — nginx serves byte ranges natively, so video seeking
  and partial playback work with zero application code.
- `autoindex off; server_tokens off;`

### Hosting

Under 100 GB of static files this is a small problem. Rough shapes to evaluate:

- **Small VPS + nginx, CDN in front.** ~$5–7/month for a VPS with enough disk (or a
  smaller instance plus a block volume at roughly €4 per 100 GB), with a free-tier CDN
  absorbing video egress and masking the origin IP. Gives real SSH, which keeps the
  requirement-3 story simple.
- **Small VPS + nginx, no CDN.** No third party sees traffic at all. You pay bandwidth
  directly and the origin IP is exposed to every reader — acceptable, since PS is the
  part that is *meant* to be public.
- **Object storage + static hosting.** Cheapest at rest, near-zero maintenance,
  excellent range-request support for free. But "upload only over SSH" becomes "upload
  only with an API key", which changes the transport story rather than just the
  hosting one — evaluate it together with option B above.

Whatever is chosen, it should be expressible as infrastructure-as-code, and the
provisioning must apply the hygiene list from the transport section.

---

## Component 2 — Bundle format

A bundle is a directory. `bundle.json` is the rendered page's data in
machine-readable form, useful for citation and for re-rendering later without BP:

```json
{
  "schema": 1,
  "slug": "…",
  "published_at": "2026-01-01T00:00:00Z",
  "entity_kind": "post",
  "attribution": "Archived by <project name>",
  "subject": { "platform": "instagram", "…": "allowlisted fields only" },
  "assets": [
    {
      "file": "assets/<sha256[:32]>.mp4",
      "media_type": "video",
      "sha256": "<full sha256>",
      "bytes": 618987,
      "aspect_ratio": 0.5625,
      "poster": "assets/<sha256[:32]>_poster.jpg",
      "provenance": { "tier": "ots", "…": "see Component 4" }
    }
  ],
  "captured_at": "2026-01-01T00:00:00Z"
}
```

`index.html` is generated from this. There is deliberately no back-reference of any
kind: no BP hostname, no internal ids, no session id, no archive folder name.

This file is the contract between Track A and Track B. Track A can serve and test
against a hand-written example; Track B can build against it without a live PS.

---

## Component 3 — Redaction (the allowlist)

New package `browsing_platform/server/services/publishing/`, with `redaction.py` as
the security boundary. Every projection **starts from an empty dict** and copies named
fields in. A column added to the schema next year is invisible to PS by default.

| Entity | Published | Never |
|---|---|---|
| account | `url_suffix`, `display_name`, `bio`, `platform`, optional `post_count`, optional `id_on_platform` | `identifiers`, `data`, `url_parts`, `merged_into_account_id`, internal `id`, **all relations** |
| post | `url_suffix`, `caption`, `publication_date`, `platform` | `data`, internal ids, `notes` |
| media | `media_type`, `aspect_ratio`, rewritten asset path | raw `local_url`, raw `thumbnail_path`, `data`, `annotation` (analyst notes — opt-in only) |
| media_part | `crop_area`, `timestamp_range_start`, `timestamp_range_end` | `notes`, internal ids |
| comment | `text`, `publication_date`, commenter's `url_suffix` and `display_name` | `data`, `notes`, internal ids |
| like / tagged_account | the account's `url_suffix` only | everything else |
| **archive_session** | capture date (UTC, day precision) and platform, and nothing else | `external_id`, `archive_location`, `metadata`, `summary_html`, `structures`, `attachments`, `notes` |

`account_relation` appears in no row. Follower and following lists are never
published — they are where the archiving accounts most reliably appear.

### Archiver denylist and the publish gate

Build a forbidden-string set at publish time from: `archiver/profiles/*` directory
names, every account handle in `archiver/profiles/map.json`, every
`archiver_account.label`, every distinct `metadata.signature` value, the
hostname / MAC / LAN-IP values inside `metadata.platform`, the source archive folder
name, `ROOT_DIR`, and the OS user name. Then:

1. Any account whose `url_suffix` matches is **dropped** from likes, tags, and
   comments.
2. **Hard gate before push:** scan every byte of every text file in the bundle *and
   every filename* for any forbidden string, case-insensitively. A hit aborts the
   publish with a loud error.

The gate is belt-and-braces over the allowlist and it is the single most valuable
safety mechanism in this design. It must not be skippable, and it must run on the
final bundle, after rendering, not on the intermediate data.

---

## Component 4 — Assets and provenance

### Content-addressed copy, never re-encoded

Each asset is copied to `assets/<sha256[:32]>.<ext>`. This eliminates the
`local_archive_har/<profile>_<date>/` path leak, deduplicates across bundles, and
yields the hash the verification block needs.

**Do not re-encode published assets and do not strip their metadata.** Photos and
`*_full.mp4` files are raw CDN bytes that the archiving tooling never rewrote, so
there is no archiver-authored EXIF to remove, and re-encoding would break the
integrity chain below for no gain. (HAR-reassembled videos carry an ffmpeg `Lavf`
encoder tag; that identifies a tool, not a person.)

### Posters

Generate one derived poster per video at publish time, roughly 1080px on the longest
edge, JPEG — reusing `db_loaders/thumbnail_generator.py:_read_video_frame`. The
existing 128×128 thumbnails are far too small to serve as a page poster. Posters are
labelled as derived in `bundle.json` and sit outside the hash chain.

### Verification, best available per asset

The integrity chain in modern archives is already publishable and carries nothing
identifying — verified by inspection:

`<asset>.manifest.json` (chunk hashes, `whole_file_sha256`, merkle root, size, PAR2
index hash) → its SHA-256 is listed in `manifests.json` → `manifests.json.ots` is an
OpenTimestamps proof anchored in Bitcoin.

Tiers, highest available wins:

| Tier | Evidence | Page says |
|---|---|---|
| `ots` | asset manifest + `manifests.json` + `.ots` | "Hash anchored to the Bitcoin blockchain on \<date\>", plus verification steps |
| `tsr` | per-asset RFC-3161 token (`.tsr`, earlier era) | "Hash countersigned by a timestamping authority on \<date\>" |
| `session_tsr` | `har_hash.txt` + `har_hash.txt.tsr` | "Session capture countersigned on \<date\>; per-asset hashes were not yet recorded" |
| `hash_only` | `har_hash.txt`, untimestamped | "Session hash recorded at capture; not independently timestamped" |
| `none` | nothing on disk | "SHA-256 computed at publication; no capture-time proof available" |

Publishing the `ots` tier means shipping `manifests.json` **byte-identical**, since its
own hash is what was timestamped. That file lists the other filenames captured in the
same session, so two snapshots from one session become correlatable through their
shared merkle root. That reveals a *session*, not an archiver — recommend accepting
it, and exposing it as a publisher checkbox ("include timestamp proof") so it can be
declined case by case.

Per-asset hashing and OpenTimestamps were introduced partway through the project's
life, and there was an earlier period using an RFC-3161 authority instead. The exact
on-disk shape of the `tsr` and `session_tsr` eras needs a real example before it can be
implemented; those archives are on external storage. **Implement `ots`, `hash_only`,
and `none` first**, and leave the two `tsr` tiers as explicit unimplemented branches
that fall through to `hash_only`.

### Missing source files

Archives migrate to external storage, so `media.local_url` may point at nothing. The
builder must detect this up front and fail the whole publish with a clear message. It
must never emit a bundle with a missing asset.

---

## Component 5 — Publisher API and state

### Migration

`infra/migrations/V048__published_snapshot.sql` (V047 is the current head):

```sql
CREATE TABLE published_snapshot (
  id INT AUTO_INCREMENT PRIMARY KEY,
  create_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  slug VARCHAR(64) NOT NULL UNIQUE,
  entity ENUM('account','post','media','media_part') NOT NULL,
  entity_id INT NOT NULL,
  created_by_user_id INT NOT NULL,
  options JSON,
  bundle_sha256 CHAR(64),
  asset_count INT,
  total_bytes BIGINT,
  status ENUM('built','pushed','push_failed','retracted') NOT NULL DEFAULT 'built',
  target VARCHAR(64),
  pushed_at DATETIME NULL,
  notes TEXT,
  FOREIGN KEY (created_by_user_id) REFERENCES user(id),
  INDEX published_snapshot_entity_idx (entity, entity_id)
);
```

Mirror it into `infra/create_db.sql`. Built bundles are retained locally under
`published/<slug>/` (gitignored) — with immutable snapshots you must be able to see
what you published.

Slugs reuse the approach in `browsing_platform/server/services/sharing_manager.py:38`
(`generate_suffix()`, `secrets.choice` over alphanumerics), at length 22.

### Routes

New `browsing_platform/server/routes/publish.py`, prefix `/publish`, with
`dependencies=[Depends(auth_admin_access)]`:

| Route | Purpose |
|---|---|
| `POST /api/publish/preview` | Build into a temp directory, run the redaction gate, return rendered HTML plus a **redaction report** (field by field: included / excluded / dropped-as-archiver). Nothing is pushed. |
| `POST /api/publish/` | Build, gate, push via the configured `PublishTarget`, record the row, return `{slug, public_url}`. |
| `GET /api/publish/{entity}/{entity_id}/` | Prior snapshots for this entity. |

### Services

Under `browsing_platform/server/services/publishing/`:
`bundle_builder.py` (orchestrator) · `redaction.py` (allowlist, denylist, gate) ·
`assets.py` (content-addressed copy, posters) · `provenance.py` (tiering) ·
`renderer.py` (Jinja2, `autoescape=True`) · `targets.py` (`PublishTarget` and
implementations).

Add Jinja2 with `uv add jinja2`. It is not currently a dependency, and the project
builds HTML with f-strings today
(`archiver/summarizers/har_summary_generator.py:901`). That is unacceptable here,
because published pages render attacker-controlled captions and comment text.
Autoescaping is a requirement, not a convenience.

Entity data comes from the existing hydrators in
`browsing_platform/server/services/enriched_entities.py`
(`get_enriched_post_by_id:507`, `get_enriched_account_by_id:536`,
`get_enriched_media_by_id:452`). The publisher consumes the **domain objects**, not
the API response, and must never call `apply_flattened_entities_transform` — that
function mints `ft` file tokens and embeds `SERVER_HOST`, both of which point at BP.

---

## Component 6 — UI

New `browsing_platform/client/src/UIComponents/PublicPublishing/PublishPublicly.tsx`,
a second floating action button rendered beside the existing share FAB, visible only
when `permissions.admin`.

Mount it at the four existing `LinkSharing` call sites that map to publishable
entities — `pages/AccountPage.tsx:108,122`, `pages/PostPage.tsx:79,86`,
`pages/MediaPage.tsx:83,107`, and
`UIComponents/Entities/MediaPartFocusModal.tsx:114`. **Not** at
`pages/SessionPage.tsx:93`; archiving sessions are never publishable.

Dialog flow:

1. **Options** — a checklist (comments / likes and tags / caption / post count /
   timestamp proof). All off by default except caption.
2. **Preview** — renders the actual page alongside the redaction report, so the
   publisher sees exactly what will leave the building before anything does.
3. **Publish** — returns the public URL with a copy button, and a plain warning that
   this is permanent and cannot be un-published from BP.

Follow the existing API conventions in `browsing_platform/client/src/services/server.tsx`
(the `post` / `get` wrapper) and add fetchers to `services/DataFetcher.ts`.

---

## Component 7 — Streaming

### Presentation service

Templates emit `<video preload="none" poster="…" controls playsinline>` with an
explicit `aspect-ratio` from `media.aspect_ratio` to prevent layout shift. Opening a
page then transfers the poster JPEG and zero video bytes; playback uses nginx's native
range support.

### Browsing platform

The same fix, at these sites:

- `UIComponents/Entities/VideoPlayer.tsx:161` — add `preload="none"` and a real
  `poster`. This also allows the hidden 1×1 thumbnail-as-load-signal workaround in
  `UIComponents/Entities/Media.tsx:250-265` to be retired.
- `UIComponents/Entities/Media.tsx:234` and
  `UIComponents/SearchResults/MediaSearchResults.tsx:207` — hover previews: add
  `preload="none"`.
- `UIComponents/Entities/CroppedMediaView.tsx:227` — **exception.** This seeks to
  `timestamp_range_start` before playback, which requires metadata. Use
  `preload="metadata"` here, or defer the seek to the first `play` event.
- Add `loading="lazy"` to grid images (`Media.tsx:293,307`,
  `MediaSearchResults.tsx:186`).

### Optional follow-up, recommended (Track A)

`infra/nginx.conf` currently proxies *everything* to uvicorn, so every video byte
crosses a Starlette `BaseHTTPMiddleware`. Switch to `X-Accel-Redirect`: a small FastAPI
route validates the `ft` token
(`browsing_platform/server/services/file_tokens.py:72`, `decrypt_file_token`) and
returns an `X-Accel-Redirect` header pointing at an `internal` nginx location.
Authorisation is preserved exactly; nginx serves the bytes. This is the largest single
media-performance win available on BP and it is independent of everything else here.

---

## Files

**New**

- `presentation_service/**`
- `browsing_platform/server/routes/publish.py`
- `browsing_platform/server/services/publishing/{bundle_builder,redaction,assets,provenance,renderer,targets}.py`
- `infra/migrations/V048__published_snapshot.sql`
- `browsing_platform/client/src/UIComponents/PublicPublishing/PublishPublicly.tsx`

**Modified**

- `browsing_platform/server/server.py` — register the router
- `.env.sample`, `CLAUDE.md`, `README.md` — new `PUBLISH_TARGET`, `PUBLIC_BASE_URL`,
  `PROJECT_ATTRIBUTION` variables
- `infra/create_db.sql` — mirror V048
- `pyproject.toml` — `uv add jinja2`
- The four page and modal mount points listed in Component 6
- `browsing_platform/client/src/services/DataFetcher.ts`
- The six `<video>` / `<img>` sites listed in Component 7
- `.gitignore` — add `published/`

**Deliberately untouched**

`browsing_platform/server/routes/fast_api_request_processor.py` and
`browsing_platform/server/services/archiving_session.py`. The existing share-link
censoring is a separate, weaker mechanism; do not entangle the two.

---

## Verification

1. **Migration.** `uv run infra/migrate.py`; confirm `published_snapshot` exists.
2. **Redaction unit checks** — the security-critical part, test these directly:
   - Feed `redaction.py` a fixture account carrying `data`, `identifiers`,
     `url_parts`, and relations. Assert the output has exactly the allowlisted keys.
   - Add a new column to the fixture; assert it does **not** appear in the output.
   - Seed a known archiver handle into a comment author and a like; assert both are
     dropped and that the publish gate raises.
   - Put a profile name into a filename; assert the filename scan catches it.
3. **Build a bundle locally.** Set `PUBLISH_TARGET=local`, run the app with
   `BROWSING_PLATFORM_DEV=1`, open a post with at least one video and one image, and
   click Publish → Preview. Confirm the redaction report and the rendered page.
4. **Grep the built bundle** for `local_archive_har`, every profile directory name,
   every handle in `map.json`, the OS user name, `SERVER_HOST`, and `archive.har`.
   Expect zero hits. This is the acceptance test for archiver anonymity.
5. **Serve it standalone.** Serve `published/` with BP **stopped** — via
   `python -m http.server`, or nginx with `deploy/nginx.conf` — and load the page. It
   must render fully. Anything that 404s means the bundle is not self-contained.
6. **Streaming.** Load the page with the network panel open. Confirm zero bytes are
   fetched for the video until play is pressed, then a `206 Partial Content`. Repeat on
   BP after the Component 7 changes.
7. **Verification block.** Independently confirm that the published SHA-256 matches the
   downloaded file, that the asset manifest's hash appears in `manifests.json`, and
   that `ots verify manifests.json` passes — see
   `utils/opentimestamps/timestamper_opentimestamps.py`.
8. **Transport.** Deferred until the open decision is made. Until then only
   `LocalDirTarget` is exercised.

---

## Risks

- **The transport decision is unresolved and is the crux of the isolation
  requirement.** Everything else can ship behind `LocalDirTarget` without prejudging
  it.
- **Immutable snapshots mean mistakes are permanent.** The preview step and the publish
  gate are the only defences. Treat them as load-bearing, not as polish.
- **The `tsr` provenance tiers cannot be implemented without real examples** from the
  archives held on external storage.
- **Publishing an account is the largest bundle and the highest-risk shape** — many
  posts, many comment authors. Consider shipping post and media first, and account
  second, once the redaction gate has some mileage on it.

---

## Follow-up ticket, out of scope here

`browsing_platform/server/routes/fast_api_request_processor.py:52` censors only four
metadata keys for share-link viewers. `metadata.platform`, which carries the capture
machine's hostname, LAN IP and MAC address, is not among them, and neither are
`commit_id`, `branch`, `domain_resolutions`, `archive_location`, or `external_id`.
That is a live exposure in the *existing* share-link feature and should be fixed on its
own, independently of this design.
