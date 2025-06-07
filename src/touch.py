from evdev import InputDevice, ecodes, list_devices
import select
import time

def find_touch_device():
    try:
        device = InputDevice('/dev/input/event1')
        return device
    except Exception as e:
        
        try:
            devices = [InputDevice(path) for path in list_devices()]
            for device in devices:
                caps = device.capabilities()
                has_touch = ecodes.EV_ABS in caps and (
                    ecodes.ABS_X in caps[ecodes.EV_ABS] or 
                    ecodes.ABS_MT_POSITION_X in caps[ecodes.EV_ABS]
                )
                if has_touch or "touch" in device.name.lower() or "ads7846" in device.name.lower():
                    return device
        except Exception as e2:
            print(f"Error scanning for touch devices: {e2}")
    
    return None

def touch_monitor_thread(touch_device, app):
    if not touch_device:
        print("No touch device available for monitoring")
        return
    
    
    caps = touch_device.capabilities()
    print(f"Device capabilities: {caps}")
    
    has_abs_x = ecodes.ABS_X in caps.get(ecodes.EV_ABS, [])
    has_abs_y = ecodes.ABS_Y in caps.get(ecodes.EV_ABS, [])
    has_abs_mt_x = ecodes.ABS_MT_POSITION_X in caps.get(ecodes.EV_ABS, [])
    has_abs_mt_y = ecodes.ABS_MT_POSITION_Y in caps.get(ecodes.EV_ABS, [])
    has_btn_touch = ecodes.BTN_TOUCH in caps.get(ecodes.EV_KEY, [])
    has_abs_pressure = ecodes.ABS_PRESSURE in caps.get(ecodes.EV_ABS, [])
    
    
    touch_x = touch_y = 0
    is_touching = False
    touch_pressure = 0
    last_event_time = time.time()
    
    try:
        print("Touch monitor started - waiting for events...")
        
        while True:
            r, w, x = select.select([touch_device.fd], [], [], 0.1)
            
            if r:
                events = list(touch_device.read())
                if events:
                    
                    is_press = is_release = position_changed = False
                    current_x = current_y = current_pressure = 0
                    
                    for event in events:
                        if event.type == ecodes.EV_ABS:
                            if event.code == ecodes.ABS_X:
                                current_x = event.value
                                position_changed = True
                            elif event.code == ecodes.ABS_Y:
                                current_y = event.value
                                position_changed = True
                            elif event.code == ecodes.ABS_MT_POSITION_X:
                                current_x = event.value
                                position_changed = True
                            elif event.code == ecodes.ABS_MT_POSITION_Y:
                                current_y = event.value
                                position_changed = True
                            elif event.code == ecodes.ABS_PRESSURE:
                                current_pressure = event.value
                                if not has_btn_touch:
                                    if event.value > 0 and not is_touching:
                                        is_press = True
                                        is_touching = True
                                    elif event.value == 0 and is_touching:
                                        is_release = True
                                        is_touching = False
                        
                        elif event.type == ecodes.EV_KEY:
                            if event.code == ecodes.BTN_TOUCH:
                                if event.value == 1:
                                    is_press = True
                                    is_touching = True
                                elif event.value == 0:
                                    is_release = True
                                    is_touching = False
                        
                        elif event.type == ecodes.EV_SYN:
                            pass
                    
                    if position_changed:
                        if current_x != 0:
                            touch_x = current_x
                        if current_y != 0:
                            touch_y = current_y
                    
                    if current_pressure != 0:
                        touch_pressure = current_pressure
                    
                    if is_press:
                        app.on_touch_event(touch_x, touch_y, True, False, touch_device)
                    elif is_release:
                        app.on_touch_event(touch_x, touch_y, False, True, touch_device)
                    elif is_touching and position_changed:
                        app.on_touch_event(touch_x, touch_y, False, False, touch_device)
                    
                    last_event_time = time.time()
            
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("Touch monitor interrupted")
    except Exception as e:
        print(f"Touch monitor error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Touch monitor thread exiting")