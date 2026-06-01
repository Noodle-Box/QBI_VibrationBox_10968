#####################################################################################################################
# File: Speaker Driver
# Project: Time Locked Box Simulator
# Research Group: Suarez Lab, Queensland Brain Institute, UQ
#
# Author: Tevyn Vergara
# Date: 01/06/2026

############################################ Standard Library Imports ################################################
import time
import numpy as np
import sounddevice as sd

################################################### Functionality ####################################################

def generate_tone(frequency_hz, duration_seconds, sample_rate, amplitude):
    sample_count = int(duration_seconds * sample_rate)
    time_values = np.arange(sample_count) / sample_rate
    tone = np.sin(2 * np.pi * frequency_hz * time_values)
    return (amplitude * tone).astype(np.float32)


def play_tone(tone, sample_rate, stop_event=None):
    chunk_size = max(1, int(sample_rate * 0.05))

    with sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        for start_index in range(0, len(tone), chunk_size):
            if stop_event is not None and stop_event.is_set():
                break

            stream.write(tone[start_index:start_index + chunk_size].reshape(-1, 1))


def wait_until_next_beep(interval_seconds, beep_started_at, stop_event=None):
    next_beep_at = beep_started_at + interval_seconds

    while time.monotonic() < next_beep_at:
        if stop_event is not None and stop_event.is_set():
            break

        time.sleep(0.05)


def run_speaker(duration_seconds, stop_event, frequency_hz, beep_duration_seconds, interval_seconds, sample_rate, amplitude):

    tone = generate_tone(frequency_hz, beep_duration_seconds, sample_rate, amplitude)
    end_time = time.monotonic() + duration_seconds if duration_seconds is not None else None

    print(f"Speaker beep enabled: {frequency_hz} Hz for {beep_duration_seconds} second every {interval_seconds} seconds.")

    while end_time is None or time.monotonic() < end_time:
        if stop_event is not None and stop_event.is_set():
            break

        beep_started_at = time.monotonic()
        play_tone(tone, sample_rate, stop_event)

        if end_time is not None and time.monotonic() >= end_time:
            break

        wait_until_next_beep(interval_seconds, beep_started_at, stop_event)

    sd.stop()
    print("Speaker beep stopped.")
