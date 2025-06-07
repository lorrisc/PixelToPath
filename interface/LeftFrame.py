import customtkinter as ctk

class LeftFrame(ctk.CTkFrame):
    """Zone de gauche contenant la documentation."""
    def __init__(self, parent):
        super().__init__(parent, width=400)
        self.build()

    def build(self):
        # Titre
        titre = ctk.CTkLabel(self, text="À propos du logiciel", font=ctk.CTkFont(size=18, weight="bold"))
        titre.pack(pady=(10, 5))

        # Description
        lebel_titre_description = ctk.CTkLabel(
            self, text="Description",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lebel_titre_description.pack(pady=(0, 5))

        texte_description = "PixelToPath transforme vos images PNG en graphiques vectoriels SVG de haute qualité en utilisant Potrace. "

        label_texte_description = ctk.CTkLabel(
            self, text=texte_description,
            wraplength=260, justify="left"
        )
        label_texte_description.pack(pady=(5, 10))

        # Paramètres
        label_titre_parametre = ctk.CTkLabel(
            self, text="Paramètres",
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

        add_parameters(self, "Threshold", "Seuil de binarisation manuel. Les pixels au-dessus deviennent blancs, en dessous noirs.")
        add_parameters(self, "Threshold Auto", "Active la détection automatique du seuil idéal pour la binarisation.")
        add_parameters(self, "Invert", "Inverse les couleurs de l'image avant vectorisation (noir devient blanc et vice versa).")
        add_parameters(self, "Turdsize", "Ignore les petits objets en dessous de cette taille (en pixels). Valeur plus élevée = moins de bruit. Preview impossible : opération sur SVG uniquement !")
        add_parameters(self, "Alphamax", "Contrôle la courbure des contours vectoriels. Valeur plus élevée = contours plus lisses. Preview impossible : opération sur SVG uniquement !")