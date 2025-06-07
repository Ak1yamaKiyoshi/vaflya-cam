import sys 
import mmap
import numpy as np
import cv2 as cv

fb_device = '/dev/fb0'

def init_framebuffer():
    try:
        fb = open(fb_device, 'rb+')
        width = 800
        height = 480
        bpp = 32
        frame_size = width * height * bpp // 8
        fbmap = mmap.mmap(fb.fileno(), frame_size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ, offset=0)
        return fb, fbmap, width, height, bpp, frame_size
    except Exception as e:
        print(f"Error initializing framebuffer: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def frame_to_framebuffer_format(frame, width, height):
    if frame.shape[1] != width or frame.shape[0] != height:
        frame = cv.resize(frame, (width, height), interpolation=cv.INTER_NEAREST)

    return cv.cvtColor(frame, cv.COLOR_RGB2RGBA)

def write_frame_to_fb(frame, fbmap):
    try:
        frame_bytes = frame.tobytes()
        fbmap[:len(frame_bytes)] = frame_bytes
    except Exception as e:
        print(f"Error writing to framebuffer: {e}")