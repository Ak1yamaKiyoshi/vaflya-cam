import dataclasses
from typing import Tuple
from typing import List
from typing import Literal
from typing import Union

import numpy as np


@dataclasses.dataclass
class CameraParameters:
    analogue_gain: float
    colour_gains: Tuple[float, float]
    exposure_time: int
    resolution: Tuple[float, float] = 4056//2, 3040//2
    AeEnable: bool = False
    AwbEnable: bool = False

@dataclasses.dataclass
class CameraParameter:
    name: Literal["analogue_gain", "red_gain", "blue_gain", "exposure_time"]
    value: Union[float, int]

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
