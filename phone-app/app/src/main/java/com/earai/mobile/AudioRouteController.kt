package com.earai.mobile

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build

class AudioRouteController(context: Context) {
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var focusRequest: AudioFocusRequest? = null
    private var btScoAttempts = 0
    private val maxBtScoAttempts = 3

    fun startVoiceSession() {
        requestAudioFocus()
        setAudioModeForVoice()
        initializeBluetoothRouting()
    }

    fun stopVoiceSession() {
        disableBluetoothRouting()
        audioManager.mode = AudioManager.MODE_NORMAL
        abandonAudioFocus()
    }

    private fun setAudioModeForVoice() {
        try {
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
            audioManager.isSpeakerphoneOn = false
        } catch (e: Exception) {
            // Some devices don't allow mode change; continue anyway
        }
    }

    private fun initializeBluetoothRouting() {
        btScoAttempts = 0
        val bluetoothDevice = getAvailableBluetoothDevice()

        if (bluetoothDevice != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                // Android 12+: Use modern device enumeration and setCommunicationDevice
                enableBluetoothRoutingModern()
            } else {
                // Android < 12: Use deprecated but still functional SCO methods
                enableBluetoothRoutingLegacy()
            }
        }
    }

    private fun enableBluetoothRoutingModern() {
        try {
            // For Android 12+, set up communication device
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                @Suppress("DEPRECATION")
                audioManager.startBluetoothSco()
            }
            btScoAttempts++
            if (btScoAttempts < maxBtScoAttempts) {
                // SCO may take a moment to initialize; retry if needed
                Thread {
                    Thread.sleep(200)
                    if (btScoAttempts < maxBtScoAttempts && !isBluetoothAudioConnected()) {
                        enableBluetoothRoutingModern()
                    }
                }.start()
            }
        } catch (e: Exception) {
            // Device doesn't support this operation
        }
    }

    private fun enableBluetoothRoutingLegacy() {
        try {
            @Suppress("DEPRECATION")
            audioManager.startBluetoothSco()
            @Suppress("DEPRECATION")
            audioManager.isBluetoothScoOn = true
            btScoAttempts++
            if (btScoAttempts < maxBtScoAttempts) {
                Thread {
                    Thread.sleep(200)
                    if (btScoAttempts < maxBtScoAttempts && !isBluetoothAudioConnected()) {
                        enableBluetoothRoutingLegacy()
                    }
                }.start()
            }
        } catch (e: Exception) {
            // Device doesn't support this operation
        }
    }

    private fun disableBluetoothRouting() {
        try {
            @Suppress("DEPRECATION")
            audioManager.stopBluetoothSco()
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
                @Suppress("DEPRECATION")
                audioManager.isBluetoothScoOn = false
            }
        } catch (e: Exception) {
            // Already disabled or device doesn't support
        }
    }

    private fun getAvailableBluetoothDevice(): AudioDeviceInfo? {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                val devices = audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS)
                // Look for Bluetooth SCO or Bluetooth devices
                for (device in devices) {
                    if (isBluetoothDevice(device)) {
                        return device
                    }
                }
            } catch (e: Exception) {
                // Fall back to SCO-based approach
            }
        }
        // Fallback: assume Bluetooth is available if bluetooth SCO is available
        return if (audioManager.isBluetoothScoAvailableOffCall || audioManager.isBluetoothAOn) {
            null // Return null but proceed with SCO setup
        } else {
            null
        }
    }

    private fun isBluetoothDevice(device: AudioDeviceInfo): Boolean {
        return device.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                device.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP ||
                device.type == AudioDeviceInfo.TYPE_BLE_HEADSET ||
                (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && 
                 device.type == AudioDeviceInfo.TYPE_BLE_SPEAKER)
    }

    private fun isBluetoothAudioConnected(): Boolean {
        return audioManager.isBluetoothAOn || audioManager.isBluetoothScoOn
    }

    fun getActiveAudioDevice(): String {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                val devices = audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS)
                for (device in devices) {
                    if (device.isSink) continue
                    if (isBluetoothDevice(device)) {
                        return "Bluetooth (${device.productName})"
                    }
                }
                for (device in devices) {
                    if (device.isSink) continue
                    return when (device.type) {
                        AudioDeviceInfo.TYPE_BUILTIN_MIC -> "Built-in Microphone"
                        AudioDeviceInfo.TYPE_WIRED_HEADSET -> "Wired Headset"
                        else -> "Device (${device.type})"
                    }
                }
            } catch (e: Exception) {
                return "Unknown (enumeration failed)"
            }
        }
        return when {
            audioManager.isBluetoothAOn -> "Bluetooth"
            isBluetoothAudioConnected() -> "Bluetooth SCO"
            else -> "System Default"
        }
    }

    private fun requestAudioFocus() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .build()
            focusRequest = request
            audioManager.requestAudioFocus(request)
        } else {
            @Suppress("DEPRECATION")
            audioManager.requestAudioFocus(
                null,
                AudioManager.STREAM_VOICE_CALL,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE
            )
        }
    }

    private fun abandonAudioFocus() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            focusRequest?.let(audioManager::abandonAudioFocusRequest)
            focusRequest = null
        } else {
            @Suppress("DEPRECATION")
            audioManager.abandonAudioFocus(null)
        }
    }
}
