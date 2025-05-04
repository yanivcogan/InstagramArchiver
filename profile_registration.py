# profile_registration.py
import os
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from pydantic import BaseModel


class Profile(BaseModel):
    name: str
    insta_username: str


def register_instagram_account():
    profiles_dir = Path("profiles")
    profiles_dir.mkdir(exist_ok=True)
    map_path = profiles_dir / "map.json"
    profiles_map = []
    if map_path.exists():
        with open(map_path, "r") as m:
            profiles_map = json.loads(m.read())
            profiles_map = [Profile(**profile) for profile in profiles_map]

    profile_name = input("Enter a name for this profile: ")
    profile_name = profile_name.strip()
    if profile_name in [p.name for p in profiles_map]:
        print(f"Profile '{profile_name}' already exists. Please choose a different name.")
        return
    profile_path = profiles_dir / profile_name
    profile_insta_username = input("Enter the username of the Instagram account affiliated with this profile: ")
    profile_insta_username = profile_insta_username.strip()
    profiles_map.append(Profile(name=profile_name, insta_username=profile_insta_username))


    if profile_path.exists():
        override = input(f"Profile '{profile_name}' already exists. Override? (y/n): ")
        if override.lower() != 'y':
            print("Registration canceled.")
            return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=None)
        page = context.new_page()

        # Navigate to Instagram login page
        page.goto("https://www.instagram.com/accounts/login/")
        print("\n" + "="*50)
        print("Please log in to your Instagram account in the browser.")
        print("Once logged in, you can close the browser window.")
        print("="*50 + "\n")

        # Wait for user to log in and then close the browser themselves
        try:
            # Wait for navigation to /accounts/onetap/ or to the feed, indicating successful login
            try:
                page.wait_for_url(url="https://www.instagram.com/", timeout=120000)
            except Exception as e:
                print(f"Error waiting for URL: {e}")
                print("Please ensure you are logged in to Instagram.")
            # Wait a bit to ensure all cookies are set
            time.sleep(10)

            # Save the storage state
            storage_state = context.storage_state()
            os.makedirs(profile_path, exist_ok=True)

            with open(profile_path / "state.json", "w") as f:
                json.dump(storage_state, f)

            print(f"Profile saved successfully as '{profile_name}'")

            # Wait for user to close the browser
            input("Press Enter to close the browser...")

        except Exception as e:
            print(f"Error during registration: {e}")

        finally:
            browser.close()
            with open(map_path, "w") as m:
                json.dump([p.model_dump() for p in profiles_map], m)

if __name__ == "__main__":
    register_instagram_account()