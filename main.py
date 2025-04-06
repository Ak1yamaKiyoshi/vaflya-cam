from src.camera import Camera, CameraParameters, CamUtils, CameraServer

from src.network.static import StaticHTTPServer
import cv2 as cv


import time 
import subprocess
import os

def get_ip_addresses():
    output = subprocess.check_output("hostname -I", shell=True).decode('utf-8').strip()
    ip_addresses = output.split()
    return ip_addresses

print(get_ip_addresses())
cam = Camera()
cam.reconfigure(
    CameraParameters(22, (3, 3), CamUtils.seconds_to_microseconds(1/16))
)

def rec(_, params:CameraParameters):
    cam.reconfigure(params)

camera_server = CameraServer(callback=rec, callback_capture=cam.capture_and_save, port=4500)
camera_server.start()

static_server = StaticHTTPServer("./src/client", port=4600)
static_server.start()


static_image_server = StaticHTTPServer("./gallery/", port=4800)
static_image_server.start()


os.environ['DISPLAY'] = ":0"

cv.namedWindow("f", cv.WINDOW_NORMAL)
cv.setWindowProperty("f", cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)

try:
    while True:
        # todo: a
        frame = cam.capture(-1)
        print(frame.metadata)

        cv.imshow("f", frame.frame)    
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