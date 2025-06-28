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

@dataclass
class CameraParameters: 
    gain: float
    shutter: float
    gain_r: float
    gain_b: float 
    resolution: Tuple[int, int]
    
    lux: float = 0.0
    temperature: float = 0.0 


class Camera(Node):
    def _init(self, 
            resolution: Tuple[int, int],
            hv_flip = True, debug=False,
              ):
        if not debug:
            os.environ["LIBCAMERA_LOG_LEVELS"] = "3"

        self._latest_frame_meta = CameraParameters(1.0, 114, 1.0, 1.0, resolution)
        self._cam = pc2.Picamera2()
        self._cam.pre_callback = self._frame
        
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
        self._cam.set_controls({
            "AnalogueGain": value
        })
    
    def set_shutter(self, value:float):
        self._cam.set_controls({
            "ExposureTime": value
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
            
            self._latest_frame_meta = meta_formatted
            self._emit("latest_frame_meta", meta_formatted)
            self._emit("frame", frame)
    