# Ear AI Mobile App Architecture

## Overview
Ear AI Mobile App is an Android application that enables voice control through Bluetooth earbuds. It communicates with the Ear AI Home Server via WebSocket, handles real-time audio input, and displays assistant responses along with music playback controls.

## Technology Stack

### Core Framework
- **Android SDK** - Target API 33+, Minimum API 30
- **Kotlin** - Primary programming language
- **AndroidX** - Modern Android support libraries
- **Jetpack Compose** - Modern UI toolkit (recommended)
- **Material Design 3** - UI design system

### Real-Time Communication
- **OkHttp 4.x** - HTTP/HTTPS client
- **OkHttp WebSocket** - WebSocket implementation
- **Retrofit 2.x** - REST API client (for Spotify/Music endpoints)

### Audio & Voice
- **Android AudioRecord API** - Raw audio capture from earbuds
- **Android MediaPlayer** - Audio playback
- **ExoPlayer** - Advanced media playback (optional, for Spotify)
- **Spotify Android SDK** - Direct Spotify app control

### Data & Preferences
- **Android SharedPreferences** - Local settings storage
- **Jetpack DataStore** - Modern preference management
- **Room Database** - Local conversation history caching

### Concurrency & Networking
- **Kotlin Coroutines** - Asynchronous programming
- **Flow** - Reactive stream handling
- **WorkManager** - Background task scheduling

### Additional Libraries
- **Dagger Hilt** - Dependency injection
- **Timber** - Logging framework
- **Accompanist** - Jetpack Compose utilities

## System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                      Android Device                           │
├───────────────────────────────────────────────────────────────┤
│                    Ear AI Mobile App                          │
├───────────────────────────────────────────────────────────────┤
│ UI Layer (Jetpack Compose)                                   │
│ ├─ Home Screen                                               │
│ │  ├─ Voice Input Indicator                                 │
│ │  ├─ Assistant Response Display                            │
│ │  └─ Quick Controls (Play/Pause/Stop)                      │
│ ├─ Music Screen                                              │
│ │  ├─ Now Playing (Local/Spotify)                           │
│ │  ├─ Playlist View                                         │
│ │  └─ Playback Controls                                     │
│ ├─ Settings Screen                                           │
│ │  ├─ Server Connection Config                              │
│ │  ├─ Spotify Authentication                                │
│ │  └─ Audio Settings                                        │
│ └─ Conversation History                                      │
├───────────────────────────────────────────────────────────────┤
│ ViewModel Layer (State Management)                           │
│ ├─ AssistantViewModel                                        │
│ ├─ MusicViewModel                                            │
│ ├─ ConnectionViewModel                                       │
│ └─ SettingsViewModel                                         │
├───────────────────────────────────────────────────────────────┤
│ Repository Layer (Data Access)                               │
│ ├─ AssistantRepository                                       │
│ ├─ MusicRepository                                           │
│ ├─ SpotifyRepository                                         │
│ └─ PreferencesRepository                                     │
├───────────────────────────────────────────────────────────────┤
│ Service Layer (Android Services)                             │
│ ├─ AudioCaptureService (Foreground Service)                 │
│ ├─ WebSocketService                                          │
│ └─ MusicPlaybackService                                      │
├───────────────────────────────────────────────────────────────┤
│ Communication Layer                                          │
│ ├─ WebSocket Client                                          │
│ ├─ REST API Clients                                          │
│ └─ Server Connection Manager                                │
├───────────────────────────────────────────────────────────────┤
│ Local Storage Layer                                          │
│ ├─ SharedPreferences / DataStore                            │
│ ├─ Room Database                                             │
│ └─ Audio Buffers                                             │
└───────────────────────────────────────────────────────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
    Bluetooth Earbuds   Ear AI Home Server     Spotify App/API
    Audio Input/Output   WebSocket: Port 8765  Media Control
```

## Core Components

### 1. **UI Layer** - Jetpack Compose

#### Home Screen
```kotlin
@Composable
fun HomeScreen(
  viewModel: AssistantViewModel,
  onSettingsClick: () -> Unit
) {
  // Voice indicator animation
  // Assistant response text display
  // Inline music controls
  // Quick action buttons
}
```
- Real-time voice input status indicator (listening/processing)
- Assistant response display with message history
- Integration with music player controls
- Quick actions: Play, Pause, Stop, Settings

#### Music Screen
```kotlin
@Composable
fun MusicScreen(
  musicViewModel: MusicViewModel,
  spotifyViewModel: SpotifyViewModel
) {
  // Tabs: Local Music / Spotify
  // Now Playing card
  // Playlist view
  // Playback controls
}
```
- Now Playing card showing current track
- Playlist view with scroll
- Playback controls (play, pause, skip, random)
- Volume slider
- Local vs Spotify toggle

#### Settings Screen
```kotlin
@Composable
fun SettingsScreen(
  settingsViewModel: SettingsViewModel
) {
  // Server URL input
  // Auth token input
  // Spotify credentials
  // Audio settings
  // Connection status
}
```
- Server URL and port configuration
- Authentication token management
- Spotify app linkage
- Audio input/output device selection
- Auto-connect preference
- Volume settings

### 2. **ViewModel Layer** - State Management

#### AssistantViewModel
```kotlin
class AssistantViewModel(
  private val repository: AssistantRepository,
  private val audioService: AudioCaptureService
) : ViewModel() {
  
  val conversationHistory: Flow<List<Message>>
  val currentResponse: StateFlow<String>
  val isListening: StateFlow<Boolean>
  val connectionStatus: StateFlow<ConnectionStatus>
  
  fun startListening(): Job
  fun stopListening(): Job
  fun sendMessage(text: String): Job
  fun clearHistory(): Job
}
```
- Manages conversation state
- Handles audio capture lifecycle
- Tracks WebSocket connection status
- Exposes conversation history as Flow

#### MusicViewModel
```kotlin
class MusicViewModel(
  private val repository: MusicRepository
) : ViewModel() {
  
  val playlist: Flow<List<Song>>
  val nowPlaying: StateFlow<Song?>
  val isPlaying: StateFlow<Boolean>
  val currentPosition: StateFlow<Long>
  val volume: StateFlow<Float>
  
  fun play(songIndex: Int): Job
  fun pause(): Job
  fun resume(): Job
  fun stop(): Job
  fun next(): Job
  fun previous(): Job
  fun setVolume(level: Float): Job
  fun refreshPlaylist(): Job
}
```
- Manages music playback state
- Handles playback control events
- Tracks current position and volume
- Loads and manages playlists

#### SpotifyViewModel
```kotlin
class SpotifyViewModel(
  private val repository: SpotifyRepository
) : ViewModel() {
  
  val isAuthenticated: StateFlow<Boolean>
  val featuredPlaylists: Flow<List<SpotifyPlaylist>>
  val newReleases: Flow<List<SpotifyAlbum>>
  val recommendations: Flow<List<SpotifyTrack>>
  val searchResults: Flow<List<SpotifyItem>>
  
  fun authenticate(): Job
  fun search(query: String): Job
  fun play(spotifyUri: String): Job
  fun getFeaturedPlaylists(): Job
  fun getNewReleases(): Job
  fun getRecommendations(genres: List<String>): Job
}
```
- Handles Spotify authentication
- Manages Spotify search and playback
- Caches results in memory
- Integrates with Android Spotify app

### 3. **Service Layer** - Android Services

#### AudioCaptureService (Foreground Service)
```kotlin
class AudioCaptureService : Service() {
  
  private val audioRecord: AudioRecord
  private val audioBuffer: ByteArray
  private val captureJob: Job
  
  fun startCapture()
  fun stopCapture()
  fun getAudioStream(): Flow<AudioFrame>
}
```
- Foreground service for continuous audio capture
- Receives audio from earbuds/microphone
- Provides audio stream to UI and WebSocket
- Handles audio focus and permission management
- Notification showing active recording status

**Key Features**
- PCM audio format (16-bit, 44.1kHz or 48kHz sample rate)
- Mono or stereo input
- Real-time audio buffering
- Graceful pause/resume

#### WebSocketService
```kotlin
class WebSocketService : Service() {
  
  private val webSocketClient: OkHttpClient
  private val webSocket: WebSocket
  private val connectionState: StateFlow<ConnectionState>
  
  fun connect(serverUrl: String, authToken: String?)
  fun disconnect()
  fun send(message: AssistantMessage)
  fun onMessageReceived(response: AssistantResponse)
}
```
- Manages WebSocket lifecycle
- Auto-reconnection with exponential backoff
- Message queuing during disconnection
- Handles network transitions (WiFi → Cellular)

#### MusicPlaybackService
```kotlin
class MusicPlaybackService : Service() {
  
  private val mediaPlayer: MediaPlayer
  private val playlist: List<Song>
  
  fun playLocal(songPath: String)
  fun playSpotify(uri: String)
  fun pause()
  fun resume()
  fun stop()
}
```
- Local music playback via MediaPlayer
- Spotify URI handling (passes to Spotify app)
- Maintains playback state
- Handles audio focus conflicts

### 4. **Repository Layer** - Data Access

#### AssistantRepository
```kotlin
class AssistantRepository(
  private val webSocketService: WebSocketService,
  private val audioService: AudioCaptureService,
  private val database: ConversationDatabase
) {
  
  suspend fun sendMessage(text: String): Flow<AssistantResponse>
  suspend fun getHistory(sessionId: String): List<Message>
  suspend fun clearHistory(sessionId: String)
  fun observeConnectionStatus(): Flow<ConnectionStatus>
}
```
- Handles WebSocket communication
- Manages conversation history in Room DB
- Coordinates with audio and WebSocket services

#### MusicRepository
```kotlin
class MusicRepository(
  private val apiClient: RestClient,
  private val musicService: MusicPlaybackService
) {
  
  suspend fun getPlaylist(): List<Song>
  suspend fun play(index: Int): MusicStatus
  suspend fun pause(): MusicStatus
  suspend fun resume(): MusicStatus
  suspend fun next(): MusicStatus
  suspend fun setVolume(level: Float)
  fun observeStatus(): Flow<MusicStatus>
}
```
- Gets music endpoints from home server
- Local caching of playlist
- Handles playback state updates

#### SpotifyRepository
```kotlin
class SpotifyRepository(
  private val apiClient: RestClient,
  private val spotifyApp: SpotifyAppRemote
) {
  
  suspend fun getAuthenticated(): Boolean
  suspend fun authenticate(): String  // Auth token
  suspend fun search(query: String): List<SpotifyItem>
  suspend fun play(uri: String)
  suspend fun getRecommendations(genres: List<String>): List<SpotifyTrack>
}
```
- Communicates with home server Spotify endpoints
- Direct Spotify app control via Android intent
- Caches recommendations and search results

#### PreferencesRepository
```kotlin
class PreferencesRepository(
  private val dataStore: DataStore<Preferences>
) {
  
  fun getServerUrl(): Flow<String>
  fun getAuthToken(): Flow<String>
  fun getAutoConnect(): Flow<Boolean>
  fun getMusicVolume(): Flow<Float>
  
  suspend fun setServerUrl(url: String)
  suspend fun setAuthToken(token: String)
  suspend fun setAutoConnect(enabled: Boolean)
}
```
- Persists user settings
- Reactive preference updates

### 5. **Communication Layer**

#### WebSocket Client
```kotlin
class WebSocketClient(
  private val httpClient: OkHttpClient
) {
  
  fun createSocket(url: String): WebSocket
  fun send(message: AssistantMessage)
  fun onMessage(text: String)
  fun onFailure(t: Throwable, response: Response?)
}
```

#### REST API Clients
```kotlin
interface MusicApiService {
  @GET("music/playlist")
  suspend fun getPlaylist(): PlaylistResponse
  
  @GET("music/status")
  suspend fun getStatus(): MusicStatus
  
  @POST("music/play")
  suspend fun play(@Query("song_index") index: Int)
  
  @POST("music/pause")
  suspend fun pause()
  // ... more endpoints
}

interface SpotifyApiService {
  @GET("spotify/status")
  suspend fun checkStatus(): SpotifyStatus
  
  @POST("spotify/play")
  suspend fun play(@Query("query") query: String): SpotifyPlaybackInfo
  
  @GET("spotify/featured")
  suspend fun getFeaturedPlaylists(): FeaturedResponse
  // ... more endpoints
}
```

## Data Models

### Messages
```kotlin
data class AssistantMessage(
  val type: String = "user_utterance",
  val session_id: String,
  val text: String,
  val timestamp: String
)

data class AssistantResponse(
  val session_id: String,
  val text: String,
  val timestamp: String
)

data class Message(
  val id: Long,
  val sessionId: String,
  val role: String,  // "user" or "assistant"
  val text: String,
  val timestamp: Long
)
```

### Music Models
```kotlin
data class Song(
  val index: Int,
  val filename: String,
  val path: String
)

data class MusicStatus(
  val is_playing: Boolean,
  val is_paused: Boolean,
  val current_song: Song?,
  val current_position_ms: Long,
  val volume: Float,
  val playlist_size: Int,
  val current_index: Int
)
```

### Spotify Models
```kotlin
data class SpotifyPlaybackInfo(
  val ok: Boolean,
  val uri: String,
  val name: String,
  val artist: String,
  val url: String,
  val type: String,  // "track" or "playlist"
  val message: String
)
```

## UI State Management

```kotlin
enum class ConnectionStatus {
  DISCONNECTED,
  CONNECTING,
  CONNECTED,
  ERROR
}

enum class AudioState {
  IDLE,
  LISTENING,
  PROCESSING,
  PLAYING_RESPONSE
}

data class UIState(
  val connectionStatus: ConnectionStatus = ConnectionStatus.DISCONNECTED,
  val audioState: AudioState = AudioState.IDLE,
  val currentResponse: String = "",
  val musicNowPlaying: Song? = null,
  val isMusicPlaying: Boolean = false,
  val showLoadingIndicator: Boolean = false
)
```

## Permissions Required

```xml
<!-- Android Manifest -->
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
```

## Event Flow

### Voice Interaction Flow
```
User speaks into earbuds
         ↓
AudioCaptureService captures audio
         ↓
Audio frames sent to AssistantViewModel
         ↓
AssistantViewModel transcribes (if supported) or streams raw audio
         ↓
WebSocketService sends audio/text to home server
         ↓
Home server processes and responds
         ↓
AssistantRepository receives response
         ↓
ViewModel updates conversation history
         ↓
UI updates with assistant reply
         ↓
If music command: MusicPlaybackService executes
```

### Music Playback Flow
```
User says "play music" or taps play button
         ↓
MusicViewModel receives event
         ↓
MusicRepository -> REST API call to /music/play
         ↓
MusicPlaybackService plays local track
         ↓
UI updates now playing display
         ↓
User can skip/pause/adjust volume
         ↓
Changes reflected in UI in real-time
```

### Spotify Integration Flow
```
User says "play [song] on Spotify"
         ↓
Server searches Spotify API
         ↓
Server returns spotify:track:xxx URI
         ↓
SpotifyViewModel receives URI
         ↓
Android Intent launches Spotify app with URI
         ↓
Spotify app plays the track
         ↓
UI shows now playing info
```

## Local Storage

### Conversation History (Room DB)
```kotlin
@Database(entities = [Message::class], version = 1)
abstract class ConversationDatabase : RoomDatabase() {
  abstract fun messageDao(): MessageDao
}

@Dao
interface MessageDao {
  @Query("SELECT * FROM messages WHERE sessionId = :sessionId ORDER BY timestamp DESC")
  fun getHistoryBySession(sessionId: String): Flow<List<Message>>
  
  @Insert
  suspend fun insertMessage(message: Message)
  
  @Query("DELETE FROM messages WHERE sessionId = :sessionId")
  suspend fun clearSession(sessionId: String)
}
```

### Settings (DataStore)
```kotlin
// Proto format
message AppSettings {
  string server_url = 1;
  string auth_token = 2;
  bool auto_connect = 3;
  float music_volume = 4;
  string current_session_id = 5;
}
```

## Manifest & Configuration

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.earai.mobile">
  
  <!-- Services -->
  <service android:name=".service.AudioCaptureService" />
  <service android:name=".service.WebSocketService" />
  <service android:name=".service.MusicPlaybackService" />
  
  <!-- Activities -->
  <activity
      android:name=".MainActivity"
      android:exported="true">
    <intent-filter>
      <action android:name="android.intent.action.MAIN" />
      <category android:name="android.intent.category.LAUNCHER" />
    </intent-filter>
  </activity>
  
  <!-- Broadcast Receiver for Spotify playback events -->
  <receiver android:name=".receiver.SpotifyBroadcastReceiver" />
  
</manifest>
```

## Build Configuration

```kotlin
// build.gradle.kts
android {
  compileSdk = 34
  minSdk = 30
  targetSdk = 34
  
  buildFeatures {
    compose = true
  }
  
  composeOptions {
    kotlinCompilerExtensionVersion = "1.5.10"
  }
}

dependencies {
  // Core Android
  implementation("androidx.core:core-ktx:1.12.0")
  implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
  
  // Compose
  implementation("androidx.compose.ui:ui:1.6.0")
  implementation("androidx.compose.material3:material3:1.1.2")
  implementation("androidx.compose.runtime:runtime:1.6.0")
  
  // Networking
  implementation("com.squareup.okhttp3:okhttp:4.11.0")
  implementation("com.squareup.retrofit2:retrofit:2.10.0")
  
  // Coroutines
  implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
  
  // Room Database
  implementation("androidx.room:room-runtime:2.6.1")
  implementation("androidx.room:room-ktx:2.6.1")
  
  // DataStore
  implementation("androidx.datastore:datastore-preferences:1.0.0")
  
  // Hilt DI
  implementation("com.google.dagger:hilt-android:2.48")
  
  // Spotify
  implementation("com.spotify.android:auth:2.1.0")
  
  // Timber Logging
  implementation("com.jakewharton.timber:timber:5.0.1")
}
```

## Deployment & Release

- **Target**: Google Play Store
- **Minimum SDK**: Android 12 (API 31)
- **Build Type**: Release with ProGuard optimization
- **Signing**: App signing via Play Console
- **Version**: Semantic versioning (MAJOR.MINOR.PATCH)

## Future Enhancements

- [ ] Local voice-to-text transcription (on-device)
- [ ] Push notifications for server events
- [ ] Offline mode with local LLM
- [ ] Voice command customization
- [ ] Multi-device support
- [ ] Widget for quick controls
- [ ] Voice history backup/cloud sync
- [ ] Advanced audio DSP (noise cancellation)
- [ ] Bluetooth device management
- [ ] Premium features (priority queue, etc.)

## Dependencies Summary for Mobile App

| Library | Version | Purpose |
|---------|---------|---------|
| Jetpack Compose | 1.6.0 | Modern UI |
| OkHttp | 4.11.0 | HTTP client |
| Retrofit | 2.10.0 | REST API |
| Kotlin Coroutines | 1.7.3 | Async |
| Room | 2.6.1 | Local DB |
| DataStore | 1.0.0 | Preferences |
| Hilt | 2.48 | Dependency injection |
| Timber | 5.0.1 | Logging |
| Spotify Auth | 2.1.0 | Spotify SDK |
