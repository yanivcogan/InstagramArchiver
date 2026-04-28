import time
from typing import Literal

from playwright.sync_api import Page


def scroll_relation_to_bottom(
    page: Page,
    relation: Literal["followers", "following"],
    scroll_delay: float = 0.8,
    max_stagnant: int = 5,
) -> None:
    page.click(f"a[href$='/{relation}/']")
    time.sleep(3)

    page.wait_for_selector("#scrollview", timeout=15000)
    time.sleep(2)

    scroll_container = page.locator("#scrollview")

    last_height = 0
    stagnant = 0
    while stagnant < max_stagnant:
        scroll_container.evaluate("el => el.scrollBy(0, el.scrollHeight)")
        time.sleep(scroll_delay)
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
) -> None:
    page.goto(f"https://www.instagram.com/{username}/")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(3)

    if scrape_followers:
        print(f"Scrolling followers list for @{username}...")
        scroll_relation_to_bottom(page, "followers")
        print(f"Finished scrolling followers for @{username}.")
        time.sleep(2)

    if scrape_following:
        print(f"Scrolling following list for @{username}...")
        scroll_relation_to_bottom(page, "following")
        print(f"Finished scrolling following for @{username}.")
