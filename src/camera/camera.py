import os

os.environ["LIBCAMERA_LOG_LEVELS"] = "3"

from .types import CameraFrameWrapper, CameraParameters, RuntimeFrameMetadata
from .utils import ReplayBuffer, Config, CamUtils


from libcamera import controls

import picamera2 as pc2
import threading
import numpy as np
import cv2 as cv
import time

from datetime import datetime


class Camera:
    def __init__(self, rotate_180=True):
        self.cfg = Config()
        self._cam = pc2.Picamera2()
        self._cam.pre_callback = self._on_frame

        self.frames = ReplayBuffer(2)
        
        # Rotation configuration
        self.rotate_180 = rotate_180

        self._params_latest = CameraParameters(
            1, (2.25, 3.25), CamUtils.seconds_to_microseconds(1 / 64)
        )
        self._params_request = CameraParameters(
            7, (2.25, 3.25), CamUtils.seconds_to_microseconds(1 / 64)
        )
        self._frame_not_captured = threading.Event()
        self._camera_started = False
        self.reconfigure(self._params_request)

    def _on_frame(self, request):
        with pc2.MappedArray(request, "main") as m:
            frame = np.array(m.array, copy=False)
            frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            
            # Apply 180° rotation if enabled
            if self.rotate_180:
                frame = cv.rotate(frame, cv.ROTATE_180)

            frame_metadata = request.get_metadata()

            params = CameraParameters(
                analogue_gain=frame_metadata["AnalogueGain"],
                exposure_time=frame_metadata["ExposureTime"],
                colour_gains=frame_metadata["ColourGains"],
                resolution=frame.shape[:2][::-1],
            )

            runtime_meta = RuntimeFrameMetadata(
                lux=frame_metadata["Lux"],
                temperature=frame_metadata["ColourTemperature"],
            )

            self.frames.add(
                CameraFrameWrapper(
                    frame=frame,
                    metadata=params,
                    timestamp=time.monotonic(),
                    runtime_metadata=runtime_meta,
                )
            )

            self._params_latest = params
            self._frame_not_captured.set()

    def set_auto(self):
        """Enable auto exposure and white balance without restarting camera"""
        if self._camera_started:
            self._cam.set_controls({
                "AeEnable": True,
                "AwbEnable": True,
            })
        else:
            # Camera not started yet, will be set during reconfigure
            pass
    def disable_auto(self):
        if self._camera_started:
            self._cam.set_controls({
                "AeEnable": False,
                "AwbEnable": False,
            })
    
    def update_controls_only(self, controls_dict):
        """Update camera controls without stopping/starting the camera"""
        if self._camera_started:
            try:
                self._cam.set_controls(controls_dict)
                return True
            except Exception as e:
                print(f"Error updating controls: {e}")
                return False
        return False
    
    def make_update_parameters(self, parameter_update, value):
        latest = {
                #"NoiseReductionMode": controls.draft.NoiseReductionModeEnum.HighQuality,
                "ExposureTime": self._params_latest.exposure_time,
                "AnalogueGain": self._params_latest.analogue_gain,
                "ColourGains": self._params_latest.colour_gains   
        }
        
        if parameter_update in latest:
            latest[parameter_update] = value
        
        return CameraParameters(
            analogue_gain=latest["AnalogueGain"], 
            colour_gains=latest["ColourGains"], 
            exposure_time=latest['ExposureTime']
        )
    
    def _needs_restart(self, new_params, current_params):
        """Check if camera needs to be restarted for the new parameters"""
        # Only restart if resolution changes or if switching between auto/manual modes
        if new_params.resolution != current_params.resolution:
            return True
        
        # Check if switching between auto and manual modes
        current_auto = getattr(current_params, 'AeEnable', False)
        new_auto = getattr(new_params, 'AeEnable', False)
        
        if current_auto != new_auto:
            return True
            
        return False
        
    def reconfigure(self, params: CameraParameters):
        """Reconfigure camera, only restart if necessary"""
        self._params_request = params
        
        # Check if we need to restart the camera
        needs_restart = not self._camera_started or self._needs_restart(params, self._params_request)
        
        if needs_restart:
            # Full reconfiguration with restart
            if self._camera_started:
                self._cam.stop()
                self._camera_started = False
            
            cfg = self._cam.create_still_configuration(
                main={"size": params.resolution}, raw={"size": params.resolution}
            )
            self._cam.configure(cfg)

        # Prepare controls
        exposure_time = (
            int(params.exposure_time)
            if isinstance(params.exposure_time, float)
            else params.exposure_time
        )

        camcontrols = {
            "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.HighQuality,
        }
        
        if getattr(params, 'AeEnable', False):
            camcontrols.update({
                "AeEnable": True,
                "AwbEnable": True,
                "AeMeteringMode": controls.AeMeteringModeEnum.CentreWeighted,
                "AeExposureMode": controls.AeExposureModeEnum.Long,
                "AwbMode": controls.AwbModeEnum.Auto,
                "ExposureValue": 4.0,
            })
        else: 
            camcontrols.update({
                "AeEnable": False,
                "AwbEnable": False,
                "ExposureTime": exposure_time,
                "AnalogueGain": params.analogue_gain,
                "ColourGains": params.colour_gains
            })
        
        if needs_restart:
            # Start camera and set all controls
            self._cam.set_controls(camcontrols)
            self._cam.start()
            self._camera_started = True
        else:
            # Just update controls without restarting
            # Only update the controls that can change without restart
            runtime_controls = {}
            if not getattr(params, 'AeEnable', False):
                runtime_controls.update({
                    "ExposureTime": exposure_time,
                    "AnalogueGain": params.analogue_gain,
                    "ColourGains": params.colour_gains
                })
            
            if runtime_controls:
                self.update_controls_only(runtime_controls)
    
    def quick_update_exposure(self, exposure_time):
        """Quick exposure update without reconfiguration"""
        exposure_time = int(exposure_time) if isinstance(exposure_time, float) else exposure_time
        return self.update_controls_only({"ExposureTime": exposure_time})
    
    def quick_update_gain(self, analogue_gain):
        """Quick gain update without reconfiguration"""
        return self.update_controls_only({"AnalogueGain": analogue_gain})
    
    def quick_update_colour_gains(self, colour_gains):
        """Quick colour gains update without reconfiguration"""
        return self.update_controls_only({"ColourGains": colour_gains})

    def capture(self, seconds_ago=0.1):
        if seconds_ago == -1:
            self._frame_not_captured.wait()
            self._frame_not_captured.clear()

        return self.frames.get(seconds_ago)

    def capture_and_save(self, output_path="gallery/", seconds_ago=0.1):
        now = datetime.now()
        formatted_time = now.strftime("%Y.%m.%d-%H:%M:%S") + ".png"
        frame = self.capture(seconds_ago)
        path = os.path.join(output_path, formatted_time)

        cv.imwrite(path, frame.frame)
    
    def set_rotation(self, rotate_180):
        """Enable or disable 180° rotation"""
        self.rotate_180 = rotate_180