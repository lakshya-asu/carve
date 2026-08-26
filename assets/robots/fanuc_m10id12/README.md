# FANUC M-10iD/12 simulation reference

The source description comes from the official FANUC `fanuc_description` repository.

- Source repository: https://github.com/FANUC-CORPORATION/fanuc_description
- Imported commit: `fb40c9803a826ba68c7c8e28ba904a25efa7fcd2`
- Source model: `fanuc_m10_description/m10_12_14d`
- Source license: Apache-2.0
- Generated URDF: `fanuc_m10id12.urdf`
- Generated Isaac asset: `usd/fanuc_m10id12_reference.usda`

Run `python tools\build_fanuc_urdf.py` to rebuild the plain URDF from the official xacro macro.

This asset preserves the official description's link geometry, joint origins, axes, limits, masses, and inertia tensors. It is a kinematic and visual simulation reference. It is not proof of exact food-grade surface appearance, controller behavior, cable routing, collision fidelity, washdown performance, or physical safety.
