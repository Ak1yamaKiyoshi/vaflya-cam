#!/usr/bin/env python3
import struct
import mmap
import sys
import time
import numpy as np
import cv2 as cv
import os
import select
import threading
from evdev import InputDevice, ecodes, list_devices, categorize

fb_device = '/dev/fb0'

def init_framebuffer():
    try:
        fb = open(fb_device, 'rb+')
        width = 800
        height = 480
        bpp = 32
        frame_size = width * height * bpp // 8
        fbmap = mmap.mmap(fb.fileno(), frame_size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ, offset=0)
        print(f"Framebuffer initialized: {width}x{height}, {bpp}bpp")
        return fb, fbmap, width, height, bpp, frame_size
    except Exception as e:
        print(f"Error initializing framebuffer: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def find_touch_device():
    try:
        device = InputDevice('/dev/input/event1')
        print(f"Using touch device: {device.name} at {device.path}")
        return device
    except Exception as e:
        print(f"Error opening touchscreen device: {e}")
        
        try:
            devices = [InputDevice(path) for path in list_devices()]
            for device in devices:
                print(f"Found input device: {device.path}, name: {device.name}")
                if "touch" in device.name.lower() or "ads7846" in device.name.lower():
                    print(f"Using touch device: {device.name}")
                    return device
        except Exception as e2:
            print(f"Error scanning for touch devices: {e2}")
    
    print("No touch device found. Touch functionality will be disabled.")
    return None

def touch_monitor_thread(touch_device, on_touch_callback):
    if touch_device is None:
        return
    
    print(f"Starting touch monitor for device: {touch_device.name}")
    print(f"Device capabilities: {touch_device.capabilities(verbose=True)}")
    
    has_abs_x = ecodes.ABS_X in touch_device.capabilities().get(ecodes.EV_ABS, [])
    has_abs_y = ecodes.ABS_Y in touch_device.capabilities().get(ecodes.EV_ABS, [])
    has_abs_mt_x = ecodes.ABS_MT_POSITION_X in touch_device.capabilities().get(ecodes.EV_ABS, [])
    has_abs_mt_y = ecodes.ABS_MT_POSITION_Y in touch_device.capabilities().get(ecodes.EV_ABS, [])
    has_btn_touch = ecodes.BTN_TOUCH in touch_device.capabilities().get(ecodes.EV_KEY, [])
    
    print(f"Touch device has: ABS_X: {has_abs_x}, ABS_Y: {has_abs_y}, MT_X: {has_abs_mt_x}, MT_Y: {has_abs_mt_y}, BTN_TOUCH: {has_btn_touch}")
    
    uses_multitouch = has_abs_mt_x and has_abs_mt_y
    if uses_multitouch:
        print("Detected multi-touch device (Protocol B)")
    else:
        print("Detected single-touch device (older protocol)")
    
    touch_x = 0
    touch_y = 0
    touch_pressure = 0
    
    try:
        # Get the absolute axis info if available
        if has_abs_x and ecodes.ABS_X in touch_device.capabilities()[ecodes.EV_ABS]:
            absinfo = touch_device.absinfo(ecodes.ABS_X)
            print(f"X-axis range: {absinfo.min} to {absinfo.max}")
        if has_abs_y:
            absinfo = touch_device.absinfo(ecodes.ABS_Y)
            print(f"Y-axis range: {absinfo.min} to {absinfo.max}")
    except Exception as e:
        print(f"Error getting axis info: {e}")
    
    try:
        while True:
            r, w, x = select.select([touch_device.fd], [], [], 0.1)
            if r:
                for event in touch_device.read():
                    event_str = str(categorize(event))
                    print(f"Touch event: {event_str}")
                    
                    if event.type == ecodes.EV_ABS:
                        if event.code == ecodes.ABS_X:
                            touch_x = event.value
                        elif event.code == ecodes.ABS_Y:
                            touch_y = event.value
                        elif event.code == ecodes.ABS_PRESSURE:
                            touch_pressure = event.value
                    
                    # Detect touch press and report coordinates
                    if (event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH and event.value == 1) or \
                       (event.type == ecodes.EV_ABS and event.code == ecodes.ABS_PRESSURE and event.value > 0):
                        print(f"=== TOUCH DETECTED! Position: ({touch_x}, {touch_y}), Pressure: {touch_pressure} ===")
                        if on_touch_callback:
                            on_touch_callback(touch_x, touch_y)
            
            time.sleep(0.01)
    except Exception as e:
        print(f"Error in touch monitor: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Touch monitor thread exiting")

def frame_to_framebuffer_format(frame, width, height):
    if frame.shape[1] != width or frame.shape[0] != height:
        frame = cv.resize(frame, (width, height), interpolation=cv.INTER_NEAREST)
    
    bgra = np.zeros((height, width, 4), dtype=np.uint8)
    bgra[:, :, :3] = frame
    bgra[:, :, 3] = 255
    
    return bgra


if not os.path.exists("./galleries/"):
    os.makedirs("./galleries/")

current_gallery = f"galleries/gallery{len(os.listdir('./galleries/'))}"
os.mkdir(current_gallery)

def main():
    fb, fbmap, width, height, bpp, frame_size = init_framebuffer()
    
    try:
        import evdev
        touch_device = find_touch_device()
    except ImportError:
        print("evdev module not found. Please install with: pip install evdev")
        print("Touch functionality will be disabled.")
        touch_device = None
    
    from src.camera import (
        Camera,
        CameraParameters,
        CameraParameter,
        CamUtils,
        CameraServer,
        CameraFrameWrapper,
    )
    from src.camera.server import CameraParameterHandler
    from src.network.static import StaticHTTPServer
    from src.network.image import ImageStream
    import subprocess
    
    try:
        def get_ip_addresses():
            try:
                output = subprocess.check_output("hostname -I", shell=True).decode("utf-8").strip()
                ip_addresses = output.split()
                return ip_addresses
            except:
                return ["IP not available"]
        
        try:
            address = get_ip_addresses()[0]
        except: 
            address = "restart with Akiyama enabled..."
        
        print("Initializing camera...")
        cam = Camera()
        cam.reconfigure(CameraParameters(1,(1,1),1 ,AeEnable=True, AwbEnable=True))
        
        servers = [
            (
                "Camera configuration server",
                CameraServer(camera=cam, callback_capture=cam.capture_and_save, port=4500),
            ),
            ("Camera controls frontend", StaticHTTPServer("./src/client", port=4600)),
            ("Gallery", StaticHTTPServer("./galleries/", port=4800)),
            ("Image stream", ImageStream(5000)),
        ]
        
        for name, server in servers:
            print(f"Starting server: {name}")
            server.start()
        
        image_display = servers[-1][1]
        
        
        frame_count = 0
        start_time = time.time()
        last_frame_time = start_time
        last_capture_time = 0
        print("Starting camera display loop...")
        
        frame_interval = 0.001
        
        is_touched = False
        touch_debounce_time = 0.5
        last_touch_x = 0
        last_touch_y = 0
        
        def test_simple_colors(fbmap, width, height):
            # Red test
            red = np.zeros((height, width, 4), dtype=np.uint8)
            red[:, :, 2] = 255  # BGR: red in channel 2
            red[:, :, 3] = 255
            fbmap.seek(0)
            fbmap.write(red.tobytes())
            time.sleep(0.1)
            
            # Green test
            green = np.zeros((height, width, 4), dtype=np.uint8)
            green[:, :, 1] = 255
            green[:, :, 3] = 255
            fbmap.seek(0)
            fbmap.write(green.tobytes())
            time.sleep(0.1)
            
            # Blue test
            blue = np.zeros((height, width, 4), dtype=np.uint8)
            blue[:, :, 0] = 255
            blue[:, :, 3] = 255
            fbmap.seek(0)
            fbmap.write(blue.tobytes())
            time.sleep(0.1)
        
        def on_touch(x, y):
            nonlocal is_touched, last_capture_time, last_touch_x, last_touch_y
            current_time = time.time()
            
            last_touch_x = x
            last_touch_y = y
            
            if current_time - last_capture_time > touch_debounce_time:
                is_touched = True
                last_capture_time = current_time
                print(f"*** CAPTURE TRIGGERED at position ({x}, {y}) ***")
        
        if touch_device:
            touch_thread = threading.Thread(
                target=touch_monitor_thread, 
                args=(touch_device, on_touch),
                daemon=True
            )
            touch_thread.start()
        
        test_simple_colors(fbmap, width, height)
        
        while True:
            current_time = time.time()
            elapsed_since_last_frame = current_time - last_frame_time
            
            if elapsed_since_last_frame < frame_interval:
                sleep_time = frame_interval - elapsed_since_last_frame
                time.sleep(sleep_time)
            
            last_frame_time = time.time()
            
            frame: CameraFrameWrapper = cam.capture(-1)
            
            if is_touched:
                print(f"Processing touch at ({last_touch_x}, {last_touch_y}) - capturing and saving image")
                cam.capture_and_save(output_path=current_gallery)
                is_touched = False
            
            aspect_ratio = frame.frame.shape[1] / frame.frame.shape[0]
            new_width = int(height * aspect_ratio)
            lores = cv.resize(frame.frame, (new_width, height), interpolation=cv.INTER_NEAREST)
            
            if new_width < width:
                pad_left = (width - new_width) // 2
                pad_right = width - new_width - pad_left
                lores = cv.copyMakeBorder(
                    lores, 0, 0, pad_left, pad_right, cv.BORDER_CONSTANT, value=[0, 0, 0]
                )
            elif new_width > width:
                start_x = (new_width - width) // 2
                lores = lores[:, start_x:start_x + width]
            
            pad_side = 350
            margin = 10
            h, w = frame.frame.shape[:2]
            cx, cy = w // 2, h // 2
            crop = frame.frame[
                cy - pad_side // 2 : cy + pad_side // 2,
                cx - pad_side // 2 : cx + pad_side // 2,
            ]
            
            line_length = 8
            crop_line_length = 4
            thickness = 1
            
            crop_color = np.mean(crop, axis=(0, 1)).astype(np.uint8)
            r, g, b = crop_color[0], crop_color[1], crop_color[2]
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            
            if luminance > 127:
                color = (0, 0, 0)
            else:
                color = (255, 255, 255)
            
            h, w = crop.shape[:2]
            cx, cy = w // 2, h // 2
            cv.line(
                crop,
                (cx - crop_line_length, cy),
                (cx + crop_line_length, cy),
                color,
                thickness,
            )
            cv.line(
                crop,
                (cx, cy - crop_line_length),
                (cx, cy + crop_line_length),
                color,
                thickness,
            )
            
            h, w = lores.shape[:2]
            cx, cy = w // 2, h // 2
            cv.line(lores, (cx - line_length, cy), (cx + line_length, cy), color, thickness)
            cv.line(lores, (cx, cy - line_length), (cx, cy + line_length), color, thickness)
            
            lores_h, lores_w = lores.shape[:2]
            lores[
                lores_h - pad_side - margin : lores_h - margin, margin : margin + pad_side
            ] = crop
            
            font = cv.FONT_HERSHEY_SIMPLEX
            font_scale = 0.38
            shadow_offset = 1
            line_height = 14
            start_x = 10
            start_y = 30
            
            hz = len(cam.frames._list) / cam.frames._capacity
            
            text_items = [
                f"{address}",
                f"{CamUtils.microseconds_to_seconds(frame.metadata.exposure_time):.7f}us, {frame.metadata.analogue_gain:.1f}x",
                f"{frame.runtime_metadata.temperature}K {frame.runtime_metadata.lux:3.3f} LUX",
                f"hz: {hz:3.1f}, FPS: {frame_count/(time.time()-start_time):3.1f}",
            ]
            
            if touch_device:
                text_items.append(f"Touch: enabled ({last_touch_x},{last_touch_y})")
            else:
                text_items.append("Touch: disabled")
                
            for i, text in enumerate(text_items):
                y = start_y + (i * line_height)
                cv.putText(
                    lores,
                    text,
                    (start_x + shadow_offset, y + shadow_offset),
                    font,
                    font_scale,
                    (0, 0, 0),
                    2,
                )
                cv.putText(lores, text, (start_x, y), font, font_scale, (255, 255, 255), 1)
            
            image_display.input_image(lores)
            
            fb_frame = frame_to_framebuffer_format(lores, width, height)
            
            fbmap.seek(0)
            fbmap.write(fb_frame.tobytes())
            
            frame_count += 1
            
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                print(f"FPS: {frame_count/elapsed:.1f}, Running time: {elapsed:.1f}s")
    
    except KeyboardInterrupt:
        print("Interrupted by user")
    
    except Exception as e:
        print(f"Error in main loop: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("Cleaning up...")
        black_screen = np.zeros((height, width, 4), dtype=np.uint8)
        fbmap.seek(0)
        fbmap.write(black_screen.tobytes())
        
        fbmap.close()
        fb.close()
        
        try:
            for _, server in servers:
                server.stop()
        except:
            pass
        
        print("Done")

if __name__ == "__main__":
    main()