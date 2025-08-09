from aos.node import Node
from srcv2.ui.button import Button
from srcv2.ui.slider import Slider
from srcv2.touch import find_touch_device, touch_monitor_thread
import numpy as np
from evdev import ecodes
import threading 
import cv2 as cv

from srcv2.camera import CameraParameters

AUTO_AWB_AE_NAME = "AWB AE"
EDGES_OVERLAY_NAME = "EDGES"
ZOOM_NAME = "ZOOM"
RECORDING_NAME = "REC"
PHOTO_NAME = "PHOTO"
SHOW_CONTROLS_NAME = "CTL"
REWIND = "REWIND"


ZOOM_SLIDER_NAME = " zoom"
GAIN_SLIDER_NAME = "gain"
SHUTTER_SLIDER_NAME = "shutter"
GAIN_RED_SLIDER_NAME = "gain red" 
GAIN_BLUE_SLIDER_NAME = "gain blue"

class CamUI(Node):
    def _init(self, hv_flip=True, width=800, height=480):
        self._is_auto_setting = False
        self.rotate_180 = hv_flip
        self.width = width
        self.height = height
        self.active_button = None
        self.active_slider= None

        self.buttons = [
            Button(x=10, y=10, width=100, height=50, text=AUTO_AWB_AE_NAME, color=(200, 200, 200), toggle_mode=True, transparent=True, callback=self.event_emitter, transparent_style=1),
            Button(x=10 + 100 , y=10, width=70, height=50, text=EDGES_OVERLAY_NAME, color=(200, 200, 200), toggle_mode=True, transparent=True, callback=self.event_emitter, transparent_style=1),
            Button(x=10 + 100  + 70 , y=10, width=70, height=50, text=ZOOM_NAME, color=(200, 200, 200), toggle_mode=True, transparent=True, callback=self.event_emitter, transparent_style=1),
            Button(x=10, y=self.height - 10-50, height=50, width=100, text=RECORDING_NAME, color=(0, 0, 255), toggle_mode=True, transparent=True, callback=self.event_emitter, transparent_style=1),
            Button(x=10+100, y=self.height - 10-50, height=50, width=100, text=PHOTO_NAME, color=(255, 255, 255), toggle_mode=False, transparent=True, callback=self.event_emitter, transparent_style=1),
            Button(x= 10+100+100, y=self.height - 10-50, height=50, width=100, text=SHOW_CONTROLS_NAME, color=(200, 200, 200), toggle_mode=True, transparent=True, callback=self.event_emitter, transparent_style=1),
            Button(x= 10+100+100+100, y=self.height - 10-50, height=50, width=100, text=REWIND, color=(200, 200, 200), toggle_mode=False, transparent=True, callback=self.event_emitter, transparent_style=1)
        ]

        self.focus_button = self.buttons[1]
        self.zoom_button = self.buttons[2]
        self.show_controls_button = self.buttons[5]
        
        self.crop_x, self.crop_y = 10, 100
        self.sliders = [
            Slider(x=10 + 100 + 70 + 70 + 10, y=10 + 25 + 10, width=100, min_val=1.0, max_val=10., initial_val=2.0, text=ZOOM_SLIDER_NAME, callback=self.event_emitter),
            Slider(x=10, y=self.height -100-  10-50,          width=500, min_val=1.0, max_val=21., initial_val=2.0, text=GAIN_SLIDER_NAME, callback=self.event_emitter),
            Slider(x=10, y=self.height -100-  10-50-50,       width=500, min_val=114, max_val=320_000., initial_val=114, text=SHUTTER_SLIDER_NAME, callback=self.event_emitter),
            Slider(x=10, y=self.height -100-  10-50-50-50,    width=500, min_val=0.5, max_val=7., initial_val=1.0, text=GAIN_BLUE_SLIDER_NAME, callback=self.event_emitter),
            Slider(x=10, y=self.height -100-  10-50-50-50-50, width=500, min_val=0.5, max_val=7., initial_val=1.0, text=GAIN_RED_SLIDER_NAME, callback=self.event_emitter),
        ]
        
        self.zoom_slider = self.sliders[0]
        
        self.gain_slider = self.sliders[1]
        self.gain_red_slider = self.sliders[3]
        self.gain_blue_slider = self.sliders[4]
        self.shutter_slider = self.sliders[2]
        
        self.touch_device = find_touch_device()
        self.monitor_thread = threading.Thread(
            daemon=True,
            target=touch_monitor_thread,
            args=(self.touch_device, self),
        )
        self.frame = None
        self.frame_received = threading.Event()
        self.monitor_thread.start()
        
    def set_latest_camera_params(self, val:CameraParameters):
        params, is_auto = val
        self._is_auto_setting = is_auto
        if is_auto:
            self.gain_slider.set_value(params.gain)
            self.gain_red_slider.set_value(params.gain_r)
            self.gain_blue_slider.set_value(params.gain_b)
            self.shutter_slider.set_value(params.shutter)

    def event_emitter(self, name, value=None):
        if name == AUTO_AWB_AE_NAME:
            self._emit("set_auto_awb_ae", value)
        if name == PHOTO_NAME:
            self._emit("capture_photo", True)
        if name == RECORDING_NAME:
            self._emit("recording", value)

        if not self._is_auto_setting:
            if name == GAIN_SLIDER_NAME:
                self._emit("ui_new_gain", value)
            if name == GAIN_BLUE_SLIDER_NAME:
                self._emit("ui_new_gain_blue", value)
            if name == GAIN_RED_SLIDER_NAME:
                self._emit("ui_new_gain_red", value)
            if name == SHUTTER_SLIDER_NAME:
                self._emit("ui_new_shutter", value)

    def map_touch_coordinates(self, touch_x, touch_y, touch_device):
        try:
            x_info = touch_device.absinfo(ecodes.ABS_X)
            y_info = touch_device.absinfo(ecodes.ABS_Y)
            screen_x = int((touch_x - x_info.min) * self.width / (x_info.max - x_info.min))
            screen_y = int((touch_y - y_info.min) * self.height / (y_info.max - y_info.min))
        except:
            try:
                x_info = touch_device.absinfo(ecodes.ABS_MT_POSITION_X)
                y_info = touch_device.absinfo(ecodes.ABS_MT_POSITION_Y)
                screen_x = int((touch_x - x_info.min) * self.width / (x_info.max - x_info.min))
                screen_y = int((touch_y - y_info.min) * self.height / (y_info.max - y_info.min))
            except:
                screen_x, screen_y = touch_x, touch_y
        
        if self.rotate_180:
            screen_x = self.width - 1 - screen_x
            screen_y = self.height - 1 - screen_y
        
        return max(0, min(self.width - 1, screen_x)), max(0, min(self.height - 1, screen_y))


    def on_touch_event(self, touch_x, touch_y, is_press, is_release, touch_device):
        screen_x, screen_y = self.map_touch_coordinates(touch_x, touch_y, touch_device)
        
        if is_press:
            for button in self.buttons:
                if button.is_inside(screen_x, screen_y):
                    self.active_button = button
                    button.on_press()
                    break

            if not self.active_button:
                for slider in self.sliders:
                    if slider.is_inside(screen_x, screen_y):
                        self.active_slider = slider
                        slider.start_drag(screen_x)
                        break
                        
        elif is_release:
            if self.active_button:
                self.active_button.on_release()
                self.active_button = None
            if self.active_slider:
                self.active_slider.end_drag()
                self.active_slider = None

        elif self.active_slider:
            self.active_slider.update_drag(screen_x)

    def set_frame(self, frame:np.ndarray):  
        self.frame = frame 
        self.frame_received.set()
    
    def set_original_frame(self, frame:np.ndarray):
        self.original_frame = frame
    
    def mainloop(self):
        while True:
                
            self.frame_received.wait()
            self.frame_received.clear()
            frame = self.frame

            self.focus_button:Button
            if self.focus_button.is_toggled:
                gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
                canny = cv.Canny(gray, 10, 100) 
                canny_colored = cv.cvtColor(canny, cv.COLOR_GRAY2BGR)
                frame = cv.addWeighted(frame, 1.0, canny_colored, 0.7, 0)

            for button in self.buttons: 
                button.draw(frame)

            if self.show_controls_button.is_toggled:
                for slider in self.sliders:
                    slider.draw(frame)
            
            if self.zoom_button.is_toggled:
                zoom_factor = self.zoom_slider.value
                orig_height, orig_width = self.original_frame.shape[:2]
                crop_size = int(1000 / zoom_factor)
                
                crop_size = min(crop_size, min(orig_width, orig_height))
                center_x = orig_width // 2
                center_y = orig_height // 2

                x1 = max(0, center_x - crop_size // 2)
                y1 = max(0, center_y - crop_size // 2)
                x2 = min(orig_width, x1 + crop_size)
                y2 = min(orig_height, y1 + crop_size)
                
                if x2 - x1 < crop_size:
                    x1 = max(0, x2 - crop_size)
                if y2 - y1 < crop_size:
                    y1 = max(0, y2 - crop_size)
                
                cropped = self.original_frame[y1:y2, x1:x2]
                
                zoomed_crop = cv.resize(cropped, (300, 300), interpolation=cv.INTER_CUBIC)
                
                crop_x, crop_y = self.crop_x, self.crop_y
                
                frame_height, frame_width = frame.shape[:2]
                end_x = min(frame_width, crop_x + 300)
                end_y = min(frame_height, crop_y + 300)

                paste_width = end_x - crop_x
                paste_height = end_y - crop_y
                

                frame[crop_y:end_y, crop_x:end_x] = zoomed_crop[:paste_height, :paste_width]
            

            self._emit("ui_frame", frame)

