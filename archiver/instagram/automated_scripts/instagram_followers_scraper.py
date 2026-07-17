import random
import re
import time
from typing import Literal, Optional

from playwright.sync_api import Page


def scroll_relation_to_bottom(
    page: Page,
    relation: Literal["followers", "following"],
    max_accounts: Optional[int] = None,
    scroll_delay: float = 0.8,
    max_stagnant: int = 5,
) -> None:
    # Instagram has shipped variants where these buttons use either a real
    # href (`/<user>/<relation>/`) or a placeholder `href="#"`. Match either
    # the legacy href selector or any anchor whose accessible name contains
    # the relation word as a whole word (case-insensitive).
    relation_link = page.locator(
        f"a[href$='/{relation}/'], a[role='link'], a[href='#']"
    ).filter(has_text=re.compile(rf"\b{relation}\b", re.IGNORECASE)).first
    relation_link.click()
    time.sleep(3)

    page.wait_for_selector("[role='dialog'][aria-modal='true']", timeout=15000)
    time.sleep(2)

    handle = page.evaluate_handle("""() => {
        const dialog = document.querySelector('[role="dialog"][aria-modal="true"]');
        if (!dialog) return document.body;
        for (const el of dialog.querySelectorAll('*')) {
            const oy = window.getComputedStyle(el).overflowY;
            if ((oy === 'scroll' || oy === 'auto') && el.scrollHeight > el.clientHeight) {
                return el;
            }
        }
        return dialog;
    }""")
    scroll_container = handle.as_element()
    if scroll_container is None:
        raise RuntimeError("Could not find scrollable container for followers list.")

    # Accumulate the set of unique profile links seen across scrolls rather than
    # counting rendered rows: Instagram virtualizes the modal list and drops
    # off-screen rows from the DOM, so a point-in-time count would plateau below
    # the cap. Unioning hrefs each iteration survives that.
    seen_accounts: set[str] = set()
    last_height = 0
    stagnant = 0
    while stagnant < max_stagnant:
        scroll_container.evaluate("el => el.scrollBy(0, el.scrollHeight)")
        time.sleep(random.uniform(scroll_delay * 0.6, scroll_delay * 1.6))

        if max_accounts is not None:
            hrefs = page.evaluate("""() => {
                const dialog = document.querySelector('[role="dialog"][aria-modal="true"]');
                if (!dialog) return [];
                const out = [];
                for (const a of dialog.querySelectorAll('a[href]')) {
                    const h = a.getAttribute('href');
                    if (h && /^\\/[^/]+\\/$/.test(h)) out.push(h);
                }
                return out;
            }""")
            seen_accounts.update(hrefs)
            if len(seen_accounts) >= max_accounts:
                print(f"Reached account cap ({max_accounts}) for {relation} — stopping scroll.")
                break

        new_height = scroll_container.evaluate("el => el.scrollHeight")
        if new_height == last_height:
            is_loading = page.locator("[data-visualcompletion='loading-state']").count() > 0
            if is_loading:
                time.sleep(1)
                stagnant = 0
            else:
                stagnant += 1
        else:
            stagnant = 0
        last_height = new_height

    close_btn = page.query_selector("button:has(svg[aria-label='Close'])")
    if close_btn:
        close_btn.click()
    else:
        print(f"Close button not found after scrolling {relation} — modal may already be closed.")
    time.sleep(1)


def run_followers_automation(
    page: Page,
    username: str,
    scrape_followers: bool,
    scrape_following: bool,
    max_accounts_per_relation_type: Optional[int] = None,
) -> None:
    page.goto(f"https://www.instagram.com/{username}/")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(3)

    if scrape_followers:
        print(f"Scrolling followers list for @{username}...")
        scroll_relation_to_bottom(page, "followers", max_accounts=max_accounts_per_relation_type)
        print(f"Finished scrolling followers for @{username}.")
        time.sleep(2)

    if scrape_following:
        print(f"Scrolling following list for @{username}...")
        scroll_relation_to_bottom(page, "following", max_accounts=max_accounts_per_relation_type)
        print(f"Finished scrolling following for @{username}.")
