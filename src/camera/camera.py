import os
os.environ["LIBCAMERA_LOG_LEVELS"] = "3"

from .types import CameraFrameWrapper, CameraParameters
from .utils import FrameList, Config

import picamera2 as pc2
import threading
import numpy as np
import cv2 as cv
import time

from datetime import datetime



class Camera:
    def __init__(self):
        self.cfg = Config()
        self._cam = pc2.Picamera2()  
        self._cam.pre_callback = self._on_frame

        self.frames = FrameList(2)

        self._params_latest = CameraParameters(1, (2.25, 3.25), 1/64)
        self._params_request = CameraParameters(1, (2.25, 3.25), 1/64)
        self._frame_not_captured = threading.Event()
        self.reconfigure(self._params_request)

    def _on_frame(self, request):
        with pc2.MappedArray(request, "main") as m:
            frame = np.array(m.array, copy=False)
            frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

            frame_metadata = request.get_metadata()
            params = CameraParameters(
                analogue_gain=frame_metadata['AnalogueGain'],
                exposure_time=frame_metadata['ExposureTime'],
                colour_gains=frame_metadata['ColourGains'],
                resolution=frame.shape[:2][::-1]
            )

            self.frames.add(
                CameraFrameWrapper(
                    frame=frame,
                    metadata=params,
                    timestamp=time.monotonic()
                )
            )

            self._params_latest = params
            self._frame_not_captured.set()

    def reconfigure(self, params: CameraParameters):
        self._params_request = params

        self._cam.stop()
        cfg = self._cam.create_still_configuration(
            main={"size": params.resolution},
            raw={}
        )

        self._cam.configure(cfg)

        exposure_time = int(params.exposure_time) if isinstance(params.exposure_time, float) else params.exposure_time

        self._cam.set_controls({
            "AeEnable": False,
            "AwbEnable": False,
            "ExposureTime": exposure_time,
            "AnalogueGain": params.analogue_gain,
            "ColourGains": params.colour_gains,
        })

        self._cam.start()
    
    def capture(self, seconds_ago=-1):
        if seconds_ago == -1:
            self._frame_not_captured.wait()
            self._frame_not_captured.clear()

        return self.frames.get(seconds_ago)
    
    def capture_and_save(self, output_path="gallery/", seconds_ago=-1):

        print("SAVE ")        
        now = datetime.now()
        formatted_time = now.strftime("%Y.%m.%d-%H:%M:%S") + ".png"
        frame = self.capture(seconds_ago)
        path = os.path.join(output_path, formatted_time)    
        print(path)
    
        cv.imwrite(path, frame.frame)



