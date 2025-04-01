import picamera2 as pc2
import logging
import time
import cv2 as cv
import os 
os.environ["LIBCAMERA_LOG_LEVELS"] = "3"


def seconds_to_microseconds(seconds):
    if seconds is None: return
    return int(seconds * 1_000_000)

def microseconds_to_seconds(microseconds):
    if microseconds is None: return
    return microseconds / 1_000_000


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


print(Config.max_exposue)

camera = pc2.Picamera2()
cfg = camera.create_still_configuration(
    main={"size": (4056, 3040)},
    raw={}  
)
camera.configure(cfg)

camera.set_controls({
    "AeEnable": False,
    "AwbEnable": False,
    "ExposureTime": seconds_to_microseconds(5),
    "AnalogueGain": 22.0,
    "ColourGains": (1.81, 2.81) # blue, red 
})

camera.start() # camera start should be after setting controls 

request = camera.capture_request()
metadata = request.get_metadata()

raw_buffer = request.make_buffer("raw")
camera.helpers.save_dng(raw_buffer, metadata, cfg["raw"], "outputs/raw_image.dng")

print(metadata)


