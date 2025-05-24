from evdev import InputDevice, ecodes, list_devices, categorize
import select

fb_device = '/dev/fb0'
import sys 
import mmap
import numpy as np
import time
import cv2 as cv

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

