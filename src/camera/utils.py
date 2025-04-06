from .types import CameraFrameWrapper

import picamera2 as pc2
import numpy as np
import logging
import time

from typing import List


class Config:
    _camera = pc2.Picamera2()
    _camera.set_logging(level=logging.CRITICAL  )
    _cfg = _camera.create_still_configuration(raw={})
    _camera.configure(_cfg)

    min_gain = _camera.camera_controls["AnalogueGain"][0]
    max_gain =  _camera.camera_controls["AnalogueGain"][1]
    min_exposure = _camera.camera_controls["ExposureTime"][0]
    max_exposue = _camera.camera_controls["ExposureTime"][1]
    _camera.close()


class CamUtils: 
    @staticmethod
    def seconds_to_microseconds(seconds):
        if seconds is None: return
        return int(seconds * 1_000_000)

    @staticmethod
    def microseconds_to_seconds(microseconds):
        if microseconds is None: return
        return microseconds / 1_000_000


class FrameList: 
    def __init__(self, capacity_seconds=2):
        self._list:List[CameraFrameWrapper] = list()
        self._capacity = capacity_seconds

    def add(self, frame:CameraFrameWrapper):
        self._list.append(frame)
        to_remove = 0
        for i, f in enumerate(self._list):
            if time.monotonic() - f.timestamp > self._capacity:
                to_remove += 1
        
        self._list = self._list[to_remove:]


    def get(self, seconds_ago:float):
        time_errors = []
        for f in self._list:
            time_errors.append((time.monotonic() - seconds_ago) - f.timestamp)
        return self._list[np.argmin(time_errors)]
