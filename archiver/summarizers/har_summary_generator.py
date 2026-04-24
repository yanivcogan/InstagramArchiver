import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from extractors.entity_types import (
    AccountAndAssociatedEntities, PostAndAssociatedEntities, ExtractedEntitiesNested,
    MediaAndAssociatedEntities, Comment, Like, TaggedAccount, AccountRelation
)
from extractors.extract_photos import PhotoAcquisitionConfig
from extractors.extract_videos import VideoAcquisitionConfig
from extractors.structures_to_entities import extract_entities_from_har, nest_entities_from_archive_session


def generate_stylesheet() -> str:
    return """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --ig-gradient: linear-gradient(45deg, #833ab4, #fd1d1d, #fcb045);
    --bg: #f0f2f5;
    --card-bg: #ffffff;
    --border: #e8eaed;
    --text-primary: #1c1e21;
    --text-secondary: #1c1e21;
    --text-link: #1877f2;
    --radius: 12px;
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.04);
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, Roboto, sans-serif;
    font-size: 14px;
    background: var(--bg);
    color: var(--text-primary);
    line-height: 1.5;
    padding: 24px;
    min-height: 100vh;
}

.summary-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 24px;
    padding: 18px 24px;
    background: var(--card-bg);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    position: relative;
    overflow: hidden;
}
.summary-title::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
    background: var(--ig-gradient);
}

.section-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 12px;
    padding-left: 4px;
}

/* ── Account card ─────────────────────────────────── */
.account-card {
    background: var(--card-bg);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    margin-bottom: 16px;
    overflow: hidden;
}

.account-header {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 20px 24px;
    border-bottom: 1px solid var(--border);
}

.account-avatar {
    width: 52px; height: 52px;
    border-radius: 50%;
    background: var(--ig-gradient);
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; font-weight: 700;
    color: #fff;
    flex-shrink: 0;
    letter-spacing: -0.5px;
    text-transform: uppercase;
}

.account-info { flex: 1; min-width: 0; }

.account-username {
    font-size: 16px; font-weight: 700;
    color: var(--text-primary);
    text-decoration: none;
    display: block;
    margin-bottom: 2px;
}
.account-username:hover { text-decoration: underline; }

.account-display-name {
    font-size: 14px; color: var(--text-secondary);
    margin-bottom: 4px;
}

.account-bio {
    font-size: 13px; color: var(--text-secondary);
    white-space: pre-line;
}

.account-stats { display: flex; gap: 8px; flex-shrink: 0; }

.stat-badge {
    background: var(--ig-gradient);
    color: #fff;
    font-size: 12px; font-weight: 600;
    padding: 4px 10px;
    border-radius: 20px;
    white-space: nowrap;
}

/* ── Relations ───────────────────────────────────── */
.relations-list {
    display: flex; flex-direction: column; gap: 2px;
}

.relation-item {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
}
.relation-item:last-child { border-bottom: none; }

.relation-type {
    font-size: 11px; font-weight: 600;
    background: #f0f2f5;
    padding: 2px 8px; border-radius: 10px;
    color: var(--text-secondary);
    flex-shrink: 0;
}

.relation-name { font-weight: 600; color: var(--text-primary); }

.relation-url {
    color: var(--text-link);
    text-decoration: none;
    font-size: 12px;
    font-family: 'Courier New', Courier, monospace;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.relation-url:hover { text-decoration: underline; }

.account-posts { padding: 0 24px 16px; }

.account-posts-label {
    font-size: 12px; font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 16px 0 12px;
}

/* ── Post card ───────────────────────────────────── */
.post-card {
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 12px;
    overflow: hidden;
    background: #fafbfc;
}

.post-header { padding: 14px 16px 10px; }

.post-meta {
    display: flex; align-items: center; flex-wrap: wrap;
    gap: 8px; margin-bottom: 8px;
}

.post-date {
    font-size: 12px; color: var(--text-secondary);
}

.post-url-chip {
    font-family: 'Courier New', Courier, monospace;
    font-size: 11px;
    background: #e8eaed;
    color: var(--text-link);
    padding: 2px 8px; border-radius: 4px;
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
    max-width: 320px;
    display: inline-block;
}
.post-url-chip:hover { background: #d8dadf; }

.post-caption {
    font-size: 14px; color: var(--text-primary);
    line-height: 1.5;
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
}
.post-caption.expanded { -webkit-line-clamp: unset; }

.caption-toggle {
    font-size: 12px; color: var(--text-link);
    cursor: pointer; background: none; border: none;
    padding: 4px 0;
    display: inline-block;
    margin-top: 2px;
}
.caption-toggle:hover { text-decoration: underline; }

/* ── Media grid ──────────────────────────────────── */
.post-media-grid {
    display: flex; flex-wrap: wrap; gap: 8px;
    padding: 0 16px 12px;
}

.media-item {
    display: flex; flex-direction: column;
    align-items: center; gap: 6px;
}

.media-preview {
    max-width: 220px; width: 220px;
    max-height: 220px;
    border-radius: 8px;
    object-fit: cover;
    border: 1px solid var(--border);
    display: block;
    background: #f0f2f5;
}
video.media-preview { height: auto; }
audio.media-preview { width: 220px; height: auto; }

.download-btn {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 5px 14px;
    background: var(--ig-gradient);
    color: #fff;
    font-size: 12px; font-weight: 600;
    text-decoration: none;
    border-radius: 6px;
    transition: opacity 0.15s;
    white-space: nowrap;
}
.download-btn:hover { opacity: 0.82; }

/* ── Collapsible sections ────────────────────────── */
.collapsible-section { border-top: 1px solid var(--border); }

.collapsible-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 16px;
    cursor: pointer;
    user-select: none;
    font-size: 13px; font-weight: 600;
    color: var(--text-secondary);
    transition: background 0.15s;
}
.collapsible-header:hover { background: #f7f8fa; }

.collapsible-indicator {
    font-size: 10px;
    display: inline-block;
    transition: transform 0.2s;
    color: var(--text-secondary);
}
.collapsible-header.open .collapsible-indicator {
    transform: rotate(90deg);
}

.collapsible-body { display: none; padding: 8px 16px 12px; }
.collapsible-body.open { display: block; }

/* JSON data — visually de-emphasized */
.json-collapsible .collapsible-header {
    font-size: 11px; color: #b0b4be;
    font-weight: 400; padding: 7px 16px;
}
.json-collapsible .collapsible-body {
    font-family: 'Courier New', Courier, monospace;
    font-size: 11px; color: #9ea3ab;
    white-space: pre-wrap; word-break: break-all;
    background: #f9fafb;
    max-height: 280px; overflow-y: auto;
    padding: 8px 16px 10px;
}

/* ── Comments ────────────────────────────────────── */
.comments-list { display: flex; flex-direction: column; gap: 6px; }

.comment-item {
    border-left: 3px solid var(--border);
    padding: 8px 12px;
    border-radius: 0 6px 6px 0;
    transition: border-color 0.15s;
    background: #fff;
}
.comment-item:hover { border-left-color: #833ab4; }
.comment-item.reply { margin-left: 24px; }

.comment-meta { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }

.comment-author {
    font-size: 13px; font-weight: 600;
    color: var(--text-primary);
    text-decoration: none;
}
.comment-author:hover { text-decoration: underline; }

.comment-date { font-size: 11px; color: var(--text-secondary); }

.comment-text {
    font-size: 13px; color: var(--text-primary);
    margin-top: 4px; line-height: 1.4;
}

/* ── Likes ───────────────────────────────────────── */
.likes-grid { display: flex; flex-wrap: wrap; gap: 6px; }

.like-pill {
    background: #f0f2f5;
    color: var(--text-primary);
    font-size: 13px;
    padding: 4px 12px;
    border-radius: 20px;
    text-decoration: none;
    transition: background 0.15s;
    white-space: nowrap;
}
.like-pill:hover { background: #e4e6eb; }

/* ── Tagged accounts ─────────────────────────────── */
.tagged-grid { display: flex; flex-wrap: wrap; gap: 6px; }

.tagged-chip {
    background: linear-gradient(45deg, rgba(131,58,180,0.08), rgba(252,176,69,0.08));
    color: #833ab4;
    font-size: 13px; font-weight: 600;
    padding: 4px 12px;
    border-radius: 20px;
    text-decoration: none;
    border: 1px solid rgba(131,58,180,0.18);
    white-space: nowrap;
}
.tagged-chip:hover {
    background: linear-gradient(45deg, rgba(131,58,180,0.16), rgba(252,176,69,0.16));
}

/* ── Metadata table ──────────────────────────────── */
.metadata-section {
    background: var(--card-bg);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    overflow: hidden;
    margin-top: 24px;
}
.metadata-section .section-title { padding: 16px 20px 4px; }

table { width: 100%; border-collapse: collapse; }
th, td {
    text-align: left;
    padding: 9px 16px;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
}
th {
    background: #f7f8fa;
    font-weight: 600; color: var(--text-secondary);
    font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em;
    width: 28%;
    white-space: nowrap;
}
tr:last-child td, tr:last-child th { border-bottom: none; }
tr:hover td { background: #f9fafb; }

ul { list-style: disc; padding-left: 20px; margin: 4px 0; }
li { margin-bottom: 2px; font-size: 13px; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d0d3da; border-radius: 3px; }
"""


def generate_scripts() -> str:
    return """
document.querySelectorAll('.collapsible-header').forEach(function(header) {
    header.addEventListener('click', function() {
        this.classList.toggle('open');
        var body = this.nextElementSibling;
        if (body) body.classList.toggle('open');
    });
});

document.querySelectorAll('.post-caption').forEach(function(caption) {
    var lineHeight = parseInt(window.getComputedStyle(caption).lineHeight) || 21;
    if (caption.scrollHeight > lineHeight * 3 + 4) {
        var btn = document.createElement('button');
        btn.className = 'caption-toggle';
        btn.textContent = 'See more';
        btn.addEventListener('click', function() {
            caption.classList.toggle('expanded');
            btn.textContent = caption.classList.contains('expanded') ? 'See less' : 'See more';
        });
        caption.parentNode.insertBefore(btn, caption.nextSibling);
    }
});
"""


def _make_collapsible(header_text: str, body_tag: Tag, soup: BeautifulSoup,
                      extra_class: str = "", start_open: bool = False) -> Tag:
    section = soup.new_tag("div")
    section['class'] = f"collapsible-section {extra_class}".strip()

    header = soup.new_tag("div")
    header['class'] = f"collapsible-header {'open' if start_open else ''}".strip()

    label = soup.new_tag("span")
    label.string = header_text
    indicator = soup.new_tag("span")
    indicator['class'] = "collapsible-indicator"
    indicator.string = "▶"

    header.append(label)
    header.append(indicator)
    section.append(header)

    existing = body_tag.get('class') or ''
    classes = [c for c in (existing if isinstance(existing, list) else existing.split()) if c]
    classes.append("collapsible-body")
    if start_open:
        classes.append("open")
    body_tag['class'] = " ".join(classes)
    section.append(body_tag)

    return section


def _make_json_collapsible(data: Any, soup: BeautifulSoup) -> Tag:
    body = soup.new_tag("pre")
    body.string = json.dumps(data, ensure_ascii=False, default=str)
    return _make_collapsible("raw data", body, soup, extra_class="json-collapsible")


def summarize_comments(comments: list[Comment], soup: BeautifulSoup) -> Tag:
    sorted_comments = sorted(comments, key=lambda c: c.publication_date or 0)
    top_level = [c for c in sorted_comments if not c.parent_comment_id_on_platform]
    replies: dict = {}
    for c in sorted_comments:
        if c.parent_comment_id_on_platform:
            replies.setdefault(c.parent_comment_id_on_platform, []).append(c)

    container = soup.new_tag("div")
    container['class'] = "comments-list"

    def render_comment(cmt: Comment, is_reply: bool = False) -> Tag:
        item = soup.new_tag("div")
        item['class'] = "comment-item reply" if is_reply else "comment-item"

        meta = soup.new_tag("div")
        meta['class'] = "comment-meta"

        name = cmt.account_display_name or cmt.account_url_suffix or "Unknown"
        if cmt.account_url:
            author = soup.new_tag("a", href=str(cmt.account_url))
        else:
            author = soup.new_tag("span")
        author['class'] = "comment-author"
        author.string = f"@{name}"
        meta.append(author)

        if cmt.publication_date:
            date_span = soup.new_tag("span")
            date_span['class'] = "comment-date"
            date_span.string = cmt.publication_date.strftime("%Y-%m-%d %H:%M")
            meta.append(date_span)

        item.append(meta)

        if cmt.text:
            text_div = soup.new_tag("div")
            text_div['class'] = "comment-text"
            text_div.string = cmt.text
            item.append(text_div)

        return item

    rendered_parent_ids = set()
    for comment in top_level:
        container.append(render_comment(comment))
        rendered_parent_ids.add(comment.id_on_platform)
        for reply in replies.get(comment.id_on_platform or '', []):
            container.append(render_comment(reply, is_reply=True))

    for parent_id, reply_list in replies.items():
        if parent_id not in rendered_parent_ids:
            for reply in reply_list:
                container.append(render_comment(reply))

    return container


def summarize_likes(likes: list[Like], soup: BeautifulSoup) -> Tag:
    grid = soup.new_tag("div")
    grid['class'] = "likes-grid"
    for like in likes:
        name = like.account_display_name or like.account_url_suffix or "Unknown"
        if like.account_url:
            pill = soup.new_tag("a", href=str(like.account_url))
        else:
            pill = soup.new_tag("span")
        pill['class'] = "like-pill"
        pill.string = f"@{name}"
        grid.append(pill)
    return grid


def summarize_tagged_accounts(tagged_accounts: list[TaggedAccount], soup: BeautifulSoup) -> Tag:
    grid = soup.new_tag("div")
    grid['class'] = "tagged-grid"
    for tagged in tagged_accounts:
        name = tagged.tagged_account_display_name or tagged.tagged_account_url_suffix or "Unknown"
        url = tagged.tagged_account_url
        if url:
            chip = soup.new_tag("a", href=url)
        else:
            chip = soup.new_tag("span")
        chip['class'] = "tagged-chip"
        chip.string = f"@{name}"
        grid.append(chip)
    return grid


def summarize_account_relations(account_relations: list[AccountRelation], soup: BeautifulSoup) -> Tag:
    container = soup.new_tag("div")
    container['class'] = "relations-list"
    for relation in account_relations:
        item = soup.new_tag("div")
        item['class'] = "relation-item"

        if relation.relation_type:
            badge = soup.new_tag("span")
            badge['class'] = "relation-type"
            badge.string = relation.relation_type
            item.append(badge)

        follower_name = relation.follower_account_display_name or relation.follower_account_url_suffix
        followed_name = relation.followed_account_display_name or relation.followed_account_url_suffix
        display = follower_name or followed_name or "Unknown"
        url = relation.follower_account_url or relation.followed_account_url

        name_span = soup.new_tag("span")
        name_span['class'] = "relation-name"
        name_span.string = display
        item.append(name_span)

        if url:
            url_link = soup.new_tag("a", href=url)
            url_link['class'] = "relation-url"
            url_link.string = url
            item.append(url_link)

        container.append(item)
    return container


def summarize_media(media: MediaAndAssociatedEntities, soup: BeautifulSoup) -> Tag:
    item = soup.new_tag("div")
    item['class'] = "media-item"

    if media.media_type == "image":
        preview = soup.new_tag("img", src=media.local_url)
    elif media.media_type == "video":
        preview = soup.new_tag("video", src=media.local_url, controls="true")
    elif media.media_type == "audio":
        preview = soup.new_tag("audio", src=media.local_url, controls="true")
    else:
        preview = soup.new_tag("span")
        preview.string = "Unsupported media"
    preview['class'] = "media-preview"
    item.append(preview)

    download = soup.new_tag("a", href=media.local_url, download="true")
    download['class'] = "download-btn"
    download.string = "↓ Download"
    item.append(download)

    return item


def summarize_post(post: PostAndAssociatedEntities, soup: BeautifulSoup) -> Tag:
    card = soup.new_tag("div")
    card['class'] = "post-card"

    # Header: meta + caption
    header = soup.new_tag("div")
    header['class'] = "post-header"

    meta = soup.new_tag("div")
    meta['class'] = "post-meta"

    if post.publication_date:
        date_span = soup.new_tag("span")
        date_span['class'] = "post-date"
        date_span.string = post.publication_date.strftime("%Y-%m-%d %H:%M")
        meta.append(date_span)

    if post.url:
        url_chip = soup.new_tag("a", href=post.url)
        url_chip['class'] = "post-url-chip"
        url_chip.string = post.url
        meta.append(url_chip)

    header.append(meta)

    if post.caption and post.caption.strip():
        caption_div = soup.new_tag("div")
        caption_div['class'] = "post-caption"
        caption_div.string = post.caption.strip()
        header.append(caption_div)

    card.append(header)

    # Media grid
    if post.post_media:
        media_grid = soup.new_tag("div")
        media_grid['class'] = "post-media-grid"
        for media in post.post_media:
            media_grid.append(summarize_media(media, soup))
        card.append(media_grid)

    # Comments
    if post.post_comments:
        n = len(post.post_comments)
        body = summarize_comments(post.post_comments, soup)
        card.append(_make_collapsible(
            f"💬 Comments ({n})", body, soup,
            start_open=(n <= 5)
        ))

    # Likes
    if post.post_likes:
        n = len(post.post_likes)
        body = summarize_likes(post.post_likes, soup)
        card.append(_make_collapsible(f"❤️ Likes ({n})", body, soup))

    # Tagged accounts
    if post.post_tagged_accounts:
        n = len(post.post_tagged_accounts)
        body = summarize_tagged_accounts(post.post_tagged_accounts, soup)
        card.append(_make_collapsible(f"🏷️ Tagged ({n})", body, soup))

    # Raw data (de-emphasized)
    card.append(_make_json_collapsible(post.data, soup))

    return card


def summarize_account(account: AccountAndAssociatedEntities, soup: BeautifulSoup) -> Tag:
    card = soup.new_tag("div")
    card['class'] = "account-card"

    # Header row
    header = soup.new_tag("div")
    header['class'] = "account-header"

    avatar = soup.new_tag("div")
    avatar['class'] = "account-avatar"
    initial = (account.url_suffix or "?")[0]
    avatar.string = initial

    info = soup.new_tag("div")
    info['class'] = "account-info"

    username_tag = soup.new_tag("a", href=account.url or "#")
    username_tag['class'] = "account-username"
    username_tag.string = f"@{account.url_suffix}" if account.url_suffix else account.url or "Unknown"
    info.append(username_tag)

    if account.display_name:
        dn = soup.new_tag("div")
        dn['class'] = "account-display-name"
        dn.string = account.display_name
        info.append(dn)

    if account.bio:
        bio = soup.new_tag("div")
        bio['class'] = "account-bio"
        bio.string = account.bio
        info.append(bio)

    stats = soup.new_tag("div")
    stats['class'] = "account-stats"
    n_posts = len(account.account_posts)
    if n_posts:
        badge = soup.new_tag("span")
        badge['class'] = "stat-badge"
        badge.string = f"{n_posts} post{'s' if n_posts != 1 else ''}"
        stats.append(badge)

    header.append(avatar)
    header.append(info)
    header.append(stats)
    card.append(header)

    # Raw JSON data
    card.append(_make_json_collapsible(account.data, soup))

    # Related accounts
    if account.account_relations:
        n = len(account.account_relations)
        body = summarize_account_relations(account.account_relations, soup)
        card.append(_make_collapsible(f"👥 Related Accounts ({n})", body, soup))

    # Posts
    if account.account_posts:
        posts_block = soup.new_tag("div")
        posts_block['class'] = "account-posts"
        label = soup.new_tag("div")
        label['class'] = "account-posts-label"
        label.string = "Posts"
        posts_block.append(label)
        account.account_posts.sort(key=lambda p: p.publication_date or 0, reverse=True)
        for post in account.account_posts:
            posts_block.append(summarize_post(post, soup))
        card.append(posts_block)

    return card


def filter_out_empty_entities(nested_entities: ExtractedEntitiesNested) -> None:
    nested_entities.media = [m for m in nested_entities.media if m.local_url]
    for p in nested_entities.posts:
        p.post_media = [m for m in p.post_media if m.local_url]
    nested_entities.posts = [
        p for p in nested_entities.posts
        if p.post_media or (p.caption and p.caption.strip())
    ]
    for a in nested_entities.accounts:
        for p in a.account_posts:
            p.post_media = [m for m in p.post_media if m.local_url]
        a.account_posts = [
            p for p in a.account_posts
            if p.post_media or (p.caption and p.caption.strip())
        ]
    nested_entities.accounts = [a for a in nested_entities.accounts if a.account_posts]


def summarize_nested_entities(nested_entities: ExtractedEntitiesNested, metadata: dict) -> str:
    filter_out_empty_entities(nested_entities)
    page_title = f"Archive Summary — {metadata.get('archiving_start_timestamp', 'Unknown Date')}"
    soup = BeautifulSoup(
        f"<html><head><meta charset='utf-8'><title>{page_title}</title></head><body></body></html>",
        "html.parser"
    )
    style_tag = soup.new_tag("style")
    style_tag.string = generate_stylesheet()
    soup.head.append(style_tag)

    body = soup.body

    title = soup.new_tag("h1")
    title['class'] = "summary-title"
    title.string = page_title
    body.append(title)

    if nested_entities.accounts:
        section = soup.new_tag("div")
        section['class'] = "accounts-section"
        lbl = soup.new_tag("div")
        lbl['class'] = "section-title"
        lbl.string = f"Accounts ({len(nested_entities.accounts)})"
        section.append(lbl)
        for account in nested_entities.accounts:
            section.append(summarize_account(account, soup))
        body.append(section)

    if nested_entities.posts:
        section = soup.new_tag("div")
        section['class'] = "orphaned-posts-section"
        lbl = soup.new_tag("div")
        lbl['class'] = "section-title"
        lbl.string = f"Additional Posts ({len(nested_entities.posts)})"
        section.append(lbl)
        for post in nested_entities.posts:
            section.append(summarize_post(post, soup))
        body.append(section)

    if nested_entities.media:
        section = soup.new_tag("div")
        section['class'] = "orphaned-media-section"
        lbl = soup.new_tag("div")
        lbl['class'] = "section-title"
        lbl.string = f"Additional Media ({len(nested_entities.media)})"
        section.append(lbl)
        grid = soup.new_tag("div")
        grid['class'] = "post-media-grid"
        for media in nested_entities.media:
            grid.append(summarize_media(media, soup))
        section.append(grid)
        body.append(section)

    # Metadata
    meta_section = soup.new_tag("div")
    meta_section['class'] = "metadata-section"
    lbl = soup.new_tag("div")
    lbl['class'] = "section-title"
    lbl.string = "Archive Metadata"
    meta_section.append(lbl)
    meta_section.append(_generate_table_rec(metadata, soup))
    body.append(meta_section)

    # Scripts
    script_tag = soup.new_tag("script")
    script_tag.string = generate_scripts()
    body.append(script_tag)

    return str(soup)


def _generate_table_rec(data: Any, soup: BeautifulSoup) -> Tag:
    if isinstance(data, dict):
        table = soup.new_tag("table")
        for k, v in data.items():
            row = soup.new_tag("tr")
            th = soup.new_tag("th")
            th.string = str(k)
            td = soup.new_tag("td")
            td.append(_generate_table_rec(v, soup))
            row.append(th)
            row.append(td)
            table.append(row)
        return table
    elif isinstance(data, list):
        ul = soup.new_tag("ul")
        for item in data:
            li = soup.new_tag("li")
            li.append(_generate_table_rec(item, soup))
            ul.append(li)
        return ul
    else:
        span = soup.new_tag("span")
        span.string = str(data)
        return span


def generate_entities_summary(
        har_path: Path,
        archive_dir: Path,
        metadata: dict,
        video_acquisition_config: VideoAcquisitionConfig = VideoAcquisitionConfig(
            download_missing=True, download_media_not_in_structures=True, download_unfetched_media=True,
            download_full_versions_of_fetched_media=True, download_highest_quality_assets_from_structures=True
        ),
        photo_acquisition_config: PhotoAcquisitionConfig = PhotoAcquisitionConfig(
            download_missing=True, download_media_not_in_structures=True, download_unfetched_media=True,
            download_highest_quality_assets_from_structures=True
        )
):
    flattened_entities = extract_entities_from_har(har_path, video_acquisition_config, photo_acquisition_config)
    nested_entities = nest_entities_from_archive_session(flattened_entities)
    html = summarize_nested_entities(nested_entities, metadata)
    archive_dir_str = archive_dir.as_posix()
    html = html.replace(archive_dir_str, ".")
    if metadata.get("profile_name"):
        html = html.replace(metadata["profile_name"], "[ANONYMIZED]")
    if metadata.get("signature"):
        html = html.replace(metadata["signature"], "[ANONYMIZED]")
    if metadata.get("my_ip"):
        html = html.replace(metadata["my_ip"], "[ANONYMIZED]")

    out_path = archive_dir / "entities_summary.html"
    print("Writing entities summary to", out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def manual_entities_summary_generation():
    har_file = input("Input path to HAR file: ")
    har_file = har_file.strip().strip('"').strip("'")
    har_path = Path(har_file)
    archive_dir = Path(har_path).parent
    metadata_path = archive_dir / "metadata.json"
    metadata = {}
    if metadata_path.exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    generate_entities_summary(
        har_path,
        archive_dir,
        metadata,
        VideoAcquisitionConfig(
            download_missing=True,
            download_media_not_in_structures=False,
            download_unfetched_media=False,
            download_full_versions_of_fetched_media=False,
            download_highest_quality_assets_from_structures=False
        ),
        PhotoAcquisitionConfig(
            download_missing=True,
            download_media_not_in_structures=False,
            download_unfetched_media=False,
            download_highest_quality_assets_from_structures=False
        )
    )


if __name__ == '__main__':
    manual_entities_summary_generation()
