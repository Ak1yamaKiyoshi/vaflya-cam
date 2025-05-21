import mmap
import sys
import time
import numpy as np
import cv2 as cv
import os
import select
import threading
import queue
import subprocess
from evdev import InputDevice, ecodes, list_devices, categorize
import sys
from typing import List, Tuple
from datetime import datetime
import shutil
import re

from src.screen.utils import * 
from src.camera import (
        Camera,
        CameraParameters,
        CameraParameter,
        CamUtils,
        CameraServer,
        CameraFrameWrapper,
)
from src.camera.utils import FrameList

class QuickSaveTask:
    def __init__(self, current_frame: CameraFrameWrapper, timestamp: float, formatted_time: str):
        self.current_frame = CameraFrameWrapper(
            frame=current_frame.frame.copy(),
            metadata=current_frame.metadata,
            runtime_metadata=current_frame.runtime_metadata,
            timestamp=current_frame.timestamp
        )
        self.timestamp = timestamp
        self.formatted_time = formatted_time

class FrameProcessingTask:
    def __init__(self, frame_list: FrameList, timestamp: float, formatted_time: str):
        self.frame_list = self._deep_copy_frame_list(frame_list)
        self.timestamp = timestamp
        self.formatted_time = formatted_time
    
    def _deep_copy_frame_list(self, original_frame_list: FrameList) -> FrameList:
        copied_list = FrameList()
        copied_frames = []
        
        for frame_wrapper in original_frame_list._list:
            copied_frame = CameraFrameWrapper(
                frame=frame_wrapper.frame.copy(),
                metadata=frame_wrapper.metadata,
                runtime_metadata=frame_wrapper.runtime_metadata,
                timestamp=frame_wrapper.timestamp
            )
            copied_frames.append(copied_frame)
        
        copied_list._list = copied_frames
        copied_list._capacity = original_frame_list._capacity
        return copied_list

quick_save_queue = queue.Queue()
frame_processing_queue = queue.Queue()

quick_save_progress = {"status": "idle", "last_saved": ""}
frame_processing_progress = {"current": 0, "total": 0, "status": "idle", "filename": ""}
total_photos_saved = 0
total_videos_created = 0

def get_hostname_ip():
    try:
        result = subprocess.run(['hostname', '-I'], 
                              capture_output=True, 
                              text=True, 
                              timeout=2)
        if result.returncode == 0:
            ips = result.stdout.strip().split()
            return ips[0] if ips else "-"
        else:
            return "-"
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return "-"

def get_rpi_power_consumption():
    try:
        result = subprocess.run(['vcgencmd', 'pmic_read_adc'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        
        if result.returncode != 0:
            return -1
        
        output = result.stdout
        
        currents = {}
        voltages = {}
        
        current_pattern = r'(\w+(?:_\w+)*?)_A\s+current\(\d+\)=([0-9.]+)A'
        for match in re.finditer(current_pattern, output):
            rail_name = match.group(1)
            current_value = float(match.group(2))
            currents[rail_name] = current_value
        
        voltage_pattern = r'(\w+(?:_\w+)*?)_V\s+volt\(\d+\)=([0-9.]+)V'
        for match in re.finditer(voltage_pattern, output):
            rail_name = match.group(1)
            voltage_value = float(match.group(2))
            voltages[rail_name] = voltage_value
        
        total_power = 0.0
        
        for rail in currents:
            if rail in voltages:
                power = currents[rail] * voltages[rail]
                total_power += power
        
        return total_power
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return -1
    except Exception as e:
        return -1

def quick_save_thread():
    global quick_save_progress, total_photos_saved
    
    while True:
        try:
            task = quick_save_queue.get()
            
            if task is None:
                break
            
            quick_save_progress["status"] = "saving photo"
            
            filename = f"{task.formatted_time}.png"
            current_frame_path = os.path.join(CURRENT_GALLERY, filename)
            
            cv.imwrite(current_frame_path, task.current_frame.frame)
            
            total_photos_saved += 1
            quick_save_progress["last_saved"] = filename
            quick_save_progress["status"] = "idle"
            
            print(f"Quick saved: {filename}")
            quick_save_queue.task_done()
            
        except Exception as e:
            quick_save_progress["status"] = "error"
            print(f"Error in quick save thread: {e}")

def frame_processing_thread():
    global frame_processing_progress, total_videos_created
    
    while True:
        try:
            task = frame_processing_queue.get()
            
            if task is None:
                break
            
            frame_processing_progress["status"] = "processing frames"
            frame_processing_progress["filename"] = task.formatted_time
            
            all_frames = task.frame_list._list
            frames = list(all_frames) if hasattr(all_frames, '__iter__') else []
            frames.sort(key=lambda f: f.timestamp)
            
            if not frames:
                frame_processing_progress["status"] = "idle"
                frame_processing_queue.task_done()
                continue
            
            frame_processing_progress["total"] = len(frames)
            frame_processing_progress["current"] = 0
            
            frames_folder_name = task.formatted_time
            frames_folder_path = os.path.join(CURRENT_GALLERY, frames_folder_name)
            os.makedirs(frames_folder_path, exist_ok=True)
            
            frame_processing_progress["status"] = "saving frames"
            frame_count = 0
            
            if frames:
                height, width = frames[0].frame.shape[:2]
            else:
                continue
            
            for frame in frames:
                frame_filename = f"{frame_count:04d}.png"
                frame_path = os.path.join(frames_folder_path, frame_filename)
                cv.imwrite(frame_path, frame.frame)
                frame_count += 1
                frame_processing_progress["current"] = frame_count
            
            if frame_count > 0:
                frame_processing_progress["status"] = "creating video"
                video_filename = f"{task.formatted_time}_video.mkv"
                video_path = os.path.join(CURRENT_GALLERY, video_filename)
                
                try:
                    create_video_with_ffmpeg(frames_folder_path, video_path, frame_count, width, height)
                    total_videos_created += 1
                except Exception as e:
                    print(f"Error creating video: {e}")
            
            frame_processing_progress["status"] = "idle"
            frame_processing_progress["current"] = 0
            frame_processing_progress["total"] = 0
            frame_processing_progress["filename"] = ""
            
            print(f"Processed {frame_count} frames and created video for {task.formatted_time}")
            frame_processing_queue.task_done()
            
        except Exception as e:
            frame_processing_progress["status"] = "error"
            print(f"Error in frame processing thread: {e}")

def create_video_with_ffmpeg(frames_folder, output_path, frame_count, width, height):
    try:
        cmd = [
            'ffmpeg',
            '-y',
            '-r', '20',
            '-i', os.path.join(frames_folder, '%04d.png'),
            '-c:v', 'mpeg2video',
            '-q:v', '2',
            '-pix_fmt', 'yuv420p',
            '-b:v', '8000k',
            output_path
        ]
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"FFmpeg error: {stderr.decode()}")
            create_video_with_opencv(frames_folder, output_path, frame_count, width, height)
        else:
            print(f"Successfully created video: {output_path}")
            
    except Exception as e:
        print(f"Error using ffmpeg: {e}")
        create_video_with_opencv(frames_folder, output_path, frame_count, width, height)

def create_video_with_opencv(frames_folder, output_path, frame_count, width, height):
    try:
        fourcc = cv.VideoWriter_fourcc(*'XVID')
        alternate_output = output_path.replace('.mkv', '_alt.avi')
        
        out = cv.VideoWriter(
            alternate_output,
            fourcc,
            20.0,
            (width, height)
        )
        
        for i in range(frame_count):
            frame_path = os.path.join(frames_folder, f"{i:04d}.png")
            frame = cv.imread(frame_path)
            if frame is not None:
                out.write(frame)
        
        out.release()
        print(f"Created alternative video with OpenCV: {alternate_output}")
    except Exception as e:
        print(f"Error creating video with OpenCV: {e}")

quick_saver = threading.Thread(target=quick_save_thread, daemon=True)
quick_saver.start()

frame_processor = threading.Thread(target=frame_processing_thread, daemon=True)
frame_processor.start()

cam = Camera()
cam.reconfigure(CameraParameters(1,(1,1),1, AeEnable=True, AwbEnable=True))

from src.camera.server import CameraParameterHandler
from src.network.static import StaticHTTPServer
from src.network.image import ImageStream

FB_DEVICE = '/dev/fb0'

GALLERIES_PATH = "./galleries/"

for gallery in os.listdir(GALLERIES_PATH):
    folder_path = os.path.join(GALLERIES_PATH, gallery)
    if not os.listdir(folder_path):
        os.rmdir(folder_path)

galleries = os.listdir(GALLERIES_PATH)
numbers = [int(match) for gallery in galleries 
           for match in re.findall(r'\d+', gallery)]

max_number = max(numbers) if numbers else 0
BOOT_NO = max_number + 1

if not os.path.exists(GALLERIES_PATH):
    os.makedirs(GALLERIES_PATH)

CURRENT_GALLERY = f"{GALLERIES_PATH}/boot_{BOOT_NO:04d}"
os.mkdir(CURRENT_GALLERY)

def on_touch(x, y):
    global is_touched, last_capture_time, last_touch_x, last_touch_y
    current_time = time.time()
    
    last_touch_x = x
    last_touch_y = y
    
    if current_time - last_capture_time > touch_debounce_time:
        is_touched = True
        last_capture_time = current_time

is_touched = False
touch_debounce_time = 0.5
last_touch_x = 0
last_touch_y = 0
last_capture_time = time.time()

TOUCH_DEVICE = find_touch_device()
touch_thread = threading.Thread(
    target=touch_monitor_thread, 
    args=(TOUCH_DEVICE, on_touch),
    daemon=True
)
touch_thread.start()

fb, fbmap, width, height, bpp, frame_size = init_framebuffer()

frame_count = 0
start_time = time.time()
fps = 0
fps_update_interval = 1.0 

target_fps = 30.0
frame_time = 1.0 / target_fps
last_frame_time = time.time()

address = "-"
last_address_update = 0
address_update_interval = 5.0

power_watts = 0.0
last_power_update = 0
power_update_interval = 5.0

servers = [
    ("Camera configuration server", CameraServer(camera=cam, callback_capture=cam.capture_and_save, port=4500)),
    ("Camera controls frontend", StaticHTTPServer("./src/client", port=4600)),
    ("Gallery", StaticHTTPServer("./galleries/", port=4800)),
    ("Image stream", ImageStream(5000)),
]

for name, server in servers:
    print(f"Starting: {name}")
    server.start()

image_server = servers[-1][1]

cam.capture(-1)

while True:
    frame: CameraFrameWrapper = cam.capture(-1)
    display_frame = frame.frame.copy()
    
    if is_touched:
        print(f"Processing touch at ({last_touch_x}, {last_touch_y}) - capturing and saving image")
        
        timestamp = time.time()
        now = datetime.fromtimestamp(timestamp)
        formatted_time = now.strftime("%Y.%m.%d-%H:%M:%S")
        
        framelist_copy = cam.frames
        frame_to_save = cam.capture(0.15)
        
        quick_task = QuickSaveTask(frame_to_save, timestamp, formatted_time)
        quick_save_queue.put(quick_task)
        
        processing_task = FrameProcessingTask(framelist_copy, timestamp, formatted_time)
        frame_processing_queue.put(processing_task)
        
        is_touched = False
    
    aspect_ratio = display_frame.shape[1] / display_frame.shape[0]
    new_width = int(height * aspect_ratio)
    lores = cv.resize(display_frame, (new_width, height), interpolation=cv.INTER_NEAREST)

    image_offset = 70
    
    if new_width < width:
        pad_left = (width - new_width) // 2 - image_offset
        pad_right = width - new_width - pad_left
        if pad_left < 0:
            image_offset = (width - new_width) // 2
            pad_left = 0
            pad_right = width - new_width
        
        lores = cv.copyMakeBorder(
            lores, 0, 0, pad_left, pad_right, cv.BORDER_CONSTANT, value=[0, 0, 0]
        )
    elif new_width > width:
        start_x = (new_width - width) // 2 - image_offset 
        if start_x < 0:
            start_x = 0
        lores = lores[:, start_x:start_x + width]

    pad_side = 350 
    display_crop_size = 200  
    margin = 10
    h, w = display_frame.shape[:2]
    cx, cy = w // 2, h // 2

    crop = display_frame[
        cy - pad_side // 2 : cy + pad_side // 2,
        cx - pad_side // 2 : cx + pad_side // 2,
    ]

    crop_display = cv.resize(crop, (display_crop_size, display_crop_size), interpolation=cv.INTER_LINEAR)

    line_length = 8
    crop_line_length = 4
    thickness = 1

    crop_color = np.mean(crop, axis=(0, 1)).astype(np.uint8)
    r, g, b = crop_color[0], crop_color[1], crop_color[2]
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    if luminance > 127:
        color = (0, 0, 0)
        grid_color = (80, 80, 80)  
    else:
        color = (255, 255, 255)
        grid_color = (160, 160, 160)
        
    crop_gray = cv.cvtColor(crop_display, cv.COLOR_BGR2GRAY)
    edges = cv.Canny(crop_gray, 50, 150)
    edges_colored = cv.cvtColor(edges, cv.COLOR_GRAY2BGR)
    crop_display = cv.addWeighted(crop_display, 0.7, edges_colored, 0.3, 0)

    h_crop, w_crop = crop_display.shape[:2]
    cx_crop, cy_crop = w_crop // 2, h_crop // 2


    h, w = lores.shape[:2]
    cx, cy = w // 2, h // 2

    lores_h, lores_w = lores.shape[:2]
    crop_x = lores_w - display_crop_size - margin  
    crop_y = margin 
    lores[crop_y:crop_y + display_crop_size, crop_x:crop_x + display_crop_size] = crop_display

    font = cv.FONT_HERSHEY_SIMPLEX
    font_scale = 0.38
    shadow_offset = 1
    line_height = 14

    text_start_x = crop_x
    text_start_y = crop_y + display_crop_size + 30

    hz = len(cam.frames._list) / cam.frames._capacity

    current_time = time.time()
    
    if current_time - last_address_update >= address_update_interval:
        address = get_hostname_ip()
        last_address_update = current_time
    
    if current_time - last_power_update >= power_update_interval:
        power_result = get_rpi_power_consumption()
        if power_result > 0:
            power_watts = power_result
        last_power_update = current_time

    elapsed_since_last_frame = current_time - last_frame_time
    sleep_time = max(0, frame_time - elapsed_since_last_frame)

    if sleep_time > 0:
        time.sleep(sleep_time)

    frame_count += 1
    elapsed_time = time.time() - start_time

    if elapsed_time >= fps_update_interval:
        fps = frame_count / elapsed_time
        print(f"HZ: {fps:.2f}")
        
        frame_count = 0
        start_time = time.time()

    touch_device = TOUCH_DEVICE

    text_items = [
        f"{address}",
        f"{CamUtils.microseconds_to_seconds(frame.metadata.exposure_time):.7f}us, {frame.metadata.analogue_gain:.1f}x",
        f"{frame.runtime_metadata.temperature}K {frame.runtime_metadata.lux:3.3f} LUX",
        f"FPS: {frame_count/(time.time()-start_time):3.1f}, {power_watts:.1f}Watts",
    ]

    if touch_device:
        text_items.append(f"Touch: enabled ({last_touch_x},{last_touch_y})")
    else:
        text_items.append("Touch: disabled")

    status_line = f"Photos: {total_photos_saved}, V: {total_videos_created}"

    if quick_save_progress["status"] != "idle":
        status_line += f" | S: {quick_save_progress['status']}"

    if frame_processing_progress["status"] != "idle":
        if frame_processing_progress["status"] == "saving frames":
            status_line += f" | P: {frame_processing_progress['current']}/{frame_processing_progress['total']} frames"
        elif frame_processing_progress["status"] == "creating video":
            status_line += f" | V {frame_processing_progress['filename']}"
        else:
            status_line += f" | P: {frame_processing_progress['status']}"

    text_items.append(status_line)

    for i, text in enumerate(text_items):
        y = text_start_y + (i * line_height)
        if y < lores_h - 10:
            cv.putText(
                lores,
                text,
                (text_start_x + shadow_offset, y + shadow_offset),
                font,
                font_scale,
                (0, 0, 0),
                2,
            )
            cv.putText(lores, text, (text_start_x, y), font, font_scale, (255, 255, 255), 1)

    image_server.input_image(lores) 
    fb_frame = frame_to_framebuffer_format(lores, width, height)
    fbmap.seek(0)
    fbmap.write(fb_frame.tobytes())
    
    last_frame_time = time.time()

quick_save_queue.put(None)
frame_processing_queue.put(None)
quick_saver.join(timeout=1.0)
frame_processor.join(timeout=1.0)