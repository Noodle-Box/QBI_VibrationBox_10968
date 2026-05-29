# QBI Vibration Box 10968

Python-controlled vibration box project with:

- Arduino motor-driver firmware built with PlatformIO
- Python motor control over serial
- Python ultrasonic microphone recording
- Python OAK-D PoE camera preview and video recording

## Setup

1. Clone or copy this repository.
2. Install Python.
3. Install VSCode. When prompted, install the recommended Python extensions.
4. Install required Python packages:

```powershell
cd "Python Files"
python -m pip install pyserial sounddevice numpy depthai opencv-python
```

5. Install `ffmpeg`, which is required for FLAC audio export, H.265 video export, MP3 preview export, and merged camera/audio video:

```powershell
winget install Gyan.FFmpeg
ffmpeg --version
```

If `ffmpeg --version` is not recognized right after install, restart PowerShell or the VSCode terminal.

Recommended VSCode extensions for the Python-side workflow:

- Python (`ms-python.python`)
- Pylance (`ms-python.vscode-pylance`)
- Python Debugger (`ms-python.debugpy`)

## Arduino Firmware

Open the PlatformIO project:

```text
Arduino Files\Motor Driver - Vibration Box
```

Build and upload the firmware to the Arduino board.

## Python Use

From the Python folder:

```powershell
cd "Python Files"
```

List Pettersson microphone devices:

```powershell
python .\Main.py --list-devices --filter "Pettersson"
```

Configure peripherals:

```powershell
python .\Main.py --set-motor on --set-mic on --set-camera on
python .\Main.py --set-time 60
python .\Main.py --motor --set-port COM6 --set-strength 50 --set-on 200 --set-off 500
python .\Main.py --mic --set-device 15 --set-format flac
python .\Main.py --camera --set-camera-record on
```

To export an MP3 microphone preview instead of FLAC:

```powershell
python .\Main.py --mic --set-format mp3
```

List OAK cameras:

```powershell
python .\Main.py --list-cameras
```

If the OAK-D PoE camera appears in OAK Viewer but not in Python discovery, copy its IP address from OAK Viewer and save it manually:

```powershell
python .\Main.py --camera --set-camera-ip 169.254.x.x
```

Check current configuration:

```powershell
python .\Main.py --info
```

Run enabled peripherals:

```powershell
python .\Main.py
```

During runtime:

```text
p             toggle motor vibration on/off
s <30-250>    set vibration strength
n <ms>        set motor on-time
m <ms>        set motor off-time
v             kill all peripherals and process clipped recordings
q             quit the motor early
```

Local hardware settings are saved into JSON files inside `Python Files`. These are ignored by git because COM ports and audio device indices are machine-specific.
