from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from aos.node import Node

class CameraParameterHandler(BaseHTTPRequestHandler):
    capture_callback = None
    parameter_callback = None
    _latest_params = {}

    @classmethod
    def set_callbacks(cls, parameter_callback=None, capture_callback=None):
        cls.parameter_callback = parameter_callback
        cls.capture_callback = capture_callback

    @classmethod
    def set_latest_params(cls, params):
        cls._latest_params = params.copy() if isinstance(params, dict) else {}

    @classmethod
    def get_latest_params(cls):
        return cls._latest_params.copy()

    @classmethod
    def update_param(cls, param_name, value):
        cls._latest_params[param_name] = value

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Access-Control-Allow-Headers, Authorization, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_response_with_cors(self, status_code, content_type="application/json", data=None):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self._send_cors_headers()
        self.end_headers()
        if data:
            self.wfile.write(json.dumps(data).encode() if isinstance(data, dict) else data)

    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self._send_response_with_cors(200, "text/plain", b"OK")

    def do_GET(self):
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path.strip("/")
            query = parse_qs(parsed_url.query)
            
            if path in ["analogue_gain", "red_gain", "blue_gain", "exposure_time"] and 'value' in query:
                value = float(query['value'][0])
                
                if path == "analogue_gain":
                    self._latest_params["analogue_gain"] = value
                elif path == "red_gain":
                    gains = self._latest_params.get("colour_gains", [1.0, 1.0])
                    self._latest_params["colour_gains"] = [gains[0], value]
                elif path == "blue_gain":
                    gains = self._latest_params.get("colour_gains", [1.0, 1.0])
                    self._latest_params["colour_gains"] = [value, gains[1]]
                elif path == "exposure_time":
                    self._latest_params["exposure_time"] = value
                
                self._latest_params["AeEnable"] = False
                self._latest_params["AwbEnable"] = False
                self._latest_params["auto_mode"] = False
                
                if self.parameter_callback:
                    self.parameter_callback(path, value, auto_disable=True)
                
                self._send_response_with_cors(200, data={"status": "success"})
                return
            
            if path == "auto_mode":
                ae_enable = self._latest_params.get("AeEnable", False)
                awb_enable = self._latest_params.get("AwbEnable", False)
                is_auto = ae_enable and awb_enable
                
                self._send_response_with_cors(200, data={"auto_mode": is_auto})
                return
            
            if path == "capture":
                if self.capture_callback is not None:
                    self.capture_callback()
                
                self._send_response_with_cors(200, data={"status": "success"})
                return
            
            if not path or path == "params":
                params = self._latest_params.copy()
                ae_enable = params.get("AeEnable", False)
                awb_enable = params.get("AwbEnable", False)
                params["auto_mode"] = ae_enable and awb_enable
                
                self._send_response_with_cors(200, data=params)
                return

            if path in ["analogue_gain", "colour_gains", "exposure_time", "resolution"]:
                if path in self._latest_params:
                    value = self._latest_params[path]
                    self._send_response_with_cors(200, data={"value": value})
                    return
                else:
                    self._send_response_with_cors(404, data={"error": "Parameter not found"})
                    return
            
            self._send_response_with_cors(404, data={"error": "Endpoint not found"})

        except Exception as e:
            self._send_response_with_cors(500, data={"error": str(e)})

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
                if path == "auto_mode" and "enabled" in data:
                    enabled = data["enabled"]
                    
                    if enabled:
                        self._latest_params["AeEnable"] = True
                        self._latest_params["AwbEnable"] = True
                        self._latest_params["auto_mode"] = True
                    else:
                        self._latest_params["AeEnable"] = False
                        self._latest_params["AwbEnable"] = False
                        self._latest_params["auto_mode"] = False
                    
                    if self.parameter_callback:
                        self.parameter_callback("auto_mode", enabled)
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "auto_mode": enabled}).encode())
                    return
                
                if path == "analogue_gain" and "value" in data:
                    value = float(data['value'])
                    self._latest_params["analogue_gain"] = value
                    self._latest_params["AeEnable"] = False
                    self._latest_params["AwbEnable"] = False
                    self._latest_params["auto_mode"] = False
                    
                    if self.parameter_callback:
                        self.parameter_callback("analogue_gain", value, auto_disable=True)

                elif path == "red_gain" and "value" in data:
                    value = float(data["value"])
                    gains = self._latest_params.get("colour_gains", [1.0, 1.0])
                    self._latest_params["colour_gains"] = [gains[0], value]
                    self._latest_params["AeEnable"] = False
                    self._latest_params["AwbEnable"] = False
                    self._latest_params["auto_mode"] = False
                    
                    if self.parameter_callback:
                        self.parameter_callback("red_gain", value, auto_disable=True)

                elif path == "blue_gain" and "value" in data:
                    value = float(data["value"])
                    gains = self._latest_params.get("colour_gains", [1.0, 1.0])
                    self._latest_params["colour_gains"] = [value, gains[1]]
                    self._latest_params["AeEnable"] = False
                    self._latest_params["AwbEnable"] = False
                    self._latest_params["auto_mode"] = False
                    
                    if self.parameter_callback:
                        self.parameter_callback("blue_gain", value, auto_disable=True)

                elif path == "exposure_time" and "value" in data:
                    value = float(data['value'])
                    self._latest_params["exposure_time"] = value
                    self._latest_params["AeEnable"] = False
                    self._latest_params["AwbEnable"] = False
                    self._latest_params["auto_mode"] = False
                    
                    if self.parameter_callback:
                        self.parameter_callback("exposure_time", value, auto_disable=True)

                elif path == "capture":
                    if self.capture_callback is not None:
                        self.capture_callback()
                    
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

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode())

            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


class ServerNode(Node):
    def _init(self):
        
        CameraParameterHandler.set_callbacks(
            parameter_callback=self.callback,
            capture_callback=self.capture_callback
        )
        
        initial_params = {
            "analogue_gain": 1.0,
            "colour_gains": [1.0, 1.0],
            "exposure_time": 1000,
            "resolution": [1920, 1080],
            "AeEnable": False,
            "AwbEnable": False
        }
        CameraParameterHandler.set_latest_params(initial_params)

    def callback(self, param_name, value, auto_disable=False):
        param_mapping = {
            "auto_mode": "auto",
            "analogue_gain": "gain", 
            "exposure_time": "shutter",
            "red_gain": "gain_red",
            "blue_gain": "gain_blue"
        }
        
        emit_name = param_mapping.get(param_name, param_name)
        self._emit(emit_name, value)
        
        if auto_disable and param_name != "auto_mode":
            self._emit("auto", False)
        
        return True

    def capture_callback(self):
        self._emit("capture", True)

    def set_parameter(self, param_name, value):
        CameraParameterHandler.update_param(param_name, value)

    def set_parameters(self, camera_params):
        CameraParameterHandler.set_latest_params(camera_params)

    def set_auto(self, value):
        CameraParameterHandler.update_param("AeEnable", value)
        CameraParameterHandler.update_param("AwbEnable", value)
        CameraParameterHandler.update_param("auto_mode", value)

    def set_gain(self, value):
        CameraParameterHandler.update_param("analogue_gain", value)

    def set_shutter(self, value):
        CameraParameterHandler.update_param("exposure_time", value)

    def set_gain_red(self, value):
        current_params = CameraParameterHandler.get_latest_params()
        gains = current_params.get("colour_gains", [1.0, 1.0])
        new_gains = [gains[0], value]
        CameraParameterHandler.update_param("colour_gains", new_gains)

    def set_gain_blue(self, value):
        current_params = CameraParameterHandler.get_latest_params()
        gains = current_params.get("colour_gains", [1.0, 1.0])
        new_gains = [value, gains[1]]
        CameraParameterHandler.update_param("colour_gains", new_gains)

    def request_auto(self, value):
        CameraParameterHandler.update_param("AeEnable", value)
        CameraParameterHandler.update_param("AwbEnable", value)
        CameraParameterHandler.update_param("auto_mode", value)
        self._emit("auto", value)

    def request_gain(self, value):
        CameraParameterHandler.update_param("analogue_gain", value)
        CameraParameterHandler.update_param("AeEnable", False)
        CameraParameterHandler.update_param("AwbEnable", False)
        CameraParameterHandler.update_param("auto_mode", False)
        self._emit("gain", value)

    def request_shutter(self, value):
        CameraParameterHandler.update_param("exposure_time", value)
        CameraParameterHandler.update_param("AeEnable", False)
        CameraParameterHandler.update_param("AwbEnable", False)
        CameraParameterHandler.update_param("auto_mode", False)
        self._emit("shutter", value)

    def request_gain_red(self, value):
        current_params = CameraParameterHandler.get_latest_params()
        gains = current_params.get("colour_gains", [1.0, 1.0])
        new_gains = [gains[0], value]
        CameraParameterHandler.update_param("colour_gains", new_gains)
        CameraParameterHandler.update_param("AeEnable", False)
        CameraParameterHandler.update_param("AwbEnable", False)
        CameraParameterHandler.update_param("auto_mode", False)
        self._emit("gain_red", value)

    def request_gain_blue(self, value):
        current_params = CameraParameterHandler.get_latest_params()
        gains = current_params.get("colour_gains", [1.0, 1.0])
        new_gains = [value, gains[1]]
        CameraParameterHandler.update_param("colour_gains", new_gains)
        CameraParameterHandler.update_param("AeEnable", False)
        CameraParameterHandler.update_param("AwbEnable", False)
        CameraParameterHandler.update_param("auto_mode", False)
        self._emit("gain_blue", value)

    def get_current_params(self):
        return CameraParameterHandler.get_latest_params()

    def mainloop(self, port=8080):
        from http.server import HTTPServer
        
        server_address = ('', port)
        httpd = HTTPServer(server_address, CameraParameterHandler)
        httpd.serve_forever()

