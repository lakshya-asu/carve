# YOLO26 synthetic reference checkpoint

`weights/best.pt` is the checkpoint used by the final Scene 2 integrated demonstrations.

- Ultralytics version: 8.4.129
- Base family: YOLO26 nano segmentation
- Training data: synthetic Isaac Sim reference-product imagery with buffer augmentation
- Checkpoint SHA-256: `8baaf05e63a5e654215dbdcf58e106ea62c24e75a54ae9f9c45e8c9c1ed9ceab`
- Box precision: 0.9440
- Mask precision: 0.96267
- Box recall: 0.79033
- Mask recall: 0.80596
- Box mAP50: 0.89715
- Mask mAP50: 0.91762
- Box mAP50-95: 0.70795
- Mask mAP50-95: 0.75210

Simulator ground truth created the training labels. The runtime model receives rendered RGB through a replaceable inference interface. Ground truth is used only as a baseline and test oracle.

This checkpoint is not validated on representative real meat, production lighting, lens contamination, fluids, glare, motion blur, occlusion, or camera domain shift. It is not evidence of physical accuracy or production performance.
