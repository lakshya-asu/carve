# YOLO26 meat reference segmentation model

## Identity

- Architecture: Ultralytics YOLO26 nano segmentation
- Base checkpoint: `models/yolo26n-seg.pt`
- Ultralytics package: 8.4.129
- Trained checkpoint: `models/yolo26_meat_reference/weights/best.pt`
- Trained SHA-256: `cf280497427a8f56fc8ef81e47c32b4a4494435187af0b1916cb03ac09225919`
- Training seed: 2601
- Training epochs: 30

The base family and task are documented by the [official YOLO26 documentation](https://docs.ultralytics.com/models/yolo26/). Ultralytics software and model licensing must be reviewed for the intended use. The project-local package includes its license files. This simulation does not establish permission for a production deployment.

## Training data

The model was trained only on 240 RGB images rendered in Isaac Sim 6.0.1. There are 192 training images and 48 validation images. The scene uses an abstract rigid meat reference, a generic Cartesian robot, a generic two-finger gripper, and reference cell geometry.

The dataset contains 160 moving-belt views and 80 Solution B buffer views. It randomizes product pose, yaw, color, lighting, height, and robot pose. Known simulator product geometry was projected through the calibrated camera to generate segmentation labels. Ground truth is not used by live inference.

No real meat image, real camera recording, or OEM asset was used.

## Synthetic validation

- Mask precision: 0.8733
- Mask recall: 0.8615
- Mask mAP50: 0.9188
- Mask mAP50-95: 0.6923
- CPU inference: about 25 ms per image on the current workstation during validation

These values measure a synthetic held-out split from the same reference scene family. They do not estimate real-world performance.

## Intended use

The model is a replaceable learned-perception example for the Isaac simulation. It converts rendered RGB into a segmentation mask and confidence. The pipeline combines that mask with rendered depth and camera calibration to estimate a planar workpiece pose.

## Limitations

- The model is not validated on real meat, wet surfaces, real lighting, motion blur, occlusion, sanitation artifacts, or camera noise.
- It does not establish physical accuracy, food safety, real-cell safety, OEM fidelity, or production readiness.
- It has one dedicated synthetic class. Ultralytics serializes that class as `item`; the adapter maps class index zero to `meat_reference`.
- Isaac's bundled TorchVision has no CUDA NMS kernel. Live NMS runs on CPU.
- Real data collection, calibration, domain adaptation, and held-out physical tests remain part of T015.
