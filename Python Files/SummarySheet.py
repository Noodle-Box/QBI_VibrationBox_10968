#######################################################################################################################
# File: Summary Sheet
# Project: Time Locked Box Simulator
# Research Group: Suarez Lab, Queensland Brain Institute, UQ
#
# Author: Tevyn Vergara
# Date: 08/07/2026

############################################ Standard Library Imports ################################################
from pathlib import Path
import openpyxl

################################################### Configuration #####################################################

SUMMARY_SHEET_PATH = Path(__file__).resolve().parent.parent / "Summary Sheet.xlsx"

HEADERS = [
    "Timestamp",
    "Recording Time (s)",
    "Speaker",
    "Speaker Freq (Hz)",
    "Speaker On Time (s)",
    "Speaker Off Time (s)",
    "Speaker On Time Log",
    "Speaker Off Time Log",
    "Speaker Pulses (Real Time)",
    "Speaker Pulses (In Simulation time)",
    "Camera",
    "View Mode",
    "Microphone",
    "Motor",
    "Motor Strength",
    "Motor On Time (s)",
    "Motor Off Time (s)",
    "Motor Pulses (Real Time)",
    "Motor Pulses (In Simulation time)",
    "FLAC Out",
    "h265 Out",
    "MP4 Out",
]

################################################### Functionality ####################################################


# Creates the Summary Sheet Excel file with headers if it does not already exist.
def ensure_summary_sheet(path=SUMMARY_SHEET_PATH):
    if path.exists():
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Runs"
    ws.append(HEADERS)
    wb.save(path)


# Appends one row to the Summary Sheet for the completed run.
# run is a Main.py RunResult; this detects output files and filters pulse logs to ON-events itself.
def append_run(run, path=SUMMARY_SHEET_PATH):
    ensure_summary_sheet(path)
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    def log_str(values):
        return ", ".join(str(v) for v in values) if values else ""

    audio_path = run.recording_paths["audio"]
    video_path = run.recording_paths["video"]

    flac_out = audio_path is not None and Path(audio_path).exists()
    if isinstance(video_path, dict):
        h265_out = any(Path(p).exists() for p in video_path.values())
    else:
        h265_out = video_path is not None and Path(video_path).exists()
    mp4_out = len(run.mp4_paths) > 0

    # Extract ON-transition timestamps; elapsed is relative to run_start_time.
    speaker_pulse_ons = [e for e in run.speaker_pulse_log if e["event"] == "ON"]
    speaker_pulse_wall = [e["wall"] for e in speaker_pulse_ons]
    speaker_pulse_elapsed = [round(e["mono"] - run.run_start_time, 2) for e in speaker_pulse_ons]

    motor_pulse_ons = [e for e in run.motor_pulse_log if e["event"] == "ON"]
    motor_pulse_wall = [e["wall"] for e in motor_pulse_ons]
    motor_pulse_elapsed = [round(e["mono"] - run.run_start_time, 2) for e in motor_pulse_ons]

    row = [
        run.run_timestamp,
        run.actual_run_time,
        "ON" if run.peripheral_settings["speaker_enabled"] else "OFF",
        run.speaker_freq,
        run.speaker_on,
        run.speaker_off,
        log_str(run.speaker_on_log),
        log_str(run.speaker_off_log),
        log_str(speaker_pulse_wall),
        log_str(speaker_pulse_elapsed),
        "ON" if run.peripheral_settings["camera_enabled"] else "OFF",
        run.camera_settings["view"],
        "ON" if run.peripheral_settings["mic_enabled"] else "OFF",
        "ON" if run.peripheral_settings["motor_enabled"] else "OFF",
        log_str(run.motor_strength_log),
        log_str(run.motor_on_time_log),
        log_str(run.motor_off_time_log),
        log_str(motor_pulse_wall),
        log_str(motor_pulse_elapsed),
        "TRUE" if flac_out else "FALSE",
        "TRUE" if h265_out else "FALSE",
        "TRUE" if mp4_out else "FALSE",
    ]

    ws.append(row)
    wb.save(path)
    print(f"Run recorded in Summary Sheet: {path}")
