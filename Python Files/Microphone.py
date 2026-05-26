import argparse
import json
import shutil
import subprocess
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd


"""
How to use this file:

1. Install the required Python packages:
   python -m pip install sounddevice numpy

2. From the project root, list available input microphones:
   python ".\\Python Files\\Microphone.py" --list-devices

   To list only microphones whose names match a keyword:
   python ".\\Python Files\\Microphone.py" --list-devices --filter "Pettersson"

   Or from inside the Python Files folder:
   python .\\Microphone.py --list-devices

3. Find the microphone device index in the printed list.
   Use the printed "system device" number when passing --device.
   Example: if the Pettersson M500 line says "system device 18", use --device 18.

4. Record a WAV file:
   python .\\Microphone.py --device 18 --duration 5

5. Save default recording settings:
   python .\\Microphone.py --set-device 18
   python .\\Microphone.py --set-time 100

6. Show current recording settings:
   python .\\Microphone.py --info

7. To change the recording sample rate, edit the SAMPLE_RATE value near the
   top of this file, then run the recording command again.

Recordings are saved into:
   Python Files\\recordings

Note: WAV is the main research recording format. MP3 export is only a preview
format and does not preserve ultrasonic content properly.


NOTE: in --list-devices, use the input Microphone with the highest sampling frequency. 
For instance, the Pettersson M500 has two default drivers listed
1. Sampling Freq: 384000 Hz - for proper ultrasonic recording mode
2. Sampling Freq: 48000 Hz - basic audio recording

I've listed it such that the devices with the highest sampling freq's are at the top.
The input microphone for this project is the Pettersson M500 however if you choose to use another microphone, it should still be detected here 
"""


DEVICE_KEYWORD = "Pettersson"
SAMPLE_RATE = 384000
CHANNELS = 1
RESOLUTION = 16
RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"
SETTINGS_PATH = Path(__file__).resolve().parent / "microphone_settings.json"
DEFAULT_RECORDING_DURATION = 5.0
FILE_FORMAT = "WAV"


def default_settings():
    return {
        "device_index": None,
        "duration_seconds": DEFAULT_RECORDING_DURATION,
    }


def load_settings():
    if not SETTINGS_PATH.exists():
        return default_settings()

    with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    defaults = default_settings()
    defaults.update(settings)
    return defaults


def save_settings(settings):
    with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


def is_input_mic(device):
    return device["max_input_channels"] > 0


def mic_matches_keyword(device, keyword):
    return keyword.lower() in device["name"].lower()


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
        print(
            f"  No.: {display_index} | "
            f"System Index: {system_index} | "
            f"Sampling Freq: {default_rate} Hz | "
            f"Name: {device['name']}"
        )


def find_input_mic(keyword):
    matching_mics = []

    for index, device in enumerate(sd.query_devices()):
        if is_input_mic(device) and mic_matches_keyword(device, keyword):
            matching_mics.append((index, device))

    if not matching_mics:
        return None

    best_index, _ = max(matching_mics, key=lambda item: item[1]["default_samplerate"])
    return best_index


def get_input_mic(device_index):
    devices = sd.query_devices()

    if device_index < 0 or device_index >= len(devices):
        return None

    device = devices[device_index]
    if not is_input_mic(device):
        return None

    return device


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


def set_recording_duration(settings, duration_seconds):
    if duration_seconds <= 0:
        print("Recording duration must be greater than 0 seconds.")
        return False

    settings["duration_seconds"] = duration_seconds
    save_settings(settings)
    print(f"Recording duration set to {duration_seconds} seconds.")
    return True


def print_recording_info(settings):
    device_index = settings["device_index"]
    duration_seconds = settings["duration_seconds"]
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
        f"Sampling Freq: {SAMPLE_RATE} Hz \n"
        f"Format: {FILE_FORMAT} \n"
        f"Location: {RECORDINGS_DIR}"
    )


def write_wav(path, audio, sample_rate):
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.asarray(audio, dtype=np.int16)

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(RESOLUTION // 8)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())


def convert_wav_to_mp3(wav_path, mp3_path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ffmpeg was not found, so MP3 export was skipped.")
        print(f"Full-quality WAV saved at: {wav_path}")
        return False

    command = [
        ffmpeg,
        "-y",
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
    subprocess.run(command, check=True)
    return True

def record_audio(device_index, duration_seconds, sample_rate):
    print(f"Recording {duration_seconds} seconds from device index {device_index}...")
    audio = sd.rec(
        int(duration_seconds * sample_rate),
        samplerate=sample_rate,
        channels=CHANNELS,
        dtype="int16",
        device=device_index,
    )
    sd.wait()
    return audio

def main():
    parser = argparse.ArgumentParser(description="Record audio from the Pettersson M500.")
    parser.add_argument("--list-devices", action="store_true", help="Show input microphone devices and exit.")
    parser.add_argument("--filter", help="Only list microphones whose names contain this keyword.")
    parser.add_argument("--set-device", type=int, help="Save the system input device index used for recording.")
    parser.add_argument("--set-time", type=float, help="Save the recording duration in seconds.")
    parser.add_argument("--info", action="store_true", help="Show the current recording settings and exit.")
    parser.add_argument("--device", type=int, help="System input device index. Overrides keyword search.")
    parser.add_argument("--keyword", default=DEVICE_KEYWORD, help="Device name keyword to auto-select for recording.")
    parser.add_argument("--duration", type=float, help="One-time recording length in seconds.")
    parser.add_argument("--mp3", action="store_true", help="Also export an MP3 preview using ffmpeg.")
    args = parser.parse_args()
    settings = load_settings()

    if args.list_devices:
        list_input_mics(args.filter)
        return

    settings_changed = False
    if args.set_device is not None:
        settings_changed = set_recording_device(settings, args.set_device) or settings_changed

    if args.set_time is not None:
        settings_changed = set_recording_duration(settings, args.set_time) or settings_changed

    if args.info:
        print_recording_info(settings)
        return

    if settings_changed:
        print_recording_info(settings)
        return

    device_index = args.device if args.device is not None else settings["device_index"]
    if device_index is None:
        device_index = find_input_mic(args.keyword)

    if device_index is None:
        print(f"No input microphone found containing '{args.keyword}'.")
        print()
        list_input_mics(args.keyword)
        return

    duration_seconds = args.duration if args.duration is not None else settings["duration_seconds"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = RECORDINGS_DIR / f"m500_{timestamp}_{SAMPLE_RATE}hz.wav"
    mp3_path = RECORDINGS_DIR / f"m500_{timestamp}_preview.mp3"

    try:
        audio = record_audio(device_index, duration_seconds, SAMPLE_RATE)
    except sd.PortAudioError as exc:
        print(f"Could not record at {SAMPLE_RATE} Hz: {exc}")
        print()
        print("Change SAMPLE_RATE near the top of this file to a rate supported by the selected microphone.")
        return

    write_wav(wav_path, audio, SAMPLE_RATE)
    print(f"Saved WAV: {wav_path}")

    if args.mp3:
        if convert_wav_to_mp3(wav_path, mp3_path):
            print(f"Saved MP3 preview: {mp3_path}")
            print("Note: MP3 is downsampled to 48 kHz and will not preserve ultrasonic content.")


if __name__ == "__main__":
    main()
