# ARIA Android Agent

The ARIA Android Agent is a powerful Accessibility Service designed to give the central A.R.I.A AI complete remote control over your Android device.

It runs persistently in the background, communicates with the ARIA backend via WebSockets, and natively translates AI commands into device actions.

## ⚡ Features

- **Gesture Automation**: Tap, long press, swipe, and scroll.
- **Smart Text Input**: Focus input fields, set text natively, or fallback to clipboard-paste emulation.
- **UI Scraping**: Dumps entire UI trees, reads screen text, and locates elements by ID, text, or content description.
- **WhatsApp Fallbacks**: A highly resilient, 4-strategy algorithm designed to find elements and send messages even if WhatsApp updates their UI.
- **System Control**: Media controls, volume, clipboard access, battery stats, WiFi data, SMS, and calls.
- **File Automation**: Read, write, list, and delete files on the Android storage (Base64 encoded).

## 🚀 Building Without Android Studio (Headless)

This project has been engineered to build completely headless via command-line tools without requiring Android Studio.

### Prerequisites (Linux)
1. Install JDK 17:
   ```bash
   sudo apt install openjdk-17-jdk
   ```
2. Download and extract the [Android Command Line Tools](https://developer.android.com/studio#command-line-tools-only) to `~/android-sdk/cmdline-tools/latest/`.

3. Set up your environment variables:
   ```bash
   export ANDROID_HOME=~/android-sdk
   export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
   ```

4. Install the required SDK packages:
   ```bash
   sdkmanager --licenses
   sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
   ```

### Building the APK

1. Update the SDK path in `local.properties` if yours differs from `~/android-sdk`.
2. Generate the Debug Keystore (one-time):
   ```bash
   keytool -genkey -v -keystore aria-debug.keystore -alias aria -keyalg RSA -keysize 2048 -validity 10000 -storepass android -keypass android -dname "CN=ARIA,OU=Dev,O=ARIA,L=X,ST=X,C=US"
   ```
3. Build using the Gradle Wrapper:
   ```bash
   chmod +x gradlew
   ./gradlew assembleDebug
   ```
4. Find the resulting APK at:
   `app/build/outputs/apk/debug/app-debug.apk`

## ⚙️ Configuration & Usage

1. **Install the APK** onto your Android device (`adb install <apk>`).
2. **Open the ARIA Agent app**.
3. **Configure the Server URL** to point to your ARIA backend (e.g., `ws://192.168.1.5:8000/ws/device`).
4. Enter an optional **Auth Token** and click **Save & Connect**.
5. Click **Open Accessibility Settings** and explicitly enable the "ARIA Agent" service in your device settings.

Once connected, ARIA will automatically discover the phone via the `list_connected_devices` tool and can issue commands remotely using the `android_run_command` tool!
