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

## 3. Start app service
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
