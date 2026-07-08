#####################################################################################################################
# File: Speaker Driver
# Project: Time Locked Box Simulator
# Research Group: Suarez Lab, Queensland Brain Institute, UQ
#
# Author: Tevyn Vergara
# Date: 01/06/2026

############################################ Standard Library Imports ################################################
import queue
import time
from datetime import datetime
import numpy as np
import sounddevice as sd

################################################### Functionality ####################################################

# Generates a sine-wave beap shape with parameters defined in main.py
def generate_tone(frequency_hz, duration_seconds, sample_rate, amplitude):
    sample_count = int(duration_seconds * sample_rate)
    time_values = np.arange(sample_count) / sample_rate
    tone = np.sin(2 * np.pi * frequency_hz * time_values)
    return (amplitude * tone).astype(np.float32)


# Enqueues a speaker parameter command; called from Main.py's keyboard thread.
def send_to_speaker(command_queue, cmd, value):
    command_queue.put((cmd, value))


# Plays a generated tone through the default audio output; used by run_speaker() for each beep.
def play_tone(tone, sample_rate, stop_event=None):
    chunk_size = max(1, int(sample_rate * 0.05))

    with sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        for start_index in range(0, len(tone), chunk_size):
            if stop_event is not None and stop_event.is_set():
                break

            stream.write(tone[start_index:start_index + chunk_size].reshape(-1, 1))


# Main Speaker Function
def run_speaker(duration_seconds, stop_event, frequency_hz, beep_duration_seconds, interval_seconds, sample_rate, amplitude, pulse_callback=None, settings_callback=None, command_queue=None):

    # Pre-generate the tone array and calculate the fixed end time
    tone = generate_tone(frequency_hz, beep_duration_seconds, sample_rate, amplitude)
    end_time = time.monotonic() + duration_seconds if duration_seconds is not None else None

    print(f"Speaker beep enabled: {frequency_hz} Hz for {beep_duration_seconds} second every {interval_seconds} seconds.")

    # Outer loop: one iteration = one full beep + wait cycle
    while end_time is None or time.monotonic() < end_time:
        if stop_event is not None and stop_event.is_set():
            break

        # Fire pulse callback and play the beep
        beep_started_at = time.monotonic()
        if pulse_callback is not None:
            pulse_callback("ON", datetime.now().strftime("%H:%M:%S.%f")[:-3], beep_started_at)
        play_tone(tone, sample_rate, stop_event)
        beep_ended_at = time.monotonic()

        # Stop immediately if run ended during the beep
        if end_time is not None and beep_ended_at >= end_time:
            break

        # Inner loop: wait for interval_seconds of silence after the beep ends, draining command queue each tick
        next_beep_at = beep_ended_at + interval_seconds
        while time.monotonic() < next_beep_at:
            if stop_event is not None and stop_event.is_set():
                break

            # Drain any t/y commands sent from the motor terminal
            if command_queue is not None:
                try:
                    while True:
                        cmd, value = command_queue.get_nowait()

                        # Rebuild the tone array since its length depends on beep duration
                        if cmd == "t":
                            beep_duration_seconds = max(0.1, value)
                            tone = generate_tone(frequency_hz, beep_duration_seconds, sample_rate, amplitude)
                            print(f"\nSpeaker on-time set to {beep_duration_seconds} s")
                            if settings_callback is not None:
                                settings_callback(beep_duration_seconds, interval_seconds)

                        # Recalculate next_beep_at so the new interval takes effect immediately
                        elif cmd == "y":
                            interval_seconds = max(0.1, value)
                            next_beep_at = beep_ended_at + interval_seconds
                            print(f"\nSpeaker off-time set to {interval_seconds} s")
                            if settings_callback is not None:
                                settings_callback(beep_duration_seconds, interval_seconds)

                except queue.Empty:
                    pass

            time.sleep(0.05)

    sd.stop()
    print("Speaker beep stopped.")
