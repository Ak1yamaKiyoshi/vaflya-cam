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
import cv2 as cv
import dataclasses
import numpy as np
import time
import subprocess
import os


def rec(_, params_req: CameraParameter):
    params = dataclasses.replace(cam._params_request)
    print(params_req)

    if params_req.name == "analogue_gain":
        params.analogue_gain = params_req.value

    elif params_req.name == "exposure_time":
        params.exposure_time = params_req.value

    elif params_req.name == "blue_gain":
        params.colour_gains = params.colour_gains[0], params_req.value

    elif params_req.name == "red_gain":
        params.colour_gains = params_req.value, params.colour_gains[1]

    cam.reconfigure(params)


def get_ip_addresses():
    output = subprocess.check_output("hostname -I", shell=True).decode("utf-8").strip()
    ip_addresses = output.split()
    return ip_addresses


address = get_ip_addresses()[0]
cam = Camera()

servers = [
    (
        "Camera configuration server",
        CameraServer(callback=rec, callback_capture=cam.capture_and_save, port=4500),
    ),
    ("Camera controls frontend", StaticHTTPServer("./src/client", port=4600)),
    ("Gallery", StaticHTTPServer("./gallery/", port=4800)),
    ("Image stream", ImageStream(5000)),
]

for _, server in servers:
    server.start()
    
image_display: ImageStream = servers[-1][1]


os.environ["DISPLAY"] = ":0"

cv.namedWindow("f", cv.WINDOW_NORMAL)
cv.setWindowProperty("f", cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)

print("got there")

prev_darkened = None
try:
    while True:
        # 320 x 480
        frame: CameraFrameWrapper = cam.capture(-1)
        lores = cv.resize(frame.frame, (426, 320), interpolation=cv.INTER_LANCZOS4)

        CameraParameterHandler.camera_params = cam._params_latest

        # cross cfg
        line_length = 8
        crop_line_lenght = 4
        thickness = 1

        # get hires crop from frame
        pad_side = 170
        margin = 10
        h, w = frame.frame.shape[:2]
        cx, cy = w // 2, h // 2
        crop = frame.frame[
            cy - pad_side // 2 : cy + pad_side // 2,
            cx - pad_side // 2 : cx + pad_side // 2,
        ]

        # get most contrast color
        crop_color = np.mean(crop, axis=(0, 1)).astype(np.uint8)

        r, g, b = crop_color[0], crop_color[1], crop_color[2]
        luminance = 0.299 * r + 0.587 * g + 0.114 * b

        if luminance > 127:
            color = (0, 0, 0)
        else:
            color = (255, 255, 255)

        # Calculate sharpnesss
        crop_gray = cv.cvtColor(crop, cv.COLOR_BGR2GRAY)
        g1 = cv.blur(crop_gray, (13, 13))
        edge_map = cv.absdiff(crop_gray, g1)
        sharpness = np.mean(edge_map)

        # draw cross on crop
        h, w = crop.shape[:2]
        cx, cy = w // 2, h // 2
        cv.line(
            crop,
            (cx - crop_line_lenght, cy),
            (cx + crop_line_lenght, cy),
            color,
            thickness,
        )
        cv.line(
            crop,
            (cx, cy - crop_line_lenght),
            (cx, cy + crop_line_lenght),
            color,
            thickness,
        )

        # draw cross and cxcy
        h, w = lores.shape[:2]
        cx, cy = w // 2, h // 2

        cv.line(lores, (cx - line_length, cy), (cx + line_length, cy), color, thickness)
        cv.line(lores, (cx, cy - line_length), (cx, cy + line_length), color, thickness)

        # pad left with black
        lores = cv.copyMakeBorder(
            lores, 0, 0, 480 - 426, 0, cv.BORDER_CONSTANT, value=[0, 0, 0]
        )

        # paste gires crop to lores
        lores_h, lores_w = lores.shape[:2]
        lores[
            lores_h - pad_side - margin : lores_h - margin, margin : margin + pad_side
        ] = crop

        # text
        font = cv.FONT_HERSHEY_SIMPLEX
        font_scale = 0.3
        shadow_offset = 1
        line_height = 10
        start_x = 10
        start_y = 30

        hz = len(cam.frames._list) / cam.frames._capacity

        text_items = [
            f"{address}",
            f"sharpness {sharpness:.1f}",
            f"gain {frame.metadata.analogue_gain:.1f}",
            f"shutter {CamUtils.microseconds_to_seconds(frame.metadata.exposure_time):.7f}",
            f"lux: {frame.runtime_metadata.lux}",
            f"temperature: {frame.runtime_metadata.temperature}",
            f"frames per second: {hz:3.1f}",
        ]

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

        image_display.input_image(lores)
        cv.imshow("f", lores)
        cv.waitKey(100)

except KeyboardInterrupt:
    cv.destroyAllWindows()

finally:
    for _, server in servers:
        server.stop()

""" 
Todo: 
    [high priority] Red and blue gain sliders eed more steps and less range (1.0 - 7.0)
    [high priority] Second shutter slider for more ranges of shutter.
    [high priority] Parameters should be persistent over page refreshes 
    [high priority] Controls page should have frame preview. 
        [high priority] Httpserver for videostreamonly, to be able to inject it in any other code 
        [low priority] WebRTC for that without compression. (since it uses udp streams under the hood)
    [mid priority] Camera server should set parameters per-parameter 
    [mid priority] There should be link to gallery on controlls page and last frame preview too. 
    [mid priority] Gallery should have images top-to-bottom new ones, with pagination on view. (currently list of links to images with top are older.)
    [low priority] Add EXIF to frames or use picamera helpers.
    [high priority] auto ip adress in js 
    
Done:
    [skip] How to get RAW images. (not so simple) (need for noise pattern and more natural colors).
        # low since offed denoising and this already looks ok 
    [done] Calculate good lux value and make helper that will allow not to overbrighten image
        no need for helper, lux displayed - enough
    [done] Add runtime metadata for CameraParameters or create metadata class with raw image data. (like lux, temperature, etc.)
    [done] display ip adress
    [done] remove darkening 
    [done] OFF DENOISING (actually fast denoising is good).
    [done] show sharpnesss value for better focus (actually good thing, helps a lot)
    [done] cross not actually a negative 
    [done] fps display 
"""
