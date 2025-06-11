# Download and extract ffmpeg if not present, and add to PATH
import os
import urllib.request
import zipfile

def ensure_ffmpeg_installed():
    # Check if ffmpeg is accessible by trying to run it
    existing_ffmpeg = os.system("ffmpeg -version >nul 2>&1")
    if existing_ffmpeg:
        return
    ffmpeg_dir = os.path.join(os.getcwd(), "ffmpeg")
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(ffmpeg_exe):
        ffmpeg_zip_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        ffmpeg_zip_path = os.path.join(os.getcwd(), "ffmpeg.zip")
        print("Downloading ffmpeg...")
        urllib.request.urlretrieve(ffmpeg_zip_url, ffmpeg_zip_path)
        with zipfile.ZipFile(ffmpeg_zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.endswith("ffmpeg.exe"):
                    zip_ref.extract(member, ffmpeg_dir)
                    # Move ffmpeg.exe to ffmpeg_dir root
                    src = os.path.join(ffmpeg_dir, member)
                    dst = os.path.join(ffmpeg_dir, "ffmpeg.exe")
                    os.replace(src, dst)
        os.remove(ffmpeg_zip_path)
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

if __name__ == "__main__":
    ensure_ffmpeg_installed()