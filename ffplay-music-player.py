 
#!/usr/bin/env python3
"""
ffplay music player – Play shuffled music from a folder.
Creates a temporary MD5‑named copy of each file before playing.
Uses ffplay in headless mode; playback stops when the process finishes.
"""

import os
import sys
import random
import atexit
import hashlib
import tempfile
import shutil
import subprocess
import platform

# ------------------------------------------------------------
# Supported audio file extensions (add more if needed)
MUSIC_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac',
              '.opus', '.wma', '.ape', '.aiff', '.dsf'}

# ------------------------------------------------------------
# Global reference to the currently running ffplay process
ffplay_process = None

def check_ffplay():
    """Verify ffplay is available; if not, suggest installation and exit."""
    if shutil.which('ffplay') is not None:
        return

    print("Error: ffplay executable not found in PATH.", file=sys.stderr)
    system = platform.system().lower()

    # Try to detect package manager and suggest appropriate command
    suggestions = []

    # Linux package managers
    if system == 'linux':
        if shutil.which('apt'):
            suggestions.append("sudo apt install ffmpeg")
        elif shutil.which('dnf'):
            suggestions.append("sudo dnf install ffmpeg")
        elif shutil.which('yum'):
            suggestions.append("sudo yum install ffmpeg")
        elif shutil.which('pacman'):
            suggestions.append("sudo pacman -S ffmpeg")
        elif shutil.which('zypper'):
            suggestions.append("sudo zypper install ffmpeg")
        elif shutil.which('emerge'):
            suggestions.append("sudo emerge --ask media-video/ffmpeg")
        # Termux on Android
        elif shutil.which('pkg'):
            suggestions.append("pkg install ffmpeg")
    # macOS
    elif system == 'darwin':
        if shutil.which('brew'):
            suggestions.append("brew install ffmpeg")
        elif shutil.which('port'):
            suggestions.append("sudo port install ffmpeg")
    # Windows (using package managers or direct download)
    elif system == 'windows':
        if shutil.which('choco'):
            suggestions.append("choco install ffmpeg")
        elif shutil.which('winget'):
            suggestions.append("winget install ffmpeg")
        else:
            suggestions.append("Download ffmpeg from https://ffmpeg.org/ and add it to PATH")

    if suggestions:
        print("Please install ffmpeg (which provides ffplay) using one of these commands:", file=sys.stderr)
        for cmd in suggestions:
            print(f"  {cmd}", file=sys.stderr)
    else:
        print("Please ensure ffplay executable is in PATH", file=sys.stderr)

    sys.exit(1)

def cleanup_ffplay():
    """Terminate the currently running ffplay process, if any."""
    global ffplay_process
    if ffplay_process and ffplay_process.poll() is None:
        ffplay_process.terminate()
        try:
            ffplay_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            ffplay_process.kill()
        ffplay_process = None

def copy_to_temp_md5(original_path):
    """
    Copy the original music file to a temporary file whose name is
    the MD5 hash of the original filename (without extension) plus
    the same extension.
    Returns the full path to the temporary copy, or None on error.
    """
    basename = os.path.basename(original_path)
    name_without_ext, ext = os.path.splitext(basename)
    hash_md5 = hashlib.md5(name_without_ext.encode('utf-8')).hexdigest()
    desired_name = hash_md5 + ext

    temp_dir = tempfile.gettempdir()
    dest_path = os.path.join(temp_dir, desired_name)

    try:
        with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=ext, delete=False) as tmp_file:
            with open(original_path, 'rb') as src:
                shutil.copyfileobj(src, tmp_file)
            tmp_path = tmp_file.name

        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(tmp_path, dest_path)
        return dest_path
    except Exception as e:
        print(f"Error creating temporary copy for {basename}: {e}", file=sys.stderr)
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
        return None

def play_file(filepath):
    """
    Play a single audio file using ffplay in headless mode.
    Blocks until playback finishes or is interrupted.
    Returns True if ffplay exited normally (return code 0), False otherwise.
    """
    global ffplay_process
    try:
        cmd = [
            'ffplay',
            '-nodisp',          # no video output
            '-autoexit',        # exit when playback ends
            '-loglevel', 'quiet',   # suppress log messages
            '-hide_banner',     # skip copyright notice
            '-i', filepath
        ]
        ffplay_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        returncode = ffplay_process.wait()
        if returncode != 0:
            print(f"ffplay exited with code {returncode} for {os.path.basename(filepath)}", file=sys.stderr)
            return False
        return True
    except KeyboardInterrupt:
        # User pressed Ctrl+C: kill ffplay and re-raise
        cleanup_ffplay()
        raise
    except Exception as e:
        print(f"Error playing {os.path.basename(filepath)}: {e}", file=sys.stderr)
        return False
    finally:
        ffplay_process = None

def gather_music_files(folder):
    """Recursively collect all supported music files from the given folder."""
    files = []
    for root, _, filenames in os.walk(folder):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in MUSIC_EXTS:
                files.append(os.path.join(root, name))
    return files

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <folder_path>")
        sys.exit(1)

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    # Ensure ffplay is available before proceeding
    check_ffplay()

    # Register cleanup to kill ffplay on normal exit
    atexit.register(cleanup_ffplay)

    # Gather music files
    songs = gather_music_files(folder)
    if not songs:
        print(f"No supported music files found in '{folder}'.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(songs)} music file(s). Starting shuffled playback with ffplay...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            random.shuffle(songs)
            for song in songs:
                print(f"Now playing: {os.path.basename(song)}")

                # Create temporary MD5‑named copy
                temp_path = copy_to_temp_md5(song)
                if temp_path is None:
                    print("Skipping due to copy error.\n")
                    continue

                try:
                    success = play_file(temp_path)
                    if success:
                        print("Finished.\n")
                    else:
                        print("Playback failed, skipping.\n")
                finally:
                    # Clean up temporary file
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Stopping playback...")
        cleanup_ffplay()
        sys.exit(0)

if __name__ == '__main__':
    main()
