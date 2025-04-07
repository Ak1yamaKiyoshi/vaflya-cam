import json
import logging
import dataclasses
from typing import Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

import threading
from .types import CameraParameters, CameraParameter


logging.basicConfig(
    level=logging.CRITICAL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("camera-server")


class CameraParameterHandler(BaseHTTPRequestHandler):
    camera_params = None
    param_callback = None
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
                value = self.camera_params.analogue_gain
            elif path == "colour_gains":
                value = self.camera_params.colour_gains
            elif path == "exposure_time":
                value = self.camera_params.exposure_time
            elif path == "resolution":
                value = self.camera_params.resolution
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

            requested_parameter = None

            try:
                data = json.loads(post_data)
            except json.JSONDecodeError:
                form_data = parse_qs(post_data)
                data = {k: v[0] for k, v in form_data.items()} if form_data else {}

            print(path, data)

            if path == "analogue_gain" and "value" in data:
                requested_parameter = CameraParameter(
                    "analogue_gain", float(data["value"])
                )

            elif path == "red_gain" and "value" in data:
                requested_parameter = CameraParameter("red_gain", float(data["value"]))

            elif path == "blue_gain" and "value" in data:
                requested_parameter = CameraParameter("blue_gain", float(data["value"]))

            elif path == "exposure_time" and "value" in data:
                requested_parameter = CameraParameter(
                    "exposure_time", int(data["value"])
                )

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

            if requested_parameter is not None and self.param_callback:
                self.param_callback(requested_parameter)

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
        host="0.0.0.0",
        port=8081,
        callback: Callable[[CameraParameters], None] = None,
        callback_capture=None,
    ):
        self.host = host
        self.port = port
        self.server = None
        self.param_callback = callback
        self.capture_callback = callback_capture

        self.camera_params = CameraParameters(
            analogue_gain=1.0,
            colour_gains=(1.0, 1.0),
            exposure_time=10000,  #
            resolution=(2028, 1520),
        )

    def start(self):
        CameraParameterHandler.camera_params = self.camera_params
        CameraParameterHandler.param_callback = self.param_callback
        CameraParameterHandler.capture_callback = self.capture_callback

        self.server = HTTPServer((self.host, self.port), CameraParameterHandler)

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.thread.join(timeout=0)
        if self.server:
            self.server.shutdown()
