#######################################################################################################################
# File: Motor Driver
# Project: Time Locked Box Simulator
# Research Group: Suarez Lab, Queensland Brain Institute, UQ
#
# Author: Tevyn Vergara
# Date: 01/06/2026


# Note: This file takes the serial commands from Main.py and sends them to Arduino controller in Arduino Files\Motor Driver - Vibration Box\src\main.cpp
# To modify arduino drive in VSCode, please install PlatformIO extension
#
# STRUCTURE: Main.py --> Motor.py --> Main.cpp

############################################ Standard Library Imports ################################################
import msvcrt
import time
import serial
from serial.tools import list_ports

################################################### Functionality ####################################################

KILL_BUTTON = "v"

def add_motor_arguments(parser):
    parser.add_argument("--motor", action="store_true", help="Configure or target motor settings.")
    parser.add_argument("--set-strength", type=int, help="With --motor, save raw motor strength, 30-250.")
    parser.add_argument("--set-on", type=int, help="With --motor, save motor on-time in milliseconds.")
    parser.add_argument("--set-off", type=int, help="With --motor, save motor off-time in milliseconds.")
    parser.add_argument("--set-port", help="With --motor, save the Arduino serial port.")
    parser.add_argument("--set-baud", type=int, help="With --motor, save the Arduino serial baud rate.")
    parser.add_argument("--motor-port", help="Save the Arduino serial port used by the motor driver.")
    parser.add_argument("--motor-baud", type=int, help="Save the Arduino serial baud rate.")
    parser.add_argument("--motor-strength", type=int, help="Save raw motor strength, 30-250.")
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
    strength = clamp(value, 30, 250)
    send_command(arduino, "s", strength)
    return strength


def stop_motor(arduino):
    send_command(arduino, "s", 0)


def set_on_time(arduino, value):
    on_time = max(0, int(value))
    send_command(arduino, "n", on_time)
    return on_time


def set_off_time(arduino, value):
    off_time = max(0, int(value))
    send_command(arduino, "m", off_time)
    return off_time


def send_all_settings(arduino, strength, on_time, off_time):
    strength = set_strength(arduino, strength)
    on_time = set_on_time(arduino, on_time)
    off_time = set_off_time(arduino, off_time)
    return strength, on_time, off_time


def save_current_settings(settings_callback, strength, on_time, off_time):
    if settings_callback is not None:
        settings_callback(strength, on_time, off_time)


def print_menu(strength, on_time, off_time, motor_on=True, time_left=None, kill_button=KILL_BUTTON):
    print()
    if time_left is not None:
        print(f"Current time left: {max(0, int(time_left))} seconds")
        print()

    print("CMD | Current Setting | Description")
    print()
    print(f"p   | {'on' if motor_on else 'off'}             | Toggle ON/OFF vibrations without quitting run time")
    print(f"s   | {strength}            | Vibration strength - strength of motor")
    print(f"n   | {on_time} ms         | Motor on time")
    print(f"m   | {off_time} ms         | Motor off time")
    print(f"{kill_button}   | -              | Kill all peripherals and process clipped recordings")
    print("q   | -              | Quit the program early. Completely exit the motor (used for emergency)")


def handle_user_command(arduino, user_input, strength, on_time, off_time, motor_on=True, settings_callback=None):
    parts = user_input.strip().split()
    if not parts:
        return strength, on_time, off_time, motor_on, False

    command = parts[0].lower()

    if command == "p":
        motor_on = not motor_on
        if motor_on:
            set_strength(arduino, strength)
            print("Motor toggled ON.")
        else:
            stop_motor(arduino)
            print("Motor toggled OFF. Run time is still active.")

        return strength, on_time, off_time, motor_on, False

    if command == "q":
        stop_motor(arduino)
        print("Emergency motor quit requested.")
        return strength, on_time, off_time, False, True

    if command == "all":
        if motor_on:
            strength, on_time, off_time = send_all_settings(arduino, strength, on_time, off_time)
        else:
            stop_motor(arduino)
            on_time = set_on_time(arduino, on_time)
            off_time = set_off_time(arduino, off_time)
        save_current_settings(settings_callback, strength, on_time, off_time)
        return strength, on_time, off_time, motor_on, False

    if len(parts) != 2:
        print("Use commands like: p, q, s 150, n 200, or m 500")
        return strength, on_time, off_time, motor_on, False

    try:
        value = int(parts[1])
    except ValueError:
        print("Value must be a whole number.")
        return strength, on_time, off_time, motor_on, False

    if command == "s":
        strength = clamp(value, 30, 250)
        if motor_on:
            strength = set_strength(arduino, strength)
        else:
            print(f"Strength saved as {strength}. Toggle motor ON to apply vibration.")
        save_current_settings(settings_callback, strength, on_time, off_time)
    elif command == "n":
        on_time = set_on_time(arduino, value)
        save_current_settings(settings_callback, strength, on_time, off_time)
    elif command == "m":
        off_time = set_off_time(arduino, value)
        save_current_settings(settings_callback, strength, on_time, off_time)
    else:
        print("Unknown command. Use p, q, s, n, m, or all.")

    return strength, on_time, off_time, motor_on, False


def read_nonblocking_command(command_buffer, stop_event=None, kill_button=KILL_BUTTON):
    while msvcrt.kbhit():
        char = msvcrt.getwch()

        if char.lower() == kill_button.lower() and stop_event is not None:
            stop_event.set()
            print()
            print("Kill requested. Stopping all peripherals and processing clipped recordings.")
            return "", "__kill__"

        if char in ("\r", "\n"):
            print()
            return "", command_buffer.strip()

        if char == "\b":
            if command_buffer:
                command_buffer = command_buffer[:-1]
                print("\b \b", end="", flush=True)
            continue

        command_buffer += char
        print(char, end="", flush=True)

    return command_buffer, None


def print_available_serial_ports():
    print("Available serial ports:")

    ports = list(list_ports.comports())
    if not ports:
        print("  No serial ports detected.")
    else:
        for port in ports:
            print(f"  {port.device}: {port.description}")


def run_manual_motor_loop(arduino, strength, on_time, off_time, settings_callback=None):
    motor_on = True

    while True:
        print_menu(strength, on_time, off_time, motor_on)
        user_input = input("> ").strip()
        strength, on_time, off_time, motor_on, should_quit = handle_user_command(
            arduino,
            user_input,
            strength,
            on_time,
            off_time,
            motor_on,
            settings_callback,
        )

        if should_quit:
            break


def run_timed_motor_loop(arduino, strength, on_time, off_time, duration_seconds, stop_event=None, kill_button=KILL_BUTTON, settings_callback=None):
    motor_on = True
    command_buffer = ""
    end_time = time.monotonic() + duration_seconds

    print_menu(strength, on_time, off_time, motor_on, end_time - time.monotonic(), kill_button)
    print("> ", end="", flush=True)

    killed = False

    while time.monotonic() < end_time:
        if stop_event is not None and stop_event.is_set():
            killed = True
            break

        command_buffer, command = read_nonblocking_command(command_buffer, stop_event, kill_button)

        if command is not None:
            if command == "__kill__":
                killed = True
                break

            strength, on_time, off_time, motor_on, should_quit = handle_user_command(
                arduino,
                command,
                strength,
                on_time,
                off_time,
                motor_on,
                settings_callback,
            )

            if should_quit:
                return

            print_menu(strength, on_time, off_time, motor_on, end_time - time.monotonic(), kill_button)
            print("> ", end="", flush=True)

        time.sleep(0.05)

    print()
    stop_motor(arduino)
    if killed:
        print("Motor stopped by kill request.")
    else:
        print("Motor record time ended. Motor stopped.")


def run_motor_driver(serial_port, baud_rate, strength, on_time, off_time, duration_seconds=None, stop_event=None, kill_button=KILL_BUTTON, settings_callback=None):
    try:
        with serial.Serial(serial_port, baud_rate, timeout=1) as arduino:
            time.sleep(2)  # Give the Arduino time to reset after opening serial.
            strength, on_time, off_time = send_all_settings(
                arduino,
                strength,
                on_time,
                off_time,
            )

            if duration_seconds is None:
                run_manual_motor_loop(arduino, strength, on_time, off_time, settings_callback)
            else:
                run_timed_motor_loop(arduino, strength, on_time, off_time, duration_seconds, stop_event, kill_button, settings_callback)
    except serial.SerialException as exc:
        print(f"Could not open {serial_port}: {exc}")
        print()
        print_available_serial_ports()
