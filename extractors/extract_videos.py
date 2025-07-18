import base64
import json
import ijson
import os
import subprocess
import traceback
import urllib
import requests

from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class MediaSegment(BaseModel):
    start: Optional[int]
    end: Optional[int]
    data: bytes


class MediaTrack(BaseModel):
    base_url: str
    segments: list[MediaSegment]
    full_track: Optional[bytes] = None


class Video(BaseModel):
    xpv_asset_id: int
    tracks: dict[str, MediaTrack]
    location: Optional[str] = None
    local_files: list[str] = []


def extract_xpv_asset_id(url):
    # Parse query string
    parsed_url = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    # Get the `efg` parameter (it may be URL-encoded)
    efg_encoded = query_params.get('efg')
    if not efg_encoded:
        return None

    # Base64-decode the efg value
    try:
        efg_json = base64.urlsafe_b64decode(efg_encoded[0] + '==')  # Add padding if missing
        efg_data = json.loads(efg_json.decode('utf-8'))
        return efg_data.get('xpv_asset_id')
    except Exception as e:
        print(f"Error decoding efg: {e}")
        return None


def extract_video_maps(har_path: Path, download_full_video: bool = True) -> list[Video]:
    """Extracts video segment data from the HAR file using streaming JSON parsing."""
    videos_dict: dict[int, Video] = dict()

    with open(har_path, 'rb') as file:
        for entry in ijson.items(file, 'log.entries.item'):
            try:
                if ".mp4" in entry['request']['url'] and "text" in entry['response']['content']:
                    url = entry['request']['url']
                    base_url = url.split(".mp4")[0]
                    xpv_asset_id = extract_xpv_asset_id(url)
                    filename = base_url.split("/")[-1]
                    start = end = None
                    if "bytestart=" in url:
                        start = int(url.split("bytestart=")[1].split("&")[0])
                    if "byteend=" in url:
                        end = int(url.split("byteend=")[1].split("&")[0])
                    response_content = base64.b64decode(entry['response']['content']['text'])
                    if xpv_asset_id not in videos_dict:
                        videos_dict[xpv_asset_id] = Video(
                            xpv_asset_id=xpv_asset_id,
                            tracks=dict(),
                        )
                    if filename not in videos_dict[xpv_asset_id].tracks:
                        videos_dict[xpv_asset_id].tracks[filename] = MediaTrack(base_url=base_url, segments=[])
                        if download_full_video:
                            try:
                                full_track_url = urllib.parse.urlunparse(
                                    urllib.parse.urlparse(url)._replace(
                                        query="&".join(
                                            f"{k}={v[0]}" if len(v) == 1 else "&".join(f"{k}={i}" for i in v)
                                            for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()
                                            if k not in ("bytestart", "byteend")
                                        )
                                    )
                                )
                                print("Downloading full track from:", full_track_url)
                                resp = requests.get(full_track_url)
                                if resp.status_code == 200:
                                    videos_dict[xpv_asset_id].tracks[filename].full_track = resp.content
                            except Exception as e:
                                print(f"Error downloading full track: {e}")
                                pass
                    videos_dict[xpv_asset_id].tracks[filename].segments.append(MediaSegment(start=start, end=end, data=response_content))
            except Exception as e:
                print(f'Error processing entry: {e}')
                traceback.print_exc()
                continue
    videos = list(videos_dict.values())
    return videos


def clean_segments(files_to_delete):
    for file in files_to_delete:
        if os.path.exists(file):
            os.remove(file)
        else:
            print(f"File {file} does not exist, skipping deletion.")


def merge_video_and_audio_tracks(video_path: Path, audio_path: Path, output_path: Path) -> bool:
    """Merge video and audio tracks into a single file."""
    try:
        # Use ffmpeg to merge video and audio
        subprocess.run(
            ['ffmpeg', '-y', '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental',
             output_path],
            check=True
        )
        # Check if the merge was successful
        if os.path.exists(output_path):
            print(f"Merged video and audio into {output_path}")
            clean_segments([video_path, audio_path])
            return True
        else:
            print(f"Failed to create merged file at {output_path}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error merging video and audio: {e}")
        return False


def save_segments_as_files(videos: list[Video], output_dir: Path, files_to_skip: Optional[dict[str, tuple[str, int]]] = None) -> list[Video]:
    if files_to_skip is None:
        files_to_skip = dict()
    existing_videos_filenames = [v[0] for v in files_to_skip.values()]

    """Extracts and saves each segment as a temporary video file."""
    for v_idx, video in enumerate(videos):
        temp_video_file = None
        temp_audio_file = None
        merged_file = None
        xpv_asset_id = video.xpv_asset_id

        file_exists = False
        for existing_file in existing_videos_filenames:
            if f"{xpv_asset_id}" in existing_file:
                print(f"Skipping existing file {existing_file} for video {xpv_asset_id}.")
                video.location = (output_dir / existing_file).as_posix()
                video.local_files.append((output_dir / existing_file).as_posix())
                file_exists = True
                break
        if file_exists:
            continue

        for track_name, track in video.tracks.items():
            track_data = b''
            if track.full_track is not None:
                # If full track is available, use it directly
                track_data = track.full_track
            else:
                # sort the segments by start byte
                track.segments.sort(key=lambda s: s.start)
                # compose a full file out of the segments.
                # Determine the total length needed for the track
                max_end = max((segment.end for segment in track.segments if segment.end is not None), default=0)
                track_data = bytearray(max_end)

                for segment in track.segments:
                    if segment.start is None:
                        # If no start, append at the end (rare, fallback)
                        track_data = segment.data
                    else:
                        # Overwrite the region with this segment's data
                        track_data[segment.start:segment.end] = segment.data
            source_type = "extracted_from_har" if track.full_track is None else "full_track_downloaded"
            single_track_file = f"track_{video.xpv_asset_id}_{track_name}_{source_type}.mp4"
            with open(output_dir / single_track_file, 'wb') as f:
                f.write(track_data)
            valid_file = clean_corrupted_files(output_dir / single_track_file)
            if not valid_file:
                print(f"File {output_dir / single_track_file} is corrupted, skipping.")
                clean_segments([output_dir / single_track_file])
                continue
            video.local_files.append((output_dir / single_track_file).as_posix())
            # determine whether the file is audio or video using ffprobe
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_type', '-of',
                 'default=noprint_wrappers=1:nokey=1',
                 str(output_dir / single_track_file)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if len(track_data) > 0:
                if 'audio' in result.stdout:
                    temp_audio_file = single_track_file
                else:
                    if temp_video_file is not None:
                        existing_file = output_dir / temp_video_file
                        new_file = output_dir / single_track_file
                        if os.path.getsize(new_file) > os.path.getsize(existing_file):
                            temp_video_file = single_track_file
                    else:
                        temp_video_file = single_track_file


        if temp_audio_file is not None and temp_video_file is not None:
            merged_file = f"{temp_video_file.split('.mp4')[0]}_with_audio.mp4"
            merge_success = merge_video_and_audio_tracks(
                output_dir / temp_video_file,
                output_dir / temp_audio_file,
                output_dir / merged_file
            )
            if merge_success:
                video.local_files.append((output_dir / merged_file).as_posix())
                video.local_files.remove((output_dir / temp_video_file).as_posix())
                video.local_files.remove((output_dir / temp_audio_file).as_posix())


        video_location = merged_file or temp_video_file or temp_audio_file or None
        if video_location:
            valid_file = clean_corrupted_files(output_dir / video_location)
            if not valid_file:
                video.location = None
            else:
                video.location = (output_dir / video_location).as_posix()
        else:
            print(f"No valid video or audio files found for video {video.xpv_asset_id}, skipping.")
            video.location = None
    return videos


def clean_corrupted_files(path_to_check: Path) -> bool:
    if os.path.exists(path_to_check) and os.path.getsize(path_to_check) < 1000:
        os.remove(path_to_check)
        return False
    try:
        # Use ffprobe to check if the file is a valid media file
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration,format_name', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name', '-of', 'default=noprint_wrappers=1:nokey=1', path_to_check],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 0 or not result.stdout.strip():
            os.remove(path_to_check) # Delete if ffprobe indicates corruption
            return False
        return True
    except Exception as e:
        print(f"Error checking file {path_to_check}: {e}")
        if os.path.exists(path_to_check):
            os.remove(path_to_check)
            return False
        return True


def videos_from_har(har_path:Path, output_dir:Path=Path('../temp_video_segments'), download_full_video: bool = True) -> list[Video]:
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Existing files in the output directory
    existing_files_name_size_tuples = [
        (file.name, file.stat().st_size) for file in output_dir.iterdir() if file.is_file()
    ]

    largest_version_of_files: dict[str, tuple[str, int]] = dict()

    for file_name, file_size in existing_files_name_size_tuples:
        print(f"Extracting {file_name}...")
        try:
            cleaned_file_name = file_name.split('track_')[1].split("_")[0]
        except IndexError:
            cleaned_file_name = file_name
        if cleaned_file_name not in largest_version_of_files or file_size > largest_version_of_files[cleaned_file_name][1]:
            largest_version_of_files[cleaned_file_name] = (file_name, file_size)


    videos = extract_video_maps(har_path, download_full_video=download_full_video)
    if not videos:
        print("No video segments found in the HAR file.")
        return []

    files_to_skip = largest_version_of_files if not download_full_video else dict()

    # Save the video segments as temporary files
    stored_videos = save_segments_as_files(videos, output_dir, files_to_skip)
    print(f"Saved {len(videos)} videos to {output_dir}.")
    return stored_videos



if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file: ")  # Replace with your actual HAR file

    videos_from_har(Path(har_file))
