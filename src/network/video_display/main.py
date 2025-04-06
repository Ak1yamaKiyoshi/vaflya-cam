import time
import base64
import numpy as np
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from threading import Thread, Lock

import cv2

class HttpImageDisplay:
    content = "Server started..."
    content_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Add CORS headers to all responses
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")  # Allow all origins
            self.send_header("Access-Control-Allow-Methods", "GET")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            
            if self.path.startswith("/c"):
                self.send_header("Content-type", "text/plain")
                self.end_headers()

                with HttpImageDisplay.content_lock:
                    self.wfile.write(HttpImageDisplay.content.encode())
            else:
                self.send_header("Content-type", "text/html")
                self.end_headers()

                html = """
                <html>
                <head>
                    <style>
                        body { margin: 0; padding: 0; overflow: hidden; background-color: #1e1e1e; }
                        #container { display: flex; flex-direction: column; height: 100vh; }
                        #imageContainer { flex-grow: 1; display: flex; justify-content: center; align-items: center; overflow: hidden; }
                        #stats { color: #fff; font-family: monospace; padding: 10px; background-color: #333; }
                        #display { max-width: 100%; max-height: 100%; }
                    </style>
                </head>
                <body>
                <div id="container">
                    <div id="imageContainer">
                        <img id="display" src="" alt="Camera Stream">
                    </div>
                    <div id="stats">Initializing...</div>
                </div>
                <script>
                let lastUpdate = Date.now();
                let frameCount = 0;
                let fps = 0;
                let dataSize = 0;
                let bandwidth = 0;

                let lastFrameCount = 0;
                let lastDataSize = 0;
                let lastMetricUpdate = Date.now();

                const display = document.getElementById('display');
                const stats = document.getElementById('stats');

                function updateMetrics() {
                    const now = Date.now();
                    const elapsed = (now - lastMetricUpdate) / 1000;
                    
                    if (elapsed >= 1) {
                        fps = (frameCount - lastFrameCount) / elapsed;
                        bandwidth = ((dataSize - lastDataSize) / elapsed) / 1024; // KB/s
                        
                        stats.textContent = `FPS: ${fps.toFixed(1)} | Bandwidth: ${bandwidth.toFixed(1)} KB/s | Latency: ${latency.toFixed(0)}ms`;
                        
                        lastFrameCount = frameCount;
                        lastDataSize = dataSize;
                        lastMetricUpdate = now;
                    }
                    
                    requestAnimationFrame(updateMetrics);
                }

                requestAnimationFrame(updateMetrics);

                function decompressData(compressedData) {
                    try {
                        const binaryString = atob(compressedData);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }
                        
                        return bytes;
                    } catch (e) {
                        console.error('Error decompressing:', e);
                        return null;
                    }
                }

                let fetchInProgress = false;
                let latency = 0;
                const maxFPS = 15;
                const minFrameTime = 1000 / maxFPS;
                let lastFrameTime = 0;
                let lastFetchTime = Date.now(); // Track when the last fetch completed

                function scheduleFetch() {
                    const now = Date.now();
                    const elapsed = now - lastFrameTime;
                    const delay = Math.max(0, minFrameTime - elapsed);
                    setTimeout(fetchImage, delay);
                }

                function checkFetchTimeout() {
                    const now = Date.now();
                    const timeSinceLastFetch = now - lastFetchTime;
                    
                    // If no fetch in the last 0.5 seconds and no fetch is currently in progress, trigger a new fetch
                    if (timeSinceLastFetch > 500 && !fetchInProgress) {
                        console.log("No fetch in the last 0.5 seconds, triggering refetch");
                        fetchImage();
                    }
                    
                    // Check again in 100ms
                    setTimeout(checkFetchTimeout, 100);
                }

                // Start the fetch timeout checker
                checkFetchTimeout();

                function fetchImage() {
                    if (fetchInProgress) {
                        return;
                    }
                    
                    fetchInProgress = true;
                    lastFrameTime = Date.now();
                    const startTime = Date.now();
                    
                    fetch('c?' + startTime)
                        .then(r => {
                            return r.text();
                        })
                        .then(encodedData => {
                            if (encodedData.startsWith('data:image')) {
                                display.src = encodedData;
                            } else {
                                display.src = encodedData;
                            }

                            dataSize += encodedData.length;
                            frameCount++;
                            latency = Date.now() - startTime;
                            
                            fetchInProgress = false;
                            lastFetchTime = Date.now(); // Update the last fetch time
                            scheduleFetch();
                        })
                        .catch(err => {
                            console.error('Fetch error:', err);
                            fetchInProgress = false;
                            lastFetchTime = Date.now(); // Update even on error to prevent immediate retries on persistent errors
                            setTimeout(fetchImage, 500);
                        });
                }

                fetchImage();
                </script>
                </body>
                </html>
                """
                self.wfile.write(html.encode())

        def log_message(*a):
            pass

    def __init__(self, port=9000, host="0.0.0.0", jpeg_quality=100, max_size=(6000, 6000)):
        self.port = port
        self.host = host
        self.server = None
        self.thread = None
        self.jpeg_quality = jpeg_quality
        self.max_size = max_size

    def upd(self, content):
        assert isinstance(content, np.ndarray), "Content must be a numpy array"
        
        if len(content.shape) == 3 and content.shape[2] == 3:
            image = content
        else:
            image = content
        
        h, w = image.shape[:2]
        max_w, max_h = self.max_size
        
        if w > max_w or h > max_h:
            scale = min(max_w / w, max_h / h)
            new_size = (int(w * scale), int(h * scale))
            
            image = cv2.resize(image, new_size, interpolation=cv2.INTER_NEAREST)
        
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        _, img_data = cv2.imencode('.jpg', image, encode_params)

        b64_data = base64.b64encode(img_data).decode('ascii')
        data_url = f"data:image/jpeg;base64,{b64_data}"

        with self.content_lock:
            HttpImageDisplay.content = data_url

    def input_image(self, image):
        self.upd(image)

    def start(self):
        if self.server is None:
            self.server = HTTPServer((self.host, self.port), self.Handler)
            self.thread = Thread(target=self.server.serve_forever)
            self.thread.daemon = True
            self.thread.start()
            print(f"Image server running at http://{self.host}:{self.port}")
            return self

    def join(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = self.thread = None