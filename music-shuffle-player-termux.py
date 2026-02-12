#!/usr/bin/env python3
"""
Termux Music Player – Play shuffled music from a folder.
Creates a temporary MD5‑named copy of each file before playing.
Stops playback automatically when the script exits.
"""

import os
import sys
import random
import time
import atexit
import hashlib
import tempfile
import subprocess
import shutil

# ------------------------------------------------------------
# Supported audio file extensions (add more if needed)
MUSIC_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac',
              '.opus', '.wma', '.ape', '.aiff', '.dsf'}

# ------------------------------------------------------------
def stop_music():
    """Stop any currently playing media."""
    try:
        subprocess.run(['termux-media-player', 'stop'],
                       check=False, capture_output=True)
    except Exception as e:
        print(f"Error while stopping music: {e}")

# ------------------------------------------------------------
def is_playing():
    """
    Return True if a track is currently loaded (playing or paused),
    False if no track is loaded or the command fails.
    """
    try:
        output = subprocess.check_output(
            ['termux-media-player', 'info'],
            text=True, stderr=subprocess.STDOUT
        )
        # "No track currently!" indicates playback has finished
        return 'No track currently' not in output
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        print("\nError: termux-media-player not found.")
        print("Please install Termux:API and its Termux package.")
        sys.exit(1)

# ------------------------------------------------------------
def copy_to_temp_md5(original_path):
    """
    Copy the original music file to a temporary file whose name is
    the MD5 hash of the original filename (without extension) plus
    the same extension. Uses tempfile.NamedTemporaryFile and then
    renames the file to the desired name.
    Returns the full path to the temporary copy.
    """
    # Compute desired filename: hash + extension
    basename = os.path.basename(original_path)
    name_without_ext, ext = os.path.splitext(basename)
    hash_md5 = hashlib.md5(name_without_ext.encode('utf-8')).hexdigest()
    desired_name = hash_md5 + ext

    temp_dir = tempfile.gettempdir()
    dest_path = os.path.join(temp_dir, desired_name)

    # Use NamedTemporaryFile to create a secure temporary file
    try:
        with tempfile.NamedTemporaryFile(dir=temp_dir,
                                         suffix=ext,
                                         delete=False) as tmp_file:
            # Copy content from original to temporary file
            with open(original_path, 'rb') as src:
                shutil.copyfileobj(src, tmp_file)
            tmp_path = tmp_file.name
        # Now rename the temporary file to the desired hash name
        if os.path.exists(dest_path):
            os.remove(dest_path)      # overwrite if exists
        os.rename(tmp_path, dest_path)
        return dest_path
    except Exception as e:
        print(f"Error creating temporary copy for {basename}: {e}")
        # Clean up temporary file if it still exists
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return None

# ------------------------------------------------------------
def play_file(filepath):
    """Play a single media file."""
    try:
        subprocess.run(['termux-media-player', 'play', filepath],
                       check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to play: {os.path.basename(filepath)}")
        return False

# ------------------------------------------------------------
def gather_music_files(folder):
    """Recursively collect all music files from the given folder."""
    files = []
    for root, _, filenames in os.walk(folder):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in MUSIC_EXTS:
                files.append(os.path.join(root, name))
    return files

# ------------------------------------------------------------
def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <folder_path>")
        sys.exit(1)

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a valid directory.")
        sys.exit(1)

    # Ensure music stops on exit
    atexit.register(stop_music)

    # Find music files
    songs = gather_music_files(folder)
    if not songs:
        print(f"No supported music files found in '{folder}'.")
        sys.exit(1)

    print(f"Found {len(songs)} music file(s). Starting shuffled playback...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            random.shuffle(songs)
            for song in songs:
                print(f"Now playing: {os.path.basename(song)}")

                # Create temporary MD5‑named copy
                temp_path = copy_to_temp_md5(song)
                if temp_path is None:
                    print("Skipping due to copy error.")
                    continue
                try:
                    # Play the temporary copy
                    if not play_file(temp_path):
                        # Clean up and skip if playback fails
                        os.remove(temp_path)
                        continue

                    # Wait until the track finishes
                    while is_playing():
                        time.sleep(1)

                    print("Finished.\n")
                finally:
                    # Remove the temporary file
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass  # might already be gone, ignore
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Stopping playback...")
        # stop_music is already registered via atexit
        stop_music()
        sys.exit(0)

# ------------------------------------------------------------
if __name__ == '__main__':
    main()