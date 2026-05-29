import json
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import cv2
import depthai as dai


SETTINGS_PATH = Path(__file__).resolve().parent / "camera_settings.json"
RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"


def default_settings():
    return {
        "device_ip": None,
        "record_video": True,
        "view": "center",
    }


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


def save_settings(settings):
    with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


def get_recording_stem():
    return datetime.now().strftime("Recording_%H%M%S_%d_%m")


def set_record_video(settings, enabled):
    settings["record_video"] = enabled
    save_settings(settings)
    print(f"Camera video recording set to {'on' if enabled else 'off'}.")
    return True


def set_device_ip(settings, device_ip):
    settings["device_ip"] = device_ip.strip() if device_ip else None
    save_settings(settings)
    print(f"Camera IP set to {settings['device_ip'] or 'auto-discover'}.")
    return True


def set_camera_view(settings, view):
    settings["view"] = view
    save_settings(settings)
    print(f"Camera view set to {view}.")
    return True


def get_device_label(device_info):
    device_id = device_info.getDeviceId()
    return device_id or device_info.name


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


def create_rgb_output(pipeline, width, height, fps):
    color_camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    output_capability = dai.ImgFrameCapability()
    output_capability.size.fixed((width, height))
    output_capability.fps.fixed(fps)
    return color_camera.requestOutput(output_capability, True)


def create_mono_output(pipeline, socket, width, height, fps):
    mono_camera = pipeline.create(dai.node.Camera).build(socket)
    output_capability = dai.ImgFrameCapability()
    output_capability.size.fixed((width, height))
    output_capability.fps.fixed(fps)
    return mono_camera.requestOutput(output_capability, True)


def create_camera_outputs(pipeline, view, width, height, fps):
    if view == "center":
        return {
            "center": create_rgb_output(pipeline, width, height, fps),
        }

    if view == "left":
        return {
            "left": create_mono_output(pipeline, dai.CameraBoardSocket.CAM_B, width, height, fps),
        }

    if view == "right":
        return {
            "right": create_mono_output(pipeline, dai.CameraBoardSocket.CAM_C, width, height, fps),
        }

    if view == "stereo":
        return {
            "left": create_mono_output(pipeline, dai.CameraBoardSocket.CAM_B, width, height, fps),
            "right": create_mono_output(pipeline, dai.CameraBoardSocket.CAM_C, width, height, fps),
        }

    raise ValueError(f"Unknown camera view: {view}")


def ensure_bgr(frame):
    if len(frame.shape) == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    return frame


def get_preview_frame(view, queues):
    if view == "stereo":
        left = ensure_bgr(queues["left"].get().getCvFrame())
        right = ensure_bgr(queues["right"].get().getCvFrame())
        return cv2.hconcat([left, right])

    queue = queues[view]
    return ensure_bgr(queue.get().getCvFrame())


def create_video_writer(path, fps, width, height):
    path.parent.mkdir(parents=True, exist_ok=True)
    codec_by_format = {
        "avi": "XVID",
        "mp4": "mp4v",
    }
    codec = codec_by_format.get(path.suffix.lower().lstrip("."), "XVID")
    fourcc = cv2.VideoWriter_fourcc(*codec)
    video_writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))

    if video_writer.isOpened():
        return video_writer, path

    video_writer.release()

    fallback_path = path.with_suffix(".mp4")
    fallback_fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fallback_writer = cv2.VideoWriter(str(fallback_path), fallback_fourcc, fps, (width, height))

    if fallback_writer.isOpened():
        print(f"Could not open AVI video writer. Recording MP4 instead: {fallback_path}")
        return fallback_writer, fallback_path

    fallback_writer.release()
    raise RuntimeError("Could not open an OpenCV video writer for AVI or MP4.")


def convert_video_to_h265(input_path, output_path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ffmpeg was not found, so H.265 export was skipped.")
        print(f"Camera video saved at: {input_path}")
        return input_path

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-c:v",
        "libx265",
        "-x265-params",
        "log-level=error",
        "-an",
        "-f",
        "hevc",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    input_path.unlink(missing_ok=True)
    return output_path


def run_camera(
    width,
    height,
    fps,
    duration_seconds,
    file_format,
    device_ip=None,
    record_video=True,
    view="center",
    window_name="OAK-D RGB",
    stop_event=None,
):
    recording_stem = get_recording_stem()
    output_format = file_format.lower()
    video_path = RECORDINGS_DIR / f"{recording_stem}.{output_format}"
    writer_path = video_path
    video_writer = None
    output_width = width * 2 if view == "stereo" else width
    output_height = height

    if record_video:
        if output_format == "h265":
            writer_path = RECORDINGS_DIR / f"{recording_stem}_capture.avi"

        video_writer, writer_path = create_video_writer(writer_path, fps, output_width, output_height)
        print(f"Recording camera video to: {video_path}")

    print(f"Starting {view} camera preview. Press q in the camera window to close preview.")

    device_info = dai.DeviceInfo(device_ip) if device_ip else None

    if device_ip:
        print(f"Connecting to OAK camera at {device_ip}...")

    device_args = [device_info] if device_info else []
    with dai.Pipeline(dai.Device(*device_args)) as pipeline:
        outputs = create_camera_outputs(pipeline, view, width, height, fps)
        queues = {
            name: output.createOutputQueue(maxSize=4, blocking=False)
            for name, output in outputs.items()
        }
        pipeline.start()
        start_time = time.monotonic()

        while True:
            frame = get_preview_frame(view, queues)

            if video_writer is not None:
                video_writer.write(frame)

            cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

            if duration_seconds is not None and time.monotonic() - start_time >= duration_seconds:
                break

            if stop_event is not None and stop_event.is_set():
                break

    if video_writer is not None:
        video_writer.release()

    cv2.destroyWindow(window_name)

    if record_video:
        if output_format == "h265":
            try:
                video_path = convert_video_to_h265(writer_path, video_path)
            except subprocess.CalledProcessError as exc:
                print(f"H.265 export failed: {exc}")
                if exc.stderr:
                    print(exc.stderr)
                video_path = writer_path

        print(f"Saved camera video: {video_path}")
        return video_path

    return None


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
