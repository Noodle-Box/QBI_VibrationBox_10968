#######################################################################################################################
# File: Microphone Driver
# Project: Time Locked Box Simulator
# Research Group: Suarez Lab, Queensland Brain Institute, UQ
#
# Author: Tevyn Vergara
# Date: 01/06/2026

############################################ Standard Library Imports ################################################
import argparse
import json
import shutil
import subprocess
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd

################################################### Functionality ####################################################
RESOLUTION = 16
RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"
SETTINGS_PATH = Path(__file__).resolve().parent / "microphone_settings.json"
DEFAULT_KEYWORD = "Pettersson"


DEFAULT_FILE_FORMAT = "FLAC"
FORMAT_WAV = "wav"
FORMAT_MP3 = "mp3"
FORMAT_FLAC = "flac"
SUPPORTED_FILE_FORMATS = (FORMAT_WAV, FORMAT_MP3, FORMAT_FLAC)


# Returns default microphone JSON settings for holding user-set parameters in main.py
def default_settings():
    return {
        "device_index": None,
        "file_format": DEFAULT_FILE_FORMAT.lower(),
    }


# Loads microphone_settings.json 
def load_settings():
    if not SETTINGS_PATH.exists():
        return default_settings()

    with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    defaults = default_settings()
    defaults.update(settings)
    return defaults


# Writes microphone_settings.json
def save_settings(settings):
    with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


# Builds the timestamp stem for audio output files
def get_recording_stem():
    return datetime.now().strftime("Recording_%H%M%S_%d_%m")


# Checks whether a sound device entry supports input channels
def is_input_mic(device):
    return device["max_input_channels"] > 0


# Checks whether a device name contains the requested keyword --> --filter "keyword"
def mic_matches_keyword(device, keyword):
    return keyword.lower() in device["name"].lower()


# Looks up the host API name for a sounddevice entry
def get_host_api_name(device):
    host_api_index = device["hostapi"]
    return sd.query_hostapis(host_api_index)["name"]


# Returns host-specific input stream settings, used by recording and preflight checks.
def get_input_extra_settings(device_index):
    device = sd.query_devices(device_index)
    host_api_name = get_host_api_name(device)

    if "WASAPI" in host_api_name:
        return sd.WasapiSettings(exclusive=True)

    return None


# Lists available input microphones in the terminal used by Main.py --> --list-devices
def list_input_mics(keyword=None):
    print("Available input microphone devices:")
    input_mics = []

    for index, device in enumerate(sd.query_devices()):
        if not is_input_mic(device):
            continue

        if keyword is not None and not mic_matches_keyword(device, keyword):
            continue

        input_mics.append((index, device))

    input_mics.sort(
        key=lambda item: (
            -int(item[1]["default_samplerate"]),
            item[1]["name"].lower(),
        )
    )

    for display_index, (system_index, device) in enumerate(input_mics):
        default_rate = int(device["default_samplerate"])
        host_api_name = get_host_api_name(device)
        print(
            f"  No.: {display_index} | "
            f"System Index: {system_index} | "
            f"Sampling Freq: {default_rate} Hz | "
            f"Host API: {host_api_name} | "
            f"Name: {device['name']}"
        )


# Auto-selects the highest-sample-rate input matching a keyword, used in resolve_recording_device()
def find_input_mic(keyword):
    matching_mics = []

    for index, device in enumerate(sd.query_devices()):
        if is_input_mic(device) and mic_matches_keyword(device, keyword):
            matching_mics.append((index, device))

    if not matching_mics:
        return None

    best_index, _ = max(matching_mics, key=lambda item: item[1]["default_samplerate"])
    return best_index


# Validates and returns input microphone by user system index
def get_input_mic(device_index):
    devices = sd.query_devices()

    if device_index < 0 or device_index >= len(devices):
        return None

    device = devices[device_index]
    if not is_input_mic(device):
        return None

    return device


# Saves the selected recording device index in JSON, used by handle_microphone_args().
def set_recording_device(settings, device_index):
    device = get_input_mic(device_index)
    if device is None:
        print(f"System index {device_index} is not an available input microphone.")
        print()
        list_input_mics()
        return False

    settings["device_index"] = device_index
    save_settings(settings)
    print(f"Recording microphone set to system index {device_index}: {device['name']}")
    return True


# Normalizes user/file format text to lowercase
def normalize_file_format(file_format):
    return file_format.strip().lower()


# Resolves the active recording format with fallback to default
def get_recording_format(settings, default_file_format=DEFAULT_FILE_FORMAT):
    file_format = normalize_file_format(settings.get("file_format", default_file_format))
    if file_format not in SUPPORTED_FILE_FORMATS:
        return normalize_file_format(default_file_format)

    return file_format


# Saves the selected microphone output format in JSON
def set_recording_format(settings, file_format):
    file_format = normalize_file_format(file_format)
    if file_format not in SUPPORTED_FILE_FORMATS:
        print("Microphone format must be wav, mp3, or flac.")
        return False

    settings["file_format"] = file_format
    save_settings(settings)
    print(f"Microphone format set to {file_format.upper()}.")
    if file_format == "mp3":
        print("MP3 export requires ffmpeg. A full-quality WAV is still recorded first.")

    return True


# Prints microphone settings to terminal, used by Main.py --> --info 
def print_recording_info(settings, sample_rate, channels, file_format, default_duration):
    device_index = settings["device_index"]
    duration_seconds = default_duration
    file_format = get_recording_format(settings, file_format).upper()

    device_label = "Auto-select"

    if device_index is not None:
        device = get_input_mic(device_index)
        if device is None:
            device_label = f"{device_index} (not currently available)"
        else:
            device_label = f"{device_index} ({device['name']})"

    print(
        f"Device Index: {device_label} \n"
        f"Duration: {duration_seconds} s \n"
        f"Sampling Freq: {sample_rate} Hz \n"
        f"Channels: {channels} \n"
        f"Format: {file_format} \n"
        f"Location: {RECORDINGS_DIR}"
    )


# Writes raw int16 audio data to a WAV file. used by record_from_settings() before final export to MP3/FLAC
def write_wav(path, audio, sample_rate, channels):
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.asarray(audio, dtype=np.int16)

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(RESOLUTION // 8)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())


# Converts a WAV file to FLAC with ffmpeg
def convert_wav_to_flac(wav_path, flac_path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ffmpeg was not found, so FLAC export was skipped.")
        print(f"Full-quality WAV saved at: {wav_path}")
        return False

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-codec:a",
        "flac",
        str(flac_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return True


# Converts a WAV file to MP3 with ffmpeg
def convert_wav_to_mp3(wav_path, mp3_path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ffmpeg was not found, so MP3 export was skipped.")
        print(f"Full-quality WAV saved at: {wav_path}")
        return False

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-ar",
        "48000",
        "-ac",
        "1",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(mp3_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return True


# Keeps and reports the WAV recording
def save_wav_recording(wav_path):
    print(f"Saved WAV: {wav_path}")
    return wav_path


# Exports MP3 from the WAV recording
def save_mp3_recording(wav_path, mp3_path):
    mp3_created = convert_wav_to_mp3(wav_path, mp3_path)
    if not mp3_created:
        return wav_path

    print(f"Saved MP3 preview: {mp3_path}")
    print("Note: MP3 is downsampled to 48 kHz and will not preserve ultrasonic content.")
    return mp3_path


# Exports FLAC from the WAV recording 
def save_flac_recording(wav_path, flac_path):
    flac_created = convert_wav_to_flac(wav_path, flac_path)
    if not flac_created:
        return wav_path

    print(f"Saved FLAC: {flac_path}")
    wav_path.unlink(missing_ok=True)
    return flac_path


# Dispatches the WAV recording to WAV, MP3, or FLAC output depending on user settings
def save_recording_by_format(wav_path, recording_format):
    recording_format = normalize_file_format(recording_format)

    if recording_format == FORMAT_WAV:
        return save_wav_recording(wav_path)

    if recording_format == FORMAT_MP3:
        return save_mp3_recording(wav_path, wav_path.with_suffix(".mp3"))

    if recording_format == FORMAT_FLAC:
        return save_flac_recording(wav_path, wav_path.with_suffix(".flac"))

    raise ValueError(f"Unsupported microphone file format: {recording_format}")


# Records audio chunks from the selected input device
def record_audio(device_index, duration_seconds, sample_rate, channels, stop_event=None):
    print(f"Recording {duration_seconds} seconds from device index {device_index}...")
    extra_settings = get_input_extra_settings(device_index)
    total_frames = int(duration_seconds * sample_rate)
    chunk_frames = max(1, int(sample_rate * 0.1))
    audio_chunks = []
    overflowed = False

    with sd.InputStream(
        device=device_index,
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
        extra_settings=extra_settings,
    ) as stream:
        frames_read = 0

        while frames_read < total_frames:
            if stop_event is not None and stop_event.is_set():
                break

            frames_to_read = min(chunk_frames, total_frames - frames_read)
            audio, chunk_overflowed = stream.read(frames_to_read)
            audio_chunks.append(audio)
            frames_read += len(audio)
            overflowed = overflowed or chunk_overflowed

    if overflowed:
        print("Warning: audio input buffer overflowed during recording.")

    if not audio_chunks:
        return np.empty((0, channels), dtype=np.int16)

    return np.concatenate(audio_chunks, axis=0)


# Tests whether the configured microphone can open at the requested rate/channels, helper before running main.py
def can_record_from_settings(
    settings,
    sample_rate,
    channels,
    keyword=DEFAULT_KEYWORD,
    device_override=None,
):
    device_index = resolve_recording_device(settings, keyword, device_override)
    if device_index is None:
        print(f"No input microphone found containing '{keyword}'.")
        print()
        list_input_mics(keyword)
        return False

    try:
        extra_settings = get_input_extra_settings(device_index)
        with sd.InputStream(
            device=device_index,
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            extra_settings=extra_settings,
        ):
            pass
    except sd.PortAudioError as exc:
        print(f"Microphone cannot record at {sample_rate} Hz: {exc}")
        print()
        print("Run this to find the correct high-frequency microphone endpoint:")
        print('  python .\\Main.py --list-devices --filter "Pettersson"')
        print()
        print("Then set the System Index for the 384000 Hz endpoint:")
        print("  python .\\Main.py --mic --set-device <system-index>")
        return False

    return True


# Chooses the recording device from explicit override, saved JSON
def resolve_recording_device(settings, keyword, device_override=None):
    device_index = device_override if device_override is not None else settings["device_index"]
    if device_index is None:
        device_index = find_input_mic(keyword)

    return device_index


# Records audio using saved settings and exports the requested format
def record_from_settings(settings, sample_rate, channels, duration_seconds, file_format, keyword, device_override, mp3, stop_event):
    device_index = resolve_recording_device(settings, keyword, device_override)
    if device_index is None:
        print(f"No input microphone found containing '{keyword}'.")
        print()
        list_input_mics(keyword)
        return None

    recording_stem = get_recording_stem()
    wav_path = RECORDINGS_DIR / f"{recording_stem}.wav"
    recording_format = get_recording_format(settings, file_format)
    if mp3:
        recording_format = FORMAT_MP3

    try:
        audio = record_audio(device_index, duration_seconds, sample_rate, channels, stop_event)
    except sd.PortAudioError as exc:
        print(f"Could not record at {sample_rate} Hz: {exc}")
        print()
        print("Change the microphone sample rate macro in Main.py to a rate supported by the selected microphone.")
        return None

    write_wav(wav_path, audio, sample_rate, channels)
    try:
        return save_recording_by_format(wav_path, recording_format)
    except subprocess.CalledProcessError as exc:
        print(f"{recording_format.upper()} export failed: {exc}")
        if exc.stderr:
            print(exc.stderr)
        return wav_path


# Registers microphone-related CLI arguments, used in main.py for parsing settings before execution
def add_microphone_arguments(parser):
    parser.add_argument("--mic", action="store_true", help="Configure or target microphone settings.")
    parser.add_argument("--list-devices", action="store_true", help="Show input microphone devices and exit.")
    parser.add_argument("--filter", help="Only list microphones whose names contain this keyword.")
    parser.add_argument("--set-device", type=int, help="Save the system input device index used for recording.")
    parser.add_argument("--set-format", choices=["wav", "mp3", "flac"], help="Save microphone output format.")
    parser.add_argument("--info", action="store_true", help="Show the current recording settings and exit.")
    parser.add_argument("--record-mic", action="store_true", help="Record microphone audio using saved settings.")
    parser.add_argument("--device", type=int, help="System input device index. Overrides keyword search.")
    parser.add_argument("--keyword", default=DEFAULT_KEYWORD, help="Device name keyword to auto-select for recording.")
    parser.add_argument("--duration", type=float, help="One-time recording length in seconds.")
    parser.add_argument("--mp3", action="store_true", help="Also export an MP3 preview using ffmpeg.")


# Handles microphone actions without starting unrelated peripherals
def handle_microphone_args(args, sample_rate, channels, file_format, duration_seconds, record_when_no_command=False):
    settings = load_settings()

    if args.list_devices:
        list_input_mics(args.filter)
        return True

    settings_changed = False
    if args.set_device is not None:
        settings_changed = set_recording_device(settings, args.set_device) or settings_changed

    if args.set_format is not None:
        settings_changed = set_recording_format(settings, args.set_format) or settings_changed

    if args.info:
        print_recording_info(settings, sample_rate, channels, file_format, duration_seconds)
        return True

    if settings_changed:
        print_recording_info(settings, sample_rate, channels, file_format, duration_seconds)
        return True

    should_record = (
        args.record_mic
        or record_when_no_command
        or args.device is not None
        or args.duration is not None
        or args.mp3
    )

    if should_record:
        record_from_settings(
            settings,
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=args.duration if args.duration is not None else duration_seconds,
            file_format=file_format,
            keyword=args.keyword,
            device_override=args.device,
            mp3=args.mp3,
            stop_event=None,
        )
        return True

    return False


# Main Microphone function
def main():
    parser = argparse.ArgumentParser(description="Record audio from the Pettersson M500.")
    add_microphone_arguments(parser)
    args = parser.parse_args()
    handle_microphone_args(
        args,
        sample_rate=44100,
        channels=1,
        file_format=DEFAULT_FILE_FORMAT,
        duration_seconds=5.0,
        record_when_no_command=True,
    )


if __name__ == "__main__":
    main()
