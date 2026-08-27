# Project page media

These files are selected copies of executed Isaac Sim evidence. They are tracked so `PROJECT_PAGE.html` works from a public repository checkout. The full run folders remain under ignored `results` directories.

## Scene 2 presentation

- `fanuc_presentation.mp4`: 13.75 second H.264 recording from the virtual presentation camera
- `fanuc_presentation_poster.png`: first readable frame used by the page
- `fanuc_presentation_contact_sheet.png`: six-frame sequence summary
- `fanuc_presentation_metrics.json`: camera, controller, limit, frame, and file evidence

The presentation camera is inside the guard envelope. It exists to explain the task and is not a proposed production sensor location. This recording proves Scene 2 articulation and jaw motion. It does not prove the unfinished YOLO-to-FANUC delivery path.

## Perception and complete-pipeline evidence

- `yolo26_segmentation.jpg`: saved learned segmentation output from Scene 1
- `overhead_rgb.png`: rendered overhead RGB input
- `overhead_depth_preview.png`: aligned depth preview
- `legacy_scene1_end_to_end.mp4`: older complete YOLO-to-delivery recording
- `legacy_scene1_contact_sheet.png`: complete-pipeline sequence summary
- `legacy_scene1_metrics.json`: complete-pipeline recording and cycle evidence

## Standard-arm and suite evidence

- `fanuc_robot_closeup.png`: Scene 2 arm and compliant gripper view
- `scene2_validation.json`: articulation, ROS 2, RGBD, and compliance results
- `full_suite_artifact_audit.json`: latest clean combined artifact audit

All robot, gripper, product, conveyor, cutter, and cell assets remain simulation references. No OEM fidelity, physical accuracy, food-safety validation, machine-safety validation, or production readiness is claimed.
