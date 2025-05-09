import base64
import json
import os
import subprocess
import traceback
import urllib
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


class Video(BaseModel):
    xpv_asset_id: int
    video_track: Optional[MediaTrack]
    audio_track: Optional[MediaTrack]
    location: Optional[str] = None


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


def extract_video_maps(har_path:Path) -> list[Video]:
    """Extracts video segment data from the HAR file."""
    with open(har_path, 'rb') as file:  # Open the file in binary mode
        har_data = json.load(file)

    videos_dict: dict[int, Video] = dict()

    # Find the API call to GraphQL and its response
    for entry in har_data['log']['entries']:
        try:
            if ".mp4" in entry['request']['url'] and "text" in entry['response']['content']:
                url = entry['request']['url']
                xpv_asset_id = extract_xpv_asset_id(url)
                filename = url.split(".mp4")[0].split("/")[-1]
                start = end = None
                if "bytestart=" in url:
                    start = int(url.split("bytestart=")[1].split("&")[0])
                if "byteend=" in url:
                    end = int(url.split("byteend=")[1].split("&")[0])
                response_content = base64.b64decode(entry['response']['content']['text'])
                if xpv_asset_id not in videos_dict:
                    videos_dict[xpv_asset_id] = Video(
                        xpv_asset_id=xpv_asset_id,
                        video_track=None,
                        audio_track=None
                    )
                is_video = "o1/v/t2/f2" in url
                if is_video:
                    if videos_dict[xpv_asset_id].video_track is None:
                        videos_dict[xpv_asset_id].video_track = MediaTrack(base_url=filename, segments=[])
                    videos_dict[xpv_asset_id].video_track.segments.append(MediaSegment(start=start, end=end, data=response_content))
                else:
                    if videos_dict[xpv_asset_id].audio_track is None:
                        videos_dict[xpv_asset_id].audio_track = MediaTrack(base_url=filename, segments=[])
                    videos_dict[xpv_asset_id].audio_track.segments.append(MediaSegment(start=start, end=end, data=response_content))
        except Exception as e:
            print(f'Error processing entry: {e}')
            traceback.print_exc()
            continue
    videos = list(videos_dict.values())
    return videos


class StoredVideo(BaseModel):
    xpv_asset_id: int
    video_track: list[str] = []
    audio_track: list[str] = []


def clean_segments(files_to_delete):
    for file in files_to_delete:
        if os.path.exists(file):
            os.remove(file)
        else:
            print(f"File {file} does not exist, skipping deletion.")


def merge_video_and_audio_tracks(video_path: Path, audio_path: Path, output_path: Path):
    """Merge video and audio tracks into a single file."""
    try:
        # Use ffmpeg to merge video and audio
        subprocess.run(
            ['ffmpeg', '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental',
             output_path],
            check=True
        )
        clean_segments([video_path, audio_path])
    except subprocess.CalledProcessError as e:
        print(f"Error merging video and audio: {e}")


def save_segments_as_files(videos: list[Video], output_dir: Path) -> list[Video]:
    """Extracts and saves each segment as a temporary video file."""
    for v_idx, video in enumerate(videos):
        temp_video_file = None
        temp_audio_file = None
        merged_file = None
        if video.video_track is not None:
            video_track = b''
            # compose a full file out of the segments.
            for segment in video.video_track.segments:
                # if the segment's start byte is None, just append the data.
                if segment.start is None:
                    video_track += segment.data
                    continue
                # add the data starting at the start byte.
                if len(video_track) < segment.end:
                    video_track += b'\x00' * (segment.end - len(video_track))
                video_track = video_track[:segment.start] + segment.data + video_track[segment.end:]
            temp_video_file = f"video_{v_idx}_no_audio.mp4"
            with open(output_dir / temp_video_file, 'wb') as f:
                f.write(video_track)

        if video.audio_track is not None:
            audio_track = b''
            # compose a full file out of the segments.
            for segment in video.audio_track.segments:
                # each segment has data and a start byte. Add the data starting at the start byte.
                if len(audio_track) < segment.end:
                    audio_track += b'\x00' * (segment.end - len(audio_track))
                audio_track = audio_track[:segment.start] + segment.data + audio_track[segment.end:]
            temp_audio_file = f"audio_{v_idx}_no_video.mp4"
            with open(output_dir / temp_audio_file, 'wb') as f:
                f.write(audio_track)

        if temp_audio_file is not None and temp_video_file is not None:
            merged_file = f"merged_{v_idx}.mp4"
            merge_video_and_audio_tracks(
                output_dir / temp_video_file,
                output_dir / temp_audio_file,
                output_dir / merged_file
            )

        video.location = merged_file or temp_video_file or temp_audio_file or None
        if video.location:
            valid_file = clean_corrupted_files(output_dir / video.location)
            if not valid_file:
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


def videos_from_har(har_path:Path, output_dir:Path=Path('temp_video_segments')):
    videos = extract_video_maps(har_path)
    if not videos:
        print("No video segments found in the HAR file.")
        return

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    # Save the video segments as temporary files
    save_segments_as_files(videos, output_dir)
    print(f"Saved {len(videos)} videos to {output_dir}.")



if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file: ")  # Replace with your actual HAR file

    videos_from_har(Path(har_file))
