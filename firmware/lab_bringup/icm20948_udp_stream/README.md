# ICM-20948 waist IMU UDP stream

This ESP32 sketch reads a physical ICM-20948 over I2C and sends raw
accelerometer and gyroscope samples to the laptop's normal UDP ingestion port.
It emits the hardware-agnostic `imu` packet contract; no estimator or axis swap
lives in firmware.

## Dependencies

- ESP32 Arduino core 3.3.12 (the current verified build version)
- SparkFun 9DoF IMU Breakout - ICM 20948 library 1.3.2

Install them with Arduino CLI:

```bash
arduino-cli core install esp32:esp32@3.3.12
arduino-cli lib install "SparkFun 9DoF IMU Breakout - ICM 20948 - Arduino Library@1.3.2"
```

## Wiring

Power the breakout according to its board documentation. For the commonly used
3.3 V I2C breakout and the default config:

```text
ESP32 3V3    -> ICM-20948 VIN/3V3
ESP32 GND    -> ICM-20948 GND
ESP32 GPIO21 -> ICM-20948 SDA
ESP32 GPIO22 -> ICM-20948 SCL
```

The default SparkFun breakout I2C address uses AD0 high (`0x69`). Set
`ICM_AD0_VALUE` to `false` only when the board is physically configured for
`0x68`.

## Configure and flash

Copy `config_example.h` to the ignored `config.h`. Set the Wi-Fi credentials,
the laptop's LAN address, and a stable physical node ID. The laptop and ESP32
must be on a network that permits client-to-client UDP traffic.

```bash
cp firmware/lab_bringup/icm20948_udp_stream/config_example.h \
  firmware/lab_bringup/icm20948_udp_stream/config.h
arduino-cli compile --fqbn esp32:esp32:esp32 \
  firmware/lab_bringup/icm20948_udp_stream
arduino-cli upload --fqbn esp32:esp32:esp32 --port /dev/cu.usbserial-XXXX \
  firmware/lab_bringup/icm20948_udp_stream
arduino-cli monitor --port /dev/cu.usbserial-XXXX --config baudrate=115200
```

The sketch targets 50 Hz, prints the sent packet rate and failures once per
second, converts acceleration from mg to `m/s^2`, and converts angular velocity
from degrees/second to `rad/s`. Magnetometer readings are deliberately not sent;
the backend currently exposes relative gyro heading, not magnetic north.

## Join the IMU to the UWB tag

Copy `backend/config/responders.example.yaml` to the ignored
`backend/config/responders.local.yaml`. Give the logical responder its real UWB
node ID and the same `IMU_NODE_ID` configured above. Measure and record the
sensor-to-body rotation instead of silently swapping axes.

Start the backend with:

```bash
E014_SOURCE=udp \
E014_RESPONDERS_CONFIG=backend/config/responders.local.yaml \
python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

At startup, keep the waist unit stationary for the first 50 samples so the
relative-heading integrator can estimate gyro bias. Then face building `+x` and
use the UI heading-alignment control.

For an isolated 30-second packet acceptance check, stop the backend and run:

```bash
python -m tools.lab_bringup.receive_udp_packets --duration-s 30
```

Acceptance requires a stable rate near 50 packets/s, zero parse failures, and
accelerometer/gyro values that change when the physical unit is moved.
