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
import json
import msvcrt
import queue
import time
from datetime import datetime
from pathlib import Path
import serial
from serial.tools import list_ports

################################################### Functionality ####################################################

SETTINGS_PATH = Path(__file__).resolve().parent / "motor_settings.json"


# Loads motor_settings.json and fills missing keys from defaults_fn()'s values
def load_settings(defaults_fn):
    defaults = defaults_fn()
    if SETTINGS_PATH.exists():
        with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
            defaults.update(json.load(settings_file))
    return defaults


# Writes motor_settings.json
def save_settings(settings):
    with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


# Updates one motor setting and saves it
def set_setting(settings, key, value):
    settings[key] = value
    save_settings(settings)
    return True


# Saves live motor settings changed during runtime
def save_live_settings(defaults_fn, strength, on_time, off_time):
    settings = load_settings(defaults_fn)
    settings["strength"] = strength
    settings["on_time"] = on_time
    settings["off_time"] = off_time
    save_settings(settings)


# Motor arguments for setting user parameters
def add_motor_arguments(parser):
    parser.add_argument("--motor", action="store_true", help="Configure or target motor settings.")
    parser.add_argument("--set-strength", type=int, help="With --motor, save raw motor strength, 30-250.")
    parser.add_argument("--set-on", type=float, help="With --motor, save motor on-time in seconds.")
    parser.add_argument("--set-off", type=float, help="With --motor, save motor off-time in seconds.")
    parser.add_argument("--set-port", help="With --motor, save the Arduino serial port.")
    parser.add_argument("--set-baud", type=int, help="With --motor, save the Arduino serial baud rate.")
    parser.add_argument("--motor-port", help="Save the Arduino serial port used by the motor driver.")
    parser.add_argument("--motor-baud", type=int, help="Save the Arduino serial baud rate.")
    parser.add_argument("--motor-strength", type=int, help="Save raw motor strength, 30-250.")
    parser.add_argument("--motor-on-time", type=float, help="Save motor on-time in seconds.")
    parser.add_argument("--motor-off-time", type=float, help="Save motor off-time in seconds.")


# Restricts a numeric value to a minimum and maximum
def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, int(value)))


# Sends one serial command to the Arduino motor firmware
def send_command(arduino, command_type, value):
    message = f"{command_type}:{value}\n"
    arduino.write(message.encode("utf-8"))
    arduino.flush()


# Sets raw motor vibration strength over serial
def set_strength(arduino, value):
    strength = clamp(value, 30, 250)
    send_command(arduino, "s", strength)
    return strength


# Stops vibration by sending strength zero if needed
def stop_motor(arduino):
    send_command(arduino, "s", 0)


# Sets motor on-time over serial; value is in seconds, Arduino receives milliseconds.
def set_on_time(arduino, value):
    on_time = max(0.0, float(value))
    send_command(arduino, "n", int(round(on_time * 1000)))
    return on_time


# Sets motor off-time over serial; value is in seconds, Arduino receives milliseconds.
def set_off_time(arduino, value):
    off_time = max(0.0, float(value))
    send_command(arduino, "m", int(round(off_time * 1000)))
    return off_time


# Sends strength, on-time, and off-time together in one go
def send_all_settings(arduino, strength, on_time, off_time):
    strength = set_strength(arduino, strength)
    on_time = set_on_time(arduino, on_time)
    off_time = set_off_time(arduino, off_time)
    return strength, on_time, off_time


# Persists live motor setting changes through a callback
def save_current_settings(settings_callback, strength, on_time, off_time):
    if settings_callback is not None:
        settings_callback(strength, on_time, off_time)


# Prints the live motor command menu; used by manual and timed motor loops.
def print_menu(strength, on_time, off_time, kill_button, motor_on=True, time_left=None, speaker_enabled=False, speaker_on=None, speaker_off=None):
    print()
    if time_left is not None:
        print(f"Current time left: {max(0, int(time_left))} seconds")
        print()

    print("CMD | Current Setting | Description")
    print()
    print(f"{'p':<3} | {('on' if motor_on else 'off'):<15} | Toggle ON/OFF vibrations without quitting run time")
    print(f"{'s':<3} | {strength:<15} | Vibration strength - strength of motor")
    print(f"{'n':<3} | {f'{on_time} s':<15} | Motor on time")
    print(f"{'m':<3} | {f'{off_time} s':<15} | Motor off time")
    if speaker_enabled:
        on_str  = f"{speaker_on} s"  if speaker_on  is not None else "-"
        off_str = f"{speaker_off} s" if speaker_off is not None else "-"
        print(f"{'t':<3} | {on_str:<15} | Speaker on-time in seconds")
        print(f"{'y':<3} | {off_str:<15} | Speaker off-time in seconds")
    print(f"{kill_button:<3} | {'-':<15} | Kill all peripherals and process clipped recordings")


# Parses one motor command string and applies it over serial; called from the motor queue drain loop.
def apply_motor_command(arduino, user_input, strength, on_time, off_time, motor_on=True, settings_callback=None):

    # Split the terminal input into command and optional value.
    parts = user_input.strip().split()
    if not parts:
        return strength, on_time, off_time, motor_on

    # Read the command letter and route commands that do not need a value.
    command = parts[0].lower()

    if command == "p":
        # Toggle vibration without ending the timed recording run.
        motor_on = not motor_on
        if motor_on:
            set_strength(arduino, strength)
            print("Motor toggled ON.")
        else:
            stop_motor(arduino)
            print("Motor toggled OFF. Run time is still active.")

        return strength, on_time, off_time, motor_on

    if command == "all":
        # Re-send all motor settings and enable latest values.
        if motor_on:
            strength, on_time, off_time = send_all_settings(arduino, strength, on_time, off_time)
        else:
            stop_motor(arduino)
            on_time = set_on_time(arduino, on_time)
            off_time = set_off_time(arduino, off_time)
        save_current_settings(settings_callback, strength, on_time, off_time)
        return strength, on_time, off_time, motor_on

    # Correct user for incorrect command formats
    if len(parts) != 2:
        print("Use commands like: p, s 150, n 200, or m 500")
        return strength, on_time, off_time, motor_on

    # Convert the command value to a float (on/off times accept decimals, strength is rounded later)
    try:
        value = float(parts[1])
    except ValueError:
        print("Value must be a number.")
        return strength, on_time, off_time, motor_on

    # Apply the value to the requested motor setting and save it for --info.
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
        print("Unknown command. Use p, s, n, m, or all.")

    return strength, on_time, off_time, motor_on


# Reads typed terminal input without blocking the timed run
def read_nonblocking_command(command_buffer, stop_event, kill_button):
    while msvcrt.kbhit():

        # Read one available keypress without waiting for the user to press Enter.
        char = msvcrt.getwch()

        # Trigger the shared kill event immediately when kill key is pressed.
        if char.lower() == kill_button.lower() and stop_event is not None:
            stop_event.set()
            print()
            print("Kill requested. Stopping all peripherals and processing clipped recordings.")
            return "", "__kill__"

        # Submit the buffered command when the user presses Enter.
        if char in ("\r", "\n"):
            print()
            return "", command_buffer.strip()

        # Support backspace editing for partially typed commands.
        if char == "\b":
            if command_buffer:
                command_buffer = command_buffer[:-1]
                print("\b \b", end="", flush=True)
            continue

        # Add normal typed characters to the pending command buffer.
        command_buffer += char
        print(char, end="", flush=True)

    # Return the current buffer and no command when no complete input is ready.
    return command_buffer, None


# Prints detected serial ports, used when opening the configured Arduino COM port fails.
def print_available_serial_ports():
    print("Available serial ports:")

    ports = list(list_ports.comports())
    if not ports:
        print("  No serial ports detected.")
    else:
        for port in ports:
            print(f"  {port.device}: {port.description}")


# Runs the motor in interactive-only mode, used by run_motor_driver() when no duration is provided.
def run_manual_motor_loop(arduino, strength, on_time, off_time, kill_button, settings_callback=None):
    motor_on = True

    while True:
        print_menu(strength, on_time, off_time, kill_button, motor_on)
        user_input = input("> ").strip()
        strength, on_time, off_time, motor_on = apply_motor_command(
            arduino,
            user_input,
            strength,
            on_time,
            off_time,
            motor_on,
            settings_callback,
        )


# Drains serial lines from Arduino and fires pulse_callback for P:ON / P:OFF events.
def drain_serial_pulses(arduino, pulse_callback):
    while arduino.in_waiting > 0:
        try:
            line = arduino.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            break
        if line.startswith("P:") and pulse_callback is not None:
            event = line[2:]
            pulse_callback(event, datetime.now().strftime("%H:%M:%S.%f")[:-3], time.monotonic())


# Runs the motor for a fixed duration, draining motor_queue for live parameter updates.
# Keyboard input is handled by Main.py's keyboard thread; motor_state is a shared dict it can read.
def run_timed_motor_loop(arduino, strength, on_time, off_time, duration_seconds, stop_event, kill_button, settings_callback=None, pulse_callback=None, motor_queue=None, motor_state=None):

    motor_on = True
    end_time = time.monotonic() + duration_seconds
    killed = False

    # Keep running until the timer expires or a stop is requested
    while time.monotonic() < end_time:
        if stop_event is not None and stop_event.is_set():
            killed = True
            break

        # Drain any pulse event lines the Arduino sent back this tick
        drain_serial_pulses(arduino, pulse_callback)

        # Apply any motor commands queued by the keyboard thread in Main.py
        if motor_queue is not None:
            try:
                while True:
                    cmd_str = motor_queue.get_nowait()
                    strength, on_time, off_time, motor_on = apply_motor_command(arduino, cmd_str, strength, on_time, off_time, motor_on, settings_callback)
                    if motor_state is not None:
                        motor_state["strength"] = strength
                        motor_state["on_time"] = on_time
                        motor_state["off_time"] = off_time
                        motor_state["motor_on"] = motor_on
            except queue.Empty:
                pass

        time.sleep(0.05)

    # Drain any remaining pulse events before the loop exits
    drain_serial_pulses(arduino, pulse_callback)

    # Always stop motor output when the timed loop exits
    print()
    stop_motor(arduino)
    if killed:
        print("Motor stopped by kill request.")
    else:
        print("Motor record time ended. Motor stopped.")

# Main Motor Driver function
def run_motor_driver(serial_port, baud_rate, strength, on_time, off_time, kill_button, duration_seconds=None, stop_event=None, settings_callback=None, pulse_callback=None, motor_queue=None, motor_state=None):
    try:
        # Attempt to open configured serial port and send initial settings
        with serial.Serial(serial_port, baud_rate, timeout=1) as arduino:
            time.sleep(2)  # Give the Arduino time to reset after opening serial.
            strength, on_time, off_time = send_all_settings(arduino, strength, on_time, off_time)

            if duration_seconds is None:
                run_manual_motor_loop(arduino, strength, on_time, off_time, kill_button, settings_callback)
            else:
                run_timed_motor_loop(arduino, strength, on_time, off_time, duration_seconds, stop_event, kill_button, settings_callback, pulse_callback, motor_queue, motor_state)
    except serial.SerialException as exc:
        print(f"Could not open {serial_port}: {exc}")
        print()
        print_available_serial_ports()
