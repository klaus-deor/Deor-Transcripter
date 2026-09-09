"""Global hotkey management module."""

import threading
from typing import Callable, Optional, Dict
from pynput import keyboard


class HotkeyManager:
    """Manages global keyboard hotkeys."""

    # Left/right variants and synonyms collapse to a single canonical name
    KEY_ALIASES = {
        'ctrl': 'ctrl', 'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl', 'control': 'ctrl',
        'alt': 'alt', 'alt_l': 'alt', 'alt_r': 'alt', 'alt_gr': 'alt',
        'shift': 'shift', 'shift_l': 'shift', 'shift_r': 'shift',
        'cmd': 'super', 'cmd_l': 'super', 'cmd_r': 'super',
        'super': 'super', 'win': 'super',
        'escape': 'esc',
        'return': 'enter',
    }

    def __init__(self):
        """Initialize the hotkey manager."""
        self.listener: Optional[keyboard.Listener] = None
        self.hotkeys: Dict[str, Callable] = {}
        self.pressed_keys = set()
        self.is_running = False
        # Hotkeys currently held down, so auto-repeat doesn't re-trigger them
        self._active_hotkeys = set()

    def _canonical_key_name(self, key) -> str:
        """
        Convert a pynput key event to a canonical name (e.g. 'ctrl', 'r').

        While modifiers are held, Windows reports character keys without a
        usable `char` (vk only) or as a control character, so the virtual key
        code is the reliable source.
        """
        if isinstance(key, keyboard.Key):
            return self.KEY_ALIASES.get(key.name, key.name)

        char = getattr(key, 'char', None)
        if char and char.isprintable():
            return char.lower()

        vk = getattr(key, 'vk', None)
        if vk is not None:
            if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:  # 0-9, A-Z
                return chr(vk).lower()
            if 0x60 <= vk <= 0x69:  # numpad 0-9
                return chr(vk - 0x60 + ord('0'))

        if char and ord(char) < 32:  # control character, e.g. '\x12' for ctrl+r
            return chr(ord(char) + 64).lower()

        return str(key)

    def _canonical_hotkey(self, hotkey_str: str) -> set:
        """
        Convert a hotkey string (e.g. "ctrl+alt+r") to canonical key names.

        Args:
            hotkey_str: Hotkey string

        Returns:
            Set of canonical key names
        """
        names = set()
        for part in hotkey_str.lower().split('+'):
            part = part.strip()
            if part:
                names.add(self.KEY_ALIASES.get(part, part))
        return names

    def _normalize_key(self, key_str: str) -> set:
        """
        Normalize a hotkey string to a set of keys.

        Args:
            key_str: Hotkey string (e.g., "ctrl+alt+r")

        Returns:
            Set of normalized key names
        """
        parts = key_str.lower().split('+')
        normalized = set()

        for part in parts:
            part = part.strip()

            # Map common key names
            key_map = {
                'ctrl': keyboard.Key.ctrl_l,
                'control': keyboard.Key.ctrl_l,
                'alt': keyboard.Key.alt_l,
                'shift': keyboard.Key.shift_l,
                'super': keyboard.Key.cmd,
                'win': keyboard.Key.cmd,
                'cmd': keyboard.Key.cmd,
            }

            if part in key_map:
                normalized.add(key_map[part])
            else:
                # Regular character key
                try:
                    normalized.add(keyboard.KeyCode.from_char(part))
                except:
                    # Try as a special key
                    try:
                        normalized.add(getattr(keyboard.Key, part))
                    except:
                        print(f"Warning: Unknown key '{part}'")

        return normalized

    def _key_to_string(self, key) -> str:
        """
        Convert a key object to string representation.

        Args:
            key: Key object

        Returns:
            String representation of the key
        """
        if isinstance(key, keyboard.KeyCode):
            return key.char if key.char else str(key)
        elif isinstance(key, keyboard.Key):
            return key.name
        else:
            return str(key)

    def _on_press(self, key):
        """
        Handle key press events.

        Args:
            key: The key that was pressed
        """
        try:
            self.pressed_keys.add(key)
            self._check_hotkeys()
        except Exception as e:
            print(f"Error in key press handler: {e}")

    def _on_release(self, key):
        """
        Handle key release events.

        Args:
            key: The key that was released
        """
        try:
            if key in self.pressed_keys:
                self.pressed_keys.remove(key)
            # Refresh state only: releasing a key must never fire a hotkey, or
            # letting go of shift in ctrl+alt+shift+r would trigger ctrl+alt+r
            self._check_hotkeys(trigger=False)
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def _check_hotkeys(self, trigger: bool = True):
        """
        Check if any registered hotkeys match the currently pressed keys.

        Args:
            trigger: Whether a newly matched hotkey should fire its callback
        """
        pressed = {self._canonical_key_name(k) for k in self.pressed_keys}

        still_active = set()
        for hotkey_str, callback in list(self.hotkeys.items()):
            expected = self._canonical_hotkey(hotkey_str)

            # Exact match: every expected key is down and nothing else is
            if not expected or expected != pressed:
                continue

            still_active.add(hotkey_str)

            # Only fire on the transition, so key auto-repeat doesn't
            # trigger the callback over and over while the keys are held
            if trigger and hotkey_str not in self._active_hotkeys:
                try:
                    callback()
                except Exception as e:
                    print(f"Error executing hotkey callback: {e}")

        self._active_hotkeys = still_active

    def register_hotkey(self, hotkey: str, callback: Callable) -> bool:
        """
        Register a global hotkey.

        Args:
            hotkey: Hotkey string (e.g., "ctrl+alt+r")
            callback: Function to call when hotkey is pressed

        Returns:
            True if registration successful, False otherwise
        """
        try:
            # Validate the hotkey format
            normalized = self._normalize_key(hotkey)
            if not normalized:
                print(f"Invalid hotkey format: {hotkey}")
                return False

            self.hotkeys[hotkey] = callback
            print(f"Registered hotkey: {hotkey}")
            return True

        except Exception as e:
            print(f"Error registering hotkey: {e}")
            return False

    def unregister_hotkey(self, hotkey: str) -> bool:
        """
        Unregister a global hotkey.

        Args:
            hotkey: Hotkey string to unregister

        Returns:
            True if unregistration successful, False otherwise
        """
        if hotkey in self.hotkeys:
            del self.hotkeys[hotkey]
            print(f"Unregistered hotkey: {hotkey}")
            return True
        else:
            print(f"Hotkey not found: {hotkey}")
            return False

    def unregister_all(self) -> None:
        """Unregister all hotkeys."""
        self.hotkeys.clear()
        self._active_hotkeys.clear()
        print("All hotkeys unregistered")

    def start(self) -> bool:
        """
        Start listening for hotkeys.

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            print("Hotkey listener already running")
            return False

        try:
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self.listener.start()
            self.is_running = True
            print("Hotkey listener started")
            return True

        except Exception as e:
            print(f"Error starting hotkey listener: {e}")
            return False

    def stop(self) -> None:
        """Stop listening for hotkeys."""
        if self.listener:
            self.listener.stop()
            self.listener = None
            self.is_running = False
            self.pressed_keys.clear()
            self._active_hotkeys.clear()
            print("Hotkey listener stopped")

    def is_hotkey_pressed(self, hotkey: str) -> bool:
        """
        Check if a specific hotkey is currently pressed.

        Args:
            hotkey: Hotkey string to check

        Returns:
            True if hotkey is pressed, False otherwise
        """
        expected = self._canonical_hotkey(hotkey)
        pressed = {self._canonical_key_name(k) for k in self.pressed_keys}
        return bool(expected) and expected.issubset(pressed)


class HotkeyValidator:
    """Validates and normalizes hotkey strings."""

    VALID_MODIFIERS = ['ctrl', 'control', 'alt', 'shift', 'super', 'win', 'cmd']
    VALID_SPECIAL_KEYS = [
        'space', 'enter', 'tab', 'backspace', 'delete', 'esc', 'escape',
        'up', 'down', 'left', 'right',
        'home', 'end', 'page_up', 'page_down',
        'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12'
    ]

    @staticmethod
    def validate(hotkey: str) -> tuple[bool, str]:
        """
        Validate a hotkey string.

        Args:
            hotkey: Hotkey string to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not hotkey or not isinstance(hotkey, str):
            return False, "Hotkey must be a non-empty string"

        parts = [p.strip().lower() for p in hotkey.split('+')]

        if len(parts) < 1:
            return False, "Hotkey must contain at least one key"

        # Check for valid modifiers and keys
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)

            if part in HotkeyValidator.VALID_MODIFIERS:
                if is_last:
                    return False, "Hotkey must end with a regular key, not a modifier"
                continue

            if part in HotkeyValidator.VALID_SPECIAL_KEYS:
                continue

            # Check if it's a single character
            if len(part) == 1 and part.isalnum():
                continue

            return False, f"Invalid key: '{part}'"

        return True, ""

    @staticmethod
    def normalize(hotkey: str) -> str:
        """
        Normalize a hotkey string to a consistent format.

        Args:
            hotkey: Hotkey string to normalize

        Returns:
            Normalized hotkey string
        """
        parts = [p.strip().lower() for p in hotkey.split('+')]
        return '+'.join(parts)

    @staticmethod
    def format_for_display(hotkey: str) -> str:
        """
        Format a hotkey string for display to users.

        Args:
            hotkey: Hotkey string

        Returns:
            Formatted hotkey string
        """
        parts = [p.strip().capitalize() for p in hotkey.split('+')]
        return ' + '.join(parts)
