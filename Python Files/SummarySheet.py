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

SUMMARY_SHEET_PATH = Path(__file__).resolve().parent / "Summary Sheet.xlsx"

HEADERS = [
    "Timestamp",
    "Recording Time (s)",
    "Speaker",
    "Speaker Freq (Hz)",
    "Speaker On Time (s)",
    "Speaker Off Time (s)",
    "Speaker Pulses (Real Time)",
    "Speaker Pulses (In Simulation time)",
    "Camera",
    "View Mode",
    "Microphone",
    "Motor",
    "Motor Strength",
    "Motor On Time (ms)",
    "Motor Off Time (ms)",
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
# data keys: timestamp, recording_time, speaker_enabled, speaker_freq, speaker_on, speaker_off,
#             speaker_pulse_wall, speaker_pulse_elapsed, camera_enabled, camera_view, mic_enabled,
#             motor_enabled, motor_strength_log, motor_on_time_log, motor_off_time_log,
#             motor_pulse_wall, motor_pulse_elapsed, flac_out, h265_out, mp4_out
def append_run(data, path=SUMMARY_SHEET_PATH):
    ensure_summary_sheet(path)
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    def log_str(values):
        return ", ".join(str(v) for v in values) if values else ""

    row = [
        data.get("timestamp", ""),
        data.get("recording_time", ""),
        "ON" if data.get("speaker_enabled") else "OFF",
        data.get("speaker_freq", ""),
        data.get("speaker_on", ""),
        data.get("speaker_off", ""),
        log_str(data.get("speaker_pulse_wall", [])),
        log_str(data.get("speaker_pulse_elapsed", [])),
        "ON" if data.get("camera_enabled") else "OFF",
        data.get("camera_view", ""),
        "ON" if data.get("mic_enabled") else "OFF",
        "ON" if data.get("motor_enabled") else "OFF",
        log_str(data.get("motor_strength_log", [])),
        log_str(data.get("motor_on_time_log", [])),
        log_str(data.get("motor_off_time_log", [])),
        log_str(data.get("motor_pulse_wall", [])),
        log_str(data.get("motor_pulse_elapsed", [])),
        "TRUE" if data.get("flac_out") else "FALSE",
        "TRUE" if data.get("h265_out") else "FALSE",
        "TRUE" if data.get("mp4_out") else "FALSE",
    ]

    ws.append(row)
    wb.save(path)
    print(f"Run recorded in Summary Sheet: {path}")
