import os
import platform
import subprocess
from qtpy import QtWidgets, QtGui, QtCore

from ayon_googledrive.logger import log


class GDriveMenuBuilder:
    """Class to build and update the Google Drive menu"""
    
    def __init__(self, addon_instance):
        self.addon = addon_instance
        self.gdrive_manager = addon_instance._gdrive_manager
        self.log = log
        self._icon_cache = {}  # Cache icons for performance
    
    def _get_icon(self, icon_type):
        """Get icon for menu items based on type."""  
        # Return from cache if available
        if icon_type in self._icon_cache:
            return self._icon_cache[icon_type]
            
        icon = QtGui.QIcon()
        
        # Create colored circle icons with explicit size to ensure visibility
        if icon_type in ["ok", "warning", "error"]:
            # Map icon types to colors
            color_map = {
                "ok": QtGui.QColor(0, 180, 0),       # Green
                "warning": QtGui.QColor(255, 165, 0), # Orange
                "error": QtGui.QColor(255, 0, 0)      # Red
            }
            
            color = color_map.get(icon_type)
            if color:
                # Create pixmap with colored circle
                size = 16  # Icon size
                pixmap = QtGui.QPixmap(size, size)
                pixmap.fill(QtCore.Qt.transparent)
                
                painter = QtGui.QPainter(pixmap)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                painter.setBrush(QtGui.QBrush(color))
                painter.setPen(QtGui.QPen(QtCore.Qt.black, 1))
                painter.drawEllipse(2, 2, size-4, size-4)
                painter.end()
                
                icon = QtGui.QIcon(pixmap)
                
        # Cache the icon for future use
        self._icon_cache[icon_type] = icon
        return icon
    
    def update_menu_contents(self, menu):
        """Update menu contents dynamically when about to be shown."""
        try:
            menu.clear()
            
            # Add loading indicator while we check the status
            loading_action = QtWidgets.QAction("Checking Google Drive status...", menu)
            loading_action.setEnabled(False)
            menu.addAction(loading_action)
            
            # Process Qt events to show loading message
            QtWidgets.QApplication.processEvents()
            
            self.log.debug("Updating Google Drive menu contents")
            
            # Clear the menu again before adding actual items
            menu.clear()
            
            # Check installation status
            if not self.gdrive_manager.is_googledrive_installed():
                # Not installed - change main menu item to show status
                self._set_menu_status(menu, "Google Drive: Not Installed", "error")
                
                install_action = QtWidgets.QAction("Install Google Drive", menu)
                install_action.triggered.connect(self.addon._install_googledrive)
                menu.addAction(install_action)
                return
                
            # Check if running
            if not self.gdrive_manager.is_googledrive_running():
                # Not running - change main menu item to show status
                self._set_menu_status(menu, "Google Drive: Not Running", "warning")
                
                start_action = QtWidgets.QAction("Start Google Drive", menu)
                start_action.triggered.connect(self.addon._start_googledrive)
                menu.addAction(start_action)
                return
                
            # Check if logged in
            if not self.gdrive_manager.is_user_logged_in():
                # Not logged in - change main menu item to show status
                self._set_menu_status(menu, "Google Drive: Login Required", "warning")
                
                login_action = QtWidgets.QAction("Please login to Google Drive", menu)
                login_action.setEnabled(False)
                menu.addAction(login_action)
                return
            
            # If we get here, Google Drive seems to be working
            # Now check if all configured mappings are working
            has_all_mappings = self._check_all_mappings_valid()
            
            if has_all_mappings:
                # Everything is perfect - all mappings are valid
                self._set_menu_status(menu, "Google Drive: Connected", "ok")
            else:
                # Some mappings may have issues
                self._set_menu_status(menu, "Google Drive: Connection Issue", "warning")
            
            # Add mapping status submenu with direct links to locations
            self._add_mapping_submenu(menu)
            
        except Exception as e:
            self.log.error(f"Error updating Google Drive menu: {e}")
            self._set_menu_status(menu, "Google Drive: Error", "error")
            self._add_error_menu_item(menu, str(e))
    
    def _set_menu_status(self, menu, title, icon_type):
        """Set the menu title and icon with proper status indication"""
        menu.setTitle(title)
        
        # Get and set the icon
        icon = self._get_icon(icon_type)
        menu.setIcon(icon)
        
        # Force the icon to show by setting its size policy
        if hasattr(menu, 'setIconSize'):
            menu.setIconSize(QtCore.QSize(16, 16))
    
    def _check_all_mappings_valid(self):
        """Check if all configured mappings are valid"""
        mappings = self.addon.settings.get("mappings", [])
        if not mappings:
            return True  # No mappings to check
            
        # Get platform-specific targets
        os_type = platform.system()
        
        all_valid = True
        for mapping in mappings:
            if os_type == "Windows":
                target = mapping.get("windows_target", "")
            elif os_type == "Darwin":
                target = mapping.get("macos_target", "")
            elif os_type == "Linux":
                target = mapping.get("linux_target", "")
            else:
                target = ""
                
            # Simple check if target exists
            if not target or not os.path.exists(target):
                all_valid = False
                break
                
        return all_valid
    
    def _add_error_menu_item(self, menu, error_message):
        """Add an error menu item"""
        error_action = QtWidgets.QAction(f"Error: {error_message}", menu)
        error_action.setIcon(self._get_icon("error"))
        menu.addAction(error_action)

    def _add_mapping_submenu(self, menu):
        """Add mappings submenu with detailed status"""
        # Get mappings from settings
        settings = self.addon.settings
        mappings = settings.get("mappings", [])
        
        if not mappings:
            no_mappings_action = QtWidgets.QAction("No drive mappings configured", menu)
            no_mappings_action.setEnabled(False)
            menu.addAction(no_mappings_action)
            return
        
        # Add drive mappings directly to the menu
        for mapping in mappings:
            self._add_drive_mapping_item(menu, mapping)
    
    def _add_drive_mapping_item(self, menu, mapping):
        """Add a single drive mapping with status and open folder action"""
        try:
            name = mapping.get("name", "Unnamed")
            # source_path = mapping.get("source_path", "Unknown")
            
            # Get target path based on platform
            os_type = platform.system()
            if os_type == "Windows":
                target = mapping.get("windows_target", "")
            elif os_type == "Darwin":
                target = mapping.get("macos_target", "")
            elif os_type == "Linux":
                target = mapping.get("linux_target", "")
            else:
                target = ""
                
            # Check if target exists
            target_exists = os.path.exists(target) if target else False
            
            # Create the menu item
            status_action = QtWidgets.QAction(name, menu)
            
            # Determine status and icon
            if target_exists:
                status_action.setIcon(self._get_icon("ok"))
                # Connect action to open the folder location
                status_action.triggered.connect(lambda checked=False, t=target: self._open_location(t))
            else:
                status_action.setIcon(self._get_icon("error"))
                status_text = f"{name} (Not Connected)"
                status_action.setText(status_text)
                status_action.setEnabled(False)
            
            menu.addAction(status_action)
        except Exception as e:
            self.log.error(f"Error adding drive mapping menu item: {e}")
    
    def _open_location(self, path):
        """Open a file location with the platform's default file browser"""
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", path])
            else:  # Linux
                subprocess.run(["xdg-open", path])
                
            self.log.debug(f"Opening location: {path}")
        except Exception as e:
            self.log.error(f"Error opening location {path}: {e}")

    def get_menu_items(self):
        """Get menu items for ITrayService."""
        from qtpy import QtWidgets
        
        menu_items = []
        
        # Add loading indicator - will be updated when shown
        menu_items.append({
            "label": "Loading Google Drive...",
            "enabled": False
        })
        
        # Add update function that will be called when menu is about to show
        menu_items.append({
            "on_about_to_show": self.update_menu_contents
        })
        
        return menu_items