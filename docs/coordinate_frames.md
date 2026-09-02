# Coordinate Frames

## World / Local Frame

Use a local right-handed metric frame:

```text
+x = chosen local forward / east-like map direction
+y = left / north-like map direction
+z = up
```

Exact physical alignment is established during setup and map calibration.

## IMU / Body Frame

Do not assume breakout-board silk labels automatically match the shoe frame.

Each hardware setup must document:

- raw sensor axes
- mounted shoe axes
- fixed transform from sensor to shoe/body

Never silently swap axes in code. Axis transforms belong in documented calibration/configuration paths.

## Units

Use SI internally:

```text
distance           metres
velocity           metres/second
acceleration       metres/second^2
angular velocity   radians/second
angles             radians
pressure           pascals
time transport     integer microseconds
```

Transport timestamps are integer microseconds. Estimator internals may convert time deltas to seconds.

