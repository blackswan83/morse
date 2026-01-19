# Location Spoofer for iPhone

A native Mac application for simulating GPS locations on connected iPhones. Built with SwiftUI and powered by pymobiledevice3.

## Features

### Core Features (Phase 1)
- **Interactive Map** - Click anywhere on the map to place a pin
- **Location Search** - Search for any address or place name
- **Quick Locations** - One-click access to preset cities (Riyadh, London, New York, etc.)
- **Device Detection** - Automatic iPhone connection monitoring
- **Set/Clear Location** - Easy controls to spoof or reset GPS
- **Tunnel Management** - Auto-start tunnel service with admin prompt
- **Persistent Settings** - Remembers your last used location

### Route Simulation (Phase 2)
- **Draw Routes** - Click multiple points on the map to create a route
- **Speed Presets** - Walking (5 km/h), Jogging (10), Cycling (20), Driving (40), Highway (100)
- **Custom Speed** - Slider for precise speed control (1-150 km/h)
- **Play/Pause/Stop** - Full control over route simulation
- **Progress Tracking** - Real-time progress bar with ETA
- **Loop Mode** - Continuous route repetition for live location sharing
- **GPX Import** - Load routes from fitness apps (coming soon)

### Advanced Features
- **Menu Bar Access** - Quick controls from the menu bar
- **Keyboard Shortcuts** - ⌘L to set, ⌘K to clear location
- **Save Locations** - Store your favorite places
- **Dark Mode** - Full support for macOS dark mode

## Requirements

### System Requirements
- macOS 13.0 (Ventura) or later
- Xcode 15+ (to build from source)

### iPhone Requirements
- iOS 16 or later
- **Developer Mode enabled**:
  1. Go to Settings → Privacy & Security
  2. Scroll down to Developer Mode
  3. Toggle ON and restart
- USB connection to Mac
- Trust the computer when prompted

### Dependencies
- Python 3.8+
- pymobiledevice3
- libimobiledevice (optional, for additional tools)

## Installation

### Quick Setup

Run the setup script to install all dependencies:

```bash
cd LocationSpoofer
chmod +x Scripts/setup.sh
./Scripts/setup.sh
```

### Manual Setup

1. **Install Homebrew** (if not installed):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install Python 3**:
   ```bash
   brew install python3
   ```

3. **Install pymobiledevice3**:
   ```bash
   pip3 install pymobiledevice3
   ```

4. **Install libimobiledevice** (optional):
   ```bash
   brew install libimobiledevice
   ```

### Building the App

1. Open `LocationSpoofer.xcodeproj` in Xcode
2. Select your development team (or leave blank for local testing)
3. Press ⌘R to build and run

Or build from command line:
```bash
xcodebuild -project LocationSpoofer.xcodeproj -scheme LocationSpoofer -configuration Release build
```

## Usage

### Using the Mac App

1. **Connect iPhone** via USB cable
2. **Start Tunnel**: Click the "Start" button in the Device Status panel (requires admin password)
3. **Select Location**: Either:
   - Click on the map to place a pin
   - Use the search bar to find a location
   - Click a quick location button
4. **Set Location**: Click "Set Location" to spoof the GPS
5. **Clear Location**: Click "Reset to Real GPS" when done

### Using Command Line

**Start the tunnel** (keep this running in a terminal):
```bash
sudo python3 -m pymobiledevice3 remote tunneld
```

**Set a location**:
```bash
python3 -m pymobiledevice3 developer dvt simulate-location set --tunnel "" 24.7136 46.6753
```

**Clear location**:
```bash
python3 -m pymobiledevice3 developer dvt simulate-location clear --tunnel ""
```

### Quick Location Script

```bash
# Spoof to a preset city
./Scripts/quick_spoof.sh riyadh
./Scripts/quick_spoof.sh london

# Custom coordinates
./Scripts/quick_spoof.sh "40.7128 -74.0060"

# Clear location
./Scripts/quick_spoof.sh clear
```

### Route Simulation (CLI)

```bash
# Walk around Riyadh
python3 Scripts/move_location.py --route riyadh --speed 5

# Drive in London (loop continuously)
python3 Scripts/move_location.py --route london --speed 40 --loop

# Custom waypoints
python3 Scripts/move_location.py --waypoints '24.71,46.67;24.72,46.68;24.73,46.65' --speed 10

# From GPX file
python3 Scripts/move_location.py --gpx my_route.gpx --speed 15
```

## Quick Location Reference

| City       | Coordinates              |
|------------|--------------------------|
| Riyadh     | 24.7136, 46.6753        |
| London     | 51.5074, -0.1278        |
| New York   | 40.7128, -74.0060       |
| Paris      | 48.8566, 2.3522         |
| Dubai      | 25.2048, 55.2708        |
| Tokyo      | 35.6762, 139.6503       |
| Sydney     | -33.8688, 151.2093      |
| Singapore  | 1.3521, 103.8198        |

## Speed Reference

| Mode         | Speed (km/h) |
|--------------|--------------|
| Walking      | 5            |
| Jogging      | 10           |
| Cycling      | 15-25        |
| City Driving | 30-50        |
| Highway      | 80-120       |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                Mac App (SwiftUI)                    │
├─────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────────┐   │
│  │  Map View │  │  Controls │  │ Device Status │   │
│  └─────┬─────┘  └─────┬─────┘  └───────┬───────┘   │
│        │              │                │            │
│        └──────────────┼────────────────┘            │
│                       │                             │
│              ┌────────▼────────┐                    │
│              │ LocationManager │                    │
│              │  (Swift class)  │                    │
│              └────────┬────────┘                    │
│                       │                             │
│              ┌────────▼─────────┐                   │
│              │  Process/Shell   │                   │
│              │  Command Runner  │                   │
│              └────────┬─────────┘                   │
└───────────────────────┼─────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │   pymobiledevice3  │
              │   (Python CLI)     │
              └─────────┬─────────┘
                        │
              ┌─────────▼─────────┐
              │   iPhone (USB)     │
              └───────────────────┘
```

## Project Structure

```
LocationSpoofer/
├── LocationSpoofer.xcodeproj/     # Xcode project
├── LocationSpoofer/
│   ├── LocationSpooferApp.swift   # App entry point
│   ├── Views/
│   │   ├── ContentView.swift      # Main view
│   │   ├── MapViewRepresentable.swift
│   │   ├── DeviceStatusView.swift
│   │   ├── ActionButtonsView.swift
│   │   ├── QuickLocationsView.swift
│   │   ├── RouteSimulationView.swift
│   │   ├── SettingsView.swift
│   │   └── MenuBarView.swift
│   ├── Models/
│   │   └── Coordinate.swift       # Data models
│   ├── Managers/
│   │   ├── LocationManager.swift  # Location spoofing
│   │   ├── DeviceManager.swift    # iPhone detection
│   │   └── TunnelManager.swift    # Tunnel service
│   └── Resources/
│       └── Assets.xcassets/
├── Scripts/
│   ├── move_location.py           # Route simulation
│   ├── setup.sh                   # Dependency installer
│   ├── start_tunnel.sh            # Tunnel starter
│   └── quick_spoof.sh             # Quick CLI tool
└── README.md
```

## Troubleshooting

### "No iPhone Detected"
1. Check USB cable connection
2. Unlock iPhone and tap "Trust" when prompted
3. Try a different USB port
4. Restart iPhone

### "Tunnel Not Running"
1. Click "Start" button and enter admin password
2. Or manually run: `sudo python3 -m pymobiledevice3 remote tunneld`
3. Keep the tunnel running while spoofing

### "Failed to Set Location"
1. Ensure Developer Mode is enabled on iPhone
2. Check tunnel is running
3. Try clearing location first, then setting again
4. Restart the tunnel service

### "pymobiledevice3 not found"
1. Run the setup script: `./Scripts/setup.sh`
2. Or manually: `pip3 install pymobiledevice3`

### Python Path Issues
1. Go to Settings (⌘,) → Python tab
2. Set the correct Python path (usually `/usr/bin/python3` or `/usr/local/bin/python3`)
3. Click "Check Installation" to verify

## Limitations

1. **Mac Required** - No standalone iPhone app can spoof GPS
2. **USB Required** - Must be physically connected (wireless may work briefly after initial USB setup on some iOS versions)
3. **iOS 17+ Complexity** - Requires running a tunnel service with admin privileges
4. **Resets on Restart** - Restarting iPhone clears the spoofed location
5. **System-wide** - Affects all apps, not just one specific app

## License

MIT License - Use at your own risk. This tool is for educational and privacy purposes only.

## Credits

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - Python library for iOS device communication
- [libimobiledevice](https://github.com/libimobiledevice/libimobiledevice) - Cross-platform iOS protocol library
