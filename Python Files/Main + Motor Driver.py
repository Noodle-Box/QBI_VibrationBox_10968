import time
import serial
from serial.tools import list_ports


SERIAL_PORT = "COM6"  # Change this to the Arduino port shown by PlatformIO/Device Manager.
BAUD_RATE = 9600

strength = 50  # Percent, 0-100. Arduino maps this to PWM 0-255.
on_time = 200  # Milliseconds.
off_time = 500  # Milliseconds.


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, int(value)))


def send_command(arduino, command_type, value):
    message = f"{command_type}:{value}\n"
    arduino.write(message.encode("utf-8"))
    arduino.flush()
    print(f"Sent {message.strip()}")


def set_strength(arduino, value):
    global strength

    strength = clamp(value, 0, 100)
    send_command(arduino, "s", strength)


def set_on_time(arduino, value):
    global on_time

    on_time = max(0, int(value))
    send_command(arduino, "n", on_time)


def set_off_time(arduino, value):
    global off_time

    off_time = max(0, int(value))
    send_command(arduino, "f", off_time)


def send_all_settings(arduino):
    set_strength(arduino, strength)
    set_on_time(arduino, on_time)
    set_off_time(arduino, off_time)


def print_menu():
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


def handle_user_command(arduino, user_input):
    parts = user_input.strip().split()
    if not parts:
        return

    command = parts[0].lower()

    if command == "all":
        send_all_settings(arduino)
        return

    if len(parts) != 2:
        print("Use commands like: s 50, n 200, or f 500")
        return

    try:
        value = int(parts[1])
    except ValueError:
        print("Value must be a whole number.")
        return

    if command == "s":
        set_strength(arduino, value)
    elif command == "n":
        set_on_time(arduino, value)
    elif command == "f":
        set_off_time(arduino, value)
    else:
        print("Unknown command. Use s, n, f, all, or q.")


def main():
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as arduino:
            time.sleep(2)  # Give the Arduino time to reset after opening serial.
            send_all_settings(arduino)

            while True:
                print_menu()
                user_input = input("> ").strip()

                if user_input.lower() == "q":
                    set_strength(arduino, 0)
                    break

                handle_user_command(arduino, user_input)
    except serial.SerialException as exc:
        print(f"Could not open {SERIAL_PORT}: {exc}")
        print()
        print("Available serial ports:")

        ports = list(list_ports.comports())
        if not ports:
            print("  No serial ports detected.")
        else:
            for port in ports:
                print(f"  {port.device}: {port.description}")


if __name__ == "__main__":
    main()
