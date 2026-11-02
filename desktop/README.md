# Desktop host

The macOS app opens directly into the complete embedded dashboard with Simulation
already running. Use the **Mac host** bar in the dashboard to switch to Real
Sensors or start public sharing. Real Sensors also starts the DWM3000 UDP adapter
and preserves its raw datagrams under
`~/Library/Logs/E014 Firefighter Tracking/`.

On the first real-sensor run, wear the IMU in its normal waist mount, stand
upright and still for a few seconds, then click **Calibrate Upright IMU**. The app
measures and saves the sensor-to-body rotation under Application Support and
reuses it on later launches. Recalibrate after changing the physical mounting.

**Share Publicly** starts a free Cloudflare Quick Tunnel and copies its HTTPS URL.
The URL is temporary, changes when the tunnel restarts, and is not an uptime-backed
deployment. Anyone with that URL can view the telemetry, so stop the app after a
demo.

Build the unsigned local application with:

```bash
./scripts/build_macos_app.sh
```

The result is `dist/E014 Firefighter Tracking.app`. macOS may require a one-time
right-click **Open** because the local build is not notarized.
