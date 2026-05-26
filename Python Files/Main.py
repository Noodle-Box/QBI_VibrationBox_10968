import argparse
import json
import threading
from pathlib import Path

# Local functionality drivers (You shouldn't have to change these)
import Microphone
import Motor


# Motor Macros (Change if needed)
MOTOR_SERIAL_PORT = "COM6"
MOTOR_BAUD_RATE = 9600
MOTOR_STRENGTH = 50  # Percent, 0-100. Arduino maps this to PWM 0-255.
MOTOR_ON_TIME = 200  # Milliseconds.
MOTOR_OFF_TIME = 500  # Milliseconds.

# Microphone Macros (Change if needed)
MICROPHONE_SAMPLE_RATE = 384000  # Sample rate in Hz.
MICROPHONE_CHANNELS = 1  # Mono recording. Set to 2 for stereo if microphone supports it.
MICROPHONE_FILE_FORMAT = "WAV"
MIC_DEFAULT_TIME = 10.0  # Duration of recording in seconds.

PERIPHERAL_SETTINGS_PATH = Path(__file__).resolve().parent / "peripheral_settings.json"
MOTOR_SETTINGS_PATH = Path(__file__).resolve().parent / "motor_settings.json"


def default_peripheral_settings():
    return {
        "motor_enabled": True,
        "mic_enabled": True,
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


def on_off_label(enabled):
    return "On" if enabled else "Off"


def get_microphone_duration():
    mic_settings = Microphone.load_settings()
    return mic_settings["duration_seconds"] or MIC_DEFAULT_TIME


def print_microphone_settings():
    Microphone.print_recording_info(
        Microphone.load_settings(),
        sample_rate=MICROPHONE_SAMPLE_RATE,
        channels=MICROPHONE_CHANNELS,
        file_format=MICROPHONE_FILE_FORMAT,
        default_duration=MIC_DEFAULT_TIME,
    )


def print_motor_settings():
    motor_settings = load_motor_settings()
    print(
        f"Serial Port: {motor_settings['serial_port']} \n"
        f"Baud Rate: {motor_settings['baud_rate']} \n"
        f"Strength: {motor_settings['strength']}% \n"
        f"On-Time: {motor_settings['on_time']} ms \n"
        f"Off-Time: {motor_settings['off_time']} ms"
    )


def print_enabled_peripheral_settings(settings):
    if settings["motor_enabled"]:
        print("Motor Settings")
        print_motor_settings()

    if settings["motor_enabled"] and settings["mic_enabled"]:
        print()

    if settings["mic_enabled"]:
        print("Microphone Settings")
        print_microphone_settings()

    if not settings["motor_enabled"] and not settings["mic_enabled"]:
        print("No peripherals are enabled.")


def print_selected_peripheral_settings(show_motor, show_mic):
    if show_motor:
        print("Motor Settings")
        print_motor_settings()

    if show_motor and show_mic:
        print()

    if show_mic:
        print("Microphone Settings")
        print_microphone_settings()


def print_system_info(settings):
    print("Peripheral State")
    print(f"Motor: {on_off_label(settings['motor_enabled'])}")
    print(f"Mic: {on_off_label(settings['mic_enabled'])}")
    print()
    print_enabled_peripheral_settings(settings)


def record_microphone():
    Microphone.record_from_settings(
        Microphone.load_settings(),
        sample_rate=MICROPHONE_SAMPLE_RATE,
        channels=MICROPHONE_CHANNELS,
        duration_seconds=get_microphone_duration(),
        file_format=MICROPHONE_FILE_FORMAT,
    )


def run_enabled_peripherals(peripheral_settings):
    motor_enabled = peripheral_settings["motor_enabled"]
    mic_enabled = peripheral_settings["mic_enabled"]

    if not motor_enabled and not mic_enabled:
        print("No peripherals are enabled. Use --set-motor on or --set-mic on.")
        return

    if mic_enabled:
        mic_ready = Microphone.can_record_from_settings(
            Microphone.load_settings(),
            sample_rate=MICROPHONE_SAMPLE_RATE,
            channels=MICROPHONE_CHANNELS,
        )
        if not mic_ready:
            return

    if mic_enabled and motor_enabled:
        motor_settings = load_motor_settings()
        motor_thread = threading.Thread(
            target=Motor.run_motor_driver,
            kwargs={
                "serial_port": motor_settings["serial_port"],
                "baud_rate": motor_settings["baud_rate"],
                "strength": motor_settings["strength"],
                "on_time": motor_settings["on_time"],
                "off_time": motor_settings["off_time"],
            },
        )
        motor_thread.start()

        record_microphone()
        motor_thread.join()
        return

    if mic_enabled:
        record_microphone()
        return

    motor_settings = load_motor_settings()
    Motor.run_motor_driver(
        serial_port = motor_settings["serial_port"],
        baud_rate = motor_settings["baud_rate"],
        strength = motor_settings["strength"],
        on_time = motor_settings["on_time"],
        off_time = motor_settings["off_time"],
    )


def main():
    parser = argparse.ArgumentParser(description="Control the motor driver and microphone.")
    Microphone.add_microphone_arguments(parser)
    parser.add_argument("--motor", action="store_true", help="Configure or target motor settings.")
    parser.add_argument("--mic", action="store_true", help="Configure or target microphone settings.")
    parser.add_argument("--set-motor", choices=["on", "off"], help="Enable or disable the motor driver.")
    parser.add_argument("--set-mic", choices=["on", "off"], help="Enable or disable the microphone.")
    parser.add_argument("--set-strength", type=int, help="With --motor, save motor strength percent, 0-100.")
    parser.add_argument("--set-on", type=int, help="With --motor, save motor on-time in milliseconds.")
    parser.add_argument("--set-off", type=int, help="With --motor, save motor off-time in milliseconds.")
    parser.add_argument("--set-port", help="With --motor, save the Arduino serial port.")
    parser.add_argument("--set-baud", type=int, help="With --motor, save the Arduino serial baud rate.")
    parser.add_argument("--set-duration", type=float, help="With --mic, save the recording duration in seconds.")
    parser.add_argument("--motor-port", help="Save the Arduino serial port used by the motor driver.")
    parser.add_argument("--motor-baud", type=int, help="Save the Arduino serial baud rate.")
    parser.add_argument("--motor-strength", type=int, help="Save motor strength percent, 0-100.")
    parser.add_argument("--motor-on-time", type=int, help="Save motor on-time in milliseconds.")
    parser.add_argument("--motor-off-time", type=int, help="Save motor off-time in milliseconds.")
    args = parser.parse_args()
    peripheral_settings = load_peripheral_settings()
    motor_settings = load_motor_settings()

    if args.list_devices:
        Microphone.handle_microphone_args(
            args,
            sample_rate = MICROPHONE_SAMPLE_RATE,
            channels = MICROPHONE_CHANNELS,
            file_format = MICROPHONE_FILE_FORMAT,
            duration_seconds = MIC_DEFAULT_TIME,
        )
        return

    peripheral_settings_changed = False
    if args.set_motor is not None:
        peripheral_settings["motor_enabled"] = args.set_motor == "on"
        peripheral_settings_changed = True

    if args.set_mic is not None:
        peripheral_settings["mic_enabled"] = args.set_mic == "on"
        peripheral_settings_changed = True

    motor_selected = args.motor
    mic_selected = args.mic

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
            max(0, min(100, motor_strength)),
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

    mic_duration = args.set_duration if args.set_duration is not None else args.set_time
    if mic_duration is not None:
        microphone_settings_changed = Microphone.set_recording_duration(mic_settings, mic_duration) or microphone_settings_changed

    if peripheral_settings_changed:
        save_peripheral_settings(peripheral_settings)

    if args.info:
        print_system_info(peripheral_settings)
        return

    if peripheral_settings_changed:
        print_enabled_peripheral_settings(peripheral_settings)
        return

    if motor_settings_changed or microphone_settings_changed:
        print_selected_peripheral_settings(
            show_motor=motor_selected or (motor_settings_changed and not mic_selected),
            show_mic=mic_selected or (microphone_settings_changed and not motor_selected),
        )
        return

    if args.record_mic or args.device is not None or args.duration is not None or args.mp3:
        Microphone.handle_microphone_args(
            args,
            sample_rate = MICROPHONE_SAMPLE_RATE,
            channels = MICROPHONE_CHANNELS,
            file_format = MICROPHONE_FILE_FORMAT,
            duration_seconds = MIC_DEFAULT_TIME,
        )
        return

    run_enabled_peripherals(peripheral_settings)


if __name__ == "__main__":
    main()
