#!/usr/bin/env python3

import threading
import time
import sys
import os
import queue
import subprocess
from datetime import datetime
from evdev import ecodes
from src.screen import init_framebuffer, frame_to_framebuffer_format, write_frame_to_fb
from src.touch import find_touch_device, touch_monitor_thread

from src.ui.button import Button
from src.ui.slider import Slider
from src.camera import Camera, CameraParameters, CameraServer
from src.camera.utils import FrameList
from src.network.static import StaticHTTPServer
from src.network.image import ImageStream

import numpy as np
import cv2 as cv

class UI_NAMES:
    SHUTTER_SLIDER = "Shutter"
    GAIN_R_SLIDER = "R/G"
    GAIN_B_SLIDER = "B/G"
    GAIN_SLIDER = "Gain"

class PhotoSaveTask:
    def __init__(self, frame, timestamp, formatted_time):
        self.frame = frame.copy()
        self.timestamp = timestamp
        self.formatted_time = formatted_time

class VideoSaveTask:
    def __init__(self, frame_list, timestamp, formatted_time):
        self.frame_list = self._deep_copy_frame_list(frame_list)
        self.timestamp = timestamp
        self.formatted_time = formatted_time
    
    def _deep_copy_frame_list(self, original_frame_list):
        copied_list = FrameList()
        copied_frames = []
        
        for frame_wrapper in original_frame_list._list:
            copied_frame = type(frame_wrapper)(
                frame=frame_wrapper.frame.copy(),
                metadata=frame_wrapper.metadata,
                runtime_metadata=frame_wrapper.runtime_metadata,
                timestamp=frame_wrapper.timestamp
            )
            copied_frames.append(copied_frame)
        
        copied_list._list = copied_frames
        copied_list._capacity = original_frame_list._capacity
        return copied_list

class App:
    def __init__(self):
        self.red_gain = 2.25
        self.blue_gain = 3.25
        self.analogue_gain = 1.0
        self.exposure_time = 33000
        
        # Display rotation configuration
        self.rotate_180 = True  # Set to True for 180° rotation

        self.total_photos_saved = 0
        self.total_videos_saved = 0
        self.photo_save_status = "idle"
        self.video_save_status = "idle"
        self.video_frames_processed = 0
        self.video_total_frames = 0
        self.last_saved_filename = ""
        
        self.is_auto_colors = False
        self.set_auto_timestamp = 0
        
        self.active_slider = None
        self.active_button = None
        
        # UI update control
        self.ui_update_requested = threading.Event()
        self.ui_lock = threading.Lock()
        self.last_camera_params = None
        
        self.init_directories()
        self.init_screen()
        self.init_ui()
        self.init_camera()
        self.init_saving_threads()
        self.init_servers()
        
        # Start UI update thread
        self.ui_thread = threading.Thread(target=self._ui_update_loop, daemon=True)
        self.ui_thread.start()
        
        self.update_display()

    def init_directories(self):
        self.galleries_path = "./galleries/"
        
        if os.path.exists(self.galleries_path):
            for gallery in os.listdir(self.galleries_path):
                folder_path = os.path.join(self.galleries_path, gallery)
                if os.path.isdir(folder_path) and not os.listdir(folder_path):
                    os.rmdir(folder_path)
        
        if not os.path.exists(self.galleries_path):
            os.makedirs(self.galleries_path)
            
        galleries = [d for d in os.listdir(self.galleries_path) if os.path.isdir(os.path.join(self.galleries_path, d))]
        boot_numbers = []
        for gallery in galleries:
            if gallery.startswith("boot_"):
                try:
                    boot_numbers.append(int(gallery.split("_")[1]))
                except ValueError:
                    pass
        
        boot_no = max(boot_numbers) + 1 if boot_numbers else 1
        self.current_gallery = os.path.join(self.galleries_path, f"boot_{boot_no:04d}")
        os.makedirs(self.current_gallery, exist_ok=True)

    def init_saving_threads(self):
        self.photo_save_queue = queue.Queue()
        self.video_save_queue = queue.Queue()
        
        self.photo_save_thread = threading.Thread(target=self._photo_save_worker, daemon=True)
        self.video_save_thread = threading.Thread(target=self._video_save_worker, daemon=True)
        
        self.photo_save_thread.start()
        self.video_save_thread.start()

    def init_servers(self):
        self.servers = [
            ("Camera configuration server", CameraServer(camera=self.camera, callback_capture=self.camera.capture_and_save, port=4500)),
            ("Camera controls frontend", StaticHTTPServer("./src/client", port=4600)),
            ("Gallery", StaticHTTPServer("./galleries/", port=4800)),
            ("Image stream", ImageStream(5000)),
        ]

        for name, server in self.servers:
            print(f"Starting: {name}")
            server.start()

        self.image_server = self.servers[-1][1]

    def _ui_update_loop(self):
        """Independent UI update loop running at 60Hz"""
        last_canvas = None
        
        while True:
            try:
                # Always try to update UI at 60Hz, regardless of camera status
                start_time = time.time()
                
                # Check if camera parameters changed and sync UI
                self._check_and_sync_camera_params()
                
                # Update display - always update even if camera is reconfiguring
                with self.ui_lock:
                    # Keep using last valid canvas if current one is None/invalid
                    if self.canvas is not None and self.canvas.size > 0:
                        last_canvas = self.canvas.copy()
                    
                    if last_canvas is not None:
                        self.update_display_with_canvas(last_canvas)
                
                # Maintain 60Hz timing
                elapsed = time.time() - start_time
                sleep_time = max(0, (1/60) - elapsed)
                time.sleep(sleep_time)
                    
            except Exception as e:
                print(f"Error in UI update loop: {e}")
                time.sleep(1/60)

    def _check_and_sync_camera_params(self):
        """Check if camera parameters changed and sync sliders accordingly"""
        try:
            current_params = self.camera._params_latest
            
            # Check if parameters changed
            if (self.last_camera_params is None or 
                current_params.exposure_time != self.last_camera_params.exposure_time or
                current_params.analogue_gain != self.last_camera_params.analogue_gain or
                current_params.colour_gains != self.last_camera_params.colour_gains):
                
                # Update local values
                self.exposure_time = current_params.exposure_time
                self.analogue_gain = current_params.analogue_gain
                self.red_gain = current_params.colour_gains[0]
                self.blue_gain = current_params.colour_gains[1]
                
                # Sync sliders (only if not currently being dragged)
                if not self.active_slider:
                    for slider in self.sliders:
                        if slider.callback == self.__shutter_callback:
                            slider.value = self.exposure_time
                        elif slider.callback == self.__gain_callback:
                            slider.value = self.analogue_gain
                        elif slider.callback == self.__gain_r_callback:
                            slider.value = self.red_gain
                        elif slider.callback == self.__gain_b_callback:
                            slider.value = self.blue_gain
                
                self.last_camera_params = current_params
                
        except Exception as e:
            print(f"Error syncing camera params: {e}")

    def _photo_save_worker(self):
        while True:
            try:
                task = self.photo_save_queue.get()
                if task is None:
                    break
                
                self.photo_save_status = "saving"
                filename = f"{task.formatted_time}.png"
                filepath = os.path.join(self.current_gallery, filename)
                
                cv.imwrite(filepath, task.frame)
                
                self.total_photos_saved += 1
                self.last_saved_filename = filename
                self.photo_save_status = "idle"
                
                print(f"Photo saved: {filename}")
                self.photo_save_queue.task_done()
                
                # Request UI update
                self.ui_update_requested.set()
                
            except Exception as e:
                self.photo_save_status = "error"
                print(f"Error saving photo: {e}")

    def _video_save_worker(self):
        while True:
            try:
                task = self.video_save_queue.get()
                if task is None:
                    break
                
                self.video_save_status = "processing"
                self.ui_update_requested.set()
                
                all_frames = task.frame_list._list
                frames = list(all_frames) if hasattr(all_frames, '__iter__') else []
                frames.sort(key=lambda f: f.timestamp)
                
                if not frames:
                    self.video_save_status = "idle"
                    self.video_save_queue.task_done()
                    continue
                
                self.video_total_frames = len(frames)
                self.video_frames_processed = 0
                
                frames_folder_name = task.formatted_time
                frames_folder_path = os.path.join(self.current_gallery, frames_folder_name)
                os.makedirs(frames_folder_path, exist_ok=True)
                
                frame_count = 0
                
                for frame in frames:
                    frame_filename = f"{frame_count:04d}.png"
                    frame_path = os.path.join(frames_folder_path, frame_filename)
                    cv.imwrite(frame_path, frame.frame)
                    frame_count += 1
                    self.video_frames_processed = frame_count
                    
                    # Update UI every 10 frames
                    if frame_count % 10 == 0:
                        self.ui_update_requested.set()
                
                self.total_videos_saved += 1
                self.video_save_status = "idle"
                self.video_frames_processed = 0
                self.video_total_frames = 0
                
                print(f"Video frames saved: {task.formatted_time}")
                self.video_save_queue.task_done()
                self.ui_update_requested.set()
                
            except Exception as e:
                self.video_save_status = "error"
                print(f"Error in video save thread: {e}")



    def init_camera(self):
        self.camera = Camera()
        # Use the values we initialized with
        self.camera.reconfigure(CameraParameters(
            analogue_gain=self.analogue_gain,
            colour_gains=(self.red_gain, self.blue_gain),
            exposure_time=self.exposure_time,
            AeEnable=True, 
            AwbEnable=True
        ))
        self.camera.capture(-1)
        # Sync sliders after camera is initialized
        self._sync_sliders_to_camera()

    def init_screen(self):
        self.fb, self.fbmap, self.width, self.height, self.bpp, self.frame_size = init_framebuffer()
        self.canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
    def init_ui(self):
        self.sliders = [
            Slider(40, 80, 720, 144, 33_000*4, 50, UI_NAMES.SHUTTER_SLIDER, self.__shutter_callback),
            Slider(40, 320, 200, 1, 22, 0.1, UI_NAMES.GAIN_SLIDER, self.__gain_callback),
            Slider(100+50, 380, 500, 0.5, 7.0, 0.1, UI_NAMES.GAIN_B_SLIDER, self.__gain_b_callback),
            Slider(100+50, 440, 500, 0.5, 7.0, 0.1, UI_NAMES.GAIN_R_SLIDER, self.__gain_r_callback),
        ]
        self.buttons = [   
            Button(-120+50, 420, 200, 100, "PH", (0, 0, 0), -45, self.__shot_callback),
            Button(620+50, 420, 200, 100, "VI", (0, 0, 0), 45, self.__video_callback),
            Button(590, 0, 200, 20, "X", (0, 0, 0), 0, self.__shot_callback),
            Button(20, 200, 50, 50, "Auto", (0, 120, 120), 0, self.__auto_callback),
            Button(20, 120, 50, 50, "Manual", (120, 120, 0), 0, self.__auto_callback)

        ]

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
        
        # Apply rotation if enabled
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
        
        # Request UI update on any touch event
        self.ui_update_requested.set()
        
    def __auto_callback(self, name):
        if name == "Auto":
            self.camera.set_auto()
        else:
            self.camera.disable_auto()
            
    def __shutter_callback(self, name, value):        
        self.exposure_time = int(value)
        # Use quick update instead of full reconfigure
        if not self.camera.quick_update_exposure(self.exposure_time):
            # Fallback to full reconfigure if quick update fails
            self.camera.reconfigure(self.camera.make_update_parameters("ExposureTime", self.exposure_time))

    def __gain_r_callback(self, name, value):
        self.red_gain = value
        self._update_colour_gains()

    def __gain_b_callback(self, name, value):
        self.blue_gain = value
        self._update_colour_gains()
    
    def _update_colour_gains(self):
        try:
            # Use quick update instead of full reconfigure
            if not self.camera.quick_update_colour_gains((self.red_gain, self.blue_gain)):
                # Fallback to full reconfigure if quick update fails
                self.camera.reconfigure(self.camera.make_update_parameters(
                    "ColourGains", (self.red_gain, self.blue_gain)
                ))
        except Exception as e:
            print(f"Error updating colour gains: {e}")

    def _sync_sliders_to_camera(self):
        """Force sync sliders to current camera parameters"""
        try:
            latest_params = self.camera._params_latest
            
            for slider in self.sliders:
                if slider.callback == self.__shutter_callback:
                    slider.value = latest_params.exposure_time
                elif slider.callback == self.__gain_callback:
                    slider.value = latest_params.analogue_gain
                elif slider.callback == self.__gain_r_callback:
                    slider.value = latest_params.colour_gains[0]
                elif slider.callback == self.__gain_b_callback:
                    slider.value = latest_params.colour_gains[1]
            
            # Update local values
            self.exposure_time = latest_params.exposure_time
            self.analogue_gain = latest_params.analogue_gain
            self.red_gain = latest_params.colour_gains[0]
            self.blue_gain = latest_params.colour_gains[1]
            
            self.last_camera_params = latest_params
            
        except Exception as e:
            print(f"Error syncing sliders to camera: {e}")

    def __shot_callback(self, name):
        self.take_photo()

    def __video_callback(self, name):
        self.save_video()
    
    def __gain_callback(self, name, value):
        self.analogue_gain = value
        # Use quick update instead of full reconfigure
        if not self.camera.quick_update_gain(self.analogue_gain):
            # Fallback to full reconfigure if quick update fails
            self.camera.reconfigure(self.camera.make_update_parameters("AnalogueGain", self.analogue_gain))

    def take_photo(self):
        try:
            frame_wrapper = self.camera.capture(0.1)

            timestamp = time.time()
            now = datetime.fromtimestamp(timestamp)
            formatted_time = now.strftime("%Y.%m.%d-%H:%M:%S.%f")[:-3]
            
            task = PhotoSaveTask(frame_wrapper.frame, timestamp, formatted_time)
            self.photo_save_queue.put(task)
            
        except Exception as e:
            print(f"Error taking photo: {e}")

    def save_video(self):
        try:
            timestamp = time.time()
            now = datetime.fromtimestamp(timestamp)
            formatted_time = now.strftime("%Y.%m.%d-%H:%M:%S.%f")[:-3]
            
            framelist_copy = self.camera.frames
            
            task = VideoSaveTask(framelist_copy, timestamp, formatted_time)
            self.video_save_queue.put(task)
            
            print(f"Video queued for processing: {formatted_time}")
            
        except Exception as e:
            print(f"Error saving video: {e}")

    def draw_status_info(self, frame):
        font = cv.FONT_HERSHEY_SIMPLEX
        font_scale = 0.38
        thickness = 1
        shadow_offset = 1
        line_height = 14

        text_start_x = self.width - 200 - 10
        text_start_y = 200 + 30

        status_lines = [
            f"Photos: {self.total_photos_saved}, Videos: {self.total_videos_saved}",
            f"P: {self.photo_save_status}",
        ]

        if self.video_save_status != "idle":
            if self.video_save_status == "processing" and self.video_total_frames > 0:
                status_lines.append(f"V: {self.video_frames_processed}/{self.video_total_frames}")
            else:
                status_lines.append(f"V: {self.video_save_status}")

        for i, text in enumerate(status_lines):
            y = text_start_y + (i * line_height)
            if y < frame.shape[0] - 10:
                cv.putText(frame, text, (text_start_x + shadow_offset, y + shadow_offset), 
                          font, font_scale, (0, 0, 0), 2)
                cv.putText(frame, text, (text_start_x, y), 
                          font, font_scale, (255, 255, 255), 1)

    def make_step(self):
        """Main camera processing loop - now separate from UI updates"""
        try:
            frame_wrapper = self.camera.capture(0)
            if frame_wrapper is None or frame_wrapper.frame is None:
                return  # Skip this frame but don't stop UI updates
                
            display_frame = frame_wrapper.frame.copy()
            
            aspect_ratio = display_frame.shape[1] / display_frame.shape[0]
            new_width = int(self.height * aspect_ratio)
            lores = cv.resize(display_frame, (new_width, self.height), interpolation=cv.INTER_NEAREST)

            image_offset = 70
            
            if new_width < self.width:
                pad_left = (self.width - new_width) // 2 - image_offset
                pad_right = self.width - new_width - pad_left
                if pad_left < 0:
                    image_offset = (self.width - new_width) // 2
                    pad_left = 0
                    pad_right = self.width - new_width
                
                lores = cv.copyMakeBorder(
                    lores, 0, 0, pad_left, pad_right, cv.BORDER_CONSTANT, value=[0, 0, 0]
                )
            elif new_width > self.width:
                start_x = (new_width - self.width) // 2 - image_offset 
                if start_x < 0:
                    start_x = 0
                lores = lores[:, start_x:start_x + self.width]

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

            crop_color = np.mean(crop, axis=(0, 1)).astype(np.uint8)
            b, g, r = crop_color[0], crop_color[1], crop_color[2]
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

            lores_h, lores_w = lores.shape[:2]
            crop_x = lores_w - display_crop_size - margin  
            crop_y = margin 
            lores[crop_y:crop_y + display_crop_size, crop_x:crop_x + display_crop_size] = crop_display

            # Update canvas and image server only when we have valid frame
            with self.ui_lock:
                self.canvas = lores
                
            self.image_server.input_image(lores)
            
            ### GAIN ADJ
            
            if self.is_auto_colors:
                self.camera.set_auto()
                self.is_auto_colors = False
                # means = np.mean(self.camera.capture(0).frame, axis=(0, 1))
                # mean_r, mean_g, mean_b = means
# 
                # cur_red_gain, cur_blue_gain = self.camera._params_latest.colour_gains
                # corr_r = mean_g / mean_r
                # corr_b = mean_g / mean_b
                # target_red_gain = cur_red_gain / corr_r
                # target_blue_gain = cur_blue_gain / corr_b
                # 
                # tolerance = 0.02  
                # adjustment_rate = 0.05
                #  
                # if abs(corr_r - 1.0) > tolerance:
                #     new_red_gain = cur_red_gain * (1 - adjustment_rate) + target_red_gain * adjustment_rate
                # else:
                #     new_red_gain = cur_red_gain
                #     
                # if abs(corr_b - 1.0) > tolerance:
                #     new_blue_gain = cur_blue_gain * (1 - adjustment_rate) + target_blue_gain * adjustment_rate
                # else:
                #     new_blue_gain = cur_blue_gain
                # 
                # new_red_gain = np.clip(new_red_gain, 0.5, 4.0)
                # new_blue_gain = np.clip(new_blue_gain, 0.5, 4.0)

                # self.camera.quick_update_colour_gains((new_red_gain, new_blue_gain))

            ###
            
        except Exception as e:
            print(f"Error in make_step: {e}")
            # Don't update canvas if there's an error, UI will keep using last valid frame

    def update_display_with_canvas(self, canvas):
        """Update the display with provided canvas"""
        # Create a copy to avoid modifying the original
        display_canvas = canvas.copy()
        
        for slider in self.sliders: 
            slider.draw(display_canvas)
        for button in self.buttons: 
            button.draw(display_canvas)
        
        self.draw_status_info(display_canvas)
        
        # Apply rotation if enabled
        if self.rotate_180:
            display_canvas = cv.rotate(display_canvas, cv.ROTATE_180)
        
        frame_bgra = frame_to_framebuffer_format(display_canvas, self.width, self.height)
        write_frame_to_fb(frame_bgra, self.fbmap)

    def update_display(self):
        """Update the display with current UI state"""
        if self.canvas is not None and self.canvas.size > 0:
            self.update_display_with_canvas(self.canvas)

    def cleanup(self):
        try:
            self.photo_save_queue.put(None)
            self.video_save_queue.put(None)
            self.photo_save_thread.join(timeout=2.0)
            self.video_save_thread.join(timeout=2.0)
            
            self.fb.close()
        except Exception as e:
            print(f"Error during cleanup: {e}")

def main():
    app = App()
    touch_device = find_touch_device()
    
    if touch_device:
        touch_thread = threading.Thread(
            target=touch_monitor_thread, 
            args=(touch_device, app), 
            daemon=True
        )
        touch_thread.start()
        
        try:
            print("Camera app started. Press Ctrl+C to exit.")
            print(f"Gallery directory: {app.current_gallery}")
            
            while True:
                # Camera processing at 30fps
                time.sleep(1/30)
                app.make_step()
                
        except KeyboardInterrupt:
            print("\nShutting down...")
    else:
        print("ERROR: No touch device found!")
        sys.exit(1)
    
    app.cleanup()

if __name__ == "__main__":
    main()