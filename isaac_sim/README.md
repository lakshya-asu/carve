# Isaac Sim integrated cell

This folder implements the Isaac Sim 6.0.1 reference cell. `run_proxy_cell.py` is retained only as historical scaffold code. It is not an accepted integration path.

The accepted runner is `run_cell.py`. It builds and saves a complete visible USD cell, renders RGB and depth, runs a replaceable rendered segmentation model, tracks and predicts the moving workpiece, controls a real Isaac articulation, verifies two-finger contact, applies a simulated grasp constraint, aligns the product, performs the downstream handoff, and exercises recovery.

Solution A performs direct transfer and rejects when the cutter permissive is unavailable. Solution B places in a centering buffer, renders a new observation, estimates slip, regrips through contact, corrects alignment, and feeds the downstream target.

Run from the project root:

```powershell
.\validate_setup.ps1
.\run_solution_a.ps1
.\run_solution_b.ps1
.\run_tests.ps1
.\run_hardening.ps1
.\run_yolo_solution_a.ps1
.\run_yolo_solution_b.ps1
.\run_yolo_tests.ps1
.\run_yolo_demo.ps1
```

Direct commands are also supported:

```powershell
$env:OMNI_KIT_ACCEPT_EULA='YES'
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\validate_setup.py --headless
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution a --cycles 4 --seed 7 --headless
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution b --cycles 4 --seed 7 --headless
C:\Users\jainl\is6\Scripts\python.exe isaac_sim\run_cell.py --solution a --cycles 6 --seed 31 --scenario-profile hardening --output-root results\hardening\seed_0031 --headless
```

The hardening profile has six scenario slots. It covers two nominal cycles, failed grasp, solution-specific downstream unavailability, emergency stop, and stale observation. `run_hardening.ps1` runs five seeds for A and B sequentially and finishes with an independent stage, media, trace, PLC, metrics, and replay audit.

`run_cell.py --vision-model yolo26` selects the trained YOLO26 segmentation adapter. It runs inference on rendered RGB, maps the learned instance mask through rendered depth and camera calibration, injects seeded timestamp and pose noise, then passes the resulting `ObjectObservation` into the unchanged tracker and controller. Isaac Sim 6.0.1 has no CUDA implementation of the bundled TorchVision NMS operator, so YOLO training uses the GPU while validation and live NMS use CPU. This preserves Isaac's installed environment.

The environment flag is appropriate only after the workstation user accepts the NVIDIA EULA.

## Fidelity limits

- Geometry and kinematics are generic references, not OEM models.
- Product deformation is approximated by rigid-body contact plus explicit slip and compliance proxies.
- Finger drive effort is the grip-force proxy. Contact impulses are not calibrated force measurements.
- The active grasp constraint is created only after both finger contacts are observed. It approximates a stable compliant hold.
- The cutter is guarded reference geometry with a PLC handshake. No blade physics is simulated.
- Physical material parameters, sanitation behavior, real safety response, and controller timing require hardware evidence.
