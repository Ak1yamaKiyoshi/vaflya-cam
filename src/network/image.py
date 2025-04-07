import http.server
import socketserver
import numpy as np
import threading
import cv2
import socket
import time


class ImageStream:
    def __init__(self, port=9000, host=None, fps=35, jpeg_qualty=90):
        self._image = None
        self.jpeg_quality = jpeg_qualty
        self.port = port
        self.host = host or self._get_host()
        self.thread = None
        self.running = False
        self.fps = fps
        self.clients = []
        self.client_lock = threading.Lock()

    def _get_host(self):
        hostname = socket.gethostname()
        try:
            return socket.gethostbyname(hostname)
        except:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
            except Exception:
                return "127.0.0.1"
            finally:
                s.close()

    def input_image(self, image: np.ndarray):
        self._image = image

    def start(self):
        if self.thread is not None:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()
        return f"http://{self.host}:{self.port}/video.mjpg"

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
            time.sleep(0.1)

    def _run_server(self):
        handler = self._create_handler()

        class ReuseAddressServer(socketserver.TCPServer):
            allow_reuse_address = True

        with ReuseAddressServer(("", self.port), handler) as httpd:
            while self.running:
                httpd.handle_request()

    def _create_handler(self):
        stream_instance = self
        jpeg_qualty = self.jpeg_quality

        class ImageHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/video.mjpg":
                    self.send_response(200)
                    self.send_header(
                        "Content-type", "multipart/x-mixed-replace; boundary=--boundary"
                    )
                    self.send_header(
                        "Cache-Control",
                        "no-store, no-cache, must-revalidate, max-age=0",
                    )
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    try:
                        while stream_instance.running:
                            if stream_instance._image is not None:
                                image = stream_instance._image
                                _, jpeg_data = cv2.imencode(
                                    ".jpg",
                                    image,
                                    [cv2.IMWRITE_JPEG_QUALITY, jpeg_qualty],
                                )

                                self.wfile.write(b"--boundary\r\n")
                                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                                self.wfile.write(
                                    f"Content-Length: {len(jpeg_data)}\r\n\r\n".encode()
                                )
                                self.wfile.write(jpeg_data.tobytes())
                                self.wfile.write(b"\r\n")
                                time.sleep(1.0 / stream_instance.fps)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass

        return ImageHandler

    def __del__(self):
        try:
            if self.running:
                self.stop()

            self._image = None
            self.clients = []
        except Exception as e:
            print(f"Error during ImageStream cleanup: {e}")
