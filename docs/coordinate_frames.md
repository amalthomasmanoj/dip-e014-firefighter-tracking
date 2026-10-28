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

Do not assume breakout-board silk labels automatically match the waist/body frame.

Each hardware setup must document:

- raw sensor axes
- mounted waist/body axes (`+x` forward, `+y` left, `+z` up)
- fixed right-handed transform from ICM-20948 sensor axes to body axes

Never silently swap axes in code. Axis transforms belong in documented calibration/configuration paths.

Live deployments provide the transform through `E014_RESPONDERS_CONFIG`. The
heading estimator consumes body-frame `gz`; it must never integrate a raw board
axis directly. World heading is zero along world `+x`, increases toward `+y`,
and is aligned deliberately at session start because the current gyro-only
baseline does not claim magnetic north.

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

## SVG Map Display

SVG screen coordinates use `+x` to the right and `+y` downward. The project world frame uses `+z` upward and the local map convention treats increasing world `y` as left/north-like/up on the display.

For the default blank XY display, convert world to SVG with an inverted display y-axis:

```text
u = u0 + s x
v = v0 - s y
```

The calibrated map transform may include rotation and translation, but it must preserve this explicit world-frame to display-frame conversion rather than silently treating SVG `+y` as world `+y`.
