import json
import logging
import dataclasses
from typing import Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import threading
from .types import CameraParameters, CameraParameter
from .camera import Camera
from dataclasses import dataclass

logging.basicConfig(
    level=logging.DEBUG,  
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("camera-server")


@dataclass
class CameraParameter:
    value: float
    min_value: float
    max_value: float
    

class CameraParameterHandler(BaseHTTPRequestHandler):
    camera: Camera
    camera_params = None
    capture_callback = None

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Access-Control-Allow-Headers, Authorization, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "86400")  # 24 hours

    def log_message(self, format, *args):
        logger.info(format % args)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b"OK")
        logger.info(f"OPTIONS request handled for {self.path}")

    def do_GET(self):
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path.strip("/")
            query = parse_qs(parsed_url.query)
            logger.info(f"GET request: {path}, query: {query}")
            
            if self.camera is None:
                logger.error("Camera not initialized")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Camera not initialized"}).encode())
                return
            
            if path in ["analogue_gain", "red_gain", "blue_gain", "exposure_time"] and 'value' in query:
                value = float(query['value'][0])
                latest = self.camera._params_latest
                
                if path == "analogue_gain":
                    latest.analogue_gain = value
                    logger.info(f"Updated analogue_gain to {value} via GET")
                elif path == "red_gain":
                    gains = latest.colour_gains
                    latest.colour_gains = gains[0], value
                    logger.info(f"Updated red_gain to {value} via GET")
                elif path == "blue_gain":
                    gains = latest.colour_gains
                    latest.colour_gains = value, gains[1]
                    logger.info(f"Updated blue_gain to {value} via GET")
                elif path == "exposure_time":
                    latest.exposure_time = value
                    logger.info(f"Updated exposure_time to {value} via GET")
                
                # Set AeEnable and AwbEnable to False when manually changing parameters
                latest.AeEnable = False
                latest.AwbEnable = False
                
                self.camera.reconfigure(latest)
                    
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode())
                return
            
            if path == "auto_mode":
                # Get the current auto mode status
                is_auto = getattr(self.camera._params_latest, "AeEnable", False) and getattr(self.camera._params_latest, "AwbEnable", False)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"auto_mode": is_auto}).encode())
                return
            
            if path == "capture":
                if self.capture_callback is not None:
                    self.capture_callback()
                    logger.info("Capture triggered via GET")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode())
                return
            
            if not path or path == "params":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()

                params = dataclasses.asdict(self.camera._params_latest)
                params["auto_mode"] = getattr(self.camera._params_latest, "AeEnable", False) and getattr(self.camera._params_latest, "AwbEnable", False)
                self.wfile.write(json.dumps(params).encode())
                logger.info(f"Sent camera parameters: {params}")
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
            logger.info(f"POST request: {path}")

            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            logger.info(f"POST data: {post_data}")

            try:
                data = json.loads(post_data)
            except json.JSONDecodeError:
                form_data = parse_qs(post_data)
                data = {k: v[0] for k, v in form_data.items()} if form_data else {}
            
            logger.info(f"Parsed data: {data}")
            
            try:
                # Handle auto mode request
                if path == "auto_mode" and "enabled" in data:
                    enabled = data["enabled"]
                    
                    if enabled:
                        logger.info("Enabling auto mode")
                        self.camera.set_auto()
                    else:
                        logger.info("Disabling auto mode")
                        # Create parameters with auto disabled
                        latest = self.camera._params_latest
                        latest.AeEnable = False
                        latest.AwbEnable = False
                        self.camera.reconfigure(latest)
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "auto_mode": enabled}).encode())
                    return
                
                latest = self.camera._params_latest
                
                if not hasattr(latest, "AeEnable"):
                    latest.AeEnable = False
                if not hasattr(latest, "AwbEnable"):
                    latest.AwbEnable = False
                
                if path == "analogue_gain" and "value" in data:
                    latest.analogue_gain = float(data['value'])
                    latest.AeEnable = False
                    latest.AwbEnable = False
                    logger.info(f"Updated analogue_gain to {data['value']}")

                elif path == "red_gain" and "value" in data:
                    gains = latest.colour_gains 
                    latest.colour_gains = gains[0], float(data["value"])
                    latest.AeEnable = False
                    latest.AwbEnable = False
                    logger.info(f"Updated red_gain to {data['value']}")

                elif path == "blue_gain" and "value" in data:
                    gains = latest.colour_gains 
                    latest.colour_gains = float(data["value"]), gains[1]
                    latest.AeEnable = False
                    latest.AwbEnable = False
                    logger.info(f"Updated blue_gain to {data['value']}")

                elif path == "exposure_time" and "value" in data:
                    latest.exposure_time = float(data['value'])
                    latest.AeEnable = False
                    latest.AwbEnable = False
                    logger.info(f"Updated exposure_time to {data['value']}")

                elif path == "capture":
                    logger.info("Capture request received")
                    if self.capture_callback is not None:
                        self.capture_callback()
                        logger.info("Capture callback executed")
                    else:
                        logger.warning("No capture callback registered")
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success"}).encode())
                    return

                else:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Parameter not found"}).encode())
                    return

                self.camera.reconfigure(latest)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode())

            except Exception as e:
                logger.error(f"Error processing request: {e}")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

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
        logger.info(f"Camera server initialized at {host}:{port}")

    def start(self):
        logger.info("Starting camera server...")
        CameraParameterHandler.capture_callback = self.capture_callback
        CameraParameterHandler.camera = self.camera
        CameraParameterHandler.camera_params = self.camera._params_latest

        self.server = HTTPServer((self.host, self.port), CameraParameterHandler)
        logger.info(f"Server created at {self.host}:{self.port}")

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info("Server thread started")

    def stop(self):
        logger.info("Stopping camera server...")
        if self.thread:
            self.thread.join(timeout=0)
        if self.server:
            self.server.shutdown()
        logger.info("Camera server stopped")