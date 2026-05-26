import argparse

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
MICROPHONE_DURATION = 5.0  # Duration of recording in seconds.


def main():
    parser = argparse.ArgumentParser(description="Control the motor driver and microphone.")
    Microphone.add_microphone_arguments(parser)
    args = parser.parse_args()

    if Microphone.handle_microphone_args(
        args,
        sample_rate=MICROPHONE_SAMPLE_RATE,
        channels=MICROPHONE_CHANNELS,
        file_format=MICROPHONE_FILE_FORMAT,
        duration_seconds=MICROPHONE_DURATION,
    ):
        return

    Motor.run_motor_driver(
        serial_port=MOTOR_SERIAL_PORT,
        baud_rate=MOTOR_BAUD_RATE,
        strength=MOTOR_STRENGTH,
        on_time=MOTOR_ON_TIME,
        off_time=MOTOR_OFF_TIME,
    )


if __name__ == "__main__":
    main()
