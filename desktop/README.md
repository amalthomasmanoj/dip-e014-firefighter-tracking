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

The **Heart rate** panel has its own sensor setup. Wear and moisten the H808S,
enter its advertised name (`H808S`) or identifier, choose the responder, and
click **Connect / update**. The app saves this assignment and starts the BLE
receiver automatically on later launches; no environment variables or Terminal
commands are needed. Heart rate remains independent of the Simulation/Real
Sensors selector so it can be demonstrated with either position source.

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

## Windows

The Windows build contains the same dashboard, simulation, real-sensor receiver,
IMU calibration, DWM3000 adapter, and public-sharing controls in one executable.
Build it on Windows with:

```powershell
.\scripts\build_windows_app.ps1
```

The result is `dist\E014-Firefighter-Tracking.exe`. On first real-sensor use,
allow the app through Windows Firewall on private networks. Windows 10/11 should
already include the Microsoft Edge WebView2 runtime required by the embedded UI.
