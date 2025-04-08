# ayon-googledrive

# AYON Google Drive Addon

This addon allows AYON to integrate with Google Drive to provide seamless access to shared drives and folders across multiple operating systems.

## Features

* **Cross-platform support** for Windows, macOS, and Linux
* **Automatic drive mapping** to maintain consistent paths across platforms
* **Shared drive integration** with Google Drive for Desktop
* **Automatic installation** of Google Drive when needed
* **Status monitoring** in the system tray
* **Customizable mappings** from shared drives to local paths

## Requirements

* Google Drive for Desktop installed (can be auto-installed by the addon)
* Google account with access to the required shared drives
* Administrator privileges may be required for some mapping operations

## Usage

### Setting up Google Drive Integration

1. Install the addon through AYON server
2. Configure the addon settings, defining your shared drive mappings
3. Open the AYON tray app, and the addon will automatically:
   * Detect if Google Drive is installed
   * Install it if needed (with your permission)
   * Start Google Drive when AYON starts
   * Create mappings to ensure consistent paths

### Configuring Drive Mappings

In the AYON Settings dialog, navigate to the Google Drive addon section where you'll find:

* **General Settings** : Options to enable/disable automatic Google Drive installation and mounting
* **Google Drive Installation Paths** : Paths to Google Drive application on different platforms
* **Google Drive Mount Point** : Default mount points for Google Drive on different platforms
* **Drive Mappings** : A list of mappings where you can add, edit, or remove entries with:
* Mapping Name: A friendly name for the mapping (e.g., "Projects")
* Source Path: Path in Google Drive (e.g., "Shared drives\Projects")
* Platform-specific target paths: Where to map the drive on Windows, macOS, and Linux

Each mapping allows you to maintain consistent access to important folders across platforms, ensuring your team has the same paths regardless of operating system.

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
* Links persist until manually removed or AYON exits

### Linux

* Supports multiple Google Drive clients (official client, google-drive-ocamlfuse, rclone)
* Creates symbolic links to Google Drive folders
* Automatically detects desktop environment for better integration

## Troubleshooting

Common issues and their solutions:

* **"Google Drive is not installed"** : The addon will offer to install it automatically
* **"Google Drive is not running"** : Click "Start Google Drive" in the menu
* **"Login required"** : You need to log in to Google Drive using its interface
* **"Drive mapping failed"** : Check if the target drive letter is already in use
* **"Permission denied"** : Some operations may require administrator privileges. For now, there are not any in-addon workarounds coded for MacOS or Linux.

## Development

This addon is designed with cross-platform compatibility in mind and uses a platform abstraction layer to handle OS-specific implementations.

Key components:

* [GDriveManager](vscode-file://vscode-app/c:/Program%20Files/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html): Core logic and high-level operations
* [GDrivePlatformBase](vscode-file://vscode-app/c:/Program%20Files/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html): Abstract base class for platform operations
* Platform-specific implementations for Windows, macOS, and Linux
* [GDriveMenuBuilder](vscode-file://vscode-app/c:/Program%20Files/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html): Dynamic UI generation based on current status

## Known Issues / TODO

### **⚠** This addon has only been tested thoroughly on Windows machines so far.

## License

See the [LICENSE](vscode-file://vscode-app/c:/Program%20Files/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) file for details.
