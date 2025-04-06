from src.camera import Camera, CameraParameters, CamUtils, CameraServer
from src.camera.server import CameraParameterHandler

from src.network.static import StaticHTTPServer
from src.network.video_display import HttpImageDisplay
import cv2 as cv
import dataclasses


import os
import signal
import psutil

import time 
import subprocess
import os

def get_ip_addresses():
    output = subprocess.check_output("hostname -I", shell=True).decode('utf-8').strip()
    ip_addresses = output.split()
    return ip_addresses

print(get_ip_addresses())
cam = Camera()



def kill_process_on_port(port):
    for proc in psutil.process_iter(['pid', 'name', 'connections']):
        try:
            for conn in proc.connections():
                if conn.laddr.port == port:
                    os.kill(proc.pid, signal.SIGTERM)
                    print(f"Killed process {proc.pid} ({proc.name()}) using port {port}")
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def rec(_, params_req:CameraParameters, typo):
    print(params_req, typo)
    
    params:CameraParameters = dataclasses.replace(cam._params_request)
    if typo == "analogue_gain":
        params.analogue_gain = params_req.analogue_gain
    elif typo == "exposure_time":
        params.exposure_time = params_req.exposure_time
    elif typo == 'red_gain':     
        params.colour_gains = (params_req.colour_gains[0], params.colour_gains[1])
    elif typo == 'blue_gain':
        params.colour_gains = (params.colour_gains[0], params_req.colour_gains[1])

    params = params_req
    print(f"SET: {params}")
    # 2484906
    if params.exposure_time == 2484906:
        
        print(f"RESET EXPOSUE: {cam._params_latest.exposure_time}")
        params.exposure_time = cam._params_latest.exposure_time
    print(f"RESETTED: {params}")
    cam.reconfigure(params)


CamUtils.seconds_to_microseconds

kill_process_on_port(4500)
kill_process_on_port(4600)
kill_process_on_port(4800)

camera_server = CameraServer(callback=rec, callback_capture=cam.capture_and_save, port=4500)
camera_server.start()

static_server = StaticHTTPServer("./src/client", port=4600)
static_server.start()


static_image_server = StaticHTTPServer("./gallery/", port=4800)
static_image_server.start()

image_display = HttpImageDisplay(5000, jpeg_quality=40)
image_display.start()

os.environ['DISPLAY'] = ":0"

cv.namedWindow("f", cv.WINDOW_NORMAL)
cv.setWindowProperty("f", cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)


def prepare_for_display(self):
    pass


prev_darkened = None
try:
    while True:
        # todo: a
        CameraParameterHandler.camera_params.analogue_gain = cam._params_request.analogue_gain
        CameraParameterHandler.camera_params.exposure_time = cam._params_request.exposure_time
        CameraParameterHandler.camera_params.colour_gains = cam._params_request.colour_gains

        # 320 x 480
        frame: CameraParameters = cam.capture(-1)

        resized = cv.resize(frame.frame, (426, 320), interpolation=cv.INTER_LANCZOS4)
        alpha = 0.5

        darkened = cv.convertScaleAbs(resized, alpha=alpha, beta=0)
        
        center_x_resized = darkened.shape[1] // 2
        center_y_resized = darkened.shape[0] // 2
        cross_size = 10

        center_color = darkened[center_y_resized, center_x_resized].tolist()
        negative_color = [255 - c for c in center_color]

        cv.line(darkened, 
            (center_x_resized - cross_size, center_y_resized),
            (center_x_resized + cross_size, center_y_resized),
            negative_color, 
            1)

        cv.line(darkened, 
            (center_x_resized, center_y_resized - cross_size),
            (center_x_resized, center_y_resized + cross_size),
            negative_color, 1)
        pad_size = 480 - 426

        padded = cv.copyMakeBorder(darkened, 0, 0, pad_size, 0, cv.BORDER_CONSTANT, value=[0, 0, 0])
        height, width = frame.frame.shape[:2]
        center_x, center_y = width // 2, height // 2
        crop_size = 150
        crop = frame.frame[center_y - crop_size//2:center_y + crop_size//2, center_x - crop_size//2:center_x + crop_size//2]
        margin = 15
        padded[320-crop_size-margin:320-margin, margin:margin+crop_size] = crop
        exposure_time = CamUtils.microseconds_to_seconds(frame.metadata.exposure_time) 
        exposure_str = f"{exposure_time}"
        font = cv.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        text_gain = f"Gain: {frame.metadata.analogue_gain:.1f}"
        text_exposure = f"Exp: {exposure_str}"
        text_x = 5
        text_y_gain = 280
        text_y_exposure = 300
        cv.putText(padded, text_gain, (text_x+1, text_y_gain+1), font, font_scale, (0, 0, 0), font_thickness + 1)
        cv.putText(padded, text_gain, (text_x, text_y_gain), font, font_scale, (255, 255, 255), font_thickness)
        cv.putText(padded, text_exposure, (text_x+1, text_y_exposure+1), font, font_scale, (0, 0, 0), font_thickness + 1)
        cv.putText(padded, text_exposure, (text_x, text_y_exposure), font, font_scale, (255, 255, 255), font_thickness)
        
        brightened = cv.convertScaleAbs(padded, alpha=1/alpha, beta=0)
        image_display.upd(brightened)

        cv.imshow("f", padded)

        cv.waitKey(100)

except KeyboardInterrupt:    
    cv.destroyAllWindows()






""" 
TODO:
    in DIsplay display LUX value, shutterspeed as fraction, gain. hz. 
    make parameters consistent over reboots 
    image stream to javascript page (http and only then webrtc)
    gallery accessible from javascipt page or last image taken 
    more detailed sliders for shutterspeed (current are not clear and difficult to operate)

    remove white borders from imshow. 


"""