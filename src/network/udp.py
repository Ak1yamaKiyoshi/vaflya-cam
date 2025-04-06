import numpy as np
import cv2 as cv

import socket
import pickle
import struct


class UDPImageServer:
    def __init__(self, address="0.0.0.0", port=5005):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.address = (address, port)
        self.max_size = 65507

    def send_frame(self, frame: np.ndarray):
        _, decoded = cv.imencode('.jpg', frame, [cv.IMWRITE_JPEG_QUALITY, 80])
        data = pickle.dumps(decoded)

        if len(data) > self.max_size:
            chunks = [data[i:i+self.max_size] for i in range(0, len(data), self.max_size)]
            self.sock.sendto(struct.pack("!I", len(chunks)), self.address)
            for i, chunk in enumerate(chunks):
                self.sock.sendto(chunk, self.address)
        else:
            self.sock.sendto(struct.pack("!I", 1), self.address)
            self.sock.sendto(data, self.address)
