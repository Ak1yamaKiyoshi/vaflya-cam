import http.server
import socketserver
import threading
import os
import time


class StaticHTTPServer:
    def __init__(self, directory, port=8000):
        self.directory = os.path.abspath(directory)
        self.port = port
        self.server_thread = None

        handler_class = type(
            "CustomHTTPRequestHandler",
            (http.server.SimpleHTTPRequestHandler,),
            {"directory": self.directory},
        )

        class ReuseAddressServer(socketserver.TCPServer):
            allow_reuse_address = True

        self.httpd = ReuseAddressServer(("", self.port), handler_class)

    def start(self):
        if self.server_thread is not None and self.server_thread.is_alive():
            return
        self.server_thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True
        )
        self.server_thread.start()

    def serve_forever(self):
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        if hasattr(self, "httpd"):
            self.httpd.shutdown()
            self.httpd.server_close()
            time.sleep(0.1)

    def __del__(self):
        try:
            self.stop()
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=1)
        except Exception as e:
            print(f"Error during StaticHTTPServer cleanup: {e}")
