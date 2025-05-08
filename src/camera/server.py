import json
import logging
import dataclasses
from typing import Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

import threading
from .types import CameraParameters, CameraParameter
from .camera import Camera


logging.basicConfig(
    level=logging.CRITICAL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("camera-server")


class CameraParameterHandler(BaseHTTPRequestHandler):
    camera: Camera
    capture_callback = None

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        try:
            path = self.path.strip("/")
            if not path or path == "params":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()

                params = dataclasses.asdict(self.camera_params)
                self.wfile.write(json.dumps(params).encode())
                return

            if path == "analogue_gain":
                value = self.camera._params_latest.analogue_gain
            elif path == "colour_gains":
                value = self.camera._params_latest.colour_gains
            elif path == "exposure_time":
                value = self.camera._params_latest.exposure_time
            elif path == "resolution":
                value = self.camera._params_latest.resolution
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Parameter not found"}).encode())
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"value": value}).encode())

        except Exception as e:
            logger.error(f"Error handling GET request: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            path = self.path.strip("/")

            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(post_data)
            except json.JSONDecodeError:
                form_data = parse_qs(post_data)
                data = {k: v[0] for k, v in form_data.items()} if form_data else {}
            try:
                latest = self.camera._params_latest
                if path == "analogue_gain" and "value" in data:
                    latest.analogue_gain = float(data['value'])

                elif path == "red_gain" and "value" in data:
                    gains = latest.colour_gains 
                    latest.colour_gains = gains[0], float(data["value"])

                elif path == "blue_gain" and "value" in data:
                    gains = latest.colour_gains 
                    latest.colour_gains = float(data["value"]), gains[1]

                elif path == "exposure_time" and "value" in data:
                    latest.exposure_time = float(data['value'])

                elif path == "capture":
                    if self.capture_callback is not None:
                        self.capture_callback()

                else:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Parameter not found"}).encode())
                    return

                self.camera.reconfigure(latest)
            except Exception as e:
                print(e)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()

        except Exception as e:
            logger.error(f"Error handling POST request: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


class CameraServer:
    def __init__(
        self,
        camera: Camera, 
        host="0.0.0.0",
        port=8081,
        callback_capture=None,
    ):
        self.host = host
        self.port = port
        self.server = None
        self.camera = camera
        self.capture_callback = callback_capture

    def start(self):
        CameraParameterHandler.capture_callback = self.capture_callback
        CameraParameterHandler.camera = self.camera

        self.server = HTTPServer((self.host, self.port), CameraParameterHandler)

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.thread.join(timeout=0)
        if self.server:
            self.server.shutdown()
