import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES

from interface.LeftFrame import LeftFrame
from interface.RightFrame import RightFrame

import os
import tempfile

# Configuration générale
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("interface/themes/yellow.json")

class App(TkinterDnD.Tk):
    """Fenêtre principale."""
    def __init__(self):
        super().__init__()
        self.title("PixelToPath")
        self.geometry("1350x900+30+30")

        # Création d'un répertoire temporaire pour l'application
        self.app_temp_dir = os.path.join(tempfile.gettempdir(), "PixelToPath")
        os.makedirs(self.app_temp_dir, exist_ok=True)

        self.build_interface()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_interface(self):
        frame_principal = ctk.CTkFrame(self, fg_color="#ebebeb")
        frame_principal.pack(fill="both", expand=True, padx=10, pady=10)

        self.doc_frame = LeftFrame(frame_principal)
        self.doc_frame.configure(fg_color="#dbdbdb")  # gauche gris foncé
        self.doc_frame.pack(side="left", fill="y", padx=(0, 10))

        self.right_frame = RightFrame(frame_principal, app_temp_dir=self.app_temp_dir)
        self.right_frame.configure(fg_color="#ebebeb")  # droite même couleur que fond app
        self.right_frame.pack(side="right", fill="both", expand=True)

    def on_close(self):
        # Nettoyer les fichiers temporaires
        if os.path.exists(self.app_temp_dir):
            for file in os.listdir(self.app_temp_dir):
                path = os.path.join(self.app_temp_dir, file)
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"Erreur suppression {path} : {e}")
            try:
                os.rmdir(self.app_temp_dir)
            except OSError:
                pass  # Dossier non vide ou autre erreur

        self.destroy()  # Fermer la fenêtre


if __name__ == "__main__":
    app = App()

    # Favicon
    app.wm_iconbitmap("interface/assets/logo.ico")

    app.mainloop()