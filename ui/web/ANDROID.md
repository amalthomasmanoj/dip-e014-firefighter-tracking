# Android viewer

The Android app is a display client. Sensor ingestion, anchor surveying, EKF/ESKF
fusion, and raw logging remain on the Mac host.

On first launch, paste either URL shown in the Mac app:

- **Local URL** when the phone and Mac are on the same Wi-Fi network.
- **Public URL** when using the temporary Cloudflare tunnel.

Use **Server** in the app header whenever that address changes.

## Build

The checked-in Capacitor project requires Android SDK 36 and Java 21. From
`ui/web`, run `npm run build:android`, then build `android` with Android Studio.
The repository's **Android APK** GitHub Actions workflow also produces an
installable debug APK artifact without requiring a local Android toolchain.

The debug APK is for direct testing. A Play Store release requires a private
signing key and a signed release bundle; no signing credentials belong in this
repository.
