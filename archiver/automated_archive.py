import datetime
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from pydantic import BaseModel

from archiver.archive import (
    ArchiveSessionMetadata,
    StorageConfig,
    finish_recording,
    get_tls_cert_info,
    screen_record,
)
from archiver.automated_scripts.instagram_followers_scraper import run_followers_automation
from archiver.dialogs import (
    DialogForm,
    FormFieldBool,
    FormFieldText,
    FormSection,
    show_dialog_form,
)
from archiver.profile_registration import Profile
from archiver.profile_selection import select_profile
from root_anchor import ROOT_DIR
from utils.commit_tracker.git_helper import ensure_committed
from utils.ffmpeg_installer import ensure_ffmpeg_installed
from utils.misc import get_my_public_ip, get_system_info

load_dotenv()


class AutomatedSessionConfig(BaseModel):
    usernames: list[str]
    scrape_followers: bool
    scrape_following: bool
    storage_config: StorageConfig


def get_automated_session_config() -> Optional[AutomatedSessionConfig]:
    default_signature = os.getenv("DEFAULT_SIGNATURE", "")
    raw = show_dialog_form(
        DialogForm(
            title="Automated Follower Scraper",
            submit_button_text="Start",
            sections=[
                FormSection(
                    title="Targets",
                    fields=[
                        FormFieldText(
                            title="Instagram usernames to scrape (comma or newline separated)",
                            key="usernames_raw",
                            default_value="",
                        ),
                        FormFieldBool(
                            title="Scrape followers",
                            key="scrape_followers",
                            default_value=True,
                        ),
                        FormFieldBool(
                            title="Scrape following",
                            key="scrape_following",
                            default_value=True,
                        ),
                    ],
                ),
                FormSection(
                    title="Summary",
                    fields=[
                        FormFieldText(
                            title="Signature (Full Name)",
                            key="signature",
                            default_value=default_signature,
                        ),
                        FormFieldText(
                            title="Notes about the content",
                            key="notes",
                            default_value="",
                        ),
                    ],
                ),
                FormSection(
                    title="Video Downloading Configuration",
                    fields=[
                        FormFieldBool(
                            title="Download Auxiliary Media (profile pictures of other users, thumbnails, etc.)",
                            key="v_download_media_not_in_structures",
                            default_value=False,
                        ),
                        FormFieldBool(
                            title="Download Related Media that Hasn't Been Fetched During the Session",
                            key="v_download_unfetched_media",
                            default_value=False,
                        ),
                        FormFieldBool(
                            title="Download Full Versions of Fetched Media",
                            key="v_download_full_versions_of_fetched_media",
                            default_value=True,
                        ),
                        FormFieldBool(
                            title="Download Highest Quality Assets from Structures",
                            key="v_download_highest_quality_assets_from_structures",
                            default_value=True,
                        ),
                    ],
                ),
                FormSection(
                    title="Photo Downloading Configuration",
                    fields=[
                        FormFieldBool(
                            title="Download Auxiliary Media (profile pictures of other users, thumbnails, etc.)",
                            key="p_download_media_not_in_structures",
                            default_value=False,
                        ),
                        FormFieldBool(
                            title="Download Related Media that Hasn't Been Fetched During the Session",
                            key="p_download_unfetched_media",
                            default_value=False,
                        ),
                        FormFieldBool(
                            title="Download Highest Quality Assets from Structures",
                            key="p_download_highest_quality_assets_from_structures",
                            default_value=True,
                        ),
                    ],
                ),
            ],
        )
    )

    if raw is None:
        return None

    usernames_raw: str = raw.pop("usernames_raw", "")
    # split on commas and newlines, strip whitespace, drop empties
    parts = [u.strip() for part in usernames_raw.replace(",", "\n").splitlines() for u in [part.strip()] if u]
    usernames = [u for u in parts if u]

    if not usernames:
        print("No usernames entered — nothing to do.")
        return None

    storage_config = StorageConfig(
        signature=raw["signature"],
        notes=raw["notes"],
        v_download_media_not_in_structures=raw["v_download_media_not_in_structures"],
        v_download_unfetched_media=raw["v_download_unfetched_media"],
        v_download_full_versions_of_fetched_media=raw["v_download_full_versions_of_fetched_media"],
        v_download_highest_quality_assets_from_structures=raw["v_download_highest_quality_assets_from_structures"],
        p_download_media_not_in_structures=raw["p_download_media_not_in_structures"],
        p_download_unfetched_media=raw["p_download_unfetched_media"],
        p_download_highest_quality_assets_from_structures=raw["p_download_highest_quality_assets_from_structures"],
    )

    return AutomatedSessionConfig(
        usernames=usernames,
        scrape_followers=raw["scrape_followers"],
        scrape_following=raw["scrape_following"],
        storage_config=storage_config,
    )


def archive_followers_session(
    profile: Profile,
    username: str,
    commit_id: Optional[str],
    branch: Optional[str],
    config: AutomatedSessionConfig,
) -> None:
    profiles_dir = Path(ROOT_DIR) / "archiver" / "profiles"
    profile_path = profiles_dir / profile.name

    if not profile_path.exists() or not (profile_path / "state.json").exists():
        print(f"Profile '{profile.name}' not found. Please register it first.")
        return

    target_url = f"https://www.instagram.com/{username}/"

    archiving_start_time = datetime.datetime.now()
    archiving_start_timestamp = archiving_start_time.isoformat()
    archive_dir = (
        Path(ROOT_DIR)
        / "archives"
        / f"{profile.name}_{username}_{archiving_start_time.strftime('%Y%m%d_%H%M%S')}"
    )
    archive_dir.mkdir(parents=True, exist_ok=True)

    my_public_ip = get_my_public_ip()
    tls_cert = get_tls_cert_info("www.instagram.com")

    with open(profile_path / "state.json", "r") as f:
        storage_state = json.load(f)

    stop_event = threading.Event()
    recording_thread = None
    video_path = archive_dir / "screen_recording.mp4"
    metadata = ArchiveSessionMetadata(
        commit_id=commit_id,
        branch=branch,
        profile_name=profile.insta_username,
        target_url=target_url,
        archiving_start_timestamp=archiving_start_timestamp,
        recording_start_timestamp=datetime.datetime.now().isoformat(),
        archiving_timezone=datetime.datetime.now().astimezone().tzname(),
        har_archive=archive_dir / "har_workspace" / "archive.har",
        my_ip=my_public_ip,
        platform=get_system_info(),
        tls_cert=tls_cert,
    )

    try:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=False)
            browser_build_id = f"{browser.browser_type.name}_{browser.version}"
            metadata.browser_build_id = browser_build_id
            context = browser.new_context(
                storage_state=storage_state,
                record_har_path=metadata.har_archive,
                record_har_content="attach",
                record_video_dir=archive_dir / "screen_recordings",
            )

            page = context.new_page()
            frame_hashes_path = archive_dir / "frame_hashes.jsonl"
            recording_thread = threading.Thread(
                target=screen_record,
                args=(str(video_path), stop_event, str(frame_hashes_path)),
            )
            recording_thread.start()

            try:
                print(f"Starting automated followers scrape for @{username}")
                run_followers_automation(
                    page,
                    username,
                    config.scrape_followers,
                    config.scrape_following,
                )
                print(f"Automation complete for @{username}")
            except Exception as e:
                if "Target closed" in str(e) or "browser has disconnected" in str(e).lower():
                    print("Browser shutdown detected, wrapping up archiving session...")
                else:
                    print(f"Error during automated archiving of @{username}: {e}")
            finally:
                try:
                    context.close()
                except Exception as e:
                    print(f"Warning: context.close() raised an error: {e}")
                try:
                    browser.close()
                except Exception as e:
                    print(f"Warning: browser.close() raised an error: {e}")
    except Exception as e:
        print(f"Playwright session ended with an error: {e}")

    finish_recording(
        recording_thread,
        archive_dir,
        metadata,
        stop_event,
        storage_config=config.storage_config,
    )


if __name__ == "__main__":
    commit_id, branch = ensure_committed()
    ensure_ffmpeg_installed()
    selected_profile = select_profile()
    config = get_automated_session_config()
    if config is None:
        sys.exit(0)
    for username in config.usernames:
        archive_followers_session(selected_profile, username, commit_id, branch, config)
    sys.exit(0)
