                import customtkinter as ctk
from tkinter import messagebox, filedialog
import pandas as pd
import requests
from PIL import Image
from io import BytesIO
from fuzzywuzzy import fuzz
import os
import shutil
import cairosvg
import threading
from queue import Queue
from dotenv import load_dotenv

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
SELECTED_SYMBOLS_DIR = "selected_symbols"
MAX_GRID_COLUMNS = 4


class SymbolPickerApp:
    """The main application controller."""

    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Symbol Picker")
        self.root.attributes("-zoomed", True)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

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

        try:
            self.base_vocab_df = pd.read_csv(
                "Gabe_Esperanto cards_filtered_cleaned_no_starters_no_jn_rerank.csv"
            )
        except FileNotFoundError as e:
            messagebox.showerror("Error", f"Could not find required file: {e.filename}")
            self.root.destroy()
            return

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
            # Ask the user if they want to save their work
            user_choice = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes. Would you like to save before returning to the home screen?",
            )
            filename = os.path.basename(self.symbol_picker_page.output_filename)

            if user_choice is True:  # User clicked "Yes"
                if self.symbol_picker_page.save_to_current_file():

                    self.show_start_page()
                    messagebox.showinfo(
                        "Saved", f"Progress saved to\n{filename}"
                    )
                # If save fails, an error is shown and we stay on the page
            elif user_choice is False:  # User clicked "No"
                self.show_start_page()
            # If user_choice is None (Cancel), do nothing

    def toggle_theme(self):
        current_mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("Light" if current_mode == "Dark" else "Dark")
        self.update_theme_button_text()

    def update_theme_button_text(self):
        current_mode = ctk.get_appearance_mode()
        next_mode = "Dark" if current_mode == "Light" else "Light"
        self.theme_button.configure(text=f"{next_mode} Theme")

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
        for col in ["symbol_filename", "symbol_name", "symbol_source"]:
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


# ---
# Symbol Picker Page
# ---
class SymbolPickerPage:
    def __init__(self, master, controller):
        self.master = master
        self.root = controller.root
        self.controller = controller
        self.autosave_var = ctk.BooleanVar(value=True)  # Variable for checkbox state

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
            self.mulberry_df = pd.read_csv("symbol-info.csv")
            self.openmoji_df = pd.read_csv(
                os.path.join("openmoji-618x618-color", "metadata.csv")
            )
        except FileNotFoundError as e:
            messagebox.showerror(
                "Error", f"Could not find a required local symbol file: {e.filename}"
            )
            self.controller.show_start_page()
            return

        self.setup_gui()

    def reload(self, output_filename, dataframe, start_index=0):
        self.output_filename = output_filename
        self.output_df = dataframe
        self.current_index = start_index
        self.symbol_buttons = []
        self.selected_index = -1
        self.grid_row, self.grid_col = 0, 0
        self.results_queue = Queue()
        self.current_search_id = 0
        self.cached_results = {}
        if not os.path.exists(SELECTED_SYMBOLS_DIR):
            os.makedirs(SELECTED_SYMBOLS_DIR)
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

        # --- Fonts and Frames setup (condensed for brevity) ---
        self.italic_font = ctk.CTkFont(
            family="Arial", size=int(FONT_SIZE_NORMAL * UI_SCALE), slant="italic"
        )
        self.normal_font = ctk.CTkFont(
            family="Arial", size=int(FONT_SIZE_NORMAL * UI_SCALE)
        )
        self.header_font = ctk.CTkFont(
            family="Arial", size=int(FONT_SIZE_LARGE * UI_SCALE), weight="bold"
        )
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
        ctk.CTkLabel(controls_frame, text="Custom Search:", font=self.normal_font).pack(
            side="left", padx=(0, int(PADDING_SMALL * UI_SCALE))
        )
        self.custom_search_entry = ctk.CTkEntry(
            controls_frame, width=int(ENTRY_WIDTH * UI_SCALE), font=self.normal_font
        )
        self.custom_search_entry.pack(
            side="left", padx=(0, int(PADDING_LARGE * UI_SCALE))
        )
        self.custom_search_entry.bind(
            "<Return>", lambda event: self.refresh_symbol_grid()
        )
        self.custom_search_entry.bind("<FocusIn>", self.disable_root_key_bindings)
        self.custom_search_entry.bind("<FocusOut>", self.enable_root_key_bindings)
        ctk.CTkLabel(controls_frame, text="Icon Size:", font=self.normal_font).pack(
            side="left", padx=(0, int(PADDING_SMALL * UI_SCALE))
        )
        self.size_dropdown = ctk.CTkComboBox(
            controls_frame,
            values=list(self.size_map.keys()),
            command=self.on_size_select,
            width=int(COMBOBOX_WIDTH * UI_SCALE),
            font=self.normal_font,
        )
        self.size_dropdown.set("Medium")
        self.size_dropdown.pack(side="left", padx=(0, int(PADDING_LARGE * UI_SCALE)))
        ctk.CTkLabel(controls_frame, text="Padding:", font=self.normal_font).pack(
            side="left", padx=(0, int(PADDING_SMALL * UI_SCALE))
        )
        self.padding_dropdown = ctk.CTkComboBox(
            controls_frame,
            values=list(self.padding_map.keys()),
            command=self.on_padding_select,
            width=int(COMBOBOX_WIDTH * 1.2 * UI_SCALE),
            font=self.normal_font,
        )
        self.padding_dropdown.set("Medium")
        self.padding_dropdown.pack(side="left")
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
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.main_frame, label_text="Symbols", label_font=self.normal_font
        )
        self.scrollable_frame.grid(row=2, column=0, sticky="nsew")
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
        nav_frame = ctk.CTkFrame(self.main_frame)
        nav_frame.grid(
            row=3, column=0, sticky="ew", pady=(int(PADDING_NORMAL * UI_SCALE), 0)
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

        # --- Bottom Frame for Save Button and Autosave Checkbox ---
        bottom_frame = ctk.CTkFrame(self.main_frame)
        bottom_frame.grid(
            row=4, column=0, sticky="ew", pady=int(PADDING_NORMAL * UI_SCALE)
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
        self.grid_row, self.grid_col = 0, 0
        self.symbol_buttons = []
        self.selected_index = -1
        for source in ["Mulberry", "OpenMoji", "ARASAAC", "Flaticon"]:
            if source in self.cached_results:
                self.display_header(source)
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
            filename = self.output_df.loc[self.current_index, "symbol_filename"]
            symbol_name = self.output_df.loc[self.current_index, "symbol_name"]
            source = self.output_df.loc[self.current_index, "symbol_source"]
            filepath = os.path.join(SELECTED_SYMBOLS_DIR, filename)
            image_data = None
            if filepath.endswith(".svg"):
                image_data = cairosvg.svg2png(
                    url=filepath, output_width=256, output_height=256
                )
            else:
                with open(filepath, "rb") as f:
                    image_data = f.read()
            image = Image.open(BytesIO(image_data))
            img_size = int(256 * UI_SCALE)
            ctk_image = ctk.CTkImage(light_image=image, size=(img_size, img_size))
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
        custom_query = self.custom_search_entry.get().strip()
        query = custom_query if custom_query else self.current_word
        if query == "(No Word)":
            return
        self.grid_row, self.grid_col = 0, 0
        self.symbol_buttons = []
        self.selected_index = -1
        self.flaticon_button.configure(state="normal")
        self.process_local_search_batch(self.search_mulberry(query), "Mulberry")
        self.process_local_search_batch(self.search_openmoji(query), "OpenMoji")
        self.display_header("ARASAAC")
        self.start_threaded_searches(query)
        self.process_queue()

    def start_threaded_searches(self, query, sources=["ARASAAC"]):
        api_searches = []
        if "ARASAAC" in sources:
            api_searches.append((self.search_arasaac, query, "ARASAAC"))
        if "Flaticon" in sources:
            api_searches.append((self.search_flaticon, query, "Flaticon"))
        for search_func, q, source_name in api_searches:
            thread = threading.Thread(
                target=self.run_search_in_thread,
                args=(search_func, q, source_name, self.current_search_id),
            )
            thread.daemon = True
            thread.start()

    def fetch_flaticon_symbols(self):
        self.flaticon_button.configure(state="disabled")
        self.display_header("Flaticon")
        query = self.custom_search_entry.get().strip() or self.current_word
        self.start_threaded_searches(query, sources=["Flaticon"])

    def run_search_in_thread(self, search_func, query, source, search_id):
        symbol_metadata = search_func(query)
        if not symbol_metadata:
            return
        for symbol in symbol_metadata:
            if search_id != self.current_search_id:
                return
            try:
                if "url" in symbol:
                    response = requests.get(symbol["url"], stream=True, timeout=10)
                    response.raise_for_status()
                    image_data = response.content
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

    def display_header(self, source):
        if self.grid_col != 0:
            self.grid_row += 1
        source_label = ctk.CTkLabel(
            self.scrollable_frame, text=f"--- {source} ---", font=self.header_font
        )
        source_label.grid(
            row=self.grid_row,
            column=0,
            columnspan=MAX_GRID_COLUMNS,
            pady=int(PADDING_NORMAL * UI_SCALE),
            sticky="w",
        )
        self.grid_row += 1
        self.grid_col = 0

    def display_symbol(self, source, symbol, data, data_type):
        try:
            current_size = self.get_current_icon_size()
            image_data = None
            if data_type == "svg_path":
                image_data = cairosvg.svg2png(
                    url=data, output_width=current_size, output_height=current_size
                )
            elif data_type == "png_data":
                image_data = data
            image = Image.open(BytesIO(image_data))
            ctk_image = ctk.CTkImage(
                light_image=image, size=(current_size, current_size)
            )
            btn = ctk.CTkButton(
                self.scrollable_frame,
                image=ctk_image,
                text=symbol["name"][:30],
                compound="top",
                command=lambda s=symbol, src=source: self.select_symbol(s, src),
                fg_color="transparent",
                border_width=0,
                text_color=("black", "white"),
                font=self.normal_font,
            )
            btn.grid(
                row=self.grid_row,
                column=self.grid_col,
                padx=self.get_current_padding(),
                pady=self.get_current_padding(),
            )
            self.symbol_buttons.append(btn)
            self.grid_col = (self.grid_col + 1) % MAX_GRID_COLUMNS
            if self.grid_col == 0:
                self.grid_row += 1
            if self.selected_index == -1 and self.symbol_buttons:
                self.selected_index = 0
                self.update_selection_highlight()
        except Exception as e:
            print(f"Error displaying image for '{symbol.get('name', 'N/A')}': {e}")

    def process_local_search_batch(self, symbols, source):
        if not symbols:
            return
        self.display_header(source)
        self.cached_results[source] = []
        for symbol in symbols:
            try:
                if "path" in symbol:
                    if symbol["path"].endswith(".svg"):
                        self.cached_results[source].append(
                            (symbol, symbol["path"], "svg_path")
                        )
                        self.display_symbol(source, symbol, symbol["path"], "svg_path")
                    else:
                        with open(symbol["path"], "rb") as f:
                            image_data = f.read()
                        self.cached_results[source].append(
                            (symbol, image_data, "png_data")
                        )
                        self.display_symbol(source, symbol, image_data, "png_data")
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
            self.current_word_list = [word.strip() for word in parts if word.strip()]
            if not self.current_word_list:
                self.current_word_list = ["(Empty)"]
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

    def on_key_press(self, event):
        if not self.symbol_buttons or self.selected_index == -1:
            return
        key, new_index = event.keysym, self.selected_index
        if key == "Right":
            new_index += 1
        elif key == "Left":
            new_index -= 1
        elif key == "Down":
            new_index += MAX_GRID_COLUMNS
        elif key == "Up":
            new_index -= MAX_GRID_COLUMNS
        elif key == "Return":
            self.symbol_buttons[self.selected_index].invoke()
            return
        if 0 <= new_index < len(self.symbol_buttons):
            self.selected_index = new_index
            self.update_selection_highlight()

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

    def select_symbol(self, symbol, source):
        sanitized_word = "".join(x for x in self.base_word_for_filename if x.isalnum())
        if not sanitized_word:
            sanitized_word = f"entry{self.current_index}"
        filename = ""
        try:
            if "path" in symbol:
                original_filename = os.path.basename(symbol["path"])
                filename = f"{sanitized_word}_{source}_{original_filename}"
                shutil.copy(
                    symbol["path"], os.path.join(SELECTED_SYMBOLS_DIR, filename)
                )
            else:
                response = requests.get(symbol["url"], stream=True, timeout=10)
                response.raise_for_status()
                if "ARASAAC" in source:
                    pictogram_id = symbol["url"].split("/")[-1]
                    symbol_name_cleaned = (
                        "".join(
                            c
                            for c in symbol["name"]
                            if c.isalnum() or c in (" ", "_", "-")
                        )
                        .strip()
                        .replace(" ", "_")
                    )
                    filename = f"{sanitized_word}_{source}_{symbol_name_cleaned}_{pictogram_id}.png"
                else:
                    base_name = os.path.basename(symbol["url"].split("?")[0])
                    if not os.path.splitext(base_name)[1]:
                        base_name += ".png"
                    filename = f"{sanitized_word}_{source}_{base_name}"
                with open(os.path.join(SELECTED_SYMBOLS_DIR, filename), "wb") as f:
                    shutil.copyfileobj(response.raw, f)
            self.output_df.loc[self.current_index, "symbol_filename"] = filename
            self.output_df.loc[self.current_index, "symbol_name"] = symbol["name"]
            self.output_df.loc[self.current_index, "symbol_source"] = source
            self.auto_save()
            self.next_word()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save symbol: {e}")

    def next_word(self):
        if self.current_index < len(self.output_df) - 1:
            self.current_index += 1
            self.search_for_symbols()
        else:
            messagebox.showinfo(
                "End of List", "You are at the end of the vocabulary list."
            )

    def prev_word(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.search_for_symbols()

    def auto_save(self):
        if not self.autosave_var.get():
            return
        self.save_to_current_file()

    def save_to_current_file(self):
        """Saves the current DataFrame to its output_filename."""
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
                self.output_filename = new_filename  # Update the current filename
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")

    # --- Symbol Search Functions ---
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
                }
                for _, row in df.sort_values(by="score", ascending=False)
                .head(4)
                .iterrows()
            ]
        except Exception as e:
            print(f"Error searching OpenMoji: {e}")
            return []

    def search_arasaac(self, query):
        try:
            response = requests.get(f"{ARASAAC_API_URL}{query}", timeout=10)
            response.raise_for_status()
            return [
                {
                    "name": item.get("keywords", [{}])[0].get("keyword", "N/A"),
                    "url": f"https://api.arasaac.org/api/pictograms/{item['_id']}",
                }
                for item in response.json()[:4]
            ]
        except Exception as e:
            print(f"Error searching ARASAAC: {e}")
            return []

    def search_flaticon(self, query):
        if FLATICON_API_KEY == "YOUR_FLATICON_API_KEY" or not FLATICON_API_KEY:
            print("Flaticon API key not set. Skipping search.")
            return []
        headers = {"x-freepik-api-key": FLATICON_API_KEY, "Accept": "application/json"}
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
            return []
        results = []
        for item in search_data.get("data", []):
            try:
                icon_id = item.get("id")
                icon_name = item.get("name", "N/A")
                if not icon_id:
                    continue
                download_url_template = FLATICON_API_URLS["download"]
                download_url = download_url_template.format(id=icon_id)
                download_params = {"format": "png"}
                download_response = requests.get(
                    download_url, headers=headers, params=download_params, timeout=10
                )
                download_response.raise_for_status()
                download_data = download_response.json()
                final_url = download_data.get("data", {}).get("url")
                if final_url:
                    results.append({"name": icon_name, "url": final_url})
            except Exception as e:
                print(
                    f"  -> ERROR getting download link for icon ID {item.get('id')}: {e}"
                )
                continue
        return results


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = SymbolPickerApp(root)
    root.mainloop()
