-- V047 — archiver account access index
--
-- Operators archive with several different Instagram accounts (modeled only as
-- local Playwright profiles in archiver/profiles/map.json — never in the DB).
-- When viewing a target account in the browsing platform there was no way to
-- tell which archiving account already follows it (has access) or has a pending
-- follow request to it. This migration adds:
--
--   * user.archiver — a role flag (alongside the existing admin flag) that
--     gates the sensitive archiver-access API. See services/permissions.py
--     auth_archiver_access.
--   * archiver_account — one row per registered archiving account, identified
--     by its human-readable label (from the import manifest).
--   * archiver_account_access — the relationship index between an archiver
--     account and target usernames, in four directions (following / requested /
--     followed_by / follow_requests_from), parsed from Instagram "export my
--     data" dumps by db_loaders/archiver_access_loader.py.
--
-- Exports carry usernames only (no pk/id_on_platform), so target identity is
-- url_suffix + platform, matched case-insensitively. url_suffix is non-unique
-- and recyclable, so this index is a best-effort convenience signal, not an
-- identity assertion.

ALTER TABLE user
    ADD COLUMN archiver tinyint DEFAULT 0 NOT NULL;

CREATE TABLE archiver_account
(
    id             int auto_increment
        primary key,
    create_date    timestamp default CURRENT_TIMESTAMP not null,
    update_date    timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP,
    label          varchar(200)                        not null,
    last_import_at datetime                            null,
    constraint uq_archiver_account_label
        unique (label)
)
    engine = InnoDB;

CREATE TABLE archiver_account_access
(
    id                 int auto_increment
        primary key,
    create_date        timestamp default CURRENT_TIMESTAMP                                          not null,
    archiver_account_id int                                                                         not null,
    target_url_suffix  varchar(200)                                                                 not null comment 'target username, stored lowercased',
    platform           enum ('instagram', 'facebook', 'telegram', 'youtube', 'twitter', 'threads') default 'instagram' not null,
    status             enum ('following', 'requested', 'followed_by', 'follow_requests_from')        not null,
    observed_at        datetime                                                                     null comment 'timestamp from the export entry',
    constraint archiver_account_access_account_fk
        foreign key (archiver_account_id) references archiver_account (id)
            on delete cascade,
    -- status is part of the key: the same archiver+target+platform can hold
    -- several directions at once (e.g. a mutual follow is following + followed_by).
    constraint uq_archiver_account_access
        unique (archiver_account_id, target_url_suffix, platform, status)
)
    engine = InnoDB;

CREATE INDEX archiver_account_access_target_index
    ON archiver_account_access (target_url_suffix, platform);
