import customtkinter as ctk
from PIL import Image
import webbrowser

class LeftFrame(ctk.CTkFrame):
    """Zone de gauche contenant la documentation."""
    def __init__(self, parent):
        super().__init__(parent, width=400)
        self.build()

    def build(self):
        # Titre
        titre = ctk.CTkLabel(self, text="About the Software", font=ctk.CTkFont(size=18, weight="bold"))
        titre.pack(pady=(10, 5))

        # Description
        lebel_titre_description = ctk.CTkLabel(
            self, text="Description",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lebel_titre_description.pack(pady=(0, 5))

        texte_description = "PixelToPath transforms your PNG images into high-quality SVG vector graphics using Potrace."

        label_texte_description = ctk.CTkLabel(
            self, text=texte_description,
            wraplength=260, justify="left"
        )
        label_texte_description.pack(pady=(5, 10))

        # Paramètres
        label_titre_parametre = ctk.CTkLabel(
            self, text="Settings",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        label_titre_parametre.pack(pady=(0, 5))

        def add_parameters(parent, titre, description):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(anchor="w", padx=10, pady=(5, 10), fill="x")

            label_titre = ctk.CTkLabel(
                frame, text=titre,
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w", justify="left"
            )
            label_titre.pack(anchor="w")

            label_desc = ctk.CTkLabel(
                frame, text=description,
                wraplength=260, justify="left"
            )
            label_desc.pack(anchor="w")

        add_parameters(self, "Threshold", "Manual binarization threshold. Pixels above become white, below become black.")
        add_parameters(self, "Threshold Auto", "Enables automatic detection of the ideal threshold for binarization.")
        add_parameters(self, "Invert", "Inverts the colors of the image before vectorization (black becomes white and vice versa).")
        add_parameters(self, "Turdsize", "Ignores small objects below this size (in pixels). Higher value = less noise. Preview not available: operation on SVG only!")
        add_parameters(self, "Alphamax", "Controls the curvature of vector contours. Higher value = smoother contours. Preview not available: operation on SVG only!")

        # Spacer pour pousser le bouton en bas
        spacer = ctk.CTkLabel(self, text="")
        spacer.pack(expand=True)

        # Ouvre le lien PayPal dans le navigateur
        def open_paypal():
            webbrowser.open("https://www.paypal.com/donate/?hosted_button_id=6TCT576QMTBAL")

        # Charge l'image du bouton PayPal
        paypal_image = ctk.CTkImage(
            light_image=Image.open("interface/assets/paypal.png"),
            dark_image=Image.open("interface/assets/paypal.png"),
            size=(200, 78.5)
        )

        # Bouton cliquable
        paypal_button = ctk.CTkButton(
            self, image=paypal_image,
            text="", command=open_paypal,
            width=200, height=78.5, fg_color="transparent", hover=False
        )
        paypal_button.pack(pady=20)