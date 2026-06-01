#######################################################################################################################
# File: Main Controller
# Project: Time Locked Box Simulator
# Research Group: Suarez Lab, Queensland Brain Institute, UQ
#
# Author: Tevyn Vergara
# Date: 01/06/2026

############################################## Standard Library Imports #################################################

import argparse
import json
import multiprocessing
import msvcrt
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

################################################ Local Module Imports ###################################################
import Camera
import Microphone
import Motor
import Speaker

####################################### Peripheral Settings: CHANGE THESE AS NEEDED #########################################

# Recording paths (Change for where you want to autosave the recordings)
CUSTOM_RECORDINGS_DIR = None    # Example: r"C:\Users\YourName\Documents\VibrationBoxRecordings". Use None for repo-local recordings.
RECORDINGS_DIR = Path(CUSTOM_RECORDINGS_DIR) if CUSTOM_RECORDINGS_DIR else Path(__file__).resolve().parent / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


# Recording Macros
DEFAULT_RECORD_TIME = 20.0      # (s), Recording duration
DEFAULT_MERGE_AV = True         # True exports a merged MP4 when mic and camera are enabled.
KILL_BUTTON = "k"               # Press this key to stop all peripherals during recording.


# Speaker Macros
SPEAKER_FREQ = 300              # (Hz), Beep Freq
SPEAKER_TIME = 1.0              # (s), Speaker ON time
SPEAKER_INTERVAL = 2.0          # (s), Speaker OFF time
SPEAKER_SAMPLE_RATE = 44100     # (Hz), Sample rate for audio generation
SPEAKER_AMPLITUDE = 1           # Amplitude of the sinusodial beep sound. Adjust knob on speaker for real-world volume 


# Camera Macros
CAMERA_IP = "169.254.1.222"     # Set after --list-cameras. Example: "169.254.1.222". Use None for auto-discover.
CAMERA_VIEW = "right"          # Camera view options: "center", "left", "right", "stereo".
CAMERA_WIDTH = 1280             # (pixels), Width of the camera image
CAMERA_HEIGHT = 720             # (pixels), Height of the camera image
CAMERA_FPS = 30                 # (fp/s), Frames per second for the camera
CAMERA_FILE_FORMAT = "H265"     # File format for the recorded video


# Microphone Macros
MIC_DEVICE = 19                 # Set after --list-devices. Example: 15. Use None for auto-select.
MIC_SAMPLE_RATE = 384000        # (Hz), Sample rate in Hz.
MIC_CHANNELS = 1                # (int), Mono recording. Set to 2 for stereo if microphone supports it.
MIC_FORMAT = "WAV"             # File format for the recorded audio. Common options: "WAV", "FLAC", "MP3"


# Motor Macros
MOTOR_SERIAL_PORT = "COM6"      # Serial port for motor driver. Change in "DEVICE MANAGER"
MOTOR_BAUD_RATE = 9600          # Baud rate for motor driver communication. DO NOT TOUCH
MOTOR_STRENGTH = 150            # Raw PWM strength, 30-250.
MOTOR_ON_TIME = 200             # (ms), Motor ON time
MOTOR_OFF_TIME = 300            # (ms), Motor OFF time

############################################# Helper Functions ####################################################
Camera.RECORDINGS_DIR = RECORDINGS_DIR
Microphone.RECORDINGS_DIR = RECORDINGS_DIR

PERIPHERAL_SETTINGS_PATH = Path(__file__).resolve().parent / "peripheral_settings.json"
MOTOR_SETTINGS_PATH = Path(__file__).resolve().parent / "motor_settings.json"


def default_peripheral_settings():
    return {
        "motor_enabled": True,
        "mic_enabled": True,
        "camera_enabled": False,
        "speaker_enabled": False,
        "record_time": DEFAULT_RECORD_TIME,
        "merge_av_enabled": DEFAULT_MERGE_AV,
    }


def load_peripheral_settings():
    if not PERIPHERAL_SETTINGS_PATH.exists():
        return default_peripheral_settings()

    with PERIPHERAL_SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    defaults = default_peripheral_settings()
    defaults.update(settings)
    return defaults


def save_peripheral_settings(settings):
    with PERIPHERAL_SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


def default_motor_settings():
    return {
        "serial_port": MOTOR_SERIAL_PORT,
        "baud_rate": MOTOR_BAUD_RATE,
        "strength": MOTOR_STRENGTH,
        "on_time": MOTOR_ON_TIME,
        "off_time": MOTOR_OFF_TIME,
    }


def load_motor_settings():
    if not MOTOR_SETTINGS_PATH.exists():
        return default_motor_settings()

    with MOTOR_SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    defaults = default_motor_settings()
    defaults.update(settings)
    return defaults


def save_motor_settings(settings):
    with MOTOR_SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


def set_motor_setting(settings, key, value):
    settings[key] = value
    save_motor_settings(settings)
    return True


def save_live_motor_settings(strength, on_time, off_time):
    settings = load_motor_settings()
    settings["strength"] = strength
    settings["on_time"] = on_time
    settings["off_time"] = off_time
    save_motor_settings(settings)


def save_default_microphone_settings():
    settings = Microphone.default_settings()
    settings["device_index"] = MIC_DEVICE
    settings["file_format"] = MIC_FORMAT.lower()
    Microphone.save_settings(settings)
    return settings


def save_default_camera_settings():
    if CAMERA_VIEW not in ("center", "left", "right", "stereo"):
        raise ValueError('CAMERA_VIEW must be "center", "left", "right", or "stereo".')

    settings = Camera.default_settings()
    settings["device_ip"] = CAMERA_IP
    settings["view"] = CAMERA_VIEW
    Camera.save_settings(settings)
    return settings


def save_default_project_settings(enable_all=False):
    peripheral_settings = default_peripheral_settings()
    if enable_all:
        peripheral_settings["motor_enabled"] = True
        peripheral_settings["mic_enabled"] = True
        peripheral_settings["camera_enabled"] = True
        peripheral_settings["speaker_enabled"] = True

    save_peripheral_settings(peripheral_settings)
    save_motor_settings(default_motor_settings())
    save_default_microphone_settings()
    save_default_camera_settings()
    return peripheral_settings


def on_off_label(enabled):
    return "On" if enabled else "Off"


def merge_label(enabled):
    return "MP4" if enabled else "Off"


def print_section_header(title):
    separator = "=" * 77
    print(separator)
    print(title)
    print(separator)


def print_section_footer():
    print("=" * 77)


def get_record_time(settings=None):
    if settings is None:
        settings = load_peripheral_settings()

    return settings["record_time"] or DEFAULT_RECORD_TIME


def print_microphone_settings(record_time):
    mic_settings = Microphone.load_settings()
    Microphone.print_recording_info(
        mic_settings,
        sample_rate=MIC_SAMPLE_RATE,
        channels=MIC_CHANNELS,
        file_format=Microphone.get_recording_format(mic_settings, MIC_FORMAT),
        default_duration=record_time,
    )


def print_motor_settings():
    motor_settings = load_motor_settings()
    print(
        f"Serial Port: {motor_settings['serial_port']} \n"
        f"Baud Rate: {motor_settings['baud_rate']} \n"
        f"Strength: {motor_settings['strength']} \n"
        f"On-Time: {motor_settings['on_time']} ms \n"
        f"Off-Time: {motor_settings['off_time']} ms"
    )


def print_camera_settings(record_time):
    Camera.print_camera_info(
        Camera.load_settings(),
        width=CAMERA_WIDTH,
        height=CAMERA_HEIGHT,
        fps=CAMERA_FPS,
        default_duration=record_time,
        file_format=CAMERA_FILE_FORMAT,
    )


def print_speaker_settings():
    print(
        f"Frequency: {SPEAKER_FREQ} Hz \n"
        f"Beep Duration: {SPEAKER_TIME} s \n"
        f"Interval: {SPEAKER_INTERVAL} s \n"
        f"Sample Rate: {SPEAKER_SAMPLE_RATE} Hz \n"
        f"Amplitude: {SPEAKER_AMPLITUDE}"
    )


def print_enabled_peripheral_settings(settings):
    record_time = get_record_time(settings)
    printed_section = False

    if settings["motor_enabled"]:
        print_section_header("Settings: MOTOR")
        print_motor_settings()
        printed_section = True

    if printed_section and settings["mic_enabled"]:
        print()

    if settings["mic_enabled"]:
        print_section_header("Settings: MICROPHONE")
        print_microphone_settings(record_time)
        printed_section = True

    if printed_section and settings["camera_enabled"]:
        print()

    if settings["camera_enabled"]:
        print_section_header("Settings: CAMERA")
        print_camera_settings(record_time)
        printed_section = True

    if printed_section and settings["speaker_enabled"]:
        print()

    if settings["speaker_enabled"]:
        print_section_header("Settings: SPEAKER")
        print_speaker_settings()
        printed_section = True

    if (
        not settings["motor_enabled"]
        and not settings["mic_enabled"]
        and not settings["camera_enabled"]
        and not settings["speaker_enabled"]
    ):
        print("No peripherals are enabled.")
    elif printed_section:
        print_section_footer()


def print_selected_peripheral_settings(show_motor, show_mic, show_camera, record_time):
    printed_section = False

    if show_motor:
        print_section_header("Settings: MOTOR")
        print_motor_settings()
        printed_section = True

    if printed_section and (show_mic or show_camera):
        print()

    if show_mic:
        print_section_header("Settings: MICROPHONE")
        print_microphone_settings(record_time)
        printed_section = True

    if printed_section and show_camera:
        print()

    if show_camera:
        print_section_header("Settings: CAMERA")
        print_camera_settings(record_time)
        printed_section = True

    if printed_section:
        print_section_footer()


def print_system_info(settings):
    print_section_footer()
    print("PERIPHERAL SETTINGS")
    print_section_footer()
    print(f"Motor: {on_off_label(settings['motor_enabled'])}")
    print(f"Mic: {on_off_label(settings['mic_enabled'])}")
    print(f"Camera: {on_off_label(settings['camera_enabled'])}")
    print(f"Speaker: {on_off_label(settings['speaker_enabled'])}")
    print(f"Record Time: {get_record_time(settings)} s")
    print(f"Merge Audio/Video: {merge_label(settings['merge_av_enabled'])}")
    print()
    print_enabled_peripheral_settings(settings)


def record_microphone(record_time, stop_event=None):
    mic_settings = Microphone.load_settings()
    return Microphone.record_from_settings(
        mic_settings,
        sample_rate=MIC_SAMPLE_RATE,
        channels=MIC_CHANNELS,
        duration_seconds=record_time,
        file_format=Microphone.get_recording_format(mic_settings, MIC_FORMAT),
        keyword=Microphone.DEFAULT_KEYWORD,
        device_override=None,
        mp3=False,
        stop_event=stop_event,
    )


def run_camera(record_time, stop_event=None):
    camera_settings = Camera.load_settings()
    try:
        return Camera.run_camera(
            width=CAMERA_WIDTH,
            height=CAMERA_HEIGHT,
            fps=CAMERA_FPS,
            duration_seconds=record_time,
            file_format=CAMERA_FILE_FORMAT,
            device_ip=camera_settings["device_ip"],
            record_video=camera_settings["record_video"],
            view=camera_settings["view"],
            window_name="OAK-D Camera",
            stop_event=stop_event,
        )
    except Exception as exc:
        print(f"Camera stopped with an error: {exc}")
        return None


def run_camera_process(record_time, stop_event, result_queue):
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)

    video_path = run_camera(record_time, stop_event)
    result_queue.put(str(video_path) if video_path is not None else "")


def get_camera_process_result(result_queue):
    video_path = None

    while result_queue is not None and not result_queue.empty():
        candidate = result_queue.get_nowait()
        if candidate:
            video_path = Path(candidate)

    return video_path


def run_speaker(record_time, stop_event=None):
    try:
        Speaker.run_speaker(
            duration_seconds=record_time,
            stop_event=stop_event,
            frequency_hz=SPEAKER_FREQ,
            beep_duration_seconds=SPEAKER_TIME,
            interval_seconds=SPEAKER_INTERVAL,
            sample_rate=SPEAKER_SAMPLE_RATE,
            amplitude=SPEAKER_AMPLITUDE,
        )
    except Exception as exc:
        print(f"Speaker stopped with an error: {exc}")


def get_recording_stem():
    return datetime.now().strftime("Recording_%H%M%S_%d_%m")


def merge_audio_video(video_path, audio_path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ffmpeg was not found, so audio/video merge was skipped.")
        return None

    if video_path is None or audio_path is None:
        print("Audio/video merge skipped because the video or audio file was not created.")
        return None

    output_path = RECORDINGS_DIR / f"{get_recording_stem()}.mp4"
    video_input_args = []
    if Path(video_path).suffix.lower() == ".h265":
        video_input_args = ["-f", "hevc", "-framerate", str(CAMERA_FPS)]

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *video_input_args,
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx265",
        "-x265-params",
        "log-level=error",
        "-tag:v",
        "hvc1",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "1",
        "-shortest",
        str(output_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        print(f"Audio/video merge failed: {exc}")
        if exc.stderr:
            print(exc.stderr)
        return None

    print(f"Saved merged audio/video MP4: {output_path}")
    print("Note: merged MP4 audio is downsampled to 48 kHz. The standalone audio recording keeps the original microphone data.")
    return output_path


def recover_camera_recording(start_time):
    candidates = []
    for pattern in ("Recording_*.h265", "Recording_*_capture.avi", "Recording_*.avi", "Recording_*.mp4"):
        candidates.extend(RECORDINGS_DIR.glob(pattern))

    candidates = [
        path for path in candidates
        if path.is_file() and path.stat().st_mtime >= start_time
    ]

    if not candidates:
        return None

    latest_path = max(candidates, key=lambda path: path.stat().st_mtime)
    if latest_path.suffix.lower() != ".avi" or not latest_path.stem.endswith("_capture"):
        return latest_path

    output_path = latest_path.with_name(f"{latest_path.stem.removesuffix('_capture')}.h265")
    try:
        recovered_path = Camera.convert_video_to_h265(latest_path, output_path)
        print(f"Recovered camera video from capture file: {recovered_path}")
        return recovered_path
    except subprocess.CalledProcessError as exc:
        print(f"Camera recovery H.265 export failed: {exc}")
        if exc.stderr:
            print(exc.stderr)
        return latest_path


def watch_for_global_kill(stop_event, done_event, kill_button):
    while not stop_event.is_set() and not done_event.is_set():
        if msvcrt.kbhit():
            char = msvcrt.getwch()
            if char.lower() == kill_button.lower():
                stop_event.set()
                print()
                print("Kill requested. Stopping all peripherals and processing clipped recordings.")
                return


def run_enabled_peripherals(peripheral_settings):
    motor_enabled = peripheral_settings["motor_enabled"]
    mic_enabled = peripheral_settings["mic_enabled"]
    camera_enabled = peripheral_settings["camera_enabled"]
    speaker_enabled = peripheral_settings["speaker_enabled"]
    merge_enabled = peripheral_settings["merge_av_enabled"]
    record_time = get_record_time(peripheral_settings)

    if not motor_enabled and not mic_enabled and not camera_enabled and not speaker_enabled:
        print("No peripherals are enabled. Use --set-motor on, --set-mic on, --set-camera on, or --set-speaker on.")
        return

    if mic_enabled:
        mic_ready = Microphone.can_record_from_settings(
            Microphone.load_settings(),
            sample_rate=MIC_SAMPLE_RATE,
            channels=MIC_CHANNELS,
        )
        if not mic_ready:
            return

    worker_threads = []
    camera_process = None
    camera_result_queue = None
    stop_event = multiprocessing.Event()
    done_event = threading.Event()
    run_started_at = time.time()
    recording_paths = {
        "audio": None,
        "video": None,
    }

    if not motor_enabled:
        kill_thread = threading.Thread(
            target=watch_for_global_kill,
            args=(stop_event, done_event, KILL_BUTTON),
            daemon=True,
        )
        kill_thread.start()

    if motor_enabled:
        motor_settings = load_motor_settings()
        motor_thread = threading.Thread(
            target=Motor.run_motor_driver,
            kwargs={
                "serial_port": motor_settings["serial_port"],
                "baud_rate": motor_settings["baud_rate"],
                "strength": motor_settings["strength"],
                "on_time": motor_settings["on_time"],
                "off_time": motor_settings["off_time"],
                "duration_seconds": record_time,
                "stop_event": stop_event,
                "kill_button": KILL_BUTTON,
                "settings_callback": save_live_motor_settings,
            },
        )
        motor_thread.start()
        worker_threads.append(motor_thread)

    if camera_enabled:
        camera_result_queue = multiprocessing.Queue()
        camera_process = multiprocessing.Process(
            target=run_camera_process,
            args=(record_time, stop_event, camera_result_queue),
        )
        camera_process.start()

    if speaker_enabled:
        speaker_thread = threading.Thread(target=run_speaker, args=(record_time, stop_event))
        speaker_thread.start()
        worker_threads.append(speaker_thread)

    if mic_enabled:
        recording_paths["audio"] = record_microphone(record_time, stop_event)
        for worker_thread in worker_threads:
            worker_thread.join()
        if camera_process is not None:
            camera_process.join()
            recording_paths["video"] = get_camera_process_result(camera_result_queue)
        done_event.set()

        if camera_enabled and recording_paths["video"] is None:
            recording_paths["video"] = recover_camera_recording(run_started_at)

        if merge_enabled and camera_enabled:
            merge_audio_video(recording_paths["video"], recording_paths["audio"])

        return

    for worker_thread in worker_threads:
        worker_thread.join()
    if camera_process is not None:
        camera_process.join()
        recording_paths["video"] = get_camera_process_result(camera_result_queue)
    done_event.set()

    if camera_enabled and recording_paths["video"] is None:
        recording_paths["video"] = recover_camera_recording(run_started_at)

###################################################### Main Function ###########################################################
def main():
    parser = argparse.ArgumentParser(description="Control motor, microphone, and camera peripherals.")
    Motor.add_motor_arguments(parser)
    Microphone.add_microphone_arguments(parser)
    Camera.add_camera_arguments(parser)
    parser.add_argument("--set-motor", choices=["on", "off"], help="Enable or disable the motor driver.")
    parser.add_argument("--set-mic", choices=["on", "off"], help="Enable or disable the microphone.")
    parser.add_argument("--set-camera", choices=["on", "off"], help="Enable or disable the camera.")
    parser.add_argument("--set-speaker", choices=["on", "off"], help="Enable or disable the speaker beep.")
    parser.add_argument("--set-all", choices=["on", "off"], help="Enable or disable motor, microphone, camera, and speaker.")
    parser.add_argument("--set-time", type=float, help="Save shared microphone/camera recording time in seconds.")
    parser.add_argument("--set-merge", choices=["on", "off"], help="Enable or disable merged camera/audio MP4 export.")
    args = parser.parse_args()
    peripheral_settings = load_peripheral_settings()
    motor_settings = load_motor_settings()

    if args.list_devices:
        Microphone.handle_microphone_args(
            args,
            sample_rate = MIC_SAMPLE_RATE,
            channels = MIC_CHANNELS,
            file_format = MIC_FORMAT,
            duration_seconds = get_record_time(peripheral_settings),
        )
        return

    if args.list_cameras:
        Camera.handle_camera_args(
            args,
            width=CAMERA_WIDTH,
            height=CAMERA_HEIGHT,
            fps=CAMERA_FPS,
            default_duration=get_record_time(peripheral_settings),
            file_format=CAMERA_FILE_FORMAT,
        )
        return

    if args.camera and Camera.handle_camera_args(
        args,
        width=CAMERA_WIDTH,
        height=CAMERA_HEIGHT,
        fps=CAMERA_FPS,
        default_duration=get_record_time(peripheral_settings),
        file_format=CAMERA_FILE_FORMAT,
    ):
        return

    peripheral_settings_changed = False
    record_time_changed = False
    if args.set_all is not None:
        enabled = args.set_all == "on"
        if enabled:
            peripheral_settings = save_default_project_settings(enable_all=True)
            motor_settings = load_motor_settings()
        else:
            peripheral_settings["motor_enabled"] = False
            peripheral_settings["mic_enabled"] = False
            peripheral_settings["camera_enabled"] = False
            peripheral_settings["speaker_enabled"] = False
        peripheral_settings_changed = True

    if args.set_motor is not None:
        peripheral_settings["motor_enabled"] = args.set_motor == "on"
        peripheral_settings_changed = True

    if args.set_mic is not None:
        peripheral_settings["mic_enabled"] = args.set_mic == "on"
        peripheral_settings_changed = True

    if args.set_camera is not None:
        peripheral_settings["camera_enabled"] = args.set_camera == "on"
        peripheral_settings_changed = True

    if args.set_speaker is not None:
        peripheral_settings["speaker_enabled"] = args.set_speaker == "on"
        peripheral_settings_changed = True

    if args.set_merge is not None:
        peripheral_settings["merge_av_enabled"] = args.set_merge == "on"
        peripheral_settings_changed = True

    requested_record_time = args.set_time

    if requested_record_time is not None:
        if requested_record_time <= 0:
            print("Record time must be greater than 0 seconds.")
            return

        peripheral_settings["record_time"] = requested_record_time
        peripheral_settings_changed = True
        record_time_changed = True

    motor_selected = args.motor
    mic_selected = args.mic
    camera_selected = args.camera

    motor_settings_changed = False
    motor_port = args.set_port if args.set_port is not None else args.motor_port
    motor_baud = args.set_baud if args.set_baud is not None else args.motor_baud
    motor_strength = args.set_strength if args.set_strength is not None else args.motor_strength
    motor_on_time = args.set_on if args.set_on is not None else args.motor_on_time
    motor_off_time = args.set_off if args.set_off is not None else args.motor_off_time

    if motor_port is not None:
        motor_settings_changed = set_motor_setting(motor_settings, "serial_port", motor_port) or motor_settings_changed

    if motor_baud is not None:
        motor_settings_changed = set_motor_setting(motor_settings, "baud_rate", motor_baud) or motor_settings_changed

    if motor_strength is not None:
        motor_settings_changed = set_motor_setting(
            motor_settings,
            "strength",
            max(30, min(250, motor_strength)),
        ) or motor_settings_changed

    if motor_on_time is not None:
        motor_settings_changed = set_motor_setting(
            motor_settings,
            "on_time",
            max(0, motor_on_time),
        ) or motor_settings_changed

    if motor_off_time is not None:
        motor_settings_changed = set_motor_setting(
            motor_settings,
            "off_time",
            max(0, motor_off_time),
        ) or motor_settings_changed

    microphone_settings_changed = False
    mic_settings = Microphone.load_settings()
    if args.set_device is not None:
        microphone_settings_changed = Microphone.set_recording_device(mic_settings, args.set_device) or microphone_settings_changed

    if args.set_format is not None:
        microphone_settings_changed = Microphone.set_recording_format(mic_settings, args.set_format) or microphone_settings_changed

    camera_settings_changed = False

    if peripheral_settings_changed:
        save_peripheral_settings(peripheral_settings)

    if args.info:
        print_system_info(peripheral_settings)
        return

    if peripheral_settings_changed:
        if record_time_changed:
            print_system_info(peripheral_settings)
        else:
            print_enabled_peripheral_settings(peripheral_settings)
        return

    if motor_settings_changed or microphone_settings_changed or camera_settings_changed:
        print_selected_peripheral_settings(
            show_motor=motor_selected or (motor_settings_changed and not mic_selected),
            show_mic=mic_selected or (microphone_settings_changed and not motor_selected),
            show_camera=camera_selected or (camera_settings_changed and not motor_selected and not mic_selected),
            record_time=get_record_time(peripheral_settings),
        )
        return

    if args.record_mic or args.device is not None or args.duration is not None or args.mp3:
        Microphone.handle_microphone_args(
            args,
            sample_rate = MIC_SAMPLE_RATE,
            channels = MIC_CHANNELS,
            file_format = MIC_FORMAT,
            duration_seconds = get_record_time(peripheral_settings),
        )
        return

    run_enabled_peripherals(peripheral_settings)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
