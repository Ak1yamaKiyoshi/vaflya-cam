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

# Define the framebuffer device
fb_device = '/dev/fb0'

# Initialize framebuffer
def init_framebuffer():
    try:
        fb = open(fb_device, 'rb+')
        width = 480
        height = 320
        bpp = 16
        frame_size = width * height * bpp // 8
        fbmap = mmap.mmap(fb.fileno(), frame_size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ, offset=0)
        return fb, fbmap, width, height, bpp, frame_size
    except Exception as e:
        print(f"Error initializing framebuffer: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Find touch input device
def find_touch_device():
    try:
        # Try to use the specific device for ADS7846 Touchscreen
        device = InputDevice('/dev/input/event1')
        print(f"Using touch device: {device.name} at {device.path}")
        return device
    except Exception as e:
        print(f"Error opening touchscreen device: {e}")
        
        # Fallback: look for touch device by name
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

# Touch event monitor thread with detailed console output
def touch_monitor_thread(touch_device, on_touch_callback):
    if touch_device is None:
        return
    
    print(f"Starting touch monitor for device: {touch_device.name}")
    print(f"Device capabilities: {touch_device.capabilities(verbose=True)}")
    
    # ADS7846 typically uses absolute positioning
    has_abs_x = ecodes.ABS_X in touch_device.capabilities().get(ecodes.EV_ABS, [])
    has_abs_y = ecodes.ABS_Y in touch_device.capabilities().get(ecodes.EV_ABS, [])
    has_btn_touch = ecodes.BTN_TOUCH in touch_device.capabilities().get(ecodes.EV_KEY, [])
    
    print(f"Touch device has: ABS_X: {has_abs_x}, ABS_Y: {has_abs_y}, BTN_TOUCH: {has_btn_touch}")
    
    # Read current touch values
    touch_x = 0
    touch_y = 0
    touch_pressure = 0
    
    try:
        # Get the absolute axis info if available
        if has_abs_x and ecodes.ABS_X in touch_device.capabilities()[ecodes.EV_ABS]:
            absinfo = touch_device.absinfo(ecodes.ABS_X)
            print(f"X-axis range: {absinfo.min} to {absinfo.max}")
        
        if has_abs_y and ecodes.ABS_Y in touch_device.capabilities()[ecodes.EV_ABS]:
            absinfo = touch_device.absinfo(ecodes.ABS_Y)
            print(f"Y-axis range: {absinfo.min} to {absinfo.max}")
    except Exception as e:
        print(f"Error getting axis info: {e}")
    
    try:
        while True:
            r, w, x = select.select([touch_device.fd], [], [], 0.1)
            if r:
                for event in touch_device.read():
                    # Print the event details
                    event_str = str(categorize(event))
                    print(f"Touch event: {event_str}")
                    
                    # Track coordinate values
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
            
            time.sleep(0.01)  # Small sleep to prevent CPU hogging
    except Exception as e:
        print(f"Error in touch monitor: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Touch monitor thread exiting")

def frame_to_rgb565(frame, width, height):
    if frame.shape[1] != width or frame.shape[0] != height:
        frame = cv.resize(frame, (width, height), interpolation=cv.INTER_NEAREST)
    
    rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
    
    r = (rgb[:,:,0] >> 3).astype(np.uint16) << 11
    g = (rgb[:,:,1] >> 2).astype(np.uint16) << 5
    b = (rgb[:,:,2] >> 3).astype(np.uint16)
    
    rgb565 = r | g | b
    
    return rgb565

def main():
    fb, fbmap, width, height, bpp, frame_size = init_framebuffer()
    
    try:
        import evdev
        touch_device = find_touch_device()
    except ImportError:
        print("evdev module not found. Please install with: pip install evdev")
        print("Touch functionality will be disabled.")
        touch_device = None
    
    # Import camera modules
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
        # Get IP address
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
        
        # Initialize camera
        print("Initializing camera...")
        cam = Camera()
        time.sleep(0.01)
        
        # Start servers
        servers = [
            (
                "Camera configuration server",
                CameraServer(camera=cam, callback_capture=cam.capture_and_save, port=4500),
            ),
            ("Camera controls frontend", StaticHTTPServer("./src/client", port=4600)),
            ("Gallery", StaticHTTPServer("./gallery/", port=4800)),
            ("Image stream", ImageStream(5000)),
        ]
        
        for name, server in servers:
            print(f"Starting server: {name}")
            server.start()
        
        image_display = servers[-1][1]
        
        # Set camera to auto mode
        cam.set_auto()
        
        # Main loop
        frame_count = 0
        start_time = time.time()
        last_frame_time = start_time
        last_capture_time = 0
        print("Starting camera display loop...")
        
        # Fixed frame interval for 10 FPS
        frame_interval = 0.1  # 100ms = 10 FPS
        
        # Define callback for touch events
        is_touched = False
        touch_debounce_time = 0.5  # Debounce time in seconds
        last_touch_x = 0
        last_touch_y = 0
        
        def on_touch(x, y):
            nonlocal is_touched, last_capture_time, last_touch_x, last_touch_y
            current_time = time.time()
            
            # Store touch coordinates
            last_touch_x = x
            last_touch_y = y
            
            # Debounce touch events
            if current_time - last_capture_time > touch_debounce_time:
                is_touched = True
                last_capture_time = current_time
                print(f"*** CAPTURE TRIGGERED at position ({x}, {y}) ***")
        
        # Start touch monitor thread if touch device is available
        if touch_device:
            touch_thread = threading.Thread(
                target=touch_monitor_thread, 
                args=(touch_device, on_touch),
                daemon=True
            )
            touch_thread.start()
        
        while True:
            # Enforce 10 FPS limit
            current_time = time.time()
            elapsed_since_last_frame = current_time - last_frame_time
            
            if elapsed_since_last_frame < frame_interval:
                sleep_time = frame_interval - elapsed_since_last_frame
                time.sleep(sleep_time)
            
            last_frame_time = time.time()
            
            # Capture frame
            frame: CameraFrameWrapper = cam.capture(-1)
            
            # Check for touch event
            if is_touched:
                print(f"Processing touch at ({last_touch_x}, {last_touch_y}) - capturing and saving image")
                cam.capture_and_save()
                is_touched = False
            
            # Process frame for display
            lores = cv.resize(frame.frame, (426, height), interpolation=cv.INTER_NEAREST)
            
            # Pad left with black to match TFT width
            lores = cv.copyMakeBorder(
                lores, 0, 0, width - 426, 0, cv.BORDER_CONSTANT, value=[0, 0, 0]
            )
            
            # Get hires crop from frame
            pad_side = 150
            margin = 10
            h, w = frame.frame.shape[:2]
            cx, cy = w // 2, h // 2
            crop = frame.frame[
                cy - pad_side // 2 : cy + pad_side // 2,
                cx - pad_side // 2 : cx + pad_side // 2,
            ]
            
            # Draw cross in center
            line_length = 8
            crop_line_length = 4
            thickness = 1
            
            # Get contrast color
            crop_color = np.mean(crop, axis=(0, 1)).astype(np.uint8)
            r, g, b = crop_color[0], crop_color[1], crop_color[2]
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            
            if luminance > 127:
                color = (0, 0, 0)
            else:
                color = (255, 255, 255)
            
            # Draw cross on crop
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
            
            # Draw cross on lores
            h, w = lores.shape[:2]
            cx, cy = w // 2, h // 2
            cv.line(lores, (cx - line_length, cy), (cx + line_length, cy), color, thickness)
            cv.line(lores, (cx, cy - line_length), (cx, cy + line_length), color, thickness)
            
            # Paste hires crop to lores
            lores_h, lores_w = lores.shape[:2]
            lores[
                lores_h - pad_side - margin : lores_h - margin, margin : margin + pad_side
            ] = crop
            
            # Add text
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
            
            # Add touch status with last touch position
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
            
            # Send to HTTP stream
            image_display.input_image(lores)
            
            # Convert to RGB565 for framebuffer
            rgb565 = frame_to_rgb565(lores, width, height)
            
            # Write to framebuffer
            fbmap.seek(0)
            fbmap.write(rgb565.tobytes())
            
            # Update frame count
            frame_count += 1
            
            # Print stats every 30 frames
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
        # Clean up
        print("Cleaning up...")
        # Clear screen to black
        black_screen = np.zeros((height, width), dtype=np.uint16)
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