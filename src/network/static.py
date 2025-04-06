import http.server
import socketserver
import threading
import os

class StaticHTTPServer:
    def __init__(self, directory, port=8000):
        self.directory = os.path.abspath(directory)
        self.port = port
        self.server_thread = None

        handler_class = type('CustomHTTPRequestHandler', 
                            (http.server.SimpleHTTPRequestHandler,), 
                            {'directory': self.directory})
        
        self.httpd = socketserver.TCPServer(("", self.port), handler_class)
    
    def start(self):
        if self.server_thread is not None and self.server_thread.is_alive():
            return
            
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.daemon = True
        self.server_thread.start()
    
    def serve_forever(self):
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            self.close()
    
    def close(self):
        if hasattr(self, 'httpd'):
            self.httpd.shutdown()
            self.httpd.server_close()
    
    def __del__(self):
        self.close()
        #try:
        #    self.server_thread.join()
        #except:
        #    pass