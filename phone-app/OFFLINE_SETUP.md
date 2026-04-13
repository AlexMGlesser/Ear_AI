# Offline Audio Setup (Phase 2 Path)

This setup enables local wake/listen on Android using Vosk, avoiding cloud speech services.

## 1. Download a Vosk Android model on your PC
Recommended starter model:
- vosk-model-small-en-us-0.15

## 2. Put model into app files directory as `vosk-model`
The app expects:
- `/data/data/com.earai.mobile/files/vosk-model`

Use adb to push after first app launch:
```powershell
$adb = 'C:\Users\<you>\AppData\Local\Android\Sdk\platform-tools\adb.exe'
& $adb shell run-as com.earai.mobile mkdir -p files/vosk-model
& $adb push .\vosk-model-small-en-us-0.15 /data/local/tmp/vosk-model-temp
& $adb shell run-as com.earai.mobile cp -r /data/local/tmp/vosk-model-temp/. files/vosk-model/
& $adb shell run-as com.earai.mobile ls files/vosk-model
```

If `run-as` copy is blocked on your device, use Android Studio Device File Explorer to copy model files into:
- `data/data/com.earai.mobile/files/vosk-model`

## 3. Bluetooth Audio Setup (Recommended)

The app now automatically detects and uses Bluetooth microphones (e.g., earbuds, headsets) when available.

### How to use:
1. **Pair your Bluetooth device** with your phone in Settings → Bluetooth
2. **Start the app service** — the app will automatically:
   - Detect available Bluetooth input devices
   - Enable Bluetooth SCO (Synchronous Connection Oriented) for voice communication
   - Route audio input through the Bluetooth microphone
3. **Check the diagnostics pane** in the app to verify which audio device is active

### Supported Bluetooth devices:
- Bluetooth earbuds with microphones
- Bluetooth headsets
- Bluetooth A2DP headphones (if they support mic input)
- Bluetooth Low Energy (BLE) headsets (Android 12+)

### If Bluetooth audio isn't working:
- **Verify pairing**: Ensure your device shows in Settings → Bluetooth
- **Check diagnostics**: Open the app and look at the "Audio device" line in the diagnostics pane
- **Fallback to built-in mic**: The app will use the phone's built-in microphone if:
  - No Bluetooth device is paired, or
  - Bluetooth SCO setup fails
- **Restart audio**: Stop and re-start the app service to reinitialize audio routing

### Technical details:
- For Android 12+: Uses modern `AudioDeviceInfo` enumeration
- For Android 11 and earlier: Uses Bluetooth SCO setup with automatic retry
- Audio focus is set to `VOICE_COMMUNICATION` mode for optimal noise handling

## 4. Start app service
- Open app
- Set server host/port
- Tap Start

Notification should say:
- `Offline listening active`

If model is missing and fallback switch is off, notification will report model missing and listening will not start.
This is intentional to avoid the repeated recognizer session beep loop.

If you must test without model, enable fallback switch in the app.

## Notes
- Offline mode removes most recognizer session tones from cloud recognizer path.
- Model quality and latency depend on phone CPU.
- Keep battery optimization disabled for stable background behavior.
- Bluetooth microphones typically provide better noise isolation than built-in phone mics.

## Accent Support Tips
- If your accent is frequently misheard, use a larger Vosk model than `vosk-model-small-en-us-0.15`.
- Better accuracy options (larger download, more CPU/RAM use):
	- `vosk-model-en-us-0.22`
	- `vosk-model-en-us-0.22-lgraph`
- The app now applies wake-word fuzzy matching for common pronunciations of "Dante".
- After replacing model files, restart the app service (Stop then Start) to reload the model.
- Using a Bluetooth microphone with clear audio input can further improve accent tolerance.
