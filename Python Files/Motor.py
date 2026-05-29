import time

import serial
from serial.tools import list_ports


def add_motor_arguments(parser):
    parser.add_argument("--motor", action="store_true", help="Configure or target motor settings.")
    parser.add_argument("--set-strength", type=int, help="With --motor, save motor strength percent, 0-100.")
    parser.add_argument("--set-on", type=int, help="With --motor, save motor on-time in milliseconds.")
    parser.add_argument("--set-off", type=int, help="With --motor, save motor off-time in milliseconds.")
    parser.add_argument("--set-port", help="With --motor, save the Arduino serial port.")
    parser.add_argument("--set-baud", type=int, help="With --motor, save the Arduino serial baud rate.")
    parser.add_argument("--motor-port", help="Save the Arduino serial port used by the motor driver.")
    parser.add_argument("--motor-baud", type=int, help="Save the Arduino serial baud rate.")
    parser.add_argument("--motor-strength", type=int, help="Save motor strength percent, 0-100.")
    parser.add_argument("--motor-on-time", type=int, help="Save motor on-time in milliseconds.")
    parser.add_argument("--motor-off-time", type=int, help="Save motor off-time in milliseconds.")


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, int(value)))


def send_command(arduino, command_type, value):
    message = f"{command_type}:{value}\n"
    arduino.write(message.encode("utf-8"))
    arduino.flush()
    print(f"Sent {message.strip()}")


def set_strength(arduino, value):
    strength = clamp(value, 0, 100)
    send_command(arduino, "s", strength)
    return strength


def set_on_time(arduino, value):
    on_time = max(0, int(value))
    send_command(arduino, "n", on_time)
    return on_time


def set_off_time(arduino, value):
    off_time = max(0, int(value))
    send_command(arduino, "f", off_time)
    return off_time


def send_all_settings(arduino, strength, on_time, off_time):
    strength = set_strength(arduino, strength)
    on_time = set_on_time(arduino, on_time)
    off_time = set_off_time(arduino, off_time)
    return strength, on_time, off_time


def print_menu(strength, on_time, off_time):
    print()
    print("Current Python settings:")
    print(f"  strength = {strength}%")
    print(f"  on_time  = {on_time} ms")
    print(f"  off_time = {off_time} ms")
    print()
    print("Commands:")
    print("  s <0-100>   set strength percent")
    print("  n <ms>      set motor on-time")
    print("  f <ms>      set motor off-time")
    print("  all         resend all settings")
    print("  q           stop motor and quit")


def handle_user_command(arduino, user_input, strength, on_time, off_time):
    parts = user_input.strip().split()
    if not parts:
        return strength, on_time, off_time

    command = parts[0].lower()

    if command == "all":
        return send_all_settings(arduino, strength, on_time, off_time)

    if len(parts) != 2:
        print("Use commands like: s 50, n 200, or f 500")
        return strength, on_time, off_time

    try:
        value = int(parts[1])
    except ValueError:
        print("Value must be a whole number.")
        return strength, on_time, off_time

    if command == "s":
        strength = set_strength(arduino, value)
    elif command == "n":
        on_time = set_on_time(arduino, value)
    elif command == "f":
        off_time = set_off_time(arduino, value)
    else:
        print("Unknown command. Use s, n, f, all, or q.")

    return strength, on_time, off_time


def print_available_serial_ports():
    print("Available serial ports:")

    ports = list(list_ports.comports())
    if not ports:
        print("  No serial ports detected.")
    else:
        for port in ports:
            print(f"  {port.device}: {port.description}")


def run_motor_driver(serial_port, baud_rate, strength, on_time, off_time):
    try:
        with serial.Serial(serial_port, baud_rate, timeout=1) as arduino:
            time.sleep(2)  # Give the Arduino time to reset after opening serial.
            strength, on_time, off_time = send_all_settings(
                arduino,
                strength,
                on_time,
                off_time,
            )

            while True:
                print_menu(strength, on_time, off_time)
                user_input = input("> ").strip()

                if user_input.lower() == "q":
                    set_strength(arduino, 0)
                    break

                strength, on_time, off_time = handle_user_command(
                    arduino,
                    user_input,
                    strength,
                    on_time,
                    off_time,
                )
    except serial.SerialException as exc:
        print(f"Could not open {serial_port}: {exc}")
        print()
        print_available_serial_ports()
