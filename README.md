# AYON Google Drive Addon

This addon integrates AYON with Google Drive for Desktop to provide seamless access to shared drives and folders across multiple operating systems.

## Features

* **Cross-platform support** for Windows, macOS, and Linux
* **Automatic drive mapping** to maintain consistent paths across platforms
* **Shared drive integration** with Google Drive for Desktop
* **Automatic installation** of Google Drive when needed
* **Status monitoring** in the system tray
* **Customizable mappings** from shared drives to local paths
* **Multi-language support** for shared drive folder names

## Requirements

* Google Drive for Desktop (can be auto-installed by the addon)
* Google account with access to the required shared drives
* Administrator privileges may be required for some mapping operations

## Configuration

### General Settings

In the AYON Settings dialog, navigate to the Google Drive addon section:

* **Enabled**: Enable or disable the Google Drive addon
* **Auto-Install Google Drive**: Allow AYON to auto-install Google Drive if not present
* **Auto-Restart Google Drive**: Allow AYON to auto-restart Google Drive if it isn't running
* **Show Mount Point Mismatch Notifications**: Show notifications when Google Drive is mounted at a different drive letter than configured
* **Keep Symlinks on Exit (macOS)**: Keep symlinks on exit (macOS only)

### Google Drive Paths

* **Google Drive Installation Paths**: Paths to Google Drive application on different platforms
* **Google Drive Mount Point**: Default mount points for Google Drive on different platforms
* **Download URLs**: URLs for downloading Google Drive installers

### Drive Mappings

Configure mappings between Google Drive paths and local drive letters/paths:

* **Mapping Name**: Descriptive name for this drive mapping
* **Source Path**: Path in Google Drive (e.g., "\\Shared drives\\Projects")
* **Windows Target**: Windows target drive letter or path (e.g., "P:\\")
* **macOS Target**: macOS target mount path (e.g., "/Volumes/Projects")
* **Linux Target**: Linux target mount path (e.g., "/mnt/projects")

### Localization

Configure shared drive folder names for different languages to ensure proper detection across localized Google Drive installations.

## Usage

1. Install the addon through AYON server
2. Configure the addon settings, defining your shared drive mappings
3. Open the AYON tray app - the addon will automatically:
   * Detect if Google Drive is installed
   * Install it if needed (with your permission)
   * Start Google Drive when AYON starts
   * Create mappings to ensure consistent paths

### System Tray Integration

The addon adds a Google Drive menu to the AYON system tray with:
* Status indicator for Google Drive connection
* Quick access to mapped drives
* Options to install/start Google Drive if needed

## Platform-Specific Behavior

### Windows
* Uses `SUBST` commands to map Google Drive folders to drive letters
* Mappings are temporary and automatically removed when AYON exits

### macOS
* Creates symbolic links to Google Drive folders
* Links persist until manually removed or AYON exits (configurable)

### Linux
* Creates symbolic links to Google Drive folders
* Automatically detects desktop environment for better integration

## Troubleshooting

* **"Google Drive is not installed"**: The addon will offer to install it automatically
* **"Google Drive is not running"**: Click "Start Google Drive" in the menu
* **"Login required"**: You need to log in to Google Drive using its interface
* **"Drive mapping failed"**: Check if the target drive letter is already in use
* **"Permission denied"**: Some operations may require administrator privileges

## Known Issues

* This addon has only been tested thoroughly on Windows and MacOS machines so far.

## License

See the [LICENSE](LICENSE) file for details.
