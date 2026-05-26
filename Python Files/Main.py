import argparse
import json
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


def default_peripheral_settings():
    return {
        "motor_enabled": True,
        "mic_enabled": False,
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
    print(
        f"Serial Port: {MOTOR_SERIAL_PORT} \n"
        f"Baud Rate: {MOTOR_BAUD_RATE} \n"
        f"Strength: {MOTOR_STRENGTH}% \n"
        f"On-Time: {MOTOR_ON_TIME} ms \n"
        f"Off-Time: {MOTOR_OFF_TIME} ms"
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


def print_system_info(settings):
    print("Peripheral State")
    print(f"Motor: {on_off_label(settings['motor_enabled'])}")
    print(f"Mic: {on_off_label(settings['mic_enabled'])}")
    print()
    print_enabled_peripheral_settings(settings)


def main():
    parser = argparse.ArgumentParser(description="Control the motor driver and microphone.")
    Microphone.add_microphone_arguments(parser)
    parser.add_argument("--set-motor", choices=["on", "off"], help="Enable or disable the motor driver.")
    parser.add_argument("--set-mic", choices=["on", "off"], help="Enable or disable the microphone.")
    args = parser.parse_args()
    peripheral_settings = load_peripheral_settings()

    peripheral_settings_changed = False
    if args.set_motor is not None:
        peripheral_settings["motor_enabled"] = args.set_motor == "on"
        peripheral_settings_changed = True

    if args.set_mic is not None:
        peripheral_settings["mic_enabled"] = args.set_mic == "on"
        peripheral_settings_changed = True

    if peripheral_settings_changed:
        save_peripheral_settings(peripheral_settings)
        print_enabled_peripheral_settings(peripheral_settings)
        return

    if args.info:
        print_system_info(peripheral_settings)
        return

    if Microphone.handle_microphone_args(
        args,
        sample_rate = MICROPHONE_SAMPLE_RATE,
        channels = MICROPHONE_CHANNELS,
        file_format = MICROPHONE_FILE_FORMAT,
        duration_seconds = MIC_DEFAULT_TIME,
    ):
        return

    if peripheral_settings["mic_enabled"]:
        Microphone.record_from_settings(
            Microphone.load_settings(),
            sample_rate=MICROPHONE_SAMPLE_RATE,
            channels=MICROPHONE_CHANNELS,
            duration_seconds=get_microphone_duration(),
            file_format=MICROPHONE_FILE_FORMAT,
        )

    if peripheral_settings["motor_enabled"]:
        Motor.run_motor_driver(
            serial_port = MOTOR_SERIAL_PORT,
            baud_rate = MOTOR_BAUD_RATE,
            strength = MOTOR_STRENGTH,
            on_time = MOTOR_ON_TIME,
            off_time = MOTOR_OFF_TIME,
        )

    if not peripheral_settings["motor_enabled"] and not peripheral_settings["mic_enabled"]:
        print("No peripherals are enabled. Use --set-motor on or --set-mic on.")


if __name__ == "__main__":
    main()
