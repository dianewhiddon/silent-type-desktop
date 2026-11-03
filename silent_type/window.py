"""The Camera and settings window: camera choice, preview, manual recording, history.

Normal use never needs it; the app runs from the tray. It only builds and updates
widgets and calls back into the app for every action.
"""

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from . import theme

LOG = logging.getLogger(__name__)


class MainWindow:
    def __init__(
        self,
        root,
        *,
        history,
        hold_label,
        camera_names,
        camera,
        on_camera,
        on_preview,
        on_record,
        on_copy,
        on_hide,
        on_retry=lambda: None,
        punctuate=False,
        on_punctuate=lambda enabled: None,
    ):
        self.root = root
        self.history = history
        self.on_copy = on_copy
        self.saved_rows = {}
        self.photo = None
        self.preview_window = None
        self.on_preview = on_preview
        theme.apply(root)
        body = ttk.Frame(root, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Silent Type", style="Title.TLabel").pack(anchor="w")
        control_label = (
            f"Click where you want to type, hold {hold_label} and mouth a short phrase. "
            "Release either key to type it. Escape cancels."
            if hold_label
            else "Keyboard control is off in settings. Use Start recording below."
        )
        self.wrapped = []

        def paragraph(text, **kwargs):
            label = ttk.Label(body, text=text, wraplength=680, **kwargs)
            self.wrapped.append(label)
            return label

        paragraph(control_label).pack(anchor="w", fill="x", pady=(8, 16))
        paragraph("Camera only. Video stays on this computer and is not saved.", style="Muted.TLabel").pack(
            anchor="w", fill="x"
        )
        self.status = tk.StringVar(value="Loading model…")
        status_label = ttk.Label(body, textvariable=self.status, wraplength=670, style="Section.TLabel")
        status_label.pack(anchor="w", fill="x", pady=16)
        self.wrapped.append(status_label)

        controls = ttk.Frame(body)
        controls.pack(fill="x")
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Camera").grid(row=0, column=0, sticky="w")
        self.camera = tk.StringVar(value=camera)
        self.camera_select = ttk.Combobox(
            controls, textvariable=self.camera, values=camera_names, state="readonly", width=20
        )
        self.camera_select.grid(row=0, column=1, sticky="ew", padx=8)
        self.camera_select.bind("<<ComboboxSelected>>", lambda _: on_camera(self.camera.get()))
        self.preview_button = ttk.Button(controls, text="Check camera", command=on_preview)
        self.preview_button.grid(row=0, column=2)
        self.retry_button = ttk.Button(body, text="Loading model…", command=on_retry, state="disabled")
        self.retry_button.pack(anchor="w", pady=4)
        self.record_button = ttk.Button(
            body, text="Start recording", command=on_record, style="Accent.TButton"
        )
        self.record_button.pack(anchor="w", pady=8)
        self.preview_image = None
        paragraph(
            "Start recording saves a phrase for review here. Face forward with your mouth visible.",
            style="Muted.TLabel",
        ).pack(anchor="w", fill="x")
        self.punctuate = tk.BooleanVar(value=punctuate)
        ttk.Checkbutton(
            body,
            text="Use Claude for punctuation (sends recognized text to Anthropic)",
            variable=self.punctuate,
            command=lambda: on_punctuate(self.punctuate.get()),
        ).pack(anchor="w", pady=(12, 0))
        paragraph(
            "Optional: requires your Anthropic API key; usage is billed by Anthropic.", style="Muted.TLabel"
        ).pack(anchor="w", fill="x", pady=(4, 0))

        ttk.Separator(body).pack(fill="x", pady=12)
        ttk.Label(body, text="Recent phrases", style="Section.TLabel").pack(anchor="w")
        history_frame = ttk.Frame(body)
        self.rows = ttk.Treeview(
            history_frame, columns=("phrase", "outcome"), show="headings", height=4, selectmode="browse"
        )
        self.rows.heading("phrase", text="Recognized text")
        self.rows.heading("outcome", text="Result")
        self.rows.column("phrase", width=350, minwidth=180)
        self.rows.column("outcome", width=180, minwidth=140)
        scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.rows.yview)
        self.rows.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.rows.pack(side="left", fill="both", expand=True)
        self.rows.bind("<<TreeviewSelect>>", self.select_phrase)
        self.phrase = tk.Text(
            body,
            height=3,
            wrap="word",
            font=("Segoe UI", 11),
            bg=theme.SURFACE,
            fg=theme.INK,
            padx=12,
            pady=10,
            relief="solid",
            bd=1,
            highlightcolor=theme.ACCENT,
            highlightthickness=1,
        )
        self.phrase.configure(state="disabled")

        actions = ttk.Frame(body)
        self.copy_button = ttk.Button(actions, text="Copy selected", command=self.copy_selected)
        self.copy_button.pack(side="left")
        self.clear_button = ttk.Button(actions, text="Clear history", command=self.clear_history)
        self.clear_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Hide", command=on_hide).pack(side="right")
        footer = paragraph(
            "Recognition can be wrong. Check the text before sending it.", style="Muted.TLabel"
        )
        # Reserve controls first; only the history list contracts in a short window.
        footer.pack(side="bottom", anchor="w", fill="x", pady=(4, 0))
        actions.pack(side="bottom", fill="x", pady=8)
        self.phrase.pack(side="bottom", fill="x")
        history_frame.pack(fill="both", expand=True, pady=8)
        body.bind(
            "<Configure>",
            lambda event: [label.configure(wraplength=max(200, event.width - 48)) for label in self.wrapped],
        )
        self.refresh_history()

    def set_model_loading(self, loading, failed=False):
        if loading or failed:
            self.retry_button.pack(anchor="w", pady=4, before=self.record_button)
        else:
            self.retry_button.pack_forget()
        self.retry_button.configure(
            text="Loading model…" if loading else "Retry model", state="normal" if failed else "disabled"
        )

    def set_camera(self, name):
        self.camera.set(name)

    def set_record_label(self, text):
        self.record_button.configure(text=text)

    def set_previewing(self, previewing):
        self.preview_button.configure(text="Stop camera" if previewing else "Check camera")
        if not previewing and self.preview_window is not None:
            self.preview_window.destroy()
            self.preview_window = None
            self.preview_image = None

    def show_preview(self, rgb):
        from PIL import Image, ImageTk

        if self.preview_window is None:
            self.preview_window = tk.Toplevel(self.root)
            self.preview_window.title("Check camera")
            self.preview_window.transient(self.root)
            self.preview_window.resizable(False, False)
            self.preview_window.protocol("WM_DELETE_WINDOW", self.on_preview)
            self.preview_image = ttk.Label(self.preview_window, padding=16)
            self.preview_image.pack()
            ttk.Button(self.preview_window, text="Stop camera", command=self.on_preview).pack(pady=(0, 16))
        self.photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.preview_image.configure(image=self.photo)

    def refresh_history(self):
        for row in self.rows.get_children():
            self.rows.delete(row)
        self.saved_rows = {str(row[0]): row for row in self.history.recent()}
        for key, row in self.saved_rows.items():
            self.rows.insert("", "end", iid=key, values=(row[2], row[3]))
        if self.saved_rows:
            self.rows.selection_set(next(iter(self.saved_rows)))
        else:
            self.rows.insert("", "end", iid="empty", values=("Record a phrase to see it here.", ""))
        self.select_phrase()
        self.clear_button.configure(state="normal" if self.saved_rows else "disabled")

    def select_phrase(self, *_):
        selection = self.rows.selection()
        valid = bool(selection and selection[0] in self.saved_rows)
        self.copy_button.configure(state="normal" if valid else "disabled")
        self.phrase.configure(state="normal")
        self.phrase.delete("1.0", "end")
        if selection and selection[0] in self.saved_rows:
            self.phrase.insert("1.0", self.saved_rows[selection[0]][2])
        self.phrase.configure(state="disabled")

    def copy_selected(self):
        selection = self.rows.selection()
        if selection and selection[0] in self.saved_rows:
            self.on_copy(self.saved_rows[selection[0]][2])

    def clear_history(self):
        if messagebox.askyesno(
            "Clear recent phrases?",
            "Delete the recovery history? The separate Markdown log and any backups are kept.",
            parent=self.root,
        ):
            self.history.clear()
            self.refresh_history()
