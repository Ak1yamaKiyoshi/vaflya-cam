from aos.node import Node
import os 

from libcamera import controls 
import picamera2 as pc2
import cv2 as cv
import time
import numpy as np
from dataclasses import dataclass
from typing import Tuple
import libcamera

from queue import Queue

from src.camera.utils import FrameList
from src.camera.types import CameraFrameWrapper, CameraParameter

import threading

@dataclass
class CameraParameters: 
    gain: float
    shutter: float
    gain_r: float
    gain_b: float 
    resolution: Tuple[int, int]
    
    lux: float = 0.0
    temperature: float = 0.0 


class ImageSaver:
    def __init__(self):
        self.queue = Queue()
        self.thread = threading.Thread(daemon=True, target=self.loop)
        self.thread.start()

        self.init_directories()

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

    def save(self, frame:CameraFrameWrapper):
        self.queue.put(frame)
    
    def loop(self):
        while True:
            frame_wrapper:CameraFrameWrapper = self.queue.get(block=True)
            cv.imwrite(os.path.join(self.current_gallery, f"frame_{int(time.time()*1000)}.png"), frame_wrapper.frame)

class Camera(Node):
    def _init(self, 
            resolution: Tuple[int, int],
            hv_flip = True, debug=False,
              ):
        if not debug:
            os.environ["LIBCAMERA_LOG_LEVELS"] = "3"

        self._is_auto =False
        self._latest_frame_meta = CameraParameters(1.0, 114, 1.0, 1.0, resolution)
        self._cam = pc2.Picamera2()
        self._cam.pre_callback = self._frame
        self._image_saver = ImageSaver()
        
        self.replay_buffer = FrameList(3)
        
        if hv_flip:
            print("HVFLIP")
            cfg = self._cam.create_still_configuration(
                    main={"size": resolution},
                    transform=libcamera.Transform(hflip=1, vflip=1))
        else:
            cfg = self._cam.create_still_configuration(
                    main={"size": resolution})
        
        self._cam.configure(cfg)
        self._cam.start()

    def set_gain(self, value:float):
        print("GAIN SET ")
        self._cam.set_controls({
            "AnalogueGain": value
        })
    
    def set_shutter(self, value:float):
        self._cam.set_controls({
            "ExposureTime": int(value)
        })
    
    def set_gain_red(self, value:float):
        self._cam.set_controls({
            "ColourGains": (value, self._latest_frame_meta.gain_b)
        })
    
    def set_gain_blue(self, value:float):
        self._cam.set_controls({
            "ColourGains": (self._latest_frame_meta.gain_r, value)
        })
    
    # def set_resolution(self, value:float):
    #     self._cam.set_controls({
    #         "AnalogueGain": value
    #     })

    def set_auto(self, flag:bool):
        self._is_auto = flag
        if flag:
            self._cam.set_controls({
                "AeEnable": True,
                "AwbEnable": True,
                "ExposureValue": -1.0
            })
        else:
            self._cam.set_controls({
                "AeEnable": False,
                "AwbEnable": False,
            })

    def set_take_photo(self, event):
        self._image_saver.save(self.replay_buffer.get(0))

    def set_save_rewind(self, event):
        pass

    def _frame(self, request):
        with pc2.MappedArray(request, "main") as m:
            frame = np.array(m.array, copy=False)
            frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            meta = request.get_metadata()

            meta_formatted = CameraParameters(
                gain = meta["AnalogueGain"], 
                shutter= meta["ExposureTime"],
                gain_r= meta['ColourGains'][0],
                gain_b= meta['ColourGains'][1],
                lux= meta['Lux'],
                temperature=meta['ColourTemperature'],
                resolution=frame.shape, 
            )
            
            self._emit("camera_parameters", [meta_formatted, self._is_auto])
            
            self._latest_frame_meta = meta_formatted
            self._emit("latest_frame_meta", meta_formatted)
            self._emit("frame", frame)
            self.replay_buffer.add(CameraFrameWrapper(frame,  meta_formatted, time.time(), runtime_metadata=None))
    