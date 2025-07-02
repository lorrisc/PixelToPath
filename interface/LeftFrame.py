import customtkinter as ctk
from PIL import Image
import webbrowser
from interface.utils import resource_path

class LeftFrame(ctk.CTkFrame):
    """Zone de gauche contenant la documentation avec scroll."""

    def __init__(self, parent):
        super().__init__(parent)

        # Canvas + scrollbar
        self.canvas = ctk.CTkCanvas(self, borderwidth=0, highlightthickness=0, bg="#dbdbdb")
        self.scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.window_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Pour scroll molette
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)


        self.build()

    def _on_canvas_configure(self, event):
        # Ajuster la largeur du frame scrollable à celle du canvas
        canvas_width = event.width
        self.canvas.itemconfig(self.window_frame, width=canvas_width)

    def _on_mousewheel(self, event):
        first, last = self.canvas.yview()
        if event.delta > 0 and first <= 0:
            return
        if event.delta < 0 and last >= 1:
            return
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def build(self):
        # Construire tout dans scrollable_frame
        titre = ctk.CTkLabel(
            self.scrollable_frame,
            text="About the Software",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="center",
            justify="center"
        )
        titre.grid(row=0, column=0, pady=(10, 5), padx=10, sticky="ew")

        label_titre_description = ctk.CTkLabel(
            self.scrollable_frame,
            text="Description",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="center",
            justify="center"
        )
        label_titre_description.grid(row=1, column=0, pady=(0, 5), padx=10, sticky="ew")

        texte_description = "PixelToPath transforms your PNG images into high-quality SVG vector graphics using Potrace."
        label_texte_description = ctk.CTkLabel(self.scrollable_frame, text=texte_description, wraplength=300, justify="left")
        label_texte_description.grid(row=2, column=0, pady=(5, 10), padx=10, sticky="w")

        label_titre_parametre = ctk.CTkLabel(
            self.scrollable_frame,
            text="Settings",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="center",
            justify="center"
        )
        label_titre_parametre.grid(row=3, column=0, pady=(0, 5), padx=10, sticky="ew")

        current_row = 4

        def add_parameters(parent, titre, description, row):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.grid(row=row, column=0, padx=10, pady=(5, 10), sticky="ew")
            frame.columnconfigure(0, weight=1)

            label_titre = ctk.CTkLabel(frame, text=titre, font=ctk.CTkFont(size=14, weight="bold"), anchor="w", justify="left")
            label_titre.grid(row=0, column=0, sticky="w")

            label_desc = ctk.CTkLabel(frame, text=description, wraplength=300, justify="left")
            label_desc.grid(row=1, column=0, sticky="w")

        params = [
            ("Threshold", "Manual binarization threshold. Pixels above become white, below become black."),
            ("Threshold Auto", "Enables automatic detection of the ideal threshold for binarization."),
            ("Invert", "Inverts the colors of the image before vectorization (black becomes white and vice versa)."),
            ("Turdsize", "Ignores small objects below this size (in pixels). Higher value = less noise. Preview not available: operation on SVG only!"),
            ("Alphamax", "Controls the curvature of vector contours. Higher value = smoother contours. Preview not available: operation on SVG only!")
        ]

        for titre, desc in params:
            add_parameters(self.scrollable_frame, titre, desc, current_row)
            current_row += 1

        spacer = ctk.CTkLabel(self.scrollable_frame, text="")
        spacer.grid(row=99, column=0, sticky="nswe")

        def open_paypal():
            webbrowser.open("https://www.paypal.com/donate/?hosted_button_id=6TCT576QMTBAL")

        paypal_image = ctk.CTkImage(
            light_image=Image.open(resource_path("interface/assets/paypal.png")),
            dark_image=Image.open(resource_path("interface/assets/paypal.png")),
            size=(200, 78.5)
        )

        paypal_button = ctk.CTkButton(
            self.scrollable_frame, image=paypal_image, text="", command=open_paypal,
            width=200, height=78.5, fg_color="transparent", hover=False
        )
        paypal_button.grid(row=100, column=0, pady=20)

