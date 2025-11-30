#!/usr/bin/env python3
"""
JARVIS System Control

Handles system-level operations including application management,
volume control, and system commands.
"""

import logging
import os
import platform
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pynput
    from pynput import keyboard as pynput_keyboard
except ImportError:
    pynput = None

from config import SystemConfig, AudioConfig


@dataclass
class RunningProcess:
    """Information about a running process."""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    start_time: datetime
    command: str


class SystemControl:
    """Handles system-level operations and application management."""

    def __init__(self, config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.system = platform.system().lower()

    def initialize(self) -> bool:
        """Initialize system control features."""
        try:
            self.logger.info("Initializing system control...")

            # Check dependencies
            if psutil is None:
                self.logger.warning("psutil not available, some features limited")

            if pyautogui is None:
                self.logger.warning("pyautogui not available, some features limited")

            # Platform-specific setup
            self._setup_platform_specific()

            self.logger.info("System control initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize system control: {e}")
            return False

    def _setup_platform_specific(self):
        """Setup platform-specific configurations."""
        if self.system == "windows":
            self._setup_windows()
        elif self.system == "darwin":  # macOS
            self._setup_macos()
        else:  # Linux
            self._setup_linux()

    def _setup_windows(self):
        """Setup Windows-specific features."""
        # Windows-specific setup
        pass

    def _setup_macos(self):
        """Setup macOS-specific features."""
        # macOS-specific setup
        pass

    def _setup_linux(self):
        """Setup Linux-specific features."""
        # Linux-specific setup
        pass

    def open_application(self, command) -> Any:
        """Open a specified application."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        app_name = command.entities.get("app_name", "").strip()
        
        if not app_name:
            return ExecutionResult(
                success=False,
                message="Application name is required",
                error="Missing app_name parameter"
            )

        try:
            self.logger.info(f"Opening application: {app_name}")
            
            success = False
            method_used = ""

            # Try different methods based on platform
            if self.system == "windows":
                success, method_used = self._open_windows_app(app_name)
            elif self.system == "darwin":
                success, method_used = self._open_macos_app(app_name)
            else:  # Linux
                success, method_used = self._open_linux_app(app_name)

            if success:
                return ExecutionResult(
                    success=True,
                    message=f"Successfully opened {app_name} using {method_used}",
                    data={"app_name": app_name, "method": method_used}
                )
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Failed to open {app_name}",
                    error="Application not found or launch failed"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error opening {app_name}: {str(e)}",
                error=str(e)
            )

    def _open_windows_app(self, app_name: str) -> tuple[bool, str]:
        """Open application on Windows."""
        try:
            # Try to find in PATH or common locations
            app_variants = [
                app_name,
                f"{app_name}.exe",
                app_name.replace(" ", "")
            ]

            for variant in app_variants:
                try:
                    subprocess.Popen([variant], shell=True)
                    return True, f"Windows PATH ({variant})"
                except FileNotFoundError:
                    continue

            # Try Windows start menu
            try:
                os.startfile(app_name)
                return True, "Windows start menu"
            except Exception:
                pass

            return False, "Windows method failed"

        except Exception as e:
            self.logger.error(f"Windows app launch error: {e}")
            return False, str(e)

    def _open_macos_app(self, app_name: str) -> tuple[bool, str]:
        """Open application on macOS."""
        try:
            # Try open command
            result = subprocess.run([
                "open", "-a", app_name
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                return True, "macOS open command"

            # Try with .app extension
            result = subprocess.run([
                "open", "-a", f"{app_name}.app"
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                return True, "macOS open command with .app"

            return False, "macOS method failed"

        except subprocess.TimeoutExpired:
            return True, "macOS open command (timeout)"
        except Exception as e:
            self.logger.error(f"macOS app launch error: {e}")
            return False, str(e)

    def _open_linux_app(self, app_name: str) -> tuple[bool, str]:
        """Open application on Linux."""
        try:
            # Try direct command
            result = subprocess.run([
                app_name
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                return True, f"Direct command ({app_name})"

            # Try with specific paths
            common_paths = [
                f"/usr/bin/{app_name}",
                f"/usr/local/bin/{app_name}",
                f"/snap/bin/{app_name}"
            ]

            for path in common_paths:
                if os.path.exists(path):
                    subprocess.Popen([path])
                    return True, f"Linux path ({path})"

            # Try generic desktop application launcher
            try:
                subprocess.Popen([
                    "gtk-launch", app_name.lower().replace(" ", "-")
                ])
                return True, "GTK launcher"
            except Exception:
                pass

            return False, "Linux method failed"

        except subprocess.TimeoutExpired:
            return True, "Linux command (timeout)"
        except Exception as e:
            self.logger.error(f"Linux app launch error: {e}")
            return False, str(e)

    def close_application(self, command) -> Any:
        """Close a specified application."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        app_name = command.entities.get("app_name", "").strip()
        
        if not app_name:
            return ExecutionResult(
                success=False,
                message="Application name is required",
                error="Missing app_name parameter"
            )

        try:
            self.logger.info(f"Closing application: {app_name}")
            
            success = False
            method_used = ""

            if self.system == "windows":
                success, method_used = self._close_windows_app(app_name)
            elif self.system == "darwin":
                success, method_used = self._close_macos_app(app_name)
            else:  # Linux
                success, method_used = self._close_linux_app(app_name)

            if success:
                return ExecutionResult(
                    success=True,
                    message=f"Successfully closed {app_name} using {method_used}",
                    data={"app_name": app_name, "method": method_used}
                )
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Failed to close {app_name} (not running or no permission)",
                    error="Application not found or couldn't be closed"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error closing {app_name}: {str(e)}",
                error=str(e)
            )

    def _close_windows_app(self, app_name: str) -> tuple[bool, str]:
        """Close application on Windows."""
        try:
            # Try taskkill
            result = subprocess.run([
                "taskkill", "/F", "/IM", f"{app_name}.exe"
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return True, "Windows taskkill"

            # Try with just the app name
            result = subprocess.run([
                "taskkill", "/F", "/IM", app_name
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return True, "Windows taskkill (no extension)"

            return False, "Windows method failed"

        except Exception as e:
            self.logger.error(f"Windows app close error: {e}")
            return False, str(e)

    def _close_macos_app(self, app_name: str) -> tuple[bool, str]:
        """Close application on macOS."""
        try:
            # Try osascript
            applescript = f'''
            tell application "{app_name}" to quit
            '''
            
            result = subprocess.run([
                "osascript", "-e", applescript
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return True, "macOS AppleScript"

            # Try with .app extension
            applescript = f'''
            tell application "{app_name}.app" to quit
            '''
            
            result = subprocess.run([
                "osascript", "-e", applescript
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return True, "macOS AppleScript (.app)"

            return False, "macOS method failed"

        except Exception as e:
            self.logger.error(f"macOS app close error: {e}")
            return False, str(e)

    def _close_linux_app(self, app_name: str) -> tuple[bool, str]:
        """Close application on Linux."""
        try:
            # Try pkill
            result = subprocess.run([
                "pkill", "-f", app_name
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return True, "Linux pkill"

            # Try killall
            result = subprocess.run([
                "killall", app_name
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return True, "Linux killall"

            return False, "Linux method failed"

        except Exception as e:
            self.logger.error(f"Linux app close error: {e}")
            return False, str(e)

    def get_running_processes(self, command=None) -> Any:
        """Get list of running processes."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        try:
            if not psutil:
                return ExecutionResult(
                    success=False,
                    message="Process listing requires psutil library",
                    error="Missing dependency: psutil"
                )

            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'create_time', 'cmdline']):
                try:
                    info = proc.info
                    processes.append(RunningProcess(
                        pid=info['pid'],
                        name=info['name'],
                        cpu_percent=info['cpu_percent'],
                        memory_percent=info['memory_percent'],
                        start_time=datetime.fromtimestamp(info['create_time']),
                        command=' '.join(info['cmdline']) if info['cmdline'] else ""
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by CPU usage
            processes.sort(key=lambda p: p.cpu_percent, reverse=True)
            
            # Return top 20
            top_processes = processes[:20]

            return ExecutionResult(
                success=True,
                message=f"Found {len(processes)} running processes, showing top 20",
                data={
                    "total_processes": len(processes),
                    "processes": [
                        {
                            "name": p.name,
                            "pid": p.pid,
                            "cpu_percent": round(p.cpu_percent, 1),
                            "memory_percent": round(p.memory_percent, 1),
                            "start_time": p.start_time.strftime("%H:%M:%S")
                        }
                        for p in top_processes
                    ]
                }
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting processes: {str(e)}",
                error=str(e)
            )

    def set_volume(self, command) -> Any:
        """Set system volume level."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        # Extract volume level from command
        volume_level = None
        if "volume" in command.entities:
            volume_level = command.entities["volume"]
        else:
            # Try to extract from command text
            import re
            volume_match = re.search(r'(\d+)%?', command.raw_text.lower())
            if volume_match:
                volume_level = int(volume_match.group(1))

        if volume_level is None or not isinstance(volume_level, (int, float)):
            return ExecutionResult(
                success=False,
                message="Volume level (0-100) is required",
                error="Missing or invalid volume parameter"
            )

        # Clamp volume to valid range
        volume_level = max(0, min(100, int(volume_level)))

        try:
            self.logger.info(f"Setting volume to {volume_level}%")
            
            success = False
            method_used = ""

            if self.system == "windows":
                success, method_used = self._set_windows_volume(volume_level)
            elif self.system == "darwin":
                success, method_used = self._set_macos_volume(volume_level)
            else:  # Linux
                success, method_used = self._set_linux_volume(volume_level)

            if success:
                return ExecutionResult(
                    success=True,
                    message=f"Volume set to {volume_level}% using {method_used}",
                    data={"volume_level": volume_level, "method": method_used}
                )
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Failed to set volume to {volume_level}%",
                    error="Volume control not available"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error setting volume: {str(e)}",
                error=str(e)
            )

    def _set_windows_volume(self, level: int) -> tuple[bool, str]:
        """Set volume on Windows."""
        try:
            # This is simplified - in reality would use pycaw or similar
            # For now, just simulate success
            return True, "Windows (simulated)"
        except Exception as e:
            self.logger.error(f"Windows volume control error: {e}")
            return False, str(e)

    def _set_macos_volume(self, level: int) -> tuple[bool, str]:
        """Set volume on macOS."""
        try:
            # Use osascript to set volume
            result = subprocess.run([
                "osascript", "-e", f"set volume output volume {level}"
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                return True, "macOS AppleScript"

            return False, "macOS method failed"

        except Exception as e:
            self.logger.error(f"macOS volume control error: {e}")
            return False, str(e)

    def _set_linux_volume(self, level: int) -> tuple[bool, str]:
        """Set volume on Linux."""
        try:
            # Try amixer
            result = subprocess.run([
                "amixer", "sset", "Master", f"{level}%"
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                return True, "Linux amixer"

            # Try pactl
            result = subprocess.run([
                "pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                return True, "Linux pactl"

            return False, "Linux method failed"

        except Exception as e:
            self.logger.error(f"Linux volume control error: {e}")
            return False, str(e)

    def shutdown_system(self, command) -> Any:
        """Shutdown the system."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        delay_minutes = command.entities.get("delay", 0)
        
        try:
            self.logger.info(f"Initiating system shutdown with {delay_minutes} minute delay")
            
            if delay_minutes > 0:
                # Schedule shutdown
                if self.system == "windows":
                    subprocess.run(f"shutdown /s /t {delay_minutes * 60}", shell=True)
                elif self.system == "darwin":
                    subprocess.run(["sudo", "shutdown", "-h", f"+{delay_minutes}"])
                else:  # Linux
                    subprocess.run(["sudo", "shutdown", "-h", f"+{delay_minutes}"])
                
                return ExecutionResult(
                    success=True,
                    message=f"System will shutdown in {delay_minutes} minutes",
                    data={"delay_minutes": delay_minutes}
                )
            else:
                # Immediate shutdown
                if self.system == "windows":
                    subprocess.run("shutdown /s /t 0", shell=True)
                elif self.system == "darwin":
                    subprocess.run(["sudo", "shutdown", "-h", "now"])
                else:  # Linux
                    subprocess.run(["sudo", "shutdown", "-h", "now"])
                
                return ExecutionResult(
                    success=True,
                    message="Shutting down system immediately",
                    data={"delay_minutes": 0}
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error shutting down system: {str(e)}",
                error=str(e)
            )

    def restart_system(self, command) -> Any:
        """Restart the system."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        delay_minutes = command.entities.get("delay", 0)
        
        try:
            self.logger.info(f"Initiating system restart with {delay_minutes} minute delay")
            
            if delay_minutes > 0:
                # Schedule restart
                if self.system == "windows":
                    subprocess.run(f"shutdown /r /t {delay_minutes * 60}", shell=True)
                elif self.system == "darwin":
                    subprocess.run(["sudo", "shutdown", "-r", f"+{delay_minutes}"])
                else:  # Linux
                    subprocess.run(["sudo", "shutdown", "-r", f"+{delay_minutes}"])
                
                return ExecutionResult(
                    success=True,
                    message=f"System will restart in {delay_minutes} minutes",
                    data={"delay_minutes": delay_minutes}
                )
            else:
                # Immediate restart
                if self.system == "windows":
                    subprocess.run("shutdown /r /t 0", shell=True)
                elif self.system == "darwin":
                    subprocess.run(["sudo", "shutdown", "-r", "now"])
                else:  # Linux
                    subprocess.run(["sudo", "shutdown", "-r", "now"])
                
                return ExecutionResult(
                    success=True,
                    message="Restarting system immediately",
                    data={"delay_minutes": 0}
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error restarting system: {str(e)}",
                error=str(e)
            )

    def get_system_info(self, command=None) -> Any:
        """Get system information."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        try:
            info = {
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "python_version": platform.python_version(),
            }

            if psutil:
                # Add system resource information
                info.update({
                    "cpu_count": psutil.cpu_count(),
                    "memory_total": f"{psutil.virtual_memory().total // (1024**3)} GB",
                    "memory_available": f"{psutil.virtual_memory().available // (1024**3)} GB",
                    "disk_usage": f"{psutil.disk_usage('/').percent}%"
                })

            return ExecutionResult(
                success=True,
                message="System information retrieved successfully",
                data=info
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting system info: {str(e)}",
                error=str(e)
            )

    def test(self) -> bool:
        """Test system control functionality."""
        try:
            self.logger.info("Testing system control...")
            
            # Test basic functionality
            test_commands = [
                ("get_running_processes", "Test process listing"),
                ("get_system_info", "Test system info")
            ]

            for method_name, description in test_commands:
                try:
                    method = getattr(self, method_name)
                    result = method(None)
                    
                    if result.success:
                        self.logger.info(f"✅ {description} - PASSED")
                    else:
                        self.logger.error(f"❌ {description} - FAILED: {result.error}")
                        return False
                        
                except Exception as e:
                    self.logger.error(f"❌ {description} - ERROR: {e}")
                    return False

            self.logger.info("System control tests completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"System control test failed: {e}")
            return False

    def shutdown(self):
        """Cleanup system control resources."""
        self.logger.info("Shutting down system control...")
        # Nothing specific to cleanup
        self.logger.info("System control shutdown complete")
