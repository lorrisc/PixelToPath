import customtkinter as ctk
from PIL import Image
import webbrowser
from interface.utils import resource_path

class LeftFrame(ctk.CTkFrame):
    """Zone de gauche contenant la documentation."""
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(99, weight=1)  # Le spacer pousse vers le bas
        self.build()

    def build(self):
        # Titre principal centré
        titre = ctk.CTkLabel(
            self,
            text="About the Software",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="center",
            justify="center"
        )
        titre.grid(row=0, column=0, pady=(10, 5), padx=10, sticky="ew")

        # Sous-titre 'Description' centré
        label_titre_description = ctk.CTkLabel(
            self,
            text="Description",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="center",
            justify="center"
        )
        label_titre_description.grid(row=1, column=0, pady=(0, 5), padx=10, sticky="ew")

        texte_description = "PixelToPath transforms your PNG images into high-quality SVG vector graphics using Potrace."
        label_texte_description = ctk.CTkLabel(self, text=texte_description, wraplength=300, justify="left")
        label_texte_description.grid(row=2, column=0, pady=(5, 10), padx=10, sticky="w")

        # Sous-titre 'Settings' centré
        label_titre_parametre = ctk.CTkLabel(
            self,
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
            add_parameters(self, titre, desc, current_row)
            current_row += 1

        # Spacer dynamique pour pousser le bouton vers le bas
        spacer = ctk.CTkLabel(self, text="")
        spacer.grid(row=99, column=0, sticky="nswe")  # push

        # PayPal
        def open_paypal():
            webbrowser.open("https://www.paypal.com/donate/?hosted_button_id=6TCT576QMTBAL")

        paypal_image = ctk.CTkImage(
            light_image=Image.open(resource_path("interface/assets/paypal.png")),
            dark_image=Image.open(resource_path("interface/assets/paypal.png")),
            size=(200, 78.5)
        )

        paypal_button = ctk.CTkButton(
            self, image=paypal_image, text="", command=open_paypal,
            width=200, height=78.5, fg_color="transparent", hover=False
        )
        paypal_button.grid(row=100, column=0, pady=20)
