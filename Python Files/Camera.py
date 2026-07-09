#######################################################################################################################
# File: Camera Driver
# Project: Time Locked Box Simulator
# Research Group: Suarez Lab, Queensland Brain Institute, UQ
#
# Author: Tevyn Vergara
# Date: 01/06/2026

############################################ Standard Library Imports ################################################
import json
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import cv2
import depthai as dai
################################################### Functionality ####################################################

SETTINGS_PATH = Path(__file__).resolve().parent / "camera_settings.json"
RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"


# Returns default camera JSON settings. Used by load_settings() and Main.py --set-all on.
def default_settings():
    return {
        "device_ip": None,
        "record_video": True,
        "view": "center",
    }


# Loads camera_settings.json and fills missing keys. Used by Main.py before printing info or running camera.
def load_settings():
    if not SETTINGS_PATH.exists():
        settings = default_settings()
        save_settings(settings)
        return settings

    with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    defaults = default_settings()
    defaults.update(settings)
    if defaults != settings:
        save_settings(defaults)

    return defaults


# Writes the camera_settings.json. Used in camera config and Main.py to store and hold user defined parameters.
def save_settings(settings):
    with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


# Builds the timestamp stem for camera output files
def get_recording_stem():
    return datetime.now().strftime("Recording_%H%M%S_%d_%m")


# Enables or disables camera video recording in JSON.
def set_record_video(settings, enabled):
    settings["record_video"] = enabled
    save_settings(settings)
    print(f"Camera video recording set to {'on' if enabled else 'off'}.")
    return True


# Saves the OAK camera IP in JSON format
def set_device_ip(settings, device_ip):
    settings["device_ip"] = device_ip.strip() if device_ip else None
    save_settings(settings)
    print(f"Camera IP set to {settings['device_ip'] or 'auto-discover'}.")
    return True


# Saves the selected camera view in JSON
def set_camera_view(settings, view):
    settings["view"] = view
    save_settings(settings)
    print(f"Camera view set to {view}.")
    return True


# Gets a stable display label for a DepthAI device --> list_cameras().
def get_device_label(device_info):
    device_id = device_info.getDeviceId()
    return device_id or device_info.name


# Lists available OAK cameras in the terminal --> list-cameras()
def list_cameras():
    devices = []
    seen_labels = set()

    for device_info in dai.Device.getAllAvailableDevices():
        label = get_device_label(device_info)
        seen_labels.add(label)
        devices.append(device_info)

    for device_info in dai.Device.getAllConnectedDevices():
        label = get_device_label(device_info)
        if label not in seen_labels:
            seen_labels.add(label)
            devices.append(device_info)

    if not devices:
        print("No OAK cameras found.")
        print()
        print("If OAK Viewer can see the camera, copy the camera IP from OAK Viewer and run:")
        print("  python .\\Main.py --camera --set-camera-ip <camera-ip>")
        return

    print("Available OAK cameras:")
    for index, device_info in enumerate(devices):
        print(
            f"  No.: {index} | "
            f"Name/IP: {device_info.name} | "
            f"Device ID: {device_info.getDeviceId() or 'unknown'} | "
            f"State: {device_info.state.name}"
        )


# Sets the center RGB camera output stream
def create_rgb_output(pipeline, width, height, fps):
    color_camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    output_capability = dai.ImgFrameCapability()
    output_capability.size.fixed((width, height))
    output_capability.fps.fixed(fps)

    # Stream for live preview
    preview_output = color_camera.requestOutput(output_capability, True)

    # Stream for recording - ImageManip converts to NV12 which VideoEncoder requires
    encoded_output = color_camera.requestOutput(output_capability, True)
    manip = pipeline.create(dai.node.ImageManip)
    manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    manip.setMaxOutputFrameSize(width * height * 3 // 2)
    encoded_output.link(manip.inputImage)
    encoder = pipeline.create(dai.node.VideoEncoder)
    encoder.setDefaultProfilePreset(fps, dai.VideoEncoderProperties.Profile.H265_MAIN)
    manip.out.link(encoder.input)

    encoded_queue = encoder.bitstream.createOutputQueue(maxSize=60, blocking=False)

    return preview_output, encoded_queue


# Creates a mono camera output stream for left or right sockets
def create_mono_output(pipeline, socket, width, height, fps):

    mono_camera = pipeline.create(dai.node.Camera).build(socket)
    output_capability = dai.ImgFrameCapability()
    output_capability.size.fixed((width, height))
    output_capability.fps.fixed(fps)

    # Stream for live preview
    preview_output = mono_camera.requestOutput(output_capability, True)

    # Stream for recording - ImageManip converts to NV12 which VideoEncoder requires
    encoded_output = mono_camera.requestOutput(output_capability, True)
    manip = pipeline.create(dai.node.ImageManip)
    manip.initialConfig.setFrameType(dai.ImgFrame.Type.YUV400p)
    manip.setMaxOutputFrameSize(width * height)
    encoded_output.link(manip.inputImage)
    encoder = pipeline.create(dai.node.VideoEncoder)
    encoder.setDefaultProfilePreset(fps, dai.VideoEncoderProperties.Profile.H265_MAIN)
    manip.out.link(encoder.input)

    encoded_queue = encoder.bitstream.createOutputQueue(maxSize=60, blocking=False)

    return preview_output, encoded_queue

# Builds the DepthAI output stream map for center, left, right, or stereo view
def create_camera_outputs(pipeline, view, width, height, fps):
    if view == "center":
        preview, enc_name = create_rgb_output(pipeline, width, height, fps)
        return {"center": preview}, {"center": enc_name}
    
    if view == "left":
        preview, enc_name = create_mono_output(pipeline, dai.CameraBoardSocket.CAM_B, width, height, fps)
        return {"left": preview}, {"left": enc_name}

    if view == "right":
        preview, enc_name = create_mono_output(pipeline, dai.CameraBoardSocket.CAM_C, width, height, fps)
        return {"right": preview}, {"right": enc_name}

    if view == "stereo":
        left_preview, left_enc_name = create_mono_output(pipeline, dai.CameraBoardSocket.CAM_B, width, height, fps)
        right_preview, right_enc_name = create_mono_output(pipeline, dai.CameraBoardSocket.CAM_C, width, height, fps)
        return {"left": left_preview, "right": right_preview}, {"left": left_enc_name, "right": right_enc_name}
    raise ValueError(f"Unknown camera view: {view}")


# Converts grayscale mono frames to BGR for display/writing. OpenCV stuff
def ensure_bgr(frame):
    if len(frame.shape) == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    return frame


# Reads the next frame for the selected view
def get_preview_frame(view, queues):
    if view == "stereo":
        left = ensure_bgr(queues["left"].get().getCvFrame())
        right = ensure_bgr(queues["right"].get().getCvFrame())
        return cv2.hconcat([left, right])

    queue = queues[view]
    return ensure_bgr(queue.get().getCvFrame())

# Returns left and right frames seperately for split viewing
def get_stereo_frames(queues):
    left_frame = ensure_bgr(queues["left"].get().getCvFrame())
    right_frame = ensure_bgr(queues["right"].get().getCvFrame())
    return left_frame, right_frame

# Runs live preview and optional recording for the configured OAK camera
def run_camera(width, height, fps, duration_seconds, file_format, device_ip, record_video, view, window_name, stop_event, result_queue=None, ready_event=None):
    
    # Build directly as a h265 file for immediate writing
    recording_stem = get_recording_stem()

    # File extension handler
    ext = file_format.lower()

    # Seperate the paths for stereo mode recording
    if view == "stereo":
        video_path = {
            "left": RECORDINGS_DIR / f"{recording_stem}_left.{ext}",
            "right": RECORDINGS_DIR / f"{recording_stem}_right.{ext}"
        }
    else:
        # Left, Right or Center viewing
        video_path = RECORDINGS_DIR / f"{recording_stem}.{ext}"

    # Use saved IP OR camera auto-discover
    device_info = dai.DeviceInfo(device_ip) if device_ip else None
    if device_ip:
        print(f"Connecting to OAK camera at IP: {device_ip}...buffffffffffering")

    print(f"Starting camera preview with view: {view}. Press q to stop stimulation entirely")

    device_args = [device_info] if device_info else []
    saved_video_path = None

    with dai.Pipeline(dai.Device(*device_args)) as pipeline:
        # Build two sets of outputs: one for live preview, one for recording
        # 1. preview_outputs - raw frames routed to OpenCV display
        # 2. encoded_outputs - h265 encoded frames routed to file writing

        preview_outputs, encoded_outputs = create_camera_outputs(pipeline, view, width, height, fps)

        # Create host-side queues to receieve raw frames for live preview
        preview_queues = {name: output.createOutputQueue(maxSize = 4, blocking = False) for name, output in preview_outputs.items()}

        # Create host-side queues to receive encoded H265 packets from camera for direct file writing
        encoded_queues = encoded_outputs

        # Open output file for binary writing before recording loop begins
        encoded_file = None
        if record_video:
            if view == "stereo":
                RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
                encoded_file = {
                    "left": open(video_path["left"], "wb"),
                    "right": open(video_path["right"], "wb")
                }
                print(f"Recording camera video to: {video_path['left']} and {video_path['right']} ... stand by...")
            else: 
                video_path.parent.mkdir(parents=True, exist_ok=True)
                encoded_file = open(video_path, "wb")
                print(f"Recording camera video to: {video_path} ... stand by...")
        
        # Start the DepthAI pipeline and record the start time for duration tracking
        pipeline.start()
        if ready_event is not None:
            ready_event.set()
        start_time = time.monotonic()

        try:
            while True:

                # Handle stereo view by seperating left and right frames for display
                if view == "stereo":
                    left_frame, right_frame = get_stereo_frames(preview_queues)
                    cv2.imshow("OAK-D Left", left_frame)
                    cv2.imshow("OAK-D Right", right_frame)
                else:
                    # For left, right, or center view, just display the single frame
                    frame = get_preview_frame(view, preview_queues)
                    cv2.imshow(window_name, frame)

                # Drain all encoded packets that arrived in last loop and write them directly to .h265
                if encoded_file is not None:
                    for stream_name, temp in encoded_queues.items():
                        file_handle = encoded_file[stream_name] if isinstance(encoded_file, dict) else encoded_file
                        packet = temp.tryGet()
                        while packet is not None:
                            file_handle.write(packet.getData())
                            packet = temp.tryGet()
                
                # Check for user input to stop recording or exit
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("Stopping camera preview and recording...")
                    break

                if duration_seconds is not None and (time.monotonic() - start_time) >= duration_seconds:
                    break

                if stop_event is not None and stop_event.is_set():
                    break

        finally:
            if encoded_file is not None:
                if isinstance(encoded_file, dict):
                    for file_handle in encoded_file.values():
                        file_handle.close()
                    saved_video_path = video_path
                    print(f"Camera video saved to: {video_path['left']} and {video_path['right']}")
                else:
                    encoded_file.close()
                    saved_video_path = video_path
                    print(f"Camera video saved to: {saved_video_path}")

            try:
                if view == "stereo":
                    cv2.destroyWindow("OAK-D Left")
                    cv2.destroyWindow("OAK-D Right")
                else:
                    cv2.destroyWindow(window_name)
            except cv2.error:
                pass

            # Signal the saved path before the with-block exits so the result survives a DepthAI shutdown crash.
            if result_queue is not None:
                result_queue.put(saved_video_path if record_video else None)

    cv2.destroyAllWindows()
    if record_video:
        return saved_video_path
    
    return None

# Top-level camera subprocess entry point. Must be top-level (not nested) to be picklable on Windows.
# Puts the saved video path into result_queue from inside run_camera's finally block, before
# DepthAI closes the device — so the result survives a native crash on device shutdown.
def run_camera_subprocess(record_time, width, height, fps, file_format, stop_event, result_queue, ready_event=None):
    camera_settings = load_settings()
    try:
        run_camera(
            width=width,
            height=height,
            fps=fps,
            duration_seconds=record_time,
            file_format=file_format,
            device_ip=camera_settings["device_ip"],
            record_video=camera_settings["record_video"],
            view=camera_settings["view"],
            window_name="OAK-D Camera",
            stop_event=stop_event,
            result_queue=result_queue,
            ready_event=ready_event,
        )
    except Exception as exc:
        print(f"Camera stopped with an error: {exc}")
        result_queue.put(None)
        if ready_event is not None:
            ready_event.set()


# Merges recorded camera video with microphone audio into MP4 with ffmpeg; used after camera and mic finish.
def merge_with_audio(video_path, audio_path, fps):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ffmpeg was not found, so audio/video merge was skipped.")
        return None

    if video_path is None or audio_path is None:
        print("Audio/video merge skipped because the video or audio file was not created.")
        return None

    output_path = RECORDINGS_DIR / f"{Path(video_path).stem}.mp4"

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f", "hevc",
        "-framerate", str(fps),
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-tag:v", "hvc1",
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "1",
        "-shortest",
        str(output_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        print(f"Audio/video merge failed: {exc}")
        if exc.stderr:
            print(exc.stderr)
        return None

    print(f"Saved merged audio/video MP4: {output_path}")
    print("Note: merged MP4 audio is downsampled to 48 kHz. The standalone audio recording keeps the original microphone data.")
    return output_path


# Prints camera settings to terminal --> --info
def print_camera_info(settings, width, height, fps, default_duration, file_format):
    duration_seconds = default_duration

    print(
        f"Camera IP: {settings['device_ip'] or 'Auto-discover'} \n"
        f"Resolution: {width}x{height} \n"
        f"View: {settings['view']} \n"
        f"FPS: {fps} \n"
        f"Duration: {duration_seconds} s \n"
        f"Format: {file_format} \n"
        f"Record Video: {'On' if settings['record_video'] else 'Off'} \n"
        f"Location: {RECORDINGS_DIR}"
    )


# Registers camera-related CLI arguments, used in Main.py for argument parsing
def add_camera_arguments(parser):
    parser.add_argument("--camera", action="store_true", help="Configure or target camera settings.")
    parser.add_argument("--list-cameras", action="store_true", help="List available OAK cameras.")
    parser.add_argument("--set-camera-ip", help="Save the OAK-D PoE camera IP address.")
    parser.add_argument("--set-camera-record", choices=["on", "off"], help="Enable or disable camera video recording.")
    parser.add_argument(
        "--set-view",
        dest="set_view",
        choices=["center", "left", "right", "stereo"],
        help="Save camera view mode.",
    )


# Handles camera CLI actions without starting a recording run
def handle_camera_args(args, width, height, fps, default_duration, file_format):
    settings = load_settings()

    if args.list_cameras:
        list_cameras()
        return True

    settings_changed = False
    if args.set_camera_ip is not None:
        settings_changed = set_device_ip(settings, args.set_camera_ip) or settings_changed

    if args.set_camera_record is not None:
        settings_changed = set_record_video(settings, args.set_camera_record == "on") or settings_changed

    if args.set_view is not None:
        settings_changed = set_camera_view(settings, args.set_view) or settings_changed

    if settings_changed:
        print_camera_info(settings, width, height, fps, default_duration, file_format)
        return True

    return False
