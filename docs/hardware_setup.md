# Hardware Setup

Current planning assumptions:

- 4 x Qorvo DWM3000EVB
- 4 x ESP32-WROOM development boards
- 1 x ICM-20948 IMU mounted at the waist

Baseline allocation:

- Anchor A: ESP32 + DWM3000EVB
- Anchor B: ESP32 + DWM3000EVB
- Anchor C: ESP32 + DWM3000EVB
- Firefighter tag: ESP32 + DWM3000EVB

The ICM-20948 is mounted rigidly at the waist. Record the raw board axes and
the fixed sensor-to-body rotation for every enclosure. The software supports
either a shared firefighter-tag ESP32 or a separate waist node through the
responder association configuration; the topology is never inferred from IDs.

The first waist integration consumes accelerometer and gyroscope channels only.
The magnetometer is not part of the packet contract or heading baseline because
indoor magnetic disturbances have not been characterized.

Barometer support is optional future work until hardware scope confirms it.

