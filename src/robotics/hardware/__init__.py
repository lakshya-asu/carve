"""MuJoCo models of hardware that more than one cell can be built from.

    arms                UR5e, UR20 and FANUC SR-20iA: `ArmSpec` data and a builder per arm
    ik                  tool pose to joint values, raising when the pose is out of reach
    grippers            pinch, jaw and three-finger grippers: `GripperSpec` data, XML in `assets/`
    cameras             Gemini 335L and D455 from their datasheets: `DepthCameraModel`, depth noise
    image_degradation   controlled damage to rendered images, each with its physical cause

The application that owns a scene attaches these to it. Real arms are driven through `ros2/`.
"""
