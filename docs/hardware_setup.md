# Hardware Setup

Current planning assumptions:

- 4 x Qorvo DWM3000EVB
- 4 x ESP32-WROOM development boards
- 1 x ICM-42688-P 6-axis IMU

Baseline allocation:

- Anchor A: ESP32 + DWM3000EVB
- Anchor B: ESP32 + DWM3000EVB
- Anchor C: ESP32 + DWM3000EVB
- Firefighter tag: ESP32 + DWM3000EVB

The ICM-42688-P is intended for foot-mounted inertial sensing. The software must support either a shared firefighter-tag ESP32 or a separate shoe node.

Barometer support is optional future work until hardware scope confirms it.

