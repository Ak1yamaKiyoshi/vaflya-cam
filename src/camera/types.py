
import dataclasses
from typing import Tuple
from typing import List

import numpy as np


@dataclasses.dataclass
class CameraParameters:
    analogue_gain: float 
    colour_gains: Tuple[float, float]
    exposure_time: int
    resolution: Tuple[float, float] = 2028, 1520

@dataclasses.dataclass
class RuntimeFrameMetadata:
    lux: float 
    temperature: float     

@dataclasses.dataclass
class CameraFrameWrapper:
    frame: np.ndarray
    metadata: CameraParameters
    timestamp: float 
    runtime_metadata: RuntimeFrameMetadata