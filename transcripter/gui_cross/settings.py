"""Cross-platform Settings window using tkinter."""

import traceback
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from ..config import ConfigManager
from ..audio import AudioRecorder
from ..hotkeys import HotkeyValidator
from ..providers import ProviderType, ProviderRegistry
from ..platform_utils import is_wayland


# Provider display names and info URLs
PROVIDER_INFO = {
    ProviderType.GROQ: {
        "name": "Groq",
        "url": "console.groq.com",
        "key_label": "API Key",
        "key_placeholder": "Enter your Groq API key",
    },
    ProviderType.OPENAI: {
        "name": "OpenAI",
        "url": "platform.openai.com/api-keys",
        "key_label": "API Key",
        "key_placeholder": "Enter your OpenAI API key",
    },
    ProviderType.GOOGLE_CLOUD: {
        "name": "Google Cloud",
        "url": "console.cloud.google.com",
        "key_label": "Credentials File Path",
        "key_placeholder": "Path to service account JSON file",
    },
    ProviderType.ASSEMBLYAI: {
        "name": "AssemblyAI",
        "url": "assemblyai.com/app/account",
        "key_label": "API Key",
        "key_placeholder": "Enter your AssemblyAI API key",
    },
    ProviderType.DEEPGRAM: {
        "name": "Deepgram",
        "url": "console.deepgram.com",
        "key_label": "API Key",
        "key_placeholder": "Enter your Deepgram API key",
    },
}


class SettingsWindow:
    """Cross-platform settings window using tkinter."""

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the settings window.

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.window: Optional[tk.Toplevel] = None
        self.on_settings_changed: Optional[Callable] = None

        # Variables for widgets
        self.api_key_var: Optional[tk.StringVar] = None
        self.language_var: Optional[tk.StringVar] = None
        self.model_var: Optional[tk.StringVar] = None
        self.device_var: Optional[tk.StringVar] = None
        self.hotkey_var: Optional[tk.StringVar] = None
        self.toggle_mode_var: Optional[tk.BooleanVar] = None
        self.notifications_var: Optional[tk.BooleanVar] = None
        self.autostart_var: Optional[tk.BooleanVar] = None
        self.history_var: Optional[tk.BooleanVar] = None
        self.max_history_var: Optional[tk.IntVar] = None

        # Transcription provider variables
        self.provider_var: Optional[tk.StringVar] = None
        self.fallback_var: Optional[tk.StringVar] = None

        # Display name <-> internal id maps (filled while building the tabs)
        self._language_map: dict = {}
        self._language_map_reverse: dict = {}
        self._provider_map: dict = {}
        self._provider_map_reverse: dict = {}
        self._fallback_map: dict = {}
        self._fallback_map_reverse: dict = {}
        self._model_map: dict = {}
        self._model_map_reverse: dict = {}

        # Widgets that need to be updated dynamically
        self.api_key_entry: Optional[ttk.Entry] = None
        self.api_key_label: Optional[ttk.Label] = None
        self.api_key_info_label: Optional[ttk.Label] = None
        self.model_combo: Optional[ttk.Combobox] = None
        self.show_key_btn: Optional[ttk.Button] = None

    def show(self) -> None:
        """Show the settings window."""
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return

        try:
            self._create_window()
            self._load_settings()
        except Exception as e:
            # Never leave a half-built (blank) window on screen: report and clean up
            traceback.print_exc()
            if self.window is not None:
                try:
                    self.window.destroy()
                except Exception:
                    pass
                self.window = None
            messagebox.showerror(
                "Error Opening Settings",
                f"{type(e).__name__}: {e}"
            )

    def _create_window(self) -> None:
        """Create the settings window and its widgets."""
        width, height = 600, 500

        self.window = tk.Toplevel()
        self.window.title("Transcripter Settings")
        self.window.resizable(True, True)
        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Center the window
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

        # Initialize variables
        self.api_key_var = tk.StringVar()
        self.language_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.device_var = tk.StringVar()
        self.hotkey_var = tk.StringVar()
        self.toggle_mode_var = tk.BooleanVar()
        self.notifications_var = tk.BooleanVar()
        self.autostart_var = tk.BooleanVar()
        self.history_var = tk.BooleanVar()
        self.max_history_var = tk.IntVar(value=50)
        self.provider_var = tk.StringVar()
        self.fallback_var = tk.StringVar()

        # Create notebook for tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Create tabs (each tab frame must be a child of the notebook)
        notebook.add(self._create_general_tab(notebook), text="General")
        notebook.add(self._create_audio_tab(notebook), text="Audio")
        notebook.add(self._create_transcription_tab(notebook), text="Transcription")
        notebook.add(self._create_hotkeys_tab(notebook), text="Hotkeys")
        notebook.add(self._create_history_tab(notebook), text="History")

        # Button frame
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill='x', padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Save", command=self._on_save).pack(side='right', padx=5)

        self.window.lift()
        self.window.focus_force()

    def _create_general_tab(self, parent: tk.Misc) -> ttk.Frame:
        """Create the general settings tab."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(1, weight=1)

        row = 0

        # Notifications
        ttk.Checkbutton(
            frame, text="Show notifications",
            variable=self.notifications_var
        ).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1

        # Autostart
        ttk.Checkbutton(
            frame, text="Start on system login",
            variable=self.autostart_var
        ).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1

        # Language
        ttk.Label(frame, text="Transcription language:").grid(
            row=row, column=0, sticky='w', padx=10, pady=5
        )

        languages = [
            ("Auto-detect", "auto"),
            ("English", "en"),
            ("Portuguese", "pt"),
            ("Spanish", "es"),
            ("French", "fr"),
            ("German", "de"),
            ("Italian", "it"),
            ("Japanese", "ja"),
            ("Korean", "ko"),
            ("Chinese", "zh"),
        ]

        language_combo = ttk.Combobox(
            frame, textvariable=self.language_var,
            values=[lang[0] for lang in languages],
            state='readonly'
        )
        language_combo.grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        self._language_map = {lang[0]: lang[1] for lang in languages}
        self._language_map_reverse = {lang[1]: lang[0] for lang in languages}

        return frame

    def _create_audio_tab(self, parent: tk.Misc) -> ttk.Frame:
        """Create the audio settings tab."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(1, weight=1)

        row = 0

        # Device selection
        ttk.Label(frame, text="Microphone:").grid(
            row=row, column=0, sticky='w', padx=10, pady=5
        )

        devices = ["System Default"]
        try:
            audio_devices = AudioRecorder.list_devices()
            devices.extend([d.name for d in audio_devices])
        except Exception as e:
            print(f"Error listing audio devices: {e}")

        device_combo = ttk.Combobox(
            frame, textvariable=self.device_var,
            values=devices,
            state='readonly'
        )
        device_combo.grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        row += 1

        # Info label
        info_text = "Sample rate: 16000 Hz (optimized for speech)\nFormat: Mono WAV"
        ttk.Label(frame, text=info_text, foreground='gray').grid(
            row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5
        )

        return frame

    def _create_transcription_tab(self, parent: tk.Misc) -> ttk.Frame:
        """Create the transcription settings tab with provider selection."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(1, weight=1)

        row = 0

        # Provider selection
        ttk.Label(frame, text="Transcription Provider:").grid(
            row=row, column=0, sticky='w', padx=10, pady=5
        )

        providers = []
        self._provider_map = {}
        self._provider_map_reverse = {}
        for provider_type in ProviderType:
            info = PROVIDER_INFO.get(provider_type, {})
            name = info.get("name", provider_type.value)
            installed = ProviderRegistry.is_provider_available(provider_type)
            label = f"{name}" if installed else f"{name} (SDK not installed)"
            providers.append(label)
            self._provider_map[label] = provider_type.value
            self._provider_map_reverse[provider_type.value] = label

        provider_combo = ttk.Combobox(
            frame, textvariable=self.provider_var,
            values=providers,
            state='readonly'
        )
        provider_combo.grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        provider_combo.bind('<<ComboboxSelected>>', self._on_provider_changed)
        row += 1

        # Separator
        ttk.Separator(frame, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=10
        )
        row += 1

        # API Key label
        self.api_key_label = ttk.Label(frame, text="API Key:")
        self.api_key_label.grid(row=row, column=0, sticky='w', padx=10, pady=5)
        row += 1

        # API Key entry frame
        api_frame = ttk.Frame(frame)
        api_frame.grid(row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=5)
        api_frame.columnconfigure(0, weight=1)

        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, show='*')
        self.api_key_entry.grid(row=0, column=0, sticky='ew')

        self.show_key_btn = ttk.Button(api_frame, text="Show", command=self._toggle_api_key_visibility)
        self.show_key_btn.grid(row=0, column=1, padx=(5, 0))
        row += 1

        # Info about getting API key
        self.api_key_info_label = ttk.Label(
            frame,
            text="Get your API key at: console.groq.com",
            foreground='blue',
            cursor='hand2'
        )
        self.api_key_info_label.grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1

        # Separator
        ttk.Separator(frame, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=10
        )
        row += 1

        # Model selection
        ttk.Label(frame, text="Model:").grid(
            row=row, column=0, sticky='w', padx=10, pady=5
        )

        self.model_combo = ttk.Combobox(
            frame, textvariable=self.model_var,
            state='readonly'
        )
        self.model_combo.grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        row += 1

        # Separator
        ttk.Separator(frame, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=10
        )
        row += 1

        # Fallback provider selection
        ttk.Label(frame, text="Fallback Provider:").grid(
            row=row, column=0, sticky='w', padx=10, pady=5
        )

        fallback_options = ["None (Disabled)"]
        self._fallback_map = {"None (Disabled)": ""}
        self._fallback_map_reverse = {"": "None (Disabled)"}
        for provider_type in ProviderType:
            info = PROVIDER_INFO.get(provider_type, {})
            name = info.get("name", provider_type.value)
            fallback_options.append(name)
            self._fallback_map[name] = provider_type.value
            self._fallback_map_reverse[provider_type.value] = name

        fallback_combo = ttk.Combobox(
            frame, textvariable=self.fallback_var,
            values=fallback_options,
            state='readonly'
        )
        fallback_combo.grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        row += 1

        # Fallback info
        ttk.Label(
            frame,
            text="Fallback provider is used when the primary provider fails.",
            foreground='gray'
        ).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)

        return frame

    def _on_provider_changed(self, event=None) -> None:
        """Handle provider selection change."""
        provider_display = self.provider_var.get()
        provider_id = self._provider_map.get(provider_display)
        if not provider_id:
            return

        try:
            provider_type = ProviderType(provider_id)
        except ValueError:
            return

        info = PROVIDER_INFO.get(provider_type, {})

        # Update API key label
        key_label = info.get("key_label", "API Key")
        self.api_key_label.config(text=f"{key_label}:")

        # Update info URL
        url = info.get("url", "")
        self.api_key_info_label.config(text=f"Get your credentials at: {url}")

        # Load API key for this provider
        api_key = self.config_manager.get_api_key(provider_type)
        self.api_key_var.set(api_key if api_key else "")

        # Update model combo
        self._update_model_combo(provider_type)

    def _update_model_combo(self, provider_type: ProviderType) -> None:
        """Update the model combo based on provider."""
        models = self._get_provider_models(provider_type)

        # Update model map
        self._model_map = {m["name"]: m["id"] for m in models}
        self._model_map_reverse = {m["id"]: m["name"] for m in models}

        # Update combo values
        model_names = [m["name"] for m in models]
        self.model_combo.config(values=model_names)

        # Set active model from config
        try:
            provider_config = self.config_manager.get_provider_config(provider_type)
            if hasattr(provider_config, 'model'):
                model_display = self._model_map_reverse.get(provider_config.model)
                if model_display:
                    self.model_var.set(model_display)
                elif model_names:
                    self.model_var.set(model_names[0])
            elif model_names:
                self.model_var.set(model_names[0])
        except Exception:
            if model_names:
                self.model_var.set(model_names[0])

    def _get_provider_models(self, provider_type: ProviderType) -> list[dict]:
        """Get models for a provider without requiring API key."""
        models = {
            ProviderType.GROQ: [
                {"id": "whisper-large-v3-turbo", "name": "Whisper Large V3 Turbo (Recommended)"},
                {"id": "whisper-large-v3", "name": "Whisper Large V3"},
            ],
            ProviderType.OPENAI: [
                {"id": "whisper-1", "name": "Whisper-1"},
            ],
            ProviderType.GOOGLE_CLOUD: [
                {"id": "chirp_2", "name": "Chirp 2 (Recommended)"},
                {"id": "chirp", "name": "Chirp"},
                {"id": "default", "name": "Default"},
            ],
            ProviderType.ASSEMBLYAI: [
                {"id": "best", "name": "Best (Highest accuracy)"},
                {"id": "nano", "name": "Nano (Faster, lower cost)"},
            ],
            ProviderType.DEEPGRAM: [
                {"id": "nova-2", "name": "Nova-2 (Recommended)"},
                {"id": "nova", "name": "Nova"},
                {"id": "whisper-large", "name": "Whisper Large"},
                {"id": "whisper-medium", "name": "Whisper Medium"},
                {"id": "whisper-small", "name": "Whisper Small"},
            ],
        }
        return models.get(provider_type, [])

    def _create_hotkeys_tab(self, parent: tk.Misc) -> ttk.Frame:
        """Create the hotkeys settings tab."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(1, weight=1)

        row = 0

        # Wayland warning
        if is_wayland():
            warning_frame = ttk.Frame(frame)
            warning_frame.grid(row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=10)

            # Warning box with yellow/orange background
            warning_label = tk.Label(
                warning_frame,
                text=(
                    "Wayland Detected - Hotkeys Limited\n\n"
                    "Wayland blocks global hotkeys for security.\n"
                    "Configure a system shortcut instead:\n\n"
                    "Settings > Keyboard > Custom Shortcuts\n"
                    "Command: toggle_recording.sh\n\n"
                    "See WAYLAND_FIX.md for details."
                ),
                bg='#FFF3CD',
                fg='#856404',
                relief='solid',
                borderwidth=1,
                padx=15,
                pady=10,
                justify='left',
                anchor='w'
            )
            warning_label.pack(fill='x', expand=True)
            row += 1

        # Hotkey entry
        ttk.Label(frame, text="Recording Hotkey:").grid(
            row=row, column=0, sticky='w', padx=10, pady=5
        )

        ttk.Entry(frame, textvariable=self.hotkey_var).grid(
            row=row, column=1, sticky='ew', padx=10, pady=5
        )
        row += 1

        # Toggle mode
        ttk.Checkbutton(
            frame,
            text="Toggle mode (same key starts and stops recording)",
            variable=self.toggle_mode_var
        ).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1

        # Info
        info_text = (
            "Format: modifier+key (e.g., ctrl+alt+r)\n"
            "Valid modifiers: ctrl, alt, shift, super/cmd\n"
            "Valid keys: a-z, 0-9, F1-F12, space, etc."
        )
        ttk.Label(frame, text=info_text, foreground='gray').grid(
            row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5
        )

        return frame

    def _create_history_tab(self, parent: tk.Misc) -> ttk.Frame:
        """Create the history settings tab."""
        frame = ttk.Frame(parent)
        frame.columnconfigure(1, weight=1)

        row = 0

        # Enable history
        ttk.Checkbutton(
            frame,
            text="Keep transcription history",
            variable=self.history_var
        ).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1

        # Max history items
        ttk.Label(frame, text="Maximum history items:").grid(
            row=row, column=0, sticky='w', padx=10, pady=5
        )

        spinbox = ttk.Spinbox(
            frame, from_=10, to=500, increment=10,
            textvariable=self.max_history_var, width=10
        )
        spinbox.grid(row=row, column=1, sticky='w', padx=10, pady=5)

        return frame

    def _load_settings(self) -> None:
        """Load current settings into the widgets."""
        config = self.config_manager.config

        # General
        self.notifications_var.set(config.general.show_notifications)
        self.autostart_var.set(config.general.autostart)

        lang = config.general.language if config.general.language else "auto"
        lang_display = self._language_map_reverse.get(lang, "Auto-detect")
        self.language_var.set(lang_display)

        # Audio
        device = config.audio.device_name if config.audio.device_name else "System Default"
        self.device_var.set(device)

        # Transcription provider
        active_provider = config.transcription.active_provider
        provider_display = self._provider_map_reverse.get(active_provider, "Groq")
        self.provider_var.set(provider_display)

        # Trigger provider change to load provider-specific settings
        self._on_provider_changed()

        # Fallback provider
        fallback = config.transcription.fallback_provider
        fallback_display = self._fallback_map_reverse.get(fallback, "None (Disabled)")
        self.fallback_var.set(fallback_display)

        # Hotkeys
        self.hotkey_var.set(config.hotkeys.start_recording)
        self.toggle_mode_var.set(config.hotkeys.toggle_mode)

        # History
        self.history_var.set(config.history.enabled)
        self.max_history_var.set(config.history.max_items)

    def _toggle_api_key_visibility(self) -> None:
        """Toggle API key visibility."""
        if self.api_key_entry.cget('show') == '*':
            self.api_key_entry.config(show='')
            self.show_key_btn.config(text='Hide')
        else:
            self.api_key_entry.config(show='*')
            self.show_key_btn.config(text='Show')

    def _on_save(self) -> None:
        """Handle save button click."""
        try:
            # Validate hotkey
            hotkey = self.hotkey_var.get().strip()
            is_valid, error_msg = HotkeyValidator.validate(hotkey)
            if not is_valid:
                messagebox.showerror("Invalid Hotkey", error_msg)
                return

            # Save settings
            config = self.config_manager.config

            # General
            config.general.show_notifications = self.notifications_var.get()
            config.general.autostart = self.autostart_var.get()
            lang_display = self.language_var.get()
            lang = self._language_map.get(lang_display, "auto")
            config.general.language = "" if lang == "auto" else lang

            # Audio
            device = self.device_var.get()
            config.audio.device_name = "" if device == "System Default" else device

            # Transcription provider
            provider_display = self.provider_var.get()
            provider_id = self._provider_map.get(provider_display)
            if provider_id:
                config.transcription.active_provider = provider_id

                # Save API key for this provider
                api_key = self.api_key_var.get().strip()
                if api_key:
                    try:
                        provider_type = ProviderType(provider_id)
                        self.config_manager.set_api_key(api_key, provider_type)
                    except ValueError:
                        pass

                # Save model
                model_display = self.model_var.get()
                model_id = self._model_map.get(model_display)
                if model_id:
                    try:
                        provider_type = ProviderType(provider_id)
                        self.config_manager.update_provider_config(provider_type, model=model_id)
                    except ValueError:
                        pass

            # Fallback provider
            fallback_display = self.fallback_var.get()
            fallback_id = self._fallback_map.get(fallback_display, "")
            config.transcription.fallback_provider = fallback_id

            # Hotkeys
            config.hotkeys.start_recording = HotkeyValidator.normalize(hotkey)
            config.hotkeys.stop_recording = config.hotkeys.start_recording
            config.hotkeys.toggle_mode = self.toggle_mode_var.get()

            # History
            config.history.enabled = self.history_var.get()
            config.history.max_items = self.max_history_var.get()

            # Save to file
            self.config_manager.save_config(config)

            # Notify callback
            if self.on_settings_changed:
                self.on_settings_changed()

            # Close window
            self.window.destroy()
            self.window = None

        except Exception as e:
            messagebox.showerror("Error Saving Settings", str(e))

    def _on_cancel(self) -> None:
        """Handle cancel button click."""
        self.window.destroy()
        self.window = None
