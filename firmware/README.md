# Firmware

ESP32 firmware will initialize sensor interfaces, timestamp measurements, add sequence numbers, and transmit packets to the laptop.

The real waist-mounted ICM-20948 UDP producer is in
[`lab_bringup/icm20948_udp_stream`](lab_bringup/icm20948_udp_stream/README.md).
It keeps sensor-specific code at the firmware boundary and emits the generic
IMU packet contract in SI units.

Real DWM3000 ranging remains supplied by the separately maintained tag-v3 and
anchor-v2 firmware; this repository does not invent a replacement radio driver.

