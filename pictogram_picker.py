import customtkinter as ctk
from tkinter import messagebox, filedialog
import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from fuzzywuzzy import fuzz
import os
import shutil
import cairosvg
import threading
from queue import Queue
from dotenv import load_dotenv
import ast
import time
import platform
import json
import platform  # Make sure this is at the top of your file
import json  # And this one too

# --- UI Sizing Constants ---
UI_SCALE = 1.25
FONT_SIZE_NORMAL = 13
FONT_SIZE_LARGE = 16
FONT_SIZE_TITLE = 24
PADDING_SMALL = 5
PADDING_NORMAL = 10
PADDING_LARGE = 20
ENTRY_WIDTH = 250
COMBOBOX_WIDTH = 140
BUTTON_IPAD = 10

# --- Configuration ---
load_dotenv()
FLATICON_API_KEY = str(os.getenv("FREEPIK_API_KEY"))
ARASAAC_API_URL = "https://api.arasaac.org/api/pictograms/en/search/"
FLATICON_API_URLS = {
    "search": "https://api.freepik.com/v1/icons",
    "download": "https://api.freepik.com/v1/icons/{id}/download",
}
SELECTED_SYMBOLS_DIR = "selected-symbols"
ARASAAC_CACHE_DIR = "arasaac_symbols"
MAX_GRID_COLUMNS = 4


class FormatSelectionDialog(ctk.CTkToplevel):
    """A dialog to ask the user which CSV format to use."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Select Format")
        self.lift()
        self.attributes("-topmost", True)
        self.grab_set()
        self.geometry("350x150")
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.result = None

        self.label = ctk.CTkLabel(self, text="Please select the CSV format to use:")
        self.label.pack(padx=20, pady=20)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=10)

        self.legacy_button = ctk.CTkButton(
            button_frame, text="Legacy Esperanto", command=self.on_legacy
        )
        self.legacy_button.pack(side="left", padx=10)

        self.new_button = ctk.CTkButton(
            button_frame, text="New English Diversity", command=self.on_new
        )
        self.new_button.pack(side="left", padx=10)

    def on_legacy(self):
        self.result = "legacy"
        self.destroy()

    def on_new(self):
        self.result = "new"
        self.destroy()

    def _on_closing(self):
        self.result = None
        self.destroy()

    def get_choice(self):
        self.master.wait_window(self)
        return self.result


class TextSymbolDialog(ctk.CTkToplevel):
    """A dialog to preview and adjust a text-based symbol before saving."""

    def __init__(self, master, text_to_render, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.title("Create Text Symbol")
        self.lift()
        self.attributes("-topmost", True)
        self.grab_set()
        self.geometry("600x750")
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.text_to_render = text_to_render
        self.result = None
        self.img_size = 512

        self.font_map = self._get_system_fonts()
        self.font_names = list(self.font_map.keys())
        if not self.font_names:
            messagebox.showwarning(
                "Font Not Found",
                "Could not find any system fonts. Text rendering may fall back to a default font.",
            )
            self.font_names = ["Default"]
            self.font_map = {"Default": None}

        # --- Main Frame ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(expand=True, fill="both", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # --- Image Preview ---
        self.image_label = ctk.CTkLabel(self.main_frame, text="")
        self.image_label.grid(row=0, column=0, pady=10, sticky="nsew")

        # --- Controls ---
        controls_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        controls_frame.grid(row=1, column=0, pady=10)
        controls_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(controls_frame, text="Font:").grid(row=0, column=0, padx=5, pady=5)
        self.font_selector = ctk.CTkComboBox(
            controls_frame,
            values=self.font_names,
            command=self.update_preview,
            width=400,
        )

        preferred_fonts = [
            "Noto Color Emoji",  # Best for Linux emoji
            "Noto Sans Symbols",  # Best for Linux symbols
            "Segoe UI Emoji",  # Best for Windows
            "Apple Color Emoji",  # Best for macOS
            "Arial Unicode MS",
            "DejaVu Sans",
        ]

        default_font = self.font_names[0]
        for font_name in preferred_fonts:
            matching_fonts = [
                f for f in self.font_names if font_name.lower() in f.lower()
            ]
            if matching_fonts:
                default_font = matching_fonts[0]
                print(f"Found preferred font for text symbols: {default_font}")
                break

        self.font_selector.set(default_font)
        self.font_selector.grid(
            row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew"
        )

        ctk.CTkLabel(controls_frame, text="Font Size:").grid(
            row=1, column=0, padx=5, pady=5
        )
        self.font_size_var = ctk.IntVar(value=250)
        self.font_size_slider = ctk.CTkSlider(
            controls_frame,
            from_=10,
            to=500,
            variable=self.font_size_var,
            command=self.update_preview,
        )
        self.font_size_slider.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.font_size_label = ctk.CTkLabel(
            controls_frame, textvariable=self.font_size_var, width=35
        )
        self.font_size_label.grid(row=1, column=2, padx=5, pady=5)

        # --- Buttons ---
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=10)

        self.save_button = ctk.CTkButton(
            button_frame, text="Save Symbol", command=self.on_save
        )
        self.save_button.pack(side="left", padx=10)

        self.cancel_button = ctk.CTkButton(
            button_frame, text="Cancel", command=self._on_cancel, fg_color="gray50"
        )
        self.cancel_button.pack(side="left", padx=10)

        self.update_preview()

    def _get_system_fonts(self):
        """Scans for system fonts and returns a curated list."""
        print("Scanning for system fonts...")
        full_font_map = {}
        try:
            from matplotlib.font_manager import findSystemFonts, get_font

            font_paths = findSystemFonts()
            for font_path in font_paths:
                try:
                    font = get_font(font_path)
                    display_name = font.family_name

                    style = font.style_name
                    if style.lower() not in ["regular", "normal", "book"]:
                        display_name = f"{display_name} {style}"

                    if display_name not in full_font_map:
                        full_font_map[display_name] = font_path
                except Exception:
                    continue
            print(f"Found {len(full_font_map)} total unique font families.")
        except ImportError:
            messagebox.showwarning(
                "Matplotlib not found",
                "Please install matplotlib (`pip install matplotlib`) for the best font support.",
            )
            return self._get_system_fonts_fallback()

        # --- NEW: Logic to limit the number of fonts in the dropdown ---

        # 1. Prioritize essential fonts for Unicode/emoji
        preferred_map = {}
        preferred_names = [
            "Noto Color Emoji",
            "Noto Sans Symbols",
            "Segoe UI Emoji",
            "Apple Color Emoji",
        ]
        for name, path in full_font_map.items():
            for pref_name in preferred_names:
                if pref_name.lower() in name.lower():
                    preferred_map[name] = path

        # 2. Get the rest of the fonts, sorted alphabetically
        remaining_map = {
            name: path
            for name, path in full_font_map.items()
            if name not in preferred_map
        }
        sorted_remaining = sorted(remaining_map.items())

        # 3. Combine them, ensuring preferred are first, and limit the total
        final_font_map = dict(preferred_map)
        limit = 20 - len(final_font_map)
        for name, path in sorted_remaining[:limit]:
            final_font_map[name] = path

        print(f"Limiting dropdown to {len(final_font_map)} fonts.")
        return dict(sorted(final_font_map.items()))

    def _get_system_fonts_fallback(self):
        font_map = {}
        system = platform.system()
        if system == "Windows":
            font_dirs = [
                os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts")
            ]
        elif system == "Darwin":
            font_dirs = [
                "/System/Library/Fonts",
                "/Library/Fonts",
                os.path.expanduser("~/Library/Fonts"),
            ]
        else:  # Linux
            font_dirs = [
                "/usr/share/fonts",
                "/usr/local/share/fonts",
                os.path.expanduser("~/.fonts"),
            ]

        for font_dir in font_dirs:
            if os.path.isdir(font_dir):
                for filename in os.listdir(font_dir):
                    if filename.lower().endswith((".ttf", ".otf")):
                        font_path = os.path.join(font_dir, filename)
                        try:
                            font = ImageFont.truetype(font_path, 10)
                            name, style = font.getname()
                            display_name = (
                                f"{name} {style}"
                                if style.lower() not in ["regular", "normal", "book"]
                                else name
                            )
                            if display_name not in font_map:
                                font_map[display_name] = font_path
                        except Exception:
                            continue
        return dict(sorted(font_map.items()))

    def update_preview(self, *args):
        font_size = self.font_size_var.get()
        selected_font_name = self.font_selector.get()
        font_path = self.font_map.get(selected_font_name)

        image = Image.new("RGBA", (self.img_size, self.img_size), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)

        font = None
        try:
            if font_path:
                font = ImageFont.truetype(
                    font_path, font_size, layout_engine=ImageFont.Layout.RAQM
                )
            else:
                font = ImageFont.load_default()
        except IOError:
            font = ImageFont.load_default()
        except ImportError:
            font = ImageFont.truetype(font_path, font_size)

        bbox = draw.textbbox((0, 0), self.text_to_render, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (self.img_size - text_width) / 2
        y = (self.img_size - text_height) / 2
        draw.text(
            (x - bbox[0], y - bbox[1]), self.text_to_render, fill="black", font=font
        )

        self.final_image = image
        ctk_image = ctk.CTkImage(light_image=image, size=(self.img_size, self.img_size))
        self.image_label.configure(image=ctk_image)

    def on_save(self):
        self.result = self.final_image
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def get_result(self):
        self.master.wait_window(self)
        return self.result


class SymbolPickerApp:
    """The main application controller."""

    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Symbol Picker")
        self.root.attributes("-zoomed", True)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # --- Ask for CSV Format at Startup ---
        dialog = FormatSelectionDialog(self.root)
        choice = dialog.get_choice()

        if choice == "legacy":
            csv_path = (
                "Gabe_Esperanto cards_filtered_cleaned_no_starters_no_jn_rerank.csv"
            )
        elif choice == "new":
            csv_path = "en_word_diversity_ranking.csv"
        else:
            self.root.destroy()  # Exit if no choice is made
            return

        try:
            self.base_vocab_df = pd.read_csv(csv_path)
            # User confirmed they changed their CSV manually to have the 'english' column
        except FileNotFoundError as e:
            messagebox.showerror("Error", f"Could not find required file: {e.filename}")
            self.root.destroy()
            return

        # --- Header Frame for Persistent Buttons ---
        self.header_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.header_frame.grid_columnconfigure(1, weight=1)

        self.home_button = ctk.CTkButton(
            self.header_frame, text="Go to Home", command=self.go_home_from_picker
        )

        button_height = int(30 * UI_SCALE)
        self.theme_button = ctk.CTkButton(
            self.header_frame,
            text="Switch to Light",
            command=self.toggle_theme,
            height=button_height,
        )
        self.theme_button.grid(row=0, column=2, sticky="e")
        self.update_theme_button_text()

        # --- Page Container Frame ---
        self.container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.start_page = StartPage(self.container, self)
        self.symbol_picker_page = None
        self.show_start_page()

    def go_home_from_picker(self):
        """Handle the logic for returning to the home screen from the picker."""
        if self.symbol_picker_page is None:
            return

        is_autosave_on = self.symbol_picker_page.autosave_var.get()

        if is_autosave_on:
            filename = os.path.basename(self.symbol_picker_page.output_filename)
            self.show_start_page()
            messagebox.showinfo(
                "Autosaved", f"Progress automatically saved to\n{filename}"
            )
        else:
            user_choice = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes. Would you like to save before returning to the home screen?",
            )

            if user_choice is True:
                if self.symbol_picker_page.save_to_current_file():
                    filename = os.path.basename(self.symbol_picker_page.output_filename)
                    messagebox.showinfo("Saved", f"Progress saved to\n{filename}")
                    self.show_start_page()
            elif user_choice is False:
                self.show_start_page()

    def toggle_theme(self):
        current_mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("Light" if current_mode == "Dark" else "Dark")
        self.update_theme_button_text()

    def update_theme_button_text(self):
        current_mode = ctk.get_appearance_mode()
        next_mode = "Dark" if current_mode == "Light" else "Light"
        self.theme_button.configure(text=f"Switch to {next_mode}")

    def show_start_page(self):
        if self.symbol_picker_page:
            self.symbol_picker_page.main_frame.grid_forget()
        self.home_button.grid_forget()
        self.start_page.main_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=int(PADDING_LARGE * UI_SCALE),
            pady=int(PADDING_LARGE * UI_SCALE),
        )

    def launch_symbol_picker(self, output_filename, dataframe, start_index=0):
        self.start_page.main_frame.grid_forget()
        if self.symbol_picker_page is None:
            self.symbol_picker_page = SymbolPickerPage(self.container, self)
        self.symbol_picker_page.reload(output_filename, dataframe, start_index)
        self.home_button.grid(row=0, column=0, sticky="w")
        self.symbol_picker_page.main_frame.grid(row=0, column=0, sticky="nsew")


# ---
# Start Page
# ---
class StartPage:
    def __init__(self, master, controller):
        self.master = master
        self.controller = controller
        self.main_frame = ctk.CTkFrame(self.master)
        self.main_frame.grid_columnconfigure(0, weight=1)
        title_font = ctk.CTkFont(
            family="Arial", size=int(FONT_SIZE_TITLE * UI_SCALE), weight="bold"
        )
        ctk.CTkLabel(self.main_frame, text="Symbol Picker", font=title_font).grid(
            row=0, column=0, pady=int(PADDING_LARGE * UI_SCALE)
        )
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.grid(row=1, column=0, pady=int(PADDING_LARGE * UI_SCALE))
        button_font = ctk.CTkFont(family="Arial", size=int(FONT_SIZE_LARGE * UI_SCALE))
        button_ipadding = int(BUTTON_IPAD * UI_SCALE)
        ctk.CTkButton(
            button_frame,
            text="Start New Symbol Deck",
            font=button_font,
            command=self.start_new,
        ).pack(pady=int(PADDING_NORMAL * UI_SCALE), ipady=button_ipadding)
        ctk.CTkButton(
            button_frame,
            text="Load Existing Deck",
            font=button_font,
            command=self.load_existing,
            fg_color="gray50",
        ).pack(pady=int(PADDING_NORMAL * UI_SCALE), ipady=button_ipadding)

    def start_new(self):
        dialog = ctk.CTkInputDialog(
            text="Enter a name for your new symbol deck:", title="New Deck"
        )
        deck_name = dialog.get_input()
        if not deck_name:
            return
        output_filename = f"{deck_name}.csv"
        if os.path.exists(output_filename):
            if not messagebox.askyesno(
                "Overwrite?",
                f'"{output_filename}" already exists. Do you want to overwrite it?',
            ):
                return
        new_df = self.controller.base_vocab_df.copy()
        for col in [
            "symbol_filename",
            "symbol_name",
            "symbol_source",
            "original_filename",
            "notes",
            "symbol_data",
        ]:
            if col not in new_df.columns:
                new_df[col] = pd.NA
        self.controller.launch_symbol_picker(output_filename, new_df)

    def load_existing(self):
        filename = filedialog.askopenfilename(
            title="Select a Symbol Deck",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not filename:
            return
        try:
            loaded_df = pd.read_csv(filename)
            start_index = 0
            completed_count = 0
            if "symbol_filename" in loaded_df.columns:
                completed_rows = loaded_df["symbol_filename"].notna()
                completed_count = completed_rows.sum()
                first_incomplete = (
                    completed_rows.idxmin()
                    if not completed_rows.all()
                    else len(loaded_df)
                )
                start_index = first_incomplete
            total_entries = len(loaded_df)
            message = f"Loaded {total_entries} entries. {completed_count} items have symbols.\n\nStarting at entry {start_index + 1}."
            if completed_count > 0 and start_index == len(loaded_df):
                message = f"Deck is complete with {completed_count} symbols! Loading last entry."
                start_index = len(loaded_df) - 1
            messagebox.showinfo("Deck Loaded", message)
            self.controller.launch_symbol_picker(filename, loaded_df, start_index)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file: {e}")


class SymbolPickerPage:
    def __init__(self, master, controller):
        self.master = master
        self.root = controller.root
        self.controller = controller
        self.autosave_var = ctk.BooleanVar(value=True)
        self.multi_select_mode = ctk.BooleanVar(value=False)
        self.separator_font_path = (
            self._find_system_font()
        )  # <-- NEW: Find a reliable font on startup

        self.source_column_map = {
            "Mulberry": 0,
            "OpenMoji": 0,
            "Picom": 0,
            "Flaticon": 0,
            "Sclera": 1,
            "Bliss": 1,
            "ARASAAC": 1,
        }

        # --- (The rest of the __init__ method remains the same) ---
        # --- ARASAAC Caching Setup ---
        self.arasaac_metadata_path = os.path.join(ARASAAC_CACHE_DIR, "metadata.csv")
        os.makedirs(ARASAAC_CACHE_DIR, exist_ok=True)
        try:
            self.arasaac_metadata_df = pd.read_csv(self.arasaac_metadata_path)
        except FileNotFoundError:
            self.arasaac_metadata_df = pd.DataFrame()

        base_size_map = {
            "Extra Small": 64,
            "Small": 96,
            "Medium": 128,
            "Large": 192,
            "Extra Large": 256,
        }
        self.size_map = {k: int(v * UI_SCALE) for k, v in base_size_map.items()}
        base_padding_map = {"Small": 5, "Medium": 10, "Large": 15}
        self.padding_map = {k: int(v * UI_SCALE) for k, v in base_padding_map.items()}

        try:
            # Load Mulberry and OpenMoji
            self.mulberry_df = pd.read_csv("symbol-info.csv")
            self.openmoji_df = pd.read_csv(
                os.path.join("openmoji-618x618-color", "metadata.csv")
            )

            # Pre-load Picom Symbols from filenames
            print("Loading Picom symbols...")
            picom_path = "picom-symbols/picom-og-symbols"
            picom_data = []
            if os.path.exists(picom_path):
                for filename in os.listdir(picom_path):
                    if filename.endswith(".png"):
                        base_name, _ = os.path.splitext(filename)
                        parts = base_name.rsplit("_", 1)
                        if len(parts) == 2:
                            symbol_name = parts[0]
                            picom_data.append(
                                {
                                    "name": symbol_name,
                                    "path": os.path.join(picom_path, filename),
                                }
                            )
                self.picom_df = pd.DataFrame(picom_data)
                print(f"Loaded {len(self.picom_df)} Picom symbols.")
            else:
                self.picom_df = pd.DataFrame()
                print("Warning: Picom symbol directory not found.")

            # Pre-load Sclera Symbols from filenames
            print("Loading Sclera symbols...")
            sclera_path = "sclera-symbols/"
            sclera_data = []
            if os.path.exists(sclera_path):
                for filename in os.listdir(sclera_path):
                    if filename.endswith(".png"):
                        base_name, _ = os.path.splitext(filename)
                        parts = base_name.rsplit("_", 1)
                        if len(parts) == 2 and parts[1].isdigit():
                            search_term = parts[0].replace("-", " ").replace("_", " ")
                            display_name = f"{search_term} {parts[1]}"
                        else:
                            search_term = base_name.replace("-", " ").replace("_", " ")
                            display_name = search_term

                        sclera_data.append(
                            {
                                "name": display_name,
                                "search_term": search_term,
                                "path": os.path.join(sclera_path, filename),
                            }
                        )
                self.sclera_df = pd.DataFrame(sclera_data)
                print(f"Loaded {len(self.sclera_df)} Sclera symbols.")
            else:
                self.sclera_df = pd.DataFrame()
                print("Warning: Sclera symbol directory not found.")

            # Pre-load Bliss Symbols from the pre-processed folder
            print("Loading Bliss symbols...")
            bliss_path = "bliss_h1000_bmp_padded"
            bliss_data = []
            if os.path.isdir(bliss_path):
                for filename in os.listdir(bliss_path):
                    if filename.endswith(".bmp"):
                        symbol_name, _ = os.path.splitext(filename)
                        bliss_data.append(
                            {
                                "name": symbol_name.replace("-", " "),
                                "path": os.path.join(bliss_path, filename),
                            }
                        )
                self.bliss_df = pd.DataFrame(bliss_data)
                print(f"Loaded {len(self.bliss_df)} Bliss symbols.")
            else:
                print(
                    f"Warning: Bliss symbol directory '{bliss_path}' not found. Did you run the pre-processing script?"
                )
                self.bliss_df = pd.DataFrame()

        except FileNotFoundError as e:
            messagebox.showerror(
                "Error",
                f"Could not find a required local symbol file or directory: {e}",
            )
            self.controller.show_start_page()
            return

        self.setup_gui()

    # --- NEW HELPER FUNCTION TO FIND A FONT ---
    def _find_system_font(self):
        """Find a reliable TTF font path on the current OS."""
        system = platform.system()
        if system == "Windows":
            font_path = os.path.join(
                os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "arial.ttf"
            )
            if os.path.exists(font_path):
                print(f"Found font: {font_path}")
                return font_path
        elif system == "Darwin":  # macOS
            paths = [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Arial.ttf",
            ]
            for path in paths:
                if os.path.exists(path):
                    print(f"Found font: {path}")
                    return path
        else:  # Linux
            paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]
            for path in paths:
                if os.path.exists(path):
                    print(f"Found font: {path}")
                    return path

        print(
            "Warning: Could not find a default system font for separator. Falling back."
        )
        return None

    def combine_and_save_symbols(self):
        if not self.current_selection:
            messagebox.showwarning(
                "No Selection", "Please select one or more symbols to save."
            )
            return

        symbol_names = [s["symbol_info"]["name"] for s in self.current_selection]
        symbol_sources = [s["source"] for s in self.current_selection]
        symbol_data_list = [
            {
                "name": s["symbol_info"]["name"],
                "source": s["source"],
                "original_filename": s["symbol_info"].get("original_filename", "N/A"),
            }
            for s in self.current_selection
        ]
        symbol_data_json = json.dumps(symbol_data_list)

        sanitized_word = (
            "".join(x for x in self.base_word_for_filename if x.isalnum())
            or f"entry{self.current_index}"
        )

        IMG_SIZE = 512
        SEPARATOR_WIDTH = 400

        separator_image = Image.new("RGBA", (SEPARATOR_WIDTH, IMG_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(separator_image)

        # --- UPDATED FONT LOGIC ---
        try:
            # Use the pre-found font path and the new, larger size
            font_size = 200  # <-- INCREASED SIZE
            if self.separator_font_path:
                font = ImageFont.truetype(self.separator_font_path, font_size)
            else:
                # Fallback if no font was found at all
                font = ImageFont.load_default()
        except IOError:
            font = ImageFont.load_default()

        draw.text(
            (SEPARATOR_WIDTH / 2, IMG_SIZE / 2),
            "||",
            font=font,
            fill="black",
            anchor="mm",
        )

        num_symbols = len(self.current_selection)
        total_width = (IMG_SIZE * num_symbols) + (SEPARATOR_WIDTH * (num_symbols - 1))

        combined_image = Image.new("RGBA", (total_width, IMG_SIZE), (255, 255, 255, 0))

        x_offset = 0
        for i, item in enumerate(self.current_selection):
            img = item["image_obj"].resize(
                (IMG_SIZE, IMG_SIZE), Image.Resampling.LANCZOS
            )
            combined_image.paste(img, (x_offset, 0), img)
            x_offset += IMG_SIZE

            if i < num_symbols - 1:
                combined_image.paste(separator_image, (x_offset, 0), separator_image)
                x_offset += SEPARATOR_WIDTH

        final_filename = f"{sanitized_word}_Combined_{int(time.time())}.png"
        destination_path = os.path.join(SELECTED_SYMBOLS_DIR, final_filename)
        self._save_pil_image(combined_image, destination_path)

        self._commit_symbol(
            final_filename, " / ".join(symbol_names), "Combined", symbol_data_json
        )
        self.toggle_multi_select_mode()
        self.next_word()

    # --- (The rest of the SymbolPickerPage class remains the same) ---
    # (reload, setup_gui, disable_root_key_bindings, etc... all the way to the end)
    def reload(self, output_filename, dataframe, start_index=0):
        self.output_filename = output_filename
        self.output_df = dataframe
        self.current_index = start_index
        self.symbol_buttons, self.cached_results = [], {}
        self.symbol_buttons_data = []  # <-- Store data for keyboard nav
        self.selected_index, self.current_search_id = -1, 0
        self.source_frames = {}
        self.source_counters = {}
        self.column_row_counters = {0: 0, 1: 0}
        self.results_queue = Queue()
        self.current_selection = []
        # Navigation grid attributes
        self.nav_grid_dirty = True
        self.nav_grid = []
        self.button_to_coords = {}
        self.root.after(100, self.search_for_symbols)

    def disable_root_key_bindings(self, event):
        self.root.unbind("<KeyPress>")

    def enable_root_key_bindings(self, event):
        self.root.bind("<KeyPress>", self.on_key_press)

    def setup_gui(self):
        self.main_frame = ctk.CTkFrame(self.master, fg_color="transparent")
        self.main_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=int(PADDING_NORMAL * UI_SCALE),
            pady=int(PADDING_NORMAL * UI_SCALE),
        )
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)
        button_ipadding = int(BUTTON_IPAD * UI_SCALE / 2)
        self.italic_font, self.normal_font, self.header_font = [
            ctk.CTkFont(family="Arial", size=int(s * UI_SCALE), **k)
            for s, k in [
                (FONT_SIZE_NORMAL, {"slant": "italic"}),
                (FONT_SIZE_NORMAL, {}),
                (FONT_SIZE_LARGE, {"weight": "bold"}),
            ]
        ]
        top_frame = ctk.CTkFrame(self.main_frame)
        top_frame.grid(
            row=0, column=0, sticky="ew", pady=(0, int(PADDING_NORMAL * UI_SCALE))
        )
        top_frame.grid_columnconfigure(0, weight=1)
        self.original_string_label = ctk.CTkLabel(
            top_frame, text="", font=self.italic_font
        )
        self.original_string_label.grid(
            row=0, column=0, sticky="w", padx=int(PADDING_NORMAL * UI_SCALE)
        )
        self.word_buttons_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        self.word_buttons_frame.grid(
            row=1,
            column=0,
            sticky="w",
            padx=int(PADDING_NORMAL * UI_SCALE),
            pady=int(PADDING_SMALL * UI_SCALE),
        )
        controls_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        controls_frame.grid(
            row=2,
            column=0,
            sticky="w",
            padx=int(PADDING_NORMAL * UI_SCALE),
            pady=int(PADDING_SMALL * UI_SCALE),
        )

        search_controls_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        search_controls_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            search_controls_frame, text="Custom Search:", font=self.normal_font
        ).grid(row=0, column=0, sticky="w", padx=(0, int(PADDING_SMALL * UI_SCALE)))
        self.custom_search_entry = ctk.CTkEntry(
            search_controls_frame,
            width=int(ENTRY_WIDTH * UI_SCALE),
            font=self.normal_font,
        )
        self.custom_search_entry.grid(row=0, column=1, sticky="w")
        self.custom_search_entry.bind("<Return>", lambda e: self.refresh_symbol_grid())
        self.custom_search_entry.bind("<FocusIn>", self.disable_root_key_bindings)
        self.custom_search_entry.bind("<FocusOut>", self.enable_root_key_bindings)
        ctk.CTkLabel(
            search_controls_frame, text="Text Symbol:", font=self.normal_font
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(5, 0),
            padx=(0, int(PADDING_SMALL * UI_SCALE)),
        )
        self.text_symbol_entry = ctk.CTkEntry(
            search_controls_frame,
            width=int(ENTRY_WIDTH * UI_SCALE * 0.6),
            font=self.normal_font,
        )
        self.text_symbol_entry.grid(row=1, column=1, sticky="w", pady=(5, 0))
        self.text_symbol_entry.bind("<FocusIn>", self.disable_root_key_bindings)
        self.text_symbol_entry.bind("<FocusOut>", self.enable_root_key_bindings)
        self.create_symbol_button = ctk.CTkButton(
            search_controls_frame,
            text="Create",
            command=self.create_text_symbol,
            width=int(ENTRY_WIDTH * 0.3),
        )
        self.create_symbol_button.grid(row=1, column=2, sticky="w", pady=(5, 0), padx=5)

        display_controls_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        display_controls_frame.pack(
            side="left", padx=(int(PADDING_LARGE * UI_SCALE), 0)
        )
        ctk.CTkLabel(
            display_controls_frame, text="Icon Size:", font=self.normal_font
        ).grid(row=0, column=0, padx=(0, int(PADDING_SMALL * UI_SCALE)))
        self.size_dropdown = ctk.CTkComboBox(
            display_controls_frame,
            values=list(self.size_map.keys()),
            command=self.on_size_select,
            width=int(COMBOBOX_WIDTH * UI_SCALE),
            font=self.normal_font,
        )
        self.size_dropdown.set("Medium")
        self.size_dropdown.grid(row=0, column=1)
        ctk.CTkLabel(
            display_controls_frame, text="Padding:", font=self.normal_font
        ).grid(row=1, column=0, pady=(5, 0), padx=(0, int(PADDING_SMALL * UI_SCALE)))
        self.padding_dropdown = ctk.CTkComboBox(
            display_controls_frame,
            values=list(self.padding_map.keys()),
            command=self.on_padding_select,
            width=int(COMBOBOX_WIDTH * 1.2 * UI_SCALE),
            font=self.normal_font,
        )
        self.padding_dropdown.set("Medium")
        self.padding_dropdown.grid(row=1, column=1, pady=(5, 0))

        search_buttons_frame = ctk.CTkFrame(self.main_frame)
        search_buttons_frame.grid(
            row=1, column=0, sticky="ew", pady=int(PADDING_SMALL * UI_SCALE)
        )
        self.search_button = ctk.CTkButton(
            search_buttons_frame,
            text="Refresh Search",
            command=self.refresh_symbol_grid,
            font=self.normal_font,
        )
        self.search_button.pack(
            side="left", padx=int(PADDING_SMALL * UI_SCALE), ipady=button_ipadding
        )
        self.flaticon_button = ctk.CTkButton(
            search_buttons_frame,
            text="Get Flaticon Symbols",
            command=self.fetch_flaticon_symbols,
            fg_color="gray50",
            font=self.normal_font,
        )
        self.flaticon_button.pack(
            side="left", padx=int(PADDING_SMALL * UI_SCALE), ipady=button_ipadding
        )

        self.multi_select_toggle_button = ctk.CTkButton(
            search_buttons_frame,
            text="Select Multiple",
            command=self.toggle_multi_select_mode,
            font=self.normal_font,
        )
        self.multi_select_toggle_button.pack(
            side="left", padx=(int(PADDING_LARGE * UI_SCALE), 0), ipady=button_ipadding
        )

        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.main_frame, label_text="Symbols", label_font=self.normal_font
        )
        self.scrollable_frame.grid(row=2, column=0, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure((0, 1), weight=1, uniform="group1")

        self.existing_symbol_frame = ctk.CTkFrame(self.main_frame)
        self.existing_symbol_frame.grid_columnconfigure(0, weight=1)
        self.existing_symbol_label = ctk.CTkLabel(self.existing_symbol_frame, text="")
        self.existing_symbol_label.pack(pady=int(PADDING_LARGE * UI_SCALE), expand=True)
        self.existing_symbol_info = ctk.CTkLabel(   
            self.existing_symbol_frame, text="", font=self.normal_font
        )
        self.existing_symbol_info.pack(pady=int(PADDING_NORMAL * UI_SCALE))
        ctk.CTkButton(
            self.existing_symbol_frame,
            text="Update Symbol",
            command=self.refresh_symbol_grid,
            font=self.normal_font,
        ).pack(pady=int(PADDING_LARGE * UI_SCALE), ipady=button_ipadding)
        self.existing_symbol_frame.grid_remove()

        self.selection_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.selection_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.selection_frame.grid_columnconfigure(1, weight=1)
        self.selection_preview_frame = ctk.CTkScrollableFrame(
            self.selection_frame,
            label_text="Current Selection",
            label_font=self.normal_font,
            orientation="horizontal",
            height=120,
        )
        self.selection_preview_frame.grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=5
        )
        button_container = ctk.CTkFrame(self.selection_frame, fg_color="transparent")
        button_container.grid(row=1, column=1, sticky="e")
        self.combine_button = ctk.CTkButton(
            button_container,
            text="Combine & Save",
            command=self.combine_and_save_symbols,
        )
        self.combine_button.pack(side="left", padx=5)
        self.clear_button = ctk.CTkButton(
            button_container,
            text="Clear",
            command=self.clear_selection,
            fg_color="gray50",
        )
        self.clear_button.pack(side="left", padx=5)
        self.selection_frame.grid_forget()  # Hide by default

        nav_frame = ctk.CTkFrame(self.main_frame)
        nav_frame.grid(
            row=4, column=0, sticky="ew", pady=(int(PADDING_NORMAL * UI_SCALE), 0)
        )
        nav_frame.grid_columnconfigure(1, weight=1)
        self.prev_button = ctk.CTkButton(
            nav_frame, text="<< Previous", command=self.prev_word, font=self.normal_font
        )
        self.prev_button.grid(
            row=0, column=0, padx=int(PADDING_SMALL * UI_SCALE), ipady=button_ipadding
        )
        index_entry_frame = ctk.CTkFrame(nav_frame, fg_color="transparent")
        index_entry_frame.grid(row=0, column=1)
        self.index_entry = ctk.CTkEntry(
            index_entry_frame,
            width=int(100 * UI_SCALE),
            justify="center",
            font=self.normal_font,
        )
        self.index_entry.pack(side="left")
        self.index_entry.bind("<Return>", self.go_to_index)
        self.index_entry.bind("<FocusIn>", self.disable_root_key_bindings)
        self.index_entry.bind("<FocusOut>", self.enable_root_key_bindings)
        self.index_total_label = ctk.CTkLabel(
            index_entry_frame, text="/ ?", font=self.normal_font
        )
        self.index_total_label.pack(side="left", padx=int(PADDING_SMALL * UI_SCALE))
        self.next_button = ctk.CTkButton(
            nav_frame, text="Next >>", command=self.next_word, font=self.normal_font
        )
        self.next_button.grid(
            row=0, column=2, padx=int(PADDING_SMALL * UI_SCALE), ipady=button_ipadding
        )

        notes_frame = ctk.CTkFrame(self.main_frame)
        notes_frame.grid(
            row=5, column=0, sticky="ew", pady=int(PADDING_NORMAL * UI_SCALE)
        )
        notes_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(notes_frame, text="Note:", font=self.normal_font).pack(
            side="left", padx=(10, 5)
        )
        self.note_entry = ctk.CTkEntry(notes_frame, font=self.normal_font)
        self.note_entry.pack(side="left", expand=True, fill="x", padx=5)
        self.note_entry.bind("<FocusIn>", self.disable_root_key_bindings)
        self.note_entry.bind("<FocusOut>", self.enable_root_key_bindings)
        self.add_note_button = ctk.CTkButton(
            notes_frame, text="Add Note", command=self.add_note, font=self.normal_font
        )
        self.add_note_button.pack(side="left", padx=(5, 10))

        bottom_frame = ctk.CTkFrame(self.main_frame)
        bottom_frame.grid(
            row=6, column=0, sticky="ew", pady=int(PADDING_NORMAL * UI_SCALE)
        )
        bottom_frame.grid_columnconfigure(1, weight=1)
        self.autosave_checkbox = ctk.CTkCheckBox(
            bottom_frame,
            text="Autosave",
            variable=self.autosave_var,
            font=self.normal_font,
        )
        self.autosave_checkbox.grid(row=0, column=0, padx=10)
        self.save_button = ctk.CTkButton(
            bottom_frame,
            text="Save As...",
            command=self.save_as,
            fg_color="gray50",
            font=self.normal_font,
        )
        self.save_button.grid(row=0, column=2, padx=10, ipady=button_ipadding)
        self.enable_root_key_bindings(None)

    def add_note(self):
        note_text = self.note_entry.get()
        if not note_text:
            return
        if "notes" not in self.output_df.columns:
            self.output_df["notes"] = pd.NA
        self.output_df.loc[self.current_index, "notes"] = note_text
        print(f"Note added for index {self.current_index}: {note_text}")
        self.note_entry.delete(0, "end")
        self.auto_save()

    def create_text_symbol(self):
        user_text = self.text_symbol_entry.get().strip()
        if not user_text:
            return
        dialog = TextSymbolDialog(self.root, text_to_render=user_text)
        final_image = dialog.get_result()

        if final_image:
            symbol_info = {"name": user_text, "original_filename": "custom_text.png"}

            if self.multi_select_mode.get():
                self.add_to_selection(
                    symbol_info, "Custom Text", final_image, "image_obj"
                )
            else:
                self.select_single_symbol(
                    symbol_info, "Custom Text", final_image, "image_obj"
                )

            self.text_symbol_entry.delete(0, "end")

    def _commit_symbol(self, filename, symbol_name, source, symbol_data_json):
        if "notes" not in self.output_df.columns:
            self.output_df["notes"] = pd.NA
        if "symbol_data" not in self.output_df.columns:
            self.output_df["symbol_data"] = pd.NA

        self.output_df.loc[
            self.current_index,
            [
                "symbol_filename",
                "symbol_name",
                "symbol_source",
                "symbol_data",
                "original_filename",
            ],
        ] = [
            filename,
            symbol_name,
            source,
            symbol_data_json,
            "",
        ]  # Clear old original_filename column

        self.auto_save()
        if not self.multi_select_mode.get():  # Only auto-advance in single mode
            self.next_word()

    def get_current_icon_size(self):
        return self.size_map.get(self.size_dropdown.get(), 128)

    def get_current_padding(self):
        return self.padding_map.get(self.padding_dropdown.get(), 10)

    def on_size_select(self, choice):
        self.redraw_grid_from_cache()

    def on_padding_select(self, choice):
        self.redraw_grid_from_cache()

    def redraw_grid_from_cache(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.source_frames, self.source_counters = {}, {}
        self.column_row_counters = {0: 0, 1: 0}
        self.selected_index, self.symbol_buttons, self.symbol_buttons_data = -1, [], []
        self.nav_grid_dirty = True
        for source in [
            "Mulberry",
            "OpenMoji",
            "Picom",
            "Sclera",
            "Bliss",
            "ARASAAC",
            "Flaticon",
        ]:
            if source in self.cached_results:
                for symbol, data, data_type in self.cached_results[source]:
                    self.display_symbol(source, symbol, data, data_type)

    def search_for_symbols(self):
        self.update_word_display()
        if "symbol_filename" in self.output_df.columns and pd.notna(
            self.output_df.loc[self.current_index, "symbol_filename"]
        ):
            self.show_existing_symbol() 
        else:
            self.refresh_symbol_grid()

    def show_existing_symbol(self):
        self.scrollable_frame.grid_remove()
        self.existing_symbol_frame.grid(row=2, column=0, sticky="nsew")
        try:
            row = self.output_df.loc[self.current_index]
            filename, symbol_name, source = (
                row["symbol_filename"],
                row["symbol_name"],
                row["symbol_source"],
            )
            filepath = os.path.join(SELECTED_SYMBOLS_DIR, filename)
            display_height = int(256 * UI_SCALE)
            final_image_for_display = None
            final_width, final_height = display_height, display_height

            if filepath.endswith(".svg"):
                # For SVGs, we can render them directly to the target square size
                image_data = cairosvg.svg2png(
                    url=filepath,
                    output_width=display_height,
                    output_height=display_height,
                )
                final_image_for_display = Image.open(BytesIO(image_data))
            else:
                image = Image.open(filepath)
                original_width, original_height = image.size
                
                # --- FIX: Calculate proportional width based on a fixed height ---
                aspect_ratio = original_width / original_height
                final_height = display_height
                final_width = int(final_height * aspect_ratio)
                
                # Resize the image proportionally to the new dimensions
                resized_image = image.resize((final_width, final_height), Image.Resampling.LANCZOS)
                final_image_for_display = resized_image

            # Use the calculated final width and height for the CTkImage
            ctk_image = ctk.CTkImage(
                light_image=final_image_for_display,
                size=(final_width, final_height), # <-- Use new proportional dimensions
            )
            self.existing_symbol_label.configure(image=ctk_image, text="")
            self.existing_symbol_info.configure(
                text=f"Symbol: {symbol_name}\nSource: {source}"
            )
        except Exception as e:
            self.existing_symbol_label.configure(
                image=None, text=f"Error loading symbol:\n{e}"
            )
            self.existing_symbol_info.configure(text="")
            
    def refresh_symbol_grid(self):
        self.existing_symbol_frame.grid_remove()
        self.scrollable_frame.grid(row=2, column=0, sticky="nsew")
        self.current_search_id += 1
        self.cached_results = {}
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.column_row_counters = {0: 0, 1: 0}
        query = self.custom_search_entry.get().strip() or self.current_word
        if query == "(No Word)":
            return
        self.selected_index, self.source_frames, self.source_counters = -1, {}, {}
        self.symbol_buttons, self.symbol_buttons_data = [], []
        self.nav_grid_dirty = True
        self.flaticon_button.configure(state="normal")
        self.process_local_search_batch(self.search_mulberry(query), "Mulberry")
        self.process_local_search_batch(self.search_openmoji(query), "OpenMoji")
        self.process_local_search_batch(self.search_picom(query), "Picom")
        self.process_local_search_batch(self.search_sclera(query), "Sclera")
        self.process_local_search_batch(self.search_bliss(query), "Bliss")
        arasaac_cache_results = self.check_arasaac_cache(query, self.current_index)
        self.process_local_search_batch(arasaac_cache_results, "ARASAAC")
        sources_to_search = []
        if not arasaac_cache_results:
            sources_to_search.append("ARASAAC")
        if "ARASAAC" in sources_to_search:
            self._get_or_create_source_frame("ARASAAC")
        self.start_threaded_searches(query, sources=sources_to_search)
        self.process_queue()

    def start_threaded_searches(self, query, sources=[]):
        search_map = {"Flaticon": self.search_flaticon, "ARASAAC": self.search_arasaac}
        for source_name in sources:
            if source_name in search_map:
                search_func = search_map[source_name]
                thread = threading.Thread(
                    target=self.run_search_in_thread,
                    args=(search_func, query, source_name, self.current_search_id),
                )
                thread.daemon = True
                thread.start()

    def fetch_flaticon_symbols(self):
        self.flaticon_button.configure(state="disabled")
        query = self.custom_search_entry.get().strip() or self.current_word
        self._get_or_create_source_frame("Flaticon")
        self.start_threaded_searches(query, sources=["Flaticon"])

    def run_search_in_thread(self, search_func, query, source, search_id):
        symbol_metadata_generator = (
            search_func(query, self.current_index)
            if source == "ARASAAC"
            else search_func(query)
        )
        if not symbol_metadata_generator:
            return
        for symbol in symbol_metadata_generator:
            if search_id != self.current_search_id:
                return
            try:
                if "url" in symbol and source == "Flaticon":
                    response = requests.get(symbol["url"], stream=True, timeout=10)
                    response.raise_for_status()
                    image_data = response.content
                    self.results_queue.put(
                        ("SYMBOL", source, symbol, image_data, search_id)
                    )
                elif "path" in symbol and source == "ARASAAC":
                    with open(symbol["path"], "rb") as f:
                        image_data = f.read()
                    self.results_queue.put(
                        ("SYMBOL", source, symbol, image_data, search_id)
                    )
            except Exception as e:
                print(f"Error processing symbol '{symbol.get('name')}' in thread: {e}")

    def process_queue(self):
        try:
            item_type, source, symbol_meta, image_data, search_id = (
                self.results_queue.get_nowait()
            )
            if search_id != self.current_search_id:
                return
            if source not in self.cached_results:
                self.cached_results[source] = []
            if item_type == "SYMBOL":
                self.cached_results[source].append(
                    (symbol_meta, image_data, "png_data")
                )
                self.display_symbol(source, symbol_meta, image_data, "png_data")
        except Exception:
            pass
        finally:
            self.root.after(50, self.process_queue)

    def _get_or_create_source_frame(self, source):
        if source not in self.source_frames:
            column_index = self.source_column_map.get(source, 0)
            row_index = self.column_row_counters[column_index]
            container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
            container.grid(
                row=row_index, column=column_index, sticky="new", pady=(10, 0), padx=5
            )
            self.column_row_counters[column_index] += 1
            header = ctk.CTkLabel(
                container, text=f"--- {source} ---", font=self.header_font
            )
            header.pack(side="top", anchor="w", padx=5)
            grid_frame = ctk.CTkFrame(container, fg_color="transparent")
            grid_frame.pack(side="top", fill="x")
            self.source_frames[source] = grid_frame
            self.source_counters[source] = {"row": 0, "col": 0}
        return self.source_frames[source], self.source_counters[source]

    def display_symbol(self, source, symbol, data, data_type):
        try:
            self.nav_grid_dirty = True
            parent_frame, counters = self._get_or_create_source_frame(source)
            current_size = self.get_current_icon_size()
            image_obj = self._get_image_obj(data, data_type)
            if not image_obj:
                return

            image_obj.thumbnail((current_size, current_size), Image.Resampling.LANCZOS)
            padded_image = Image.new("RGBA", (current_size, current_size), (0, 0, 0, 0))
            paste_pos = (
                (current_size - image_obj.width) // 2,
                (current_size - image_obj.height) // 2,
            )
            padded_image.paste(
                image_obj, paste_pos, image_obj if image_obj.mode == "RGBA" else None
            )

            ctk_image = ctk.CTkImage(
                light_image=padded_image, size=(current_size, current_size)
            )
            btn = ctk.CTkButton(
                parent_frame,
                image=ctk_image,
                text=symbol["name"][:30],
                compound="top",
                command=lambda s=symbol, src=source, d=data, dt=data_type: self.handle_symbol_click(
                    s, src, d, dt
                ),
                fg_color="transparent",
                border_width=0,
                text_color=("black", "white"),
                font=self.normal_font,
            )
            btn.grid(
                row=counters["row"],
                column=counters["col"],
                padx=self.get_current_padding(),
                pady=self.get_current_padding(),
            )

            self.symbol_buttons.append(btn)
            self.symbol_buttons_data.append(
                {
                    "symbol": symbol,
                    "source": source,
                    "data": data,
                    "data_type": data_type,
                }
            )

            counters["col"] = (counters["col"] + 1) % MAX_GRID_COLUMNS
            if counters["col"] == 0:
                counters["row"] += 1
            if self.selected_index == -1 and self.symbol_buttons:
                self.selected_index = 0
                self.update_selection_highlight()
        except Exception as e:
            print(f"Error displaying image for '{symbol.get('name', 'N/A')}': {e}")

    def process_local_search_batch(self, symbols, source):
        if not symbols:
            return
        self.cached_results[source] = []
        for symbol in symbols:
            try:
                if "path" in symbol:
                    path = symbol["path"]
                    if path.endswith(".svg"):
                        data_type = "svg_path"
                        self.cached_results[source].append((symbol, path, data_type))
                        self.display_symbol(source, symbol, path, data_type)
                    elif path.endswith((".png", ".bmp")):
                        data_type = "raster_data"
                        with open(path, "rb") as f:
                            data = f.read()
                        self.cached_results[source].append((symbol, data, data_type))
                        self.display_symbol(source, symbol, data, data_type)
            except Exception as e:
                print(f"Error processing local symbol '{symbol.get('name')}': {e}")

    def update_word_display(self):
        for widget in self.word_buttons_frame.winfo_children():
            widget.destroy()
        self.custom_search_entry.delete(0, "end")
        self.index_entry.delete(0, "end")
        self.index_entry.insert(0, str(self.current_index + 1))
        self.index_total_label.configure(text=f"/ {len(self.output_df)}")
        raw_text = self.output_df.loc[self.current_index, "english"]
        if pd.isna(raw_text):
            self.original_string_label.configure(text="")
            self.current_word_list = ["(No Word)"]
        else:
            self.original_string_label.configure(text=f'Original: "{str(raw_text)}"')
            processed_text = (
                str(raw_text)
                .replace("(", ",")
                .replace(")", "")
                .replace(" or ", ",")
                .replace(";", ",")
            )
            parts = processed_text.split(",")
            self.current_word_list = [
                word.strip() for word in parts if word.strip()
            ] or ["(Empty)"]
        self.current_word = self.current_word_list[0]
        self.base_word_for_filename = self.current_word_list[0]
        word_button_ipadding = int(BUTTON_IPAD * UI_SCALE / 4)
        if len(self.current_word_list) > 1:
            for i, word in enumerate(self.current_word_list):
                btn = ctk.CTkButton(
                    self.word_buttons_frame,
                    text=word,
                    font=self.normal_font,
                    command=lambda w=word: self.switch_search_term(w),
                )
                btn.grid(
                    row=0,
                    column=i,
                    padx=int(PADDING_SMALL * UI_SCALE),
                    ipady=word_button_ipadding,
                )
                if i != 0:
                    btn.configure(fg_color="gray50")

        self.note_entry.delete(0, "end")
        if "notes" in self.output_df.columns and pd.notna(
            self.output_df.loc[self.current_index, "notes"]
        ):
            self.note_entry.insert(
                0, str(self.output_df.loc[self.current_index, "notes"])
            )

    def switch_search_term(self, new_word):
        self.current_word = new_word
        for child in self.word_buttons_frame.winfo_children():
            if child.cget("text") == new_word:
                child.configure(
                    fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"]
                )
            else:
                child.configure(fg_color="gray50")
        self.refresh_symbol_grid()

    def go_to_index(self, event=None):
        try:
            target_index = int(self.index_entry.get()) - 1
            if 0 <= target_index < len(self.output_df):
                self.current_index = target_index
                self.search_for_symbols()
            else:
                messagebox.showerror(
                    "Invalid Index",
                    f"Please enter a number between 1 and {len(self.output_df)}.",
                )
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number.")
        finally:
            self.index_entry.delete(0, "end")
            self.index_entry.insert(0, str(self.current_index + 1))

    def _build_nav_grid(self):
        if not self.symbol_buttons:
            self.nav_grid, self.button_to_coords = [], {}
            return
        self.root.update_idletasks()
        buttons_by_row_y = {}
        for btn in self.symbol_buttons:
            abs_y = btn.winfo_y() + btn.master.master.winfo_y()
            found_row = False
            for y_key in buttons_by_row_y:
                if abs(abs_y - y_key) < 20:
                    buttons_by_row_y[y_key].append(btn)
                    found_row = True
                    break
            if not found_row:
                buttons_by_row_y[abs_y] = [btn]
        sorted_y_keys = sorted(buttons_by_row_y.keys())
        self.nav_grid = []
        for y in sorted_y_keys:
            row_buttons = sorted(
                buttons_by_row_y[y],
                key=lambda b: b.winfo_x() + b.master.master.winfo_x(),
            )
            self.nav_grid.append(row_buttons)
        self.button_to_coords = {}
        for r, row_list in enumerate(self.nav_grid):
            for c, btn in enumerate(row_list):
                self.button_to_coords[btn] = (r, c)
        self.nav_grid_dirty = False

    def on_key_press(self, event):
        if not self.symbol_buttons or self.selected_index < 0:
            return
        key = event.keysym
        if key == "Return":
            if 0 <= self.selected_index < len(self.symbol_buttons_data):
                data = self.symbol_buttons_data[self.selected_index]
                self.handle_symbol_click(
                    data["symbol"], data["source"], data["data"], data["data_type"]
                )
            return

        if self.nav_grid_dirty:
            self._build_nav_grid()
        if not self.nav_grid:
            return
        current_btn = self.symbol_buttons[self.selected_index]
        if current_btn not in self.button_to_coords:
            self._build_nav_grid()
            if current_btn not in self.button_to_coords:
                return
        r, c = self.button_to_coords[current_btn]
        new_r, new_c = r, c
        if key == "Right":
            new_c += 1
            if new_c >= len(self.nav_grid[r]):
                new_c, new_r = 0, new_r + 1
                if new_r >= len(self.nav_grid):
                    new_r = 0
        elif key == "Left":
            new_c -= 1
            if new_c < 0:
                new_r -= 1
                if new_r < 0:
                    new_r = len(self.nav_grid) - 1
                new_c = len(self.nav_grid[new_r]) - 1
        elif key == "Down":
            new_r = min(r + 1, len(self.nav_grid) - 1)
            new_c = min(c, len(self.nav_grid[new_r]) - 1)
        elif key == "Up":
            new_r = max(r - 1, 0)
            new_c = min(c, len(self.nav_grid[new_r]) - 1)

        try:
            new_button = self.nav_grid[new_r][new_c]
            new_index = self.symbol_buttons.index(new_button)
            self.selected_index = new_index
            self.update_selection_highlight()
        except (IndexError, ValueError):
            pass

    def update_selection_highlight(self):
        accent_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        for i, button in enumerate(self.symbol_buttons):
            if i == self.selected_index:
                button.configure(border_color=accent_color, border_width=2)
                button.focus_set()
                self.root.after(
                    50,
                    lambda b=button: self.scrollable_frame._parent_canvas.yview_moveto(
                        b.winfo_y() / self.scrollable_frame.winfo_height()
                    ),
                )
            else:
                button.configure(border_width=0)

    # +++ LOGIC FOR MODE-SWITCHING AND SELECTION +++

    def toggle_multi_select_mode(self):
        """Switches between single and multi-symbol selection modes."""
        is_multi = not self.multi_select_mode.get()
        self.multi_select_mode.set(is_multi)

        if is_multi:
            self.multi_select_toggle_button.configure(text="Cancel", fg_color="gray50")
            self.selection_frame.grid()
        else:
            self.multi_select_toggle_button.configure(
                text="Select Multiple",
                fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
            )
            self.selection_frame.grid_forget()
            self.clear_selection()

    def handle_symbol_click(self, symbol, source, data, data_type):
        """Central handler that directs action based on the current selection mode."""
        if self.multi_select_mode.get():
            self.add_to_selection(symbol, source, data, data_type)
        else:
            self.select_single_symbol(symbol, source, data, data_type)

    def select_single_symbol(self, symbol, source, data, data_type):
        """Saves a single selected symbol and advances to the next item."""
        try:
            os.makedirs(SELECTED_SYMBOLS_DIR, exist_ok=True)
            sanitized_word = (
                "".join(x for x in self.base_word_for_filename if x.isalnum())
                or f"entry{self.current_index}"
            )
            original_filename = symbol.get("original_filename", "custom.png")
            final_filename = f"{sanitized_word}_{source}_{original_filename}"
            destination_path = os.path.join(SELECTED_SYMBOLS_DIR, final_filename)

            if "path" in symbol and os.path.exists(symbol["path"]):
                shutil.copy(symbol["path"], destination_path)
            else:
                image_obj = self._get_image_obj(data, data_type)
                if image_obj:
                    self._save_pil_image(image_obj, destination_path)
                else:
                    raise ValueError("Could not get image data to save.")

            symbol_data_list = [
                {
                    "name": symbol["name"],
                    "source": source,
                    "original_filename": original_filename,
                }
            ]
            symbol_data_json = json.dumps(symbol_data_list)

            self._commit_symbol(
                final_filename, symbol["name"], source, symbol_data_json
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not save symbol: {e}")

    def add_to_selection(self, symbol, source, data, data_type):
        """Adds a symbol to the current selection list and updates the preview."""
        try:
            image_obj = self._get_image_obj(data, data_type)
            if image_obj:
                selection_data = {
                    "symbol_info": symbol,
                    "source": source,
                    "image_obj": image_obj.convert("RGBA"),
                }
                self.current_selection.append(selection_data)
                self.update_selection_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Could not add symbol to selection: {e}")

    def update_selection_preview(self):
        for widget in self.selection_preview_frame.winfo_children():
            widget.destroy()
        for item in self.current_selection:
            image = item["image_obj"]
            ctk_image = ctk.CTkImage(light_image=image, size=(80, 80))
            preview_label = ctk.CTkLabel(
                self.selection_preview_frame,
                image=ctk_image,
                text=item["symbol_info"]["name"][:20],
                compound="top",
            )
            preview_label.pack(side="left", padx=10, pady=5)

    def clear_selection(self):
        self.current_selection.clear()
        self.update_selection_preview()

    def _get_image_obj(self, data, data_type):
        """Helper to convert various data types into a PIL Image object."""
        if data_type == "image_obj":
            return data
        if data_type == "svg_path":
            png_data = cairosvg.svg2png(url=data)
            return Image.open(BytesIO(png_data))
        elif data_type in ["raster_data", "png_data"]:
            return Image.open(BytesIO(data))
        return None

    def _save_pil_image(self, image_obj, destination_path):
        """Helper to save a PIL Image object, handling transparency correctly."""
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        if image_obj.mode == "RGBA":
            background = Image.new("RGB", image_obj.size, (255, 255, 255))
            background.paste(image_obj, mask=image_obj.split()[3])
            background.save(destination_path, "PNG")
        else:
            image_obj.convert("RGB").save(destination_path, "PNG")

    def next_word(self):
        if self.current_index < len(self.output_df) - 1:
            self.current_index += 1
            self.search_for_symbols()
            self.clear_selection()
        else:
            messagebox.showinfo(
                "End of List", "You are at the end of the vocabulary list."
            )

    def prev_word(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.search_for_symbols()
            self.clear_selection()

    def auto_save(self):
        if self.autosave_var.get():
            self.save_to_current_file()

    def save_to_current_file(self):
        try:
            self.output_df.to_csv(self.output_filename, index=False)
            print(f"Saved progress to {self.output_filename}")
            return True
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save file:\n{e}")
            return False

    def save_as(self):
        new_filename = filedialog.asksaveasfilename(
            initialfile=os.path.basename(self.output_filename),
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if new_filename:
            try:
                self.output_df.to_csv(new_filename, index=False)
                messagebox.showinfo("Saved", f"Progress saved to {new_filename}")
                self.output_filename = new_filename
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")

    def search_mulberry(self, query):
        try:
            df = self.mulberry_df.copy()
            df["search_term"] = df["symbol-en"].str.replace("_", " ")
            df["score"] = df["search_term"].apply(
                lambda x: fuzz.token_sort_ratio(query, str(x))
            )
            return [
                {
                    "name": row["symbol-en"],
                    "path": os.path.join(
                        "mulberry-symbols", "EN-symbols", f"{row['symbol-en']}.svg"
                    ),
                    "original_filename": f"{row['symbol-en']}.svg",
                }
                for _, row in df.sort_values(by="score", ascending=False)
                .head(4)
                .iterrows()
            ]
        except Exception as e:
            print(f"Error searching Mulberry: {e}")
            return []

    def search_openmoji(self, query):
        try:
            df = self.openmoji_df.copy()
            df["search_term"] = (
                df["annotation"].fillna("") + " " + df["tags"].fillna("")
            )
            df["score"] = df["search_term"].apply(
                lambda x: fuzz.token_sort_ratio(query, str(x))
            )
            return [
                {
                    "name": row["annotation"],
                    "path": os.path.join(
                        "openmoji-618x618-color", "emojis", f"{row['hexcode']}.png"
                    ),
                    "original_filename": f"{row['hexcode']}.png",
                }
                for _, row in df.sort_values(by="score", ascending=False)
                .head(4)
                .iterrows()
            ]
        except Exception as e:
            print(f"Error searching OpenMoji: {e}")
            return []

    def search_picom(self, query):
        try:
            df = self.picom_df.copy()
            if df.empty:
                return []
            df["score"] = df["name"].apply(
                lambda x: fuzz.token_sort_ratio(query, str(x))
            )
            return [
                {
                    "name": row["name"],
                    "path": row["path"],
                    "original_filename": os.path.basename(row["path"]),
                }
                for _, row in df.sort_values(by="score", ascending=False)
                .head(4)
                .iterrows()
            ]
        except Exception as e:
            print(f"Error searching Picom symbols: {e}")
            return []

    def search_sclera(self, query):
        try:
            df = self.sclera_df.copy()
            if df.empty:
                return []
            df["score"] = df["search_term"].apply(
                lambda x: fuzz.token_sort_ratio(query, str(x))
            )
            return [
                {
                    "name": row["name"],
                    "path": row["path"],
                    "original_filename": os.path.basename(row["path"]),
                }
                for _, row in df.sort_values(by="score", ascending=False)
                .head(4)
                .iterrows()
            ]
        except Exception as e:
            print(f"Error searching Sclera symbols: {e}")
            return []

    def search_bliss(self, query):
        try:
            if self.bliss_df.empty:
                return []
            df = self.bliss_df.copy()
            df["score"] = df["name"].apply(
                lambda x: fuzz.token_sort_ratio(query, str(x))
            )
            return [
                {
                    "name": row["name"],
                    "path": row["path"],
                    "original_filename": os.path.basename(row["path"]),
                }
                for _, row in df.sort_values(by="score", ascending=False)
                .head(4)
                .iterrows()
            ]
        except Exception as e:
            print(f"Error searching Bliss symbols: {e}")
            return []

    def check_arasaac_cache(self, query, current_index):
        if self.arasaac_metadata_df.empty:
            return []
        cached_entries = self.arasaac_metadata_df[
            (self.arasaac_metadata_df["search_term"] == query)
            & (self.arasaac_metadata_df["search_index"] == current_index)
        ]
        if not cached_entries.empty:
            print(f"Found ARASAAC results for '{query}' in local cache.")
            results = []
            for _, row in cached_entries.iterrows():
                try:
                    keywords_val = row.get("keywords")
                    keywords_list = (
                        ast.literal_eval(keywords_val)
                        if isinstance(keywords_val, str)
                        else (keywords_val if keywords_val else [])
                    )
                    keyword = (
                        keywords_list[0].get("keyword", "N/A")
                        if keywords_list
                        else "N/A"
                    )
                    results.append(
                        {
                            "name": keyword,
                            "path": os.path.join(
                                ARASAAC_CACHE_DIR, row["local_filename"]
                            ),
                            "original_filename": row["local_filename"],
                        }
                    )
                except (ValueError, SyntaxError, KeyError) as e:
                    print(
                        f"Warning: Could not parse cached ARASAAC entry for '{query}'. Error: {e}"
                    )
            return results
        return []

    def search_arasaac(self, query, current_index):
        print(f"Fetching ARASAAC results for '{query}' from API...")
        try:
            response = requests.get(f"{ARASAAC_API_URL}{query}", timeout=10)
            response.raise_for_status()
            api_data = response.json()
        except Exception as e:
            print(f"Error searching ARASAAC: {e}")
            return
        new_metadata_rows = []
        for item in api_data[:4]:
            pictogram_id = item.get("_id")
            if not pictogram_id:
                continue
            try:
                img_url = f"https://api.arasaac.org/api/pictograms/{pictogram_id}"
                img_response = requests.get(img_url, timeout=10)
                img_response.raise_for_status()
                local_filename = f"{pictogram_id}.png"
                local_filepath = os.path.join(ARASAAC_CACHE_DIR, local_filename)
                with open(local_filepath, "wb") as f:
                    f.write(img_response.content)
                metadata_row = item.copy()
                metadata_row.update(
                    {
                        "search_term": query,
                        "search_index": current_index,
                        "local_filename": local_filename,
                    }
                )
                new_metadata_rows.append(metadata_row)
                yield {
                    "name": item.get("keywords", [{}])[0].get("keyword", "N/A"),
                    "path": local_filepath,
                    "original_filename": local_filename,
                }
            except Exception as e:
                print(f"Failed to download/save ARASAAC pictogram {pictogram_id}: {e}")
        if new_metadata_rows:
            new_df = pd.DataFrame(new_metadata_rows)
            self.arasaac_metadata_df = pd.concat(
                [self.arasaac_metadata_df, new_df], ignore_index=True
            )
            new_df.to_csv(
                self.arasaac_metadata_path,
                mode="a",
                header=not os.path.exists(self.arasaac_metadata_path),
                index=False,
            )

    def search_flaticon(self, query):
        if FLATICON_API_KEY == "YOUR_FLATICON_API_KEY" or not FLATICON_API_KEY:
            print("Flaticon API key not set. Skipping search.")
            return
        headers = {
            "x-freepik-api-key": FLATICON_API_KEY,
            "Accept": "application/json",
        }
        try:
            search_params = {"term": query, "limit": 4, "order": "relevance"}
            search_response = requests.get(
                FLATICON_API_URLS["search"],
                headers=headers,
                params=search_params,
                timeout=10,
            )
            search_response.raise_for_status()
            search_data = search_response.json()
        except Exception as e:
            print(f"Error during Flaticon search step: {e}")
            if "search_response" in locals():
                print(f"Search Response Text: {search_response.text}")
            return
        for item in search_data.get("data", [])[:4]:
            try:
                icon_id, icon_name = item.get("id"), item.get("name", "N/A")
                if not icon_id:
                    continue
                download_url = FLATICON_API_URLS["download"].format(id=icon_id)
                download_response = requests.get(
                    download_url, headers=headers, params={"format": "png"}, timeout=10
                )
                download_response.raise_for_status()
                final_url = download_response.json().get("data", {}).get("url")
                if final_url:
                    sanitized_name = (
                        "".join(c for c in icon_name if c.isalnum() or c in " _-")
                        .strip()
                        .replace(" ", "_")
                    )
                    original_filename = f"{sanitized_name}_{icon_id}.png"
                    yield {
                        "name": icon_name,
                        "url": final_url,
                        "original_filename": original_filename,
                    }
            except Exception as e:
                print(
                    f"  -> ERROR getting download link for icon ID {item.get('id')}: {e}"
                )
                continue


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = SymbolPickerApp(root)
    root.mainloop()
