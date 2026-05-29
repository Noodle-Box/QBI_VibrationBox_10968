import json
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
    }


def load_settings():
    if not SETTINGS_PATH.exists():
        return default_settings()

    with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    defaults = default_settings()
    defaults.update(settings)
    return defaults


def save_settings(settings):
    with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)


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


def run_camera(
    width,
    height,
    fps,
    duration_seconds,
    file_format,
    device_ip=None,
    record_video=True,
    window_name="OAK-D RGB",
):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = RECORDINGS_DIR / f"oak_rgb_{timestamp}.{file_format.lower()}"
    video_writer = None

    if record_video:
        video_writer, video_path = create_video_writer(video_path, fps, width, height)
        print(f"Recording camera video to: {video_path}")

    print("Starting camera preview. Press q in the camera window to close preview.")

    device_info = dai.DeviceInfo(device_ip) if device_ip else None

    if device_ip:
        print(f"Connecting to OAK camera at {device_ip}...")

    device_args = [device_info] if device_info else []
    with dai.Pipeline(dai.Device(*device_args)) as pipeline:
        rgb_output = create_rgb_output(pipeline, width, height, fps)
        rgb_queue = rgb_output.createOutputQueue(maxSize=4, blocking=False)
        pipeline.start()
        start_time = time.monotonic()

        while True:
            frame_packet = rgb_queue.get()
            frame = frame_packet.getCvFrame()

            if video_writer is not None:
                video_writer.write(frame)

            cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

            if duration_seconds is not None and time.monotonic() - start_time >= duration_seconds:
                break

    if video_writer is not None:
        video_writer.release()

    cv2.destroyWindow(window_name)

    if record_video:
        print(f"Saved camera video: {video_path}")
        return video_path

    return None


def print_camera_info(settings, width, height, fps, default_duration, file_format):
    duration_seconds = default_duration

    print(
        f"Camera IP: {settings['device_ip'] or 'Auto-discover'} \n"
        f"Resolution: {width}x{height} \n"
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

    if settings_changed:
        print_camera_info(settings, width, height, fps, default_duration, file_format)
        return True

    return False
