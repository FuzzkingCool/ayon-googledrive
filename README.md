# AYON Google Drive Addon

[![Repository](https://img.shields.io/badge/repository-FuzzkingCool%2Fayon--googledrive-181717?logo=github)](https://github.com/FuzzkingCool/ayon-googledrive)
[![Branch](https://img.shields.io/badge/branch-develop-0a66c2)](https://github.com/FuzzkingCool/ayon-googledrive/tree/develop)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://github.com/FuzzkingCool/ayon-googledrive/blob/develop/pyproject.toml)
[![License](https://img.shields.io/github/license/FuzzkingCool/ayon-googledrive)](https://github.com/FuzzkingCool/ayon-googledrive/blob/develop/LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/FuzzkingCool/ayon-googledrive/develop)](https://github.com/FuzzkingCool/ayon-googledrive/commits/develop)
[![Repo Size](https://img.shields.io/github/repo-size/FuzzkingCool/ayon-googledrive)](https://github.com/FuzzkingCool/ayon-googledrive)
[![Issues](https://img.shields.io/github/issues/FuzzkingCool/ayon-googledrive)](https://github.com/FuzzkingCool/ayon-googledrive/issues)
[![Stars](https://img.shields.io/github/stars/FuzzkingCool/ayon-googledrive?style=social)](https://github.com/FuzzkingCool/ayon-googledrive/stargazers)

AYON addon that makes naive mount-point mappings of Google Shared Drives or arbitrary subfolders configurable in the Addon Settings.

## Overview

This addon integrates AYON with Google Drive for Desktop so teams can expose shared drives or selected Google Drive subfolders through consistent local paths across Windows, macOS, and Linux.

This is especially useful in AYON pipelines where tools, templates, and artist workstations expect stable filesystem locations regardless of operating system.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
  - [General Settings](#general-settings)
  - [Google Drive Paths](#google-drive-paths)
  - [Drive Mappings](#drive-mappings)
  - [Localization](#localization)
- [Usage](#usage)
- [Platform-Specific Behavior](#platform-specific-behavior)
- [Troubleshooting](#troubleshooting)
- [Known Issues](#known-issues)
- [Development Notes](#development-notes)
- [License](#license)

## Features

- Cross-platform support for Windows, macOS, and Linux
- Automatic drive mapping to maintain consistent paths across platforms
- Shared drive integration with Google Drive for Desktop
- Optional automatic installation of Google Drive when needed
- Optional automatic restart of Google Drive when it is not running
- Status monitoring in the AYON system tray
- Customizable mappings from shared drives or subfolders to local paths
- Multi-language support for shared drive folder names

## Requirements

- AYON with this addon installed and enabled
- Google Drive for Desktop
- A Google account with access to the required shared drives or folders
- Administrator privileges may be required for some mapping operations on some systems

## Installation

1. Install the addon through your AYON server or addon distribution workflow.
2. Enable the addon in AYON.
3. Open the addon settings and configure Google Drive paths and drive mappings.
4. Launch the AYON tray application.
5. Allow the addon to install or start Google Drive if your configuration permits it.

## Configuration

In AYON Settings, navigate to the Google Drive addon section.

### General Settings

- **Enabled**: Enable or disable the Google Drive addon.
- **Auto-Install Google Drive**: Allow AYON to auto-install Google Drive if it is not present.
- **Auto-Restart Google Drive**: Allow AYON to auto-restart Google Drive if it is not running.
- **Show Mount Point Mismatch Notifications**: Show notifications when Google Drive is mounted at a different drive letter or mount point than configured.
- **Keep Symlinks on Exit (macOS)**: Keep symlinks on exit on macOS.

### Google Drive Paths

- **Google Drive Installation Paths**: Paths to the Google Drive application on different platforms.
- **Google Drive Mount Point**: Default mount points for Google Drive on different platforms.
- **Download URLs**: URLs for downloading Google Drive installers.

### Drive Mappings

Configure mappings between Google Drive paths and local drive letters or mount paths.

- **Mapping Name**: Descriptive name for the mapping.
- **Source Path**: Path in Google Drive, for example `\\Shared drives\\Projects`.
- **Windows Target**: Windows target drive letter or path, for example `P:\\`.
- **macOS Target**: macOS target mount path, for example `/Volumes/Projects`.
- **Linux Target**: Linux target mount path, for example `/mnt/projects`.

### Localization

Configure localized shared drive folder names so the addon can correctly detect Google Drive paths across installations running in different languages.

## Usage

After configuration, open the AYON tray application. The addon will automatically:

- Detect whether Google Drive is installed
- Offer installation when allowed by configuration
- Start Google Drive when AYON starts
- Create mappings that keep project paths consistent across platforms

### System Tray Integration

The addon adds a Google Drive section to the AYON tray menu with:

- A status indicator for Google Drive connection state
- Quick access to mapped drives or folders
- Options to install or start Google Drive when needed

## Platform-Specific Behavior

### Windows

- Uses `SUBST` commands to map Google Drive folders to drive letters
- Mappings are temporary and automatically removed when AYON exits

### macOS

- Creates symbolic links to Google Drive folders
- Links persist until manually removed or until AYON exits, depending on configuration

### Linux

- Creates symbolic links to Google Drive folders
- Automatically detects the desktop environment for better integration

## Troubleshooting

- **Google Drive is not installed**: The addon can offer to install it automatically if enabled.
- **Google Drive is not running**: Use the tray menu option to start Google Drive.
- **Login required**: Sign in through the Google Drive user interface.
- **Drive mapping failed**: Check whether the target drive letter or mount path is already in use.
- **Permission denied**: Some operations may require elevated privileges.
- **Wrong shared drive path detected**: Review localization settings and configured mount points.

## Known Issues

- This addon has been tested more thoroughly on Windows and macOS than on Linux.
- Mapping behavior depends on how Google Drive for Desktop is mounted and authenticated on the local machine.

## Development Notes

- Repository default branch: `develop`
- Language: Python
- Package version: `0.5.0`
- Python requirement: `>=3.9`
- License: Apache License 2.0

For packaging metadata, see [`pyproject.toml`](pyproject.toml).

## License

Licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
