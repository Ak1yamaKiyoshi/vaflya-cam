
import cv2 as cv
import threading
import os
from aos.node import Node
from srcv2.camera import CameraFrameWrapper, CameraParameters
import time
from queue import Queue
from typing import List
import queue
from src.camera.utils import ReplayBuffer




class FrameSaver(Node):
    def _init(self, galleries_path = "./galleries/"):
        self.galleries_path = galleries_path 
        self.init_directories()
        
        self.rewinds:Queue[List[CameraFrameWrapper]] = Queue()
        self.photos: Queue[CameraFrameWrapper] = Queue()
        self.video: Queue[CameraFrameWrapper] = Queue()
        self.replay_buffer = ReplayBuffer(15)

        self.video_foldername = None
        self.is_video = False
        self.video_frames_amount = 0

    def init_directories(self):
        if os.path.exists(self.galleries_path):
            for gallery in os.listdir(self.galleries_path):
                folder_path = os.path.join(self.galleries_path, gallery)
                if os.path.isdir(folder_path) and not os.listdir(folder_path):
                    os.rmdir(folder_path)
        
        if not os.path.exists(self.galleries_path):
            os.makedirs(self.galleries_path)
            
        galleries = [d for d in os.listdir(self.galleries_path) if os.path.isdir(os.path.join(self.galleries_path, d))]
        boot_numbers = []
        for gallery in galleries:
            if gallery.startswith("boot_"):
                try:
                    boot_numbers.append(int(gallery.split("_")[1]))
                except ValueError:
                    pass
        
        boot_no = max(boot_numbers) + 1 if boot_numbers else 1
        self.current_gallery = os.path.join(self.galleries_path, f"boot_{boot_no:04d}")
        os.makedirs(self.current_gallery, exist_ok=True)

    def set_frame(self, frame):
        self.replay_buffer.add(frame)
        if self.is_video:
            self.video.put(frame)

    def set_photo_event(self, _):
        print("PHOTO EVENT ")
        frame = self.replay_buffer.get(0.15)
        self.photos.put(frame.frame)

    def set_video_start_event(self, _):
        self.video_foldername = f"video_{int(time.time()*1000)}"
        self.is_video = True
        self.video_frames_amount = 0
        
        for wrapper in self.replay_buffer.get_frames_last_seconds(2):
            self.video.put(wrapper)

    def set_video_end_event(self, _):
        self.is_video = False

    def set_save_rewind(self, _):
        self.rewinds.put(self.replay_buffer.get_frames_last_seconds(3))
        
    def mainloop(self):
        photos_taken = 0 
        rewinds_saved = 0 
        while True: 
            try:
                photo_to_save = self.photos.get(block=True, timeout=0.05)
                cv.imwrite(os.path.join(self.current_gallery, f"frame_{int(time.time()*1000)}.jpg"), photo_to_save,  [cv.IMWRITE_JPEG_QUALITY, 100])
                photos_taken += 1
                self._emit("photos_taken", photos_taken)
            except queue.Empty:
                pass
            
            try:
                rewind = self.rewinds.get(block=True, timeout=0.05)
                rewind_path = os.path.join(self.current_gallery, f"rewind_{int(time.time()*1000)}")
                
                os.mkdir(rewind_path)
                for i, wrapper in enumerate(rewind):
                    # rpi outputs RGB888, therefore jpg is ok. png compression too long. > throughput better then quality at this level 
                    cv.imwrite(os.path.join(rewind_path, f"frame_{i:05d}.jpg"), wrapper.frame,  [cv.IMWRITE_JPEG_QUALITY, 100])

                rewinds_saved += 1
                self._emit("rewinds_saved", rewinds_saved)
                
            except queue.Empty:
                pass

            try:
                video_frame = self.video.get(block=True, timeout=0.05)
                self.video_frames_amount += 1
                video_frame_path = os.path.join(self.current_gallery, self.video_foldername, f"frame_{self.video_frames_amount:05d}.jpg")
                if not os.path.exists(video_frame_path):
                    try:
                        os.mkdir(video_frame_path.split("frame_")[0])
                    except FileExistsError:
                        pass
                        
                cv.imwrite(video_frame_path, video_frame.frame, [cv.IMWRITE_JPEG_QUALITY, 100])
                
            except queue.Empty:
                pass
