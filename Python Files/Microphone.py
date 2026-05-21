import argparse
import shutil
import subprocess
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd


DEVICE_KEYWORD = "Pettersson"
SAMPLE_RATE = 384000
#COMMON_SAMPLE_RATES = [384000, 250000, 192000, 176400, 96000, 48000, 44100]
CHANNELS = 1
RESOLUTION = 16
RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"


def list_input_devices():
    print("Available input devices:")
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            default_rate = int(device["default_samplerate"])
            print(f"  {index}: {device['name']} ({default_rate} Hz default)")


def find_input_device(keyword):
    keyword = keyword.lower()
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0 and keyword in device["name"].lower():
            return index
    return None


def list_supported_sample_rates(device_index):
    print(f"Testing common sample rates for input device {device_index}:")
    supported_rates = []

    for sample_rate in COMMON_SAMPLE_RATES:
        try:
            sd.check_input_settings(
                device=device_index,
                channels=CHANNELS,
                dtype="int16",
                samplerate=sample_rate,
            )
        except sd.PortAudioError:
            print(f"  {sample_rate}: not supported")
        else:
            supported_rates.append(sample_rate)
            print(f"  {sample_rate}: supported")

    return supported_rates


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
    parser.add_argument("--list-devices", action="store_true", help="Show input devices and exit.")
    parser.add_argument("--device", type=int, help="Input device index. Overrides keyword search.")
    parser.add_argument("--keyword", default=DEVICE_KEYWORD, help="Device name keyword to search for.")
    parser.add_argument("--duration", type=float, default=5.0, help="Recording length in seconds.")
    parser.add_argument("--sample-rate", type=int, default=SAMPLE_RATE, help="Recording sample rate.")
    parser.add_argument("--list-rates", action="store_true", help="Test common sample rates for the selected device.")
    parser.add_argument("--mp3", action="store_true", help="Also export an MP3 preview using ffmpeg.")
    args = parser.parse_args()

    if args.list_devices:
        list_input_devices()
        return

    device_index = args.device
    if device_index is None:
        device_index = find_input_device(args.keyword)

    if device_index is None:
        print(f"No input device found containing '{args.keyword}'.")
        print()
        list_input_devices()
        return

    if args.list_rates:
        list_supported_sample_rates(device_index)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = RECORDINGS_DIR / f"m500_{timestamp}_{args.sample_rate}hz.wav"
    mp3_path = RECORDINGS_DIR / f"m500_{timestamp}_preview.mp3"

    try:
        audio = record_audio(device_index, args.duration, args.sample_rate)
    except sd.PortAudioError as exc:
        print(f"Could not record at {args.sample_rate} Hz: {exc}")
        print()
        list_supported_sample_rates(device_index)
        print()
        print("Try again with one of the supported rates, for example:")
        print(f"  python .\\Microphone.py --device {device_index} --sample-rate 384000 --duration {args.duration}")
        return

    write_wav(wav_path, audio, args.sample_rate)
    print(f"Saved WAV: {wav_path}")

    if args.mp3:
        if convert_wav_to_mp3(wav_path, mp3_path):
            print(f"Saved MP3 preview: {mp3_path}")
            print("Note: MP3 is downsampled to 48 kHz and will not preserve ultrasonic content.")


if __name__ == "__main__":
    main()
