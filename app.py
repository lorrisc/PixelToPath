import customtkinter as ctk
from tkinterdnd2 import TkinterDnD
import tkinter as tk

import os
import tempfile

from interface.LeftFrame import LeftFrame
from interface.RightFrame import RightFrame
from interface.utils import resource_path

# Configuration générale
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme(resource_path("interface/themes/yellow.json"))

class App(TkinterDnD.Tk):
    """Fenêtre principale."""
    def __init__(self):
        super().__init__()
        self.title("PixelToPath")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        app_width = int(screen_width * 0.8)
        app_height = int(screen_height * 0.8)

        self.geometry(f"{app_width}x{app_height}+30+30")

        # Création d'un répertoire temporaire pour l'application
        self.app_temp_dir = os.path.join(tempfile.gettempdir(), "PixelToPath")
        os.makedirs(self.app_temp_dir, exist_ok=True)

        self.build_interface()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def build_interface(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        frame_principal = ctk.CTkFrame(self, fg_color="#ebebeb")
        frame_principal.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame_principal.columnconfigure(0, weight=1)
        frame_principal.columnconfigure(1, weight=5)
        frame_principal.rowconfigure(0, weight=1)

        self.doc_frame = LeftFrame(frame_principal)
        self.doc_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.right_frame = RightFrame(frame_principal, app_temp_dir=self.app_temp_dir)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.configure(fg_color="#ebebeb")

        # frame_principal = ctk.CTkFrame(self, fg_color="#ebebeb")
        # frame_principal.pack(fill="both", expand=True, padx=10, pady=10)

        # self.doc_frame = LeftFrame(frame_principal)
        # self.doc_frame.configure(fg_color="#dbdbdb")  # gauche gris foncé
        # self.doc_frame.pack(side="left", fill="y", padx=(0, 10))

        # self.right_frame = RightFrame(frame_principal, app_temp_dir=self.app_temp_dir)
        # self.right_frame.configure(fg_color="#ebebeb")  # droite même couleur que fond app
        # self.right_frame.pack(side="right", fill="both", expand=True)

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

    icon_path = resource_path("interface/assets/app_icon.png")

    icon = tk.PhotoImage(file=icon_path)
    app.iconphoto(True, icon)

    app._icon = icon

    app.mainloop()