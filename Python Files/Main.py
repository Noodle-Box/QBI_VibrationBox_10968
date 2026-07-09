#######################################################################################################################
# File: Main Controller
# Project: Time Locked Box Simulato
# Research Group: Suarez Lab, Queensland Brain Institute, UQ
#
# Author: Tevyn Vergara
# Date: 01/06/2026

############################################## Standard Library Imports #################################################

import argparse
import json
import multiprocessing
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

################################################ Local Module Imports ###################################################
import Camera
import Microphone
import Motor
import Speaker
import SummarySheet

####################################### Peripheral Settings: CHANGE THESE AS NEEDED #########################################

# Recording paths (Change for where you want to autosave the recordings)
CUSTOM_RECORDINGS_DIR = r"C:\Users\uqtverga\Documents\Local Python Dev environment\QBI---Vibration-Box-10968-\Python Files\recordings"    # Example: r"C:\Users\YourName\Documents\VibrationBoxRecordings". Use None for repo-local recordings.
RECORDINGS_DIR = Path(CUSTOM_RECORDINGS_DIR) if CUSTOM_RECORDINGS_DIR else Path(__file__).resolve().parent / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Recording Macros
DEFAULT_RECORD_TIME = 120.0     # (s), Recording duration
DEFAULT_MERGE_AV = True         # True exports a merged MP4 when mic and camera are enabled.
KILL_BUTTON = "k"               # Press this key to stop all peripherals during recording.

# Speaker Macros
SPEAKER_FREQ = 250              # (Hz), Beep Freq
SPEAKER_ON = 1.0                # (s), Speaker ON time
SPEAKER_OFF = 10.0               # (s), Speaker OFF time
SPEAKER_SAMPLE_RATE = 44100     # (Hz), Sample rate for audio generation
SPEAKER_AMPLITUDE = 1           # Amplitude of the sinusodial beep sound. Adjust knob on speaker for real-world volume 

# Camera Macros
CAMERA_IP = "169.254.1.222"     # Set after --list-cameras. Example: "169.254.1.222". Use None for auto-discover.
CAMERA_VIEW = "stereo"          # Camera view options: "center", "left", "right", "stereo".
CAMERA_WIDTH = 1280             # (pixels), Width of the camera image
CAMERA_HEIGHT = 720             # (pixels), Height of the camera image
CAMERA_FPS = 30                 # (fp/s), Frames per second for the camera
CAMERA_FILE_FORMAT = "H265"     # File format for the recorded video

# Microphone Macros
MIC_DEVICE = 20                 # Set after --list-devices. Example: 15. Use None for auto-select.
MIC_SAMPLE_RATE = 384000        # (Hz), Sample rate in Hz.
MIC_CHANNELS = 1                # (int), Mono recording. Set to 2 for stereo if microphone supports it.
MIC_FORMAT = "FLAC"             # File format for the recorded audio. Common options: "WAV", "FLAC", "MP3"

# Motor Macros
MOTOR_SERIAL_PORT = "COM6"      # Serial port for motor driver. Change in "DEVICE MANAGER"
MOTOR_BAUD_RATE = 9600          # Baud rate for motor driver communication. DO NOT TOUCH
MOTOR_STRENGTH = 200            # Raw PWM strength, 50-250.
MOTOR_ON_TIME = 1.5                # (s), Motor ON time
MOTOR_OFF_TIME = 10            # (s), Motor OFF time

############################################# Helper Functions ####################################################
Camera.RECORDINGS_DIR = RECORDINGS_DIR
Microphone.RECORDINGS_DIR = RECORDINGS_DIR

PERIPHERAL_SETTINGS_PATH = Path(__file__).resolve().parent / "peripheral_settings.json"


# Returns default peripheral settings. Used in case json user settings is missing or incomplete
def default_peripheral_settings():
    return {
        "motor_enabled": True,
        "mic_enabled": True,
        "camera_enabled": False,
        "speaker_enabled": False,
        "record_time": DEFAULT_RECORD_TIME,
        "merge_av_enabled": DEFAULT_MERGE_AV,
    }


# Loads a JSON settings file, filling in any keys missing from disk with defaults_fn()'s values
def _load_json_settings(path, defaults_fn):
    defaults = defaults_fn()
    if path.exists():
        with path.open("r", encoding="utf-8") as settings_file:
            defaults.update(json.load(settings_file))
    return defaults


# Writes a settings dict to a JSON file
def _save_json_settings(path, settings):
    with path.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


# Loads peripheral_settings.json and fills missing keys with defaults if missing or incomplete
def load_peripheral_settings():
    return _load_json_settings(PERIPHERAL_SETTINGS_PATH, default_peripheral_settings)


# Writes peripheral_settings.json
def save_peripheral_settings(settings):
    _save_json_settings(PERIPHERAL_SETTINGS_PATH, settings)


# Returns default motor settings from Main.py macros
def default_motor_settings():
    return {
        "serial_port": MOTOR_SERIAL_PORT,
        "baud_rate": MOTOR_BAUD_RATE,
        "strength": MOTOR_STRENGTH,
        "on_time": MOTOR_ON_TIME,
        "off_time": MOTOR_OFF_TIME,
    }


# Loads motor_settings.json and fills missing keys, used by info display and motor run time.
def load_motor_settings():
    return Motor.load_settings(default_motor_settings)


# Writes motor_settings.json
def save_motor_settings(settings):
    Motor.save_settings(settings)


# Takes values from main macros and writes into microphone json
def save_default_microphone_settings():
    settings = Microphone.default_settings()
    settings["device_index"] = MIC_DEVICE
    settings["file_format"] = MIC_FORMAT.lower()
    Microphone.save_settings(settings)
    return settings


# Takes values from main macros and writes into camera json
def save_default_camera_settings():
    if CAMERA_VIEW not in ("center", "left", "right", "stereo"):
        raise ValueError('CAMERA_VIEW must be "center", "left", "right", or "stereo".')

    settings = Camera.default_settings()
    settings["device_ip"] = CAMERA_IP
    settings["view"] = CAMERA_VIEW
    Camera.save_settings(settings)
    return settings


# Recreates all JSON settings from Main.py macros --> --set-all on command
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


# Returns a, or b if a is None; used to merge an old/new pair of CLI argument names
def _first_not_none(a, b):
    return a if a is not None else b


# Converts a boolean state to user-facing On/Off text
def on_off_label(enabled):
    return "On" if enabled else "Off"


# Converts merge state to terminal display text 
def merge_label(enabled):
    return "MP4" if enabled else "Off"


# Prints a titled divider section, used for terminal display of peripheral settings
def print_section_header(title):
    separator = "=" * 77
    print(separator)
    print(title)
    print(separator)


# Prints a closing divider line; used for terminal display of peripheral settings
def print_section_footer():
    print("=" * 77)


# Returns active record duration from JSON or DEFAULT_RECORD_TIME
def get_record_time(settings=None):
    if settings is None:
        settings = load_peripheral_settings()

    return settings["record_time"] or DEFAULT_RECORD_TIME


# Prints microphone settings using Microphone.py formatting. Used in --info
def print_microphone_settings(record_time):
    mic_settings = Microphone.load_settings()
    Microphone.print_recording_info(
        mic_settings,
        sample_rate=MIC_SAMPLE_RATE,
        channels=MIC_CHANNELS,
        file_format=Microphone.get_recording_format(mic_settings, MIC_FORMAT),
        default_duration=record_time,
    )


# Prints motor settings from motor_settings.json. Used in --info
def print_motor_settings():
    motor_settings = load_motor_settings()
    print(
        f"Serial Port: {motor_settings['serial_port']} \n"
        f"Baud Rate: {motor_settings['baud_rate']} \n"
        f"Strength: {motor_settings['strength']} \n"
        f"On-Time: {motor_settings['on_time']} s \n"
        f"Off-Time: {motor_settings['off_time']} s"
    )


# Prints camera settings using Camera.py formatting, used in --info 
def print_camera_settings(record_time):
    Camera.print_camera_info(
        Camera.load_settings(),
        width=CAMERA_WIDTH,
        height=CAMERA_HEIGHT,
        fps=CAMERA_FPS,
        default_duration=record_time,
        file_format=CAMERA_FILE_FORMAT,
    )


# Prints speaker settings from Main.py macros, used in --info
def print_speaker_settings():
    print(
        f"Frequency: {SPEAKER_FREQ} Hz \n"
        f"Beep Duration: {SPEAKER_ON} s \n"
        f"Interval: {SPEAKER_OFF} s \n"
        f"Sample Rate: {SPEAKER_SAMPLE_RATE} Hz \n"
        f"Amplitude: {SPEAKER_AMPLITUDE}"
    )


# Prints a list of (title, print_fn) settings sections, separated by blank lines
def _print_sections(sections):
    for index, (title, print_fn) in enumerate(sections):
        if index > 0:
            print()
        print_section_header(f"Settings: {title}")
        print_fn()


# Prints settings sections for currently enabled peripherals, used by --info
def print_enabled_peripheral_settings(settings):
    record_time = get_record_time(settings)
    sections = [
        (settings["motor_enabled"], "MOTOR", print_motor_settings),
        (settings["mic_enabled"], "MICROPHONE", lambda: print_microphone_settings(record_time)),
        (settings["camera_enabled"], "CAMERA", lambda: print_camera_settings(record_time)),
        (settings["speaker_enabled"], "SPEAKER", print_speaker_settings),
    ]
    active = [(title, print_fn) for enabled, title, print_fn in sections if enabled]

    if not active:
        print("No peripherals are enabled.")
        return

    _print_sections(active)
    print_section_footer()


# Prints settings sections for peripherals targeted by a config command.
def print_selected_peripheral_settings(show_motor, show_mic, show_camera, record_time):
    sections = [
        (show_motor, "MOTOR", print_motor_settings),
        (show_mic, "MICROPHONE", lambda: print_microphone_settings(record_time)),
        (show_camera, "CAMERA", lambda: print_camera_settings(record_time)),
    ]
    active = [(title, print_fn) for enabled, title, print_fn in sections if enabled]

    if active:
        _print_sections(active)
        print_section_footer()


# Prints full project state and enabled peripheral settings. Used in --info and record-time updates.
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

# Records microphone audio for the shared record time
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

# Starts enabled peripherals together and coordinates recording, kill, recovery, and merge behavior.
def run_enabled_peripherals(peripheral_settings):
    # Read enabled states and shared recording options from peripheral_settings.json.
    motor_enabled = peripheral_settings["motor_enabled"]
    mic_enabled = peripheral_settings["mic_enabled"]
    camera_enabled = peripheral_settings["camera_enabled"]
    speaker_enabled = peripheral_settings["speaker_enabled"]
    merge_enabled = peripheral_settings["merge_av_enabled"]
    record_time = get_record_time(peripheral_settings)

    # Stop early if the user has disabled every peripheral.
    if not motor_enabled and not mic_enabled and not camera_enabled and not speaker_enabled:
        print("No peripherals are enabled. Use --set-motor on, --set-mic on, --set-camera on, or --set-speaker on.")
        return

    # Verify microphone can open before starting other peripherals.
    if mic_enabled:
        mic_ready = Microphone.can_record_from_settings(
            Microphone.load_settings(),
            sample_rate=MIC_SAMPLE_RATE,
            channels=MIC_CHANNELS,
        )
        if not mic_ready:
            return

    # Snapshot run metadata at the very start before any threads launch.
    run_timestamp = datetime.now().strftime("%H%M_%d_%m")
    camera_settings = Camera.load_settings()
    motor_settings = load_motor_settings()

    # Motor value logs: initialised with starting values so the first entry always reflects run start.
    motor_strength_log = [motor_settings["strength"]] if motor_enabled else []
    motor_on_time_log = [motor_settings["on_time"]] if motor_enabled else []
    motor_off_time_log = [motor_settings["off_time"]] if motor_enabled else []

    # Speaker pulse log: each entry is {"event": "ON", "wall": "HH:MM:SS.mmm", "mono": float}
    speaker_pulse_log = []

    def speaker_pulse_callback(event, wall_time, mono_t):
        speaker_pulse_log.append({"event": event, "wall": wall_time, "mono": mono_t})

    speaker_on_log = [SPEAKER_ON] if speaker_enabled else []
    speaker_off_log = [SPEAKER_OFF] if speaker_enabled else []

    def speaker_settings_callback(on_time, off_time):
        speaker_on_log.append(on_time)
        speaker_off_log.append(off_time)

    # Queue for routing t/y commands from the keyboard thread to the speaker thread.
    speaker_queue = queue.SimpleQueue()

    # Queue for routing motor commands from the keyboard thread to the motor thread.
    motor_queue = queue.SimpleQueue()

    # Shared dicts so the keyboard thread can read current values when reprinting the menu.
    motor_state = {
        "strength": motor_settings["strength"],
        "on_time": motor_settings["on_time"],
        "off_time": motor_settings["off_time"],
        "motor_on": True,
    }
    speaker_state = {
        "on": SPEAKER_ON,
        "off": SPEAKER_OFF,
    }

    def motor_log_callback(strength, on_time, off_time):
        motor_strength_log.append(strength)
        motor_on_time_log.append(on_time)
        motor_off_time_log.append(off_time)
        Motor.save_live_settings(default_motor_settings, strength, on_time, off_time)

    # Motor pulse log: each entry is {"event": "ON"|"OFF", "wall": "HH:MM:SS.mmm", "mono": float}
    pulse_log = []

    def pulse_callback(event, wall_time, mono_t):
        pulse_log.append({"event": event, "wall": wall_time, "mono": mono_t})

    # Create shared runtime state for threads, camera process, and output paths.
    worker_threads = []
    stop_event = multiprocessing.Event()
    done_event = threading.Event()
    recording_paths = {
        "audio": None,
        "video": None,
    }
    camera_ready_event = multiprocessing.Event() if camera_enabled else None

    # Keyboard thread: reads terminal input, routes motor commands to motor_queue and
    # speaker t/y commands to speaker_queue. Handles kill for all peripheral combinations.
    def keyboard_thread_fn():
        command_buffer = ""
        end_time_ref = time.monotonic() + record_time

        def reprint_menu():
            Motor.print_menu(
                motor_state["strength"], motor_state["on_time"], motor_state["off_time"],
                KILL_BUTTON, motor_state["motor_on"], end_time_ref - time.monotonic(),
                speaker_enabled, speaker_state["on"], speaker_state["off"],
            )
            print("> ", end="", flush=True)

        if motor_enabled:
            # Wait for the camera to finish connecting before printing the menu so connection
            # messages appear first. Falls through after 60 s if the camera never signals.
            if camera_ready_event is not None:
                camera_ready_event.wait(timeout=60)
            reprint_menu()

        while not stop_event.is_set() and not done_event.is_set():
            command_buffer, command = Motor.read_nonblocking_command(command_buffer, stop_event, KILL_BUTTON)

            if command is not None:
                if command == "__kill__":
                    break

                parts = command.strip().split()
                if parts:
                    cmd = parts[0].lower()
                    if cmd in ("t", "y"):
                        if speaker_enabled and len(parts) == 2:
                            try:
                                value = float(parts[1])
                                Speaker.send_to_speaker(speaker_queue, cmd, value)
                                # Update speaker_state immediately so the menu reflects the new value.
                                if cmd == "t":
                                    speaker_state["on"] = max(0.1, value)
                                else:
                                    speaker_state["off"] = max(0.1, value)
                            except ValueError:
                                print("Value must be a number.")
                        elif not speaker_enabled:
                            print("Speaker is not enabled.")
                        else:
                            print("Use: t <seconds> or y <seconds>")
                    elif motor_enabled:
                        motor_queue.put(command)
                    else:
                        print("Motor is not enabled.")

                if motor_enabled:
                    time.sleep(0.1)  # Let the motor thread process the command before reprinting.
                    reprint_menu()

            time.sleep(0.05)

    keyboard_thread = threading.Thread(target=keyboard_thread_fn, daemon=True)
    keyboard_thread.start()

    # Start the motor in a thread so it can drive the Arduino in parallel with other peripherals.
    if motor_enabled:
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
                "settings_callback": motor_log_callback,
                "pulse_callback": pulse_callback,
                "motor_queue": motor_queue,
                "motor_state": motor_state,
            },
        )
        motor_thread.start()
        worker_threads.append(motor_thread)

    # Start the camera in a subprocess so a DepthAI native crash on device-close doesn't kill the main process.
    # The video path is returned via result_queue from inside Camera.py's finally block, before the crash fires.
    # camera_ready_event is set by Camera.py after pipeline.start() so the keyboard menu waits until then.
    camera_proc = None
    camera_result_queue = None
    if camera_enabled:
        camera_result_queue = multiprocessing.Queue()
        camera_proc = multiprocessing.Process(
            target=Camera.run_camera_subprocess,
            args=(record_time, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, CAMERA_FILE_FORMAT, stop_event, camera_result_queue),
            kwargs={"ready_event": camera_ready_event},
            daemon=True,
        )
        camera_proc.start()

    # Start speaker beeps in a thread so audio output runs during the shared record time.
    if speaker_enabled:
        speaker_thread = threading.Thread(
            target=Speaker.run_speaker,
            kwargs={
                "duration_seconds": record_time,
                "stop_event": stop_event,
                "frequency_hz": SPEAKER_FREQ,
                "beep_duration_seconds": SPEAKER_ON,
                "interval_seconds": SPEAKER_OFF,
                "sample_rate": SPEAKER_SAMPLE_RATE,
                "amplitude": SPEAKER_AMPLITUDE,
                "pulse_callback": speaker_pulse_callback,
                "settings_callback": speaker_settings_callback,
                "command_queue": speaker_queue,
            },
        )
        speaker_thread.start()
        worker_threads.append(speaker_thread)

    # Timer starts once all threads are launched.
    run_start_time = time.monotonic()

    # Use microphone recording as the blocking timer when the mic is enabled.
    if mic_enabled:
        recording_paths["audio"] = record_microphone(record_time, stop_event)
        actual_run_time = round(time.monotonic() - run_start_time, 1)

        # Wait for motor and speaker threads to finish after microphone recording ends.
        for worker_thread in worker_threads:
            worker_thread.join()

        # Collect the saved video path from the camera subprocess result queue.
        # The path is enqueued inside Camera.py's finally block before DepthAI closes the device,
        # so it arrives even if the subprocess crashes during device shutdown.
        if camera_enabled:
            try:
                recording_paths["video"] = camera_result_queue.get(timeout=15)
            except Exception:
                recording_paths["video"] = None
                print("Camera result not received; video path unavailable.")

        done_event.set()

        # Merge audio and video if both features are enabled.
        mp4_paths = []
        if merge_enabled and camera_enabled:
            if isinstance(recording_paths["video"], dict):
                mp4_left = Camera.merge_with_audio(recording_paths["video"]["left"], recording_paths["audio"], CAMERA_FPS)
                mp4_right = Camera.merge_with_audio(recording_paths["video"]["right"], recording_paths["audio"], CAMERA_FPS)
                mp4_paths = [p for p in [mp4_left, mp4_right] if p]
            else:
                mp4_path = Camera.merge_with_audio(recording_paths["video"], recording_paths["audio"], CAMERA_FPS)
                if mp4_path:
                    mp4_paths = [mp4_path]

        SummarySheet.append_run(RunResult(
            run_timestamp=run_timestamp, actual_run_time=actual_run_time, run_start_time=run_start_time,
            peripheral_settings=peripheral_settings, camera_settings=camera_settings,
            speaker_freq=SPEAKER_FREQ,
            speaker_pulse_log=speaker_pulse_log, speaker_on_log=speaker_on_log, speaker_off_log=speaker_off_log,
            motor_strength_log=motor_strength_log, motor_on_time_log=motor_on_time_log, motor_off_time_log=motor_off_time_log,
            motor_pulse_log=pulse_log, recording_paths=recording_paths, mp4_paths=mp4_paths,
        ))
        return

    # If microphone is off, wait for all worker threads to finish.
    for worker_thread in worker_threads:
        worker_thread.join()

    if camera_enabled:
        try:
            recording_paths["video"] = camera_result_queue.get(timeout=15)
        except Exception:
            recording_paths["video"] = None
            print("Camera result not received; video path unavailable.")

    done_event.set()
    actual_run_time = round(time.monotonic() - run_start_time, 1)

    SummarySheet.append_run(RunResult(
        run_timestamp=run_timestamp, actual_run_time=actual_run_time, run_start_time=run_start_time,
        peripheral_settings=peripheral_settings, camera_settings=camera_settings,
        speaker_freq=SPEAKER_FREQ,
        speaker_pulse_log=speaker_pulse_log, speaker_on_log=speaker_on_log, speaker_off_log=speaker_off_log,
        motor_strength_log=motor_strength_log, motor_on_time_log=motor_on_time_log, motor_off_time_log=motor_off_time_log,
        motor_pulse_log=pulse_log, recording_paths=recording_paths, mp4_paths=[],
    ))


# Bundles everything SummarySheet.append_run needs so positional args can't be swapped by mistake.
@dataclass
class RunResult:
    run_timestamp: str
    actual_run_time: float
    run_start_time: float
    peripheral_settings: dict
    camera_settings: dict
    speaker_freq: int
    speaker_pulse_log: list
    speaker_on_log: list
    speaker_off_log: list
    motor_strength_log: list
    motor_on_time_log: list
    motor_off_time_log: list
    motor_pulse_log: list
    recording_paths: dict
    mp4_paths: list

###################################################### Main Function ###########################################################
# Parses CLI arguments, updates JSON settings, prints info, or starts enabled peripherals.
def main():
    # Build one parser from all peripheral drivers plus Main.py global controls.
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

    # Load saved settings before applying any command-line changes.
    peripheral_settings = load_peripheral_settings()
    motor_settings = load_motor_settings()

    # Handle microphone device listing immediately and exit.
    if args.list_devices:
        Microphone.handle_microphone_args(
            args,
            sample_rate = MIC_SAMPLE_RATE,
            channels = MIC_CHANNELS,
            file_format = MIC_FORMAT,
            duration_seconds = get_record_time(peripheral_settings),
        )
        return

    # Handle camera listing immediately and exit.
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

    # Handle camera-only configuration commands and exit before running peripherals.
    if args.camera and Camera.handle_camera_args(
        args,
        width=CAMERA_WIDTH,
        height=CAMERA_HEIGHT,
        fps=CAMERA_FPS,
        default_duration=get_record_time(peripheral_settings),
        file_format=CAMERA_FILE_FORMAT,
    ):
        return

    # Track whether global peripheral state or record-time settings changed.
    peripheral_settings_changed = False
    record_time_changed = False

    # Reset all JSON settings from Main.py macros when --set-all on is used.
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

    # Apply individual peripheral enable/disable toggles.
    for cli_value, settings_key in (
        (args.set_motor, "motor_enabled"),
        (args.set_mic, "mic_enabled"),
        (args.set_camera, "camera_enabled"),
        (args.set_speaker, "speaker_enabled"),
    ):
        if cli_value is not None:
            peripheral_settings[settings_key] = cli_value == "on"
            peripheral_settings_changed = True

    # Apply audio/video merge toggle.
    if args.set_merge is not None:
        peripheral_settings["merge_av_enabled"] = args.set_merge == "on"
        peripheral_settings_changed = True

    # Validate and apply shared recording time.
    requested_record_time = args.set_time

    if requested_record_time is not None:
        if requested_record_time <= 0:
            print("Record time must be greater than 0 seconds.")
            return

        peripheral_settings["record_time"] = requested_record_time
        peripheral_settings_changed = True
        record_time_changed = True

    # Track which peripheral namespaces the user explicitly targeted.
    motor_selected = args.motor
    mic_selected = args.mic
    camera_selected = args.camera

    # Normalize old and new motor CLI argument names into one set of values.
    motor_settings_changed = False
    motor_port = _first_not_none(args.set_port, args.motor_port)
    motor_baud = _first_not_none(args.set_baud, args.motor_baud)
    motor_strength = _first_not_none(args.set_strength, args.motor_strength)
    motor_on_time = _first_not_none(args.set_on, args.motor_on_time)
    motor_off_time = _first_not_none(args.set_off, args.motor_off_time)

    # Apply motor configuration changes to motor_settings.json.
    motor_updates = (
        (motor_port, "serial_port", None),
        (motor_baud, "baud_rate", None),
        (motor_strength, "strength", lambda v: max(30, min(250, v))),
        (motor_on_time, "on_time", lambda v: max(0, v)),
        (motor_off_time, "off_time", lambda v: max(0, v)),
    )
    for value, key, clamp_fn in motor_updates:
        if value is not None:
            motor_settings_changed = Motor.set_setting(
                motor_settings, key, clamp_fn(value) if clamp_fn else value
            ) or motor_settings_changed

    # Apply microphone configuration changes to microphone_settings.json.
    microphone_settings_changed = False
    mic_settings = Microphone.load_settings()
    if args.set_device is not None:
        microphone_settings_changed = Microphone.set_recording_device(mic_settings, args.set_device) or microphone_settings_changed

    if args.set_format is not None:
        microphone_settings_changed = Microphone.set_recording_format(mic_settings, args.set_format) or microphone_settings_changed

    # Save global peripheral settings after all global changes are applied.
    if peripheral_settings_changed:
        save_peripheral_settings(peripheral_settings)

    # Print full system info if requested.
    if args.info:
        print_system_info(peripheral_settings)
        return

    # Print updated peripheral state after global changes and exit.
    if peripheral_settings_changed:
        if record_time_changed:
            print_system_info(peripheral_settings)
        else:
            print_enabled_peripheral_settings(peripheral_settings)
        return

    # Print only the changed peripheral settings after targeted configuration commands.
    if motor_settings_changed or microphone_settings_changed:
        print_selected_peripheral_settings(
            show_motor=motor_selected or (motor_settings_changed and not mic_selected),
            show_mic=mic_selected or (microphone_settings_changed and not motor_selected),
            show_camera=camera_selected,
            record_time=get_record_time(peripheral_settings))
        return

    # Handle standalone microphone recording options and exit.
    if args.record_mic or args.device is not None or args.duration is not None or args.mp3:
        Microphone.handle_microphone_args(
            args,
            sample_rate = MIC_SAMPLE_RATE,
            channels = MIC_CHANNELS,
            file_format = MIC_FORMAT,
            duration_seconds = get_record_time(peripheral_settings),
        )
        return

    # With no configuration-only command, run the enabled peripherals.
    run_enabled_peripherals(peripheral_settings)


if __name__ == "__main__":
    # Required for Windows multiprocessing when camera capture runs in a child process.
    multiprocessing.freeze_support()
    main()
