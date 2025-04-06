import json
import logging
import dataclasses
from typing import Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

import threading
from .types import CameraParameters


logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
            path = self.path.strip('/')
            
            if not path or path == 'params':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                
                params = dataclasses.asdict(self.camera_params)
                self.wfile.write(json.dumps(params).encode())
                return

            if path == 'analogue_gain':
                value = self.camera_params.analogue_gain
            elif path == 'colour_gains':
                value = self.camera_params.colour_gains
            elif path == 'exposure_time':
                value = self.camera_params.exposure_time
            elif path == 'resolution':
                value = self.camera_params.resolution
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Parameter not found"}).encode())
                return
            
            # Send the parameter value
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"value": value}).encode())
            
        except Exception as e:
            logger.error(f"Error handling GET request: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        try:
            path = self.path.strip('/')

            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(post_data)
            except json.JSONDecodeError:
                form_data = parse_qs(post_data)
                data = {k: v[0] for k, v in form_data.items()} if form_data else {}

            updated_params = dataclasses.asdict(self.camera_params)
            changed = False

            if path == 'analogue_gain' and 'value' in data:
                self.camera_params.analogue_gain = float(data['value'])
                updated_params['analogue_gain'] = self.camera_params.analogue_gain
                changed = True
                
            elif path == 'colour_gains' and 'red' in data and 'blue' in data:
                self.camera_params.colour_gains = (float(data['red']), float(data['blue']))
                updated_params['colour_gains'] = self.camera_params.colour_gains
                changed = True
                
            elif path == 'red_gain' and 'value' in data:
                red = float(data['value'])
                blue = self.camera_params.colour_gains[1]
                self.camera_params.colour_gains = (red, blue)
                updated_params['colour_gains'] = self.camera_params.colour_gains
                changed = True
                
            elif path == 'blue_gain' and 'value' in data:
                red = self.camera_params.colour_gains[0]
                blue = float(data['value'])
                self.camera_params.colour_gains = (red, blue)
                updated_params['colour_gains'] = self.camera_params.colour_gains
                changed = True
                
            elif path == 'exposure_time' and 'value' in data:
                self.camera_params.exposure_time = int(data['value'])
                updated_params['exposure_time'] = self.camera_params.exposure_time
                changed = True
                print(path, data)
                print(self.camera_params.exposure_time)
                
            elif path == 'resolution' and 'width' in data and 'height' in data:
                self.camera_params.resolution = (int(data['width']), int(data['height']))
                updated_params['resolution'] = self.camera_params.resolution
                changed = True
                
            elif path == 'params':
                if 'analogue_gain' in data:
                    self.camera_params.analogue_gain = float(data['analogue_gain'])
                if 'colour_gains' in data and isinstance(data['colour_gains'], list) and len(data['colour_gains']) == 2:
                    self.camera_params.colour_gains = tuple(data['colour_gains'])
                elif 'red_gain' in data and 'blue_gain' in data:
                    self.camera_params.colour_gains = (float(data['red_gain']), float(data['blue_gain']))
                if 'exposure_time' in data:
                    self.camera_params.exposure_time = int(data['exposure_time'])
                if 'resolution' in data and isinstance(data['resolution'], list) and len(data['resolution']) == 2:
                    self.camera_params.resolution = tuple(data['resolution'])
                elif 'width' in data and 'height' in data:
                    self.camera_params.resolution = (int(data['width']), int(data['height']))
                changed = True
                updated_params = dataclasses.asdict(self.camera_params)

            elif path == "capture":
                if self.capture_callback is not None:
                    self.capture_callback()

            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Parameter not found"}).encode())
                return
            
            if changed and self.param_callback:
                self.param_callback(self.camera_params, path)        
    
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "params": updated_params}).encode())
            
        except Exception as e:
            logger.error(f"Error handling POST request: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

class CameraServer:
    def __init__(self, host='0.0.0.0', port=8081, callback: Callable[[CameraParameters], None] = None, callback_capture=None):
        self.host = host
        self.port = port
        self.server = None
        self.param_callback = callback
        self.capture_callback = callback_capture

        self.camera_params = CameraParameters(
            analogue_gain=1.0,
            colour_gains=(1.0, 1.0),
            exposure_time=10000,  # 
            resolution=(2028, 1520)
        )

    def start(self):
        CameraParameterHandler.camera_params = self.camera_params
        CameraParameterHandler.param_callback = self.param_callback
        CameraParameterHandler.capture_callback = self.capture_callback

        self.server = HTTPServer((self.host, self.port), CameraParameterHandler)

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        
    def stop(self):
        if self.server:
            self.server.shutdown()
