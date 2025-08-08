import sys
import json
from pathlib import Path

from profile_registration import Profile, register_instagram_account


def select_profile() -> Profile:
    print("Fetching available profiles...")
    available_profiles_path = Path("profiles/map.json")
    if not available_profiles_path.exists():
        if input("No profiles found. Would you like to register a new profile? (yes/no): "):
            register_instagram_account()
            print("Please run the script again to select the new profile.")
        sys.exit(1)
    with open(available_profiles_path, "r") as m:
        profile_dicts: list[dict] = json.loads(m.read())
        profiles_map = [Profile(**profile) for profile in profile_dicts]
    print("Available profiles:")
    for idx, profile in enumerate(profiles_map):
        print(f"{idx} {profile.name} (Instagram username: {profile.insta_username})")
    print(f"+ new")
    profile_selection = input("Enter the profile name to use: ")
    profile_selection = profile_selection.strip()
    profile = None
    if profile_selection == "+" or profile_selection.lower() == "new":
        register_instagram_account()
        print("Please run the script again to select the new profile.")
        sys.exit(0)
    if profile_selection.isdigit():
        idx = int(profile_selection)
        if 0 <= idx < len(profiles_map):
            profile = profiles_map[idx]
        else:
            raise Exception("Invalid profile index selected.")
    else:
        for p in profiles_map:
            if p.name == profile_selection:
                profile = p
                break
    if profile is None:
        raise Exception("No matching profile found for the given name.")
    return profile