import asyncio
from typing import Optional, Literal
from bs4 import BeautifulSoup
import numpy as np
from playwright.async_api import async_playwright, Page, ElementHandle, Mouse, StorageState

from scraper.type_defs import Account, FriendsScrape, Profile


# --- Utilities ---

async def find_relative_element_by_xpath(page: Page, anchor_xpath: str, relative_xpath: str) -> ElementHandle:
    full_xpath = f"{anchor_xpath}/{relative_xpath}"
    elements = await page.query_selector_all(f'xpath={full_xpath}')
    if not elements:
        raise RuntimeError(f"❌ No element found at: {full_xpath}")
    return elements[0]


async def extract_visible_users_from_dialogue(scroll_container: ElementHandle) -> list[Account]:
    # print scroll_container for debugging
    user_elements = await scroll_container.query_selector_all(":scope > div > div > div > .html-div")
    users = []
    for a in user_elements:
        try:
            anchor = await a.query_selector("a[role='link']")
            if anchor:
                profile_url = await anchor.get_attribute("href")
                username = profile_url.strip("/").split("/")[-1]
                display_name_span = await a.query_selector("span[dir='auto']")
                display_name = await display_name_span.inner_text() if display_name_span else username
                users.append(
                    Account(
                        username=username,
                        display_name=display_name,
                        profile_url=f"https://www.instagram.com{profile_url}",
                        social_network="instagram",
                        is_private=None
                    )
                )
        except Exception as e:
            print(f"Error extracting user: {e}")
    return users


def human_delay(mean=2.0, sigma=0.5, min_delay=0.8, max_delay=6.0):
    """Generate a human-like random delay in seconds"""
    delay = np.random.lognormal(mean=np.log(mean), sigma=sigma)
    return max(min(delay, max_delay), min_delay)


async def smart_human_scroll(page: Page, scroll_container: ElementHandle, total_scroll: Optional[int] = None,
                             step: int = 150, delay: float = 0.05):
    box = await scroll_container.bounding_box()
    if not box:
        raise RuntimeError("Could not get bounding box for scroll container.")
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    mouse: Mouse = page.mouse
    scrolled = 0
    while total_scroll is None or scrolled < total_scroll:
        await mouse.move(x, y)
        await mouse.wheel(0, step)
        scrolled += step
        randomized_delay = human_delay(mean=delay, sigma=0.1, min_delay=delay * 0.3, max_delay=delay * 2)
        scroll_top = await scroll_container.evaluate("el => el.scrollTop")
        scroll_height = await scroll_container.evaluate("el => el.scrollHeight")
        client_height = await scroll_container.evaluate("el => el.clientHeight")
        if scroll_top + client_height >= scroll_height:
            break
        await asyncio.sleep(randomized_delay)


async def quick_scroll_to_bottom(scroll_container: ElementHandle):
    await scroll_container.evaluate("el => el.scrollBy(0, el.scrollHeight)")


async def is_loading(scroll_container: ElementHandle) -> bool:
    loading_indicator = await scroll_container.query_selector('[aria-label="Loading..."]')
    print("loading indicator:")
    print(loading_indicator)
    return loading_indicator is not None


async def not_scrolled_all_way_down(scroll_container: ElementHandle) -> bool:
    remaining_scroll = await scroll_container.evaluate(
        """(el) => {
            return el.scrollHeight - (el.scrollTop + el.clientHeight) ;
        }"""
    )
    print(f"remaining scroll = {remaining_scroll}")
    return remaining_scroll > 5

async def get_related_users_from_dialogue(
        page: Page,
        relation: Literal['followers', 'following'],
        scrolling_pattern: Literal['smart', 'quick'] = 'quick',
        scrolling_method: Literal['playwright', 'js'] = 'js',
        mean_iteration_delay: float = 2.0,
        max_stagnant_scrolls: int = 5,
        max_users: Optional[int] = None
) -> list[Account]:
    await page.click(f"a[href$='/{relation}/']")

    await asyncio.sleep(5)

    # Wait for modal to appear
    await page.wait_for_selector("#scrollview", timeout=10000)

    await page.wait_for_selector(
        "#scrollview button div[dir='auto']:text('Follow'), #scrollview button div[dir='auto']:text('Following')",
        timeout=10000)

    # Find the scrollable container using XPath-based relative traversal
    scroll_container = await find_relative_element_by_xpath(
        page,
        anchor_xpath=f'//div[@role="heading" and text()="{relation.capitalize()}"]',
        relative_xpath='parent::div/parent::div/parent::div/parent::div/parent::div/div[last()]'
    )

    await scroll_container.evaluate(
        """(el) => {
            console.log("Scroll container found:", el);
        }"""
    )

    all_users: list[Account] = []
    encountered_usernames: set[str] = set()
    last_scroll_height = 0
    stagnant_scrolls = 0

    if scrolling_method == 'playwright':
        while not max_users or len(all_users) < max_users:
            new_users = await extract_visible_users_from_dialogue(scroll_container)
            all_users.extend([u for u in new_users if u.username not in encountered_usernames])
            encountered_usernames.update(u.username for u in new_users)
            try:
                if scrolling_pattern == 'smart':
                    await smart_human_scroll(page, scroll_container)
                elif scrolling_pattern == 'quick':
                    await quick_scroll_to_bottom(scroll_container)
                randomized_delay = human_delay(mean=mean_iteration_delay, sigma=0.1,
                                               min_delay=mean_iteration_delay * 0.3,
                                               max_delay=mean_iteration_delay * 2)
                await asyncio.sleep(randomized_delay)
            except Exception as e:
                print(f"Error during scrolling: {e}")
                break

            # Check for loading spinner or DOM change
            new_scroll_height = await scroll_container.evaluate("el => el.scrollHeight")
            if new_scroll_height == last_scroll_height:
                print("checking if reached the end of the container")
                if await is_loading(scroll_container) or await not_scrolled_all_way_down(scroll_container):
                    stagnant_scrolls = 0
                    continue
                else:
                    stagnant_scrolls += 1
                if stagnant_scrolls >= max_stagnant_scrolls:
                    break
            else:
                stagnant_scrolls = 0
            last_scroll_height = new_scroll_height
    else:
        scroll_container_classes = await scroll_container.get_attribute("class")
        print(f"Scroll container classes: {scroll_container_classes}")
        scroll_container_selector = f".{scroll_container_classes.replace(' ', '.')}"
        js_script = """(async function () {
            const users = new Set();
            const userList = [];
            const max_users = """ + (f"{max_users}" if max_users else "Infinity") + """;
            const profileName = window.location.pathname.split("/")[1];
            let lastScrollHeight = 0;
        
            function getVisibleUsers(scrollContainer) {
                Array.from(scrollContainer.childNodes[0].childNodes[0].querySelectorAll("a")).filter(x=>x.innerText?.length).forEach(a => {
                    const display_name = a?.parentElement?.parentElement?.parentElement?.parentElement?.parentElement?.childNodes?.[1]?.innerText?.trim();
                    const profileUrl = new URL(a.href, window.location.origin).href;
        
                    if (profileUrl && !users.has(profileUrl)) {
                        users.add(profileUrl);
                        userList.push({
                            display_name: display_name,
                            profile_url: profileUrl,
                            username: profileUrl.split("/").slice(-2, -1)[0],
                            social_network: "instagram"
                        });
                    }
                });
            }
        
            async function scrollDownAndCapture() {
                const scrollContainer = document.querySelector('""" + scroll_container_selector + """');
                console.log("Using scroll container:", scrollContainer);
                if (!scrollContainer) return;
        
                let keepScrolling = true;
                while (keepScrolling) {
                    getVisibleUsers(scrollContainer);
                    scrollContainer.scrollBy(0, 500);
                    await new Promise(resolve => setTimeout(resolve, """ + f"{mean_iteration_delay * 1000}" + """));
                    const newScrollHeight = scrollContainer.scrollHeight;
                    const isLoading = document.querySelector("[data-visualcompletion='loading-state']") !== null;
                    if ((newScrollHeight !== lastScrollHeight || isLoading)) {
                        lastScrollHeight = newScrollHeight;
                        stagnant_scrolls = 0;
                    } else {
                        stagnant_scrolls += 1;
                    }
                    if (stagnant_scrolls >= """ + str(max_stagnant_scrolls) + """) {
                        keepScrolling = false;
                    }
                    if (userList.length >= max_users) {
                        keepScrolling = false;
                    }
                }
            }
        
            await scrollDownAndCapture();
            return userList;
            })();
        """
        await asyncio.sleep(2)
        all_users_dict_list = await scroll_container.evaluate(js_script)
        all_users = [Account(**user) for user in all_users_dict_list]

    unique_users: list[Account] = list({user.username: user for user in all_users}.values())

    close_button = await page.query_selector("button:has(svg[aria-label='Close'])")
    if close_button:
        await close_button.click()
    else:
        print("❌ Close button not found. Please close the modal manually.")

    return unique_users


def parse_instagram_number(s: str) -> int:
    s = s.replace(",", "").strip().upper()
    if s.endswith("K"):
        return int(float(s[:-1]) * 1_000)
    elif s.endswith("M"):
        return int(float(s[:-1]) * 1_000_000)
    elif s.endswith("B"):
        return int(float(s[:-1]) * 1_000_000_000)
    return int(float(s))


async def get_profile_details(page: Page) -> Account:
    # Wait for the page to load and the meta tags to be available
    await page.wait_for_function("document.querySelector('meta[property=\"og:description\"]') !== null", timeout=10000)
    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    description_meta = soup.find("meta", property="og:description")
    if not description_meta:
        raise RuntimeError("❌ Could not find profile description meta tag.")
    description_content = description_meta.get("content", "")
    print(description_content)
    # Format: "[follower_count] followers, [following_count] following, [post_count] posts – see Instagram photos and videos from [display_name] (@[username])"
    followers, rest = description_content.split(" followers, ", 1)
    following, rest = rest.split(" following, ", 1)
    posts, rest = rest.split(" posts – see Instagram photos and videos from ", 1)
    try:
        display_name, username = rest.split(" (@", 1)
        username = username.strip(")")
    except ValueError:
        display_name = ""
        username = rest.split("@")[1]
    followers_count = parse_instagram_number(followers)
    following_count = parse_instagram_number(following)
    posts_count = parse_instagram_number(posts)
    is_private = bool(soup.find("span", string="This account is private"))
    return Account(
        username=username,
        display_name=display_name.strip(),
        profile_url=f"https://www.instagram.com/{username}/",
        social_network="instagram",
        is_private=is_private,
        followers_count=followers_count,
        following_count=following_count,
        posts_count=posts_count
    )


async def get_playwright_insta_friends(profile: Profile, username: str) -> FriendsScrape:
    if not profile.browser_profile:
        raise Exception("No browser profile found. Please register a new profile first.")
    storage_state = StorageState(**profile.browser_profile)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context(storage_state=storage_state)
        page = await context.new_page()
        await page.goto(f"https://www.instagram.com/{username}/")
        profile = await get_profile_details(page)
        print("fetching followers")
        followers = []
        try:
            if profile.followers_count > 0 and not profile.is_private:
                followers = await get_related_users_from_dialogue(page, 'followers', max_users=1000)
        except Exception:
            print("❌ Failed to fetch followers.")
        print("fetching following")
        following = []
        try:
            if profile.following_count > 0 and not profile.is_private:
                following = await get_related_users_from_dialogue(page, 'following', max_users=1000)
        except Exception:
            print("❌ Failed to fetch following.")
        return FriendsScrape(
            followers=followers, following=following, account_details=profile
        )
