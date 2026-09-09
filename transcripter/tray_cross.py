"""Cross-platform system tray icon using pystray."""

import threading
from typing import Callable, Optional
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

from .platform_utils import is_windows, is_macos, is_linux


class CrossPlatformTray:
    """Cross-platform system tray icon using pystray."""

    def __init__(self, app_name: str = "Transcripter"):
        """
        Initialize the tray icon.

        Args:
            app_name: Name of the application
        """
        self.app_name = app_name
        self.icon: Optional['pystray.Icon'] = None

        # Callbacks
        self.on_start_recording: Optional[Callable] = None
        self.on_stop_recording: Optional[Callable] = None
        self.on_settings: Optional[Callable] = None
        self.on_history: Optional[Callable] = None
        self.on_about: Optional[Callable] = None
        self.on_quit: Optional[Callable] = None

        # State
        self.is_recording = False
        self._status = "Idle"

    def _get_resource_path(self, relative_path: str) -> Path:
        """
        Get path to resource, works for dev and PyInstaller.

        Args:
            relative_path: Path relative to the package directory

        Returns:
            Absolute path to the resource
        """
        import sys
        if getattr(sys, 'frozen', False):
            # Running as compiled executable (PyInstaller)
            base_path = Path(sys._MEIPASS)
        else:
            # Running from source
            base_path = Path(__file__).parent
        return base_path / relative_path

    def _create_image(self, recording: bool = False) -> 'Image.Image':
        """
        Create an icon image.

        Args:
            recording: Whether recording is active

        Returns:
            PIL Image object
        """
        # Try to load icon from file first
        if recording:
            icon_path = self._get_resource_path("gui/icons/recording.png")
        else:
            icon_path = self._get_resource_path("gui/icons/transcripter.png")

        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception:
                pass

        # Fallback: create a simple icon
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        if recording:
            # Red circle for recording
            draw.ellipse([4, 4, size-4, size-4], fill='red')
        else:
            # Blue circle for idle
            draw.ellipse([4, 4, size-4, size-4], fill='#4285F4')
            # Microphone-like shape
            draw.ellipse([20, 12, 44, 36], fill='white')
            draw.rectangle([26, 32, 38, 48], fill='white')
            draw.arc([18, 38, 46, 56], 0, 180, fill='white', width=3)

        return image

    def _create_menu(self) -> 'pystray.Menu':
        """
        Create the tray menu.

        Returns:
            pystray Menu object
        """
        # pystray calls dynamic text callables with the menu item itself
        def get_status(item=None):
            return f"Status: {self._status}"

        def toggle_recording(icon, item):
            if self.is_recording:
                if self.on_stop_recording:
                    self.on_stop_recording()
            else:
                if self.on_start_recording:
                    self.on_start_recording()

        def get_record_text(item=None):
            return "Stop Recording" if self.is_recording else "Start Recording"

        def on_settings(icon, item):
            if self.on_settings:
                self.on_settings()

        def on_history(icon, item):
            if self.on_history:
                self.on_history()

        def on_about(icon, item):
            if self.on_about:
                self.on_about()
            else:
                self._show_about()

        def on_quit(icon, item):
            if self.on_quit:
                self.on_quit()
            icon.stop()

        return pystray.Menu(
            pystray.MenuItem(get_status, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(get_record_text, toggle_recording, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("History", on_history),
            pystray.MenuItem("Settings", on_settings),
            pystray.MenuItem("About", on_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        )

    def create(self) -> bool:
        """
        Create and display the tray icon.

        Returns:
            True if created successfully, False otherwise
        """
        if not PYSTRAY_AVAILABLE:
            print("pystray not available. Install with: pip install pystray pillow")
            return False

        try:
            self.icon = pystray.Icon(
                self.app_name.lower(),
                self._create_image(False),
                self.app_name,
                menu=self._create_menu()
            )
            return True

        except Exception as e:
            print(f"Error creating tray icon: {e}")
            return False

    def run(self) -> None:
        """Run the tray icon (blocking)."""
        if self.icon:
            self.icon.run()

    def run_detached(self) -> threading.Thread:
        """
        Run the tray icon in a separate thread.

        Returns:
            Thread object running the tray
        """
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread

    def set_recording_state(self, is_recording: bool) -> None:
        """
        Update the tray icon to reflect recording state.

        Args:
            is_recording: Whether recording is active
        """
        self.is_recording = is_recording
        self._status = "Recording" if is_recording else "Idle"

        if self.icon:
            self.icon.icon = self._create_image(is_recording)
            # Update menu to refresh text
            self.icon.update_menu()

    def set_status(self, status: str) -> None:
        """
        Set the status text.

        Args:
            status: Status text to display
        """
        self._status = status
        if self.icon:
            self.icon.update_menu()

    def _show_about(self) -> None:
        """Show about dialog using platform-appropriate method."""
        about_text = (
            f"{self.app_name} v1.0.0\n\n"
            "Audio transcription tool using Groq Whisper API.\n\n"
            "Developers:\n"
            "- Klaus Deor\n"
            "- Claude Code (Anthropic AI)\n\n"
            "https://github.com/klaus-deor/Transcripter"
        )

        if is_windows():
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, about_text, f"About {self.app_name}", 0x40)
            except Exception:
                print(about_text)
        elif is_macos():
            try:
                import subprocess
                subprocess.run([
                    'osascript', '-e',
                    f'display dialog "{about_text}" with title "About {self.app_name}" buttons {{"OK"}} default button "OK"'
                ])
            except Exception:
                print(about_text)
        else:
            print(about_text)

    def show_notification(self, title: str, message: str) -> None:
        """
        Show a desktop notification.

        Args:
            title: Notification title
            message: Notification message
        """
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception as e:
                print(f"Notification: {title} - {message}")

    def destroy(self) -> None:
        """Clean up and remove the tray icon."""
        if self.icon:
            self.icon.stop()
            self.icon = None


class CrossPlatformNotificationManager:
    """Cross-platform notification manager."""

    def __init__(self, app_name: str = "Transcripter"):
        """
        Initialize the notification manager.

        Args:
            app_name: Application name
        """
        self.app_name = app_name
        self.tray: Optional[CrossPlatformTray] = None

    def set_tray(self, tray: CrossPlatformTray) -> None:
        """Set the tray icon for notifications."""
        self.tray = tray

    def show(self, title: str, message: str, urgency: str = "normal") -> bool:
        """
        Show a notification.

        Args:
            title: Notification title
            message: Notification message
            urgency: Urgency level (unused in cross-platform)

        Returns:
            True if shown successfully
        """
        if self.tray:
            self.tray.show_notification(title, message)
            return True

        # Fallback to platform-specific notifications
        try:
            if is_windows():
                return self._show_windows_notification(title, message)
            elif is_macos():
                return self._show_macos_notification(title, message)
            else:
                return self._show_linux_notification(title, message)
        except Exception as e:
            print(f"Notification: {title} - {message}")
            return False

    def _show_windows_notification(self, title: str, message: str) -> bool:
        """Show Windows toast notification."""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
            return True
        except ImportError:
            # Fallback to basic message
            print(f"Notification: {title} - {message}")
            return False

    def _show_macos_notification(self, title: str, message: str) -> bool:
        """Show macOS notification."""
        try:
            import subprocess
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(['osascript', '-e', script], check=True)
            return True
        except Exception:
            print(f"Notification: {title} - {message}")
            return False

    def _show_linux_notification(self, title: str, message: str) -> bool:
        """Show Linux notification using notify-send."""
        try:
            import subprocess
            subprocess.run(['notify-send', title, message], check=True)
            return True
        except Exception:
            print(f"Notification: {title} - {message}")
            return False

    def show_recording_started(self) -> None:
        """Show notification for recording started."""
        self.show("Recording Started", "Audio recording in progress...")

    def show_recording_stopped(self) -> None:
        """Show notification for recording stopped."""
        self.show("Recording Stopped", "Processing audio...")

    def show_transcription_complete(self, text_preview: str = "") -> None:
        """Show notification for transcription complete."""
        message = "Text copied to clipboard"
        if text_preview:
            preview = text_preview[:50] + "..." if len(text_preview) > 50 else text_preview
            message = f"{message}\n{preview}"
        self.show("Transcription Complete", message)

    def show_error(self, error_message: str) -> None:
        """Show error notification."""
        self.show("Transcription Error", error_message)
