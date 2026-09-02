# Sensor Interfaces

## IMU Packet

Expected fields:

```text
timestamp_us
sequence_number
ax_mps2
ay_mps2
az_mps2
gx_radps
gy_radps
gz_radps
```

## UWB Range Packet

Expected fields:

```text
timestamp_us
sequence_number
anchor_id
range_m
valid
quality
```

`quality` is nullable because hardware capability is not yet confirmed.

## Anchor Configuration

Known anchor coordinates:

```text
anchor_id
x_m
y_m
z_m
```

The baseline uses known anchor coordinates. Anchor self-survey and anchor SLAM are stretch work only.

