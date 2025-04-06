import asyncio
import fractions
import json
import logging
import threading
import time
from typing import Dict, Optional, Tuple, List
import gc

import cv2
import numpy as np
from av import VideoFrame
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRelay, MediaStreamError
from aiohttp import web

# Disable most logging
logging.basicConfig(level=logging.CRITICAL)
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

class LowCpuVideoTrack(MediaStreamTrack):
    """CPU-optimized video track."""
    kind = "video"

    def __init__(self):
        super().__init__()
        self.frame = None
        self.stopped = False
        self._start = time.time()
        self._frame_count = 0
        self._black_frame = np.zeros((120, 160, 3), dtype=np.uint8)
        self._lock = threading.Lock()
        
    def update_frame(self, frame):
        """Update the current frame with high-quality resizing."""
        # Preserve aspect ratio with smaller side at 640px
        height, width = frame.shape[:2]
        if height <= width:
            # Height is smaller
            new_height = 640
            new_width = int(width * (640 / height))
        else:
            # Width is smaller
            new_width = 640
            new_height = int(height * (640 / width))
        
        # Resize with Lanczos interpolation
        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        
        # Thread-safe update
        with self._lock:
            self.frame = frame
        
    def next_timestamp(self) -> Tuple[int, fractions.Fraction]:
        """Get timestamp for the frame."""
        time_base = fractions.Fraction(1, 9000)
        pts = int((time.time() - self._start) / time_base)
        return pts, time_base
        
    async def recv(self):
        """Return the current frame with minimal processing."""
        if self.stopped:
            raise MediaStreamError("Track ended")
        
        # Throttle frame rate
        await asyncio.sleep(0.1)
        
        # Get current frame (thread-safe)
        with self._lock:
            if self.frame is not None:
                frame_data = self.frame
            else:
                frame_data = self._black_frame
            
        # Create VideoFrame
        frame = VideoFrame.from_ndarray(frame_data, format="bgr24")
        
        # Set timestamps
        pts, time_base = self.next_timestamp()
        frame.pts = pts
        frame.time_base = time_base
        
        return frame
        
    def stop(self):
        """Stop the track."""
        self.stopped = True
        self.frame = None

@web.middleware
async def minimal_cors_middleware(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=200)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp
        
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

class WebRTCImageServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.app = web.Application(middlewares=[minimal_cors_middleware])
        
        self.app.router.add_get('/', self.index)
        self.app.router.add_post('/offer', self.handle_offer)
        
        self.peer_connections = set()
        self.tracks = []  
         
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.frame_interval = 1/60 
        self.last_frame_time = 0
        
        self._thread = None
        self._stop_event = threading.Event()
        
    async def index(self, request):
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>WebRTC Stream</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 10px; }
        video { width: 100%; max-width: 400px; background: #000; }
    </style>
</head>
<body>
    <h2>WebRTC Stream</h2>
    <video id="video" autoplay playsinline></video>
    <div><button id="start">Connect</button></div>
    <div id="status">Not connected</div>
    <script>
        const video = document.getElementById('video');
        const status = document.getElementById('status');
        
        document.getElementById('start').onclick = async () => {
            status.textContent = 'Connecting...';
            try {
                const pc = new RTCPeerConnection({
                    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                });
                
                pc.onconnectionstatechange = () => {
                    status.textContent = 'Connection state: ' + pc.connectionState;
                };
                
                pc.ontrack = e => {
                    if (e.track.kind === 'video') {
                        video.srcObject = e.streams[0];
                        status.textContent = 'Receiving video';
                    }
                };
                
                pc.addTransceiver('video', {direction: 'recvonly'});
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                
                const response = await fetch('/offer', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        sdp: pc.localDescription.sdp,
                        type: pc.localDescription.type
                    })
                });
                
                const answer = await response.json();
                await pc.setRemoteDescription(answer);
                status.textContent = 'Connected';
            } catch (e) {
                status.textContent = 'Error: ' + e.message;
                console.error(e);
            }
        };
    </script>
</body>
</html>"""
        return web.Response(content_type='text/html', text=html)
        
    async def handle_offer(self, request):
        try:
            params = await request.json()
            offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
            
            pc = RTCPeerConnection()
            self.peer_connections.add(pc)
            
            track = LowCpuVideoTrack()
            self.tracks.append(track)
            
            with self.frame_lock:
                if self.current_frame is not None:
                    track.update_frame(self.current_frame)
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                if pc.connectionState in ["failed", "closed"]:
                    if pc in self.peer_connections:
                        self.peer_connections.remove(pc)
                    track.stop()
                    if track in self.tracks:
                        self.tracks.remove(track)
                    await pc.close()
            
            pc.addTrack(track)
            
            await pc.setRemoteDescription(offer)
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            return web.Response(
                content_type="application/json",
                text=json.dumps({
                    "sdp": pc.localDescription.sdp,
                    "type": pc.localDescription.type
                })
            )
        except Exception as e:
            return web.Response(status=500, text=str(e))
    
    def send_frame(self, frame):
        current_time = time.time()
        if current_time - self.last_frame_time < self.frame_interval:
            return
            
        with self.frame_lock:
            self.current_frame = frame
            
        for track in self.tracks[:]:
            if not track.stopped:
                track.update_frame(frame)
                
        self.last_frame_time = current_time
    
    def _run_server(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        runner = web.AppRunner(self.app, access_log=None)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, self.host, self.port)
        loop.run_until_complete(site.start())
        
        
        try:
            loop.run_until_complete(self._wait_for_stop())
        finally:
            loop.run_until_complete(runner.cleanup())
            loop.close()
    
    async def _wait_for_stop(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(1.0)
    
    def start(self):
        if self._thread is not None:
            return
            
        self._thread = threading.Thread(target=self._run_server)
        self._thread.daemon = True
        self._thread.start()
        
        time.sleep(0.5)
        
    def stop(self):
        if self._thread is None:
            return
            
        for track in self.tracks:
            track.stop()
        self.tracks.clear()
            
        loop = asyncio.new_event_loop()
        for pc in self.peer_connections:
            loop.run_until_complete(pc.close())
        loop.close()
        
        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None
        
        gc.collect()
        
        print("Server stopped")
