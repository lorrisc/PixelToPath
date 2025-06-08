import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter import filedialog
from tkinterdnd2 import DND_FILES

import uuid
import os
import shutil
import subprocess

from moteur.image_utils import png_to_pbm, optimize_svg
from interface.utils import resource_path

gtk_bin_path = resource_path("bin/gtk-bin")

# Ajoute gtk-bin au PATH pour que les DLL soient détectées
os.environ["PATH"] = gtk_bin_path + os.pathsep + os.environ.get("PATH", "")

import cairosvg

class RightFrame(ctk.CTkFrame):
    """Zone de droite avec les 3 espaces (configuration, btn execution, rendu)."""

    def __init__(self, parent, app_temp_dir):
        super().__init__(parent)
        self.app_temp_dir = app_temp_dir
        self.temp_pbm_path = None # Chemin temporaire pour le fichier PBM
        self.loaded_image_path = None  # Chemin de l'image chargée
        self.temp_svg_path = None  # Chemin temporaire pour le fichier SVG
        self.build()

    def build(self):
        self.build_espace1()
        self.build_espace2()
        self.build_espace3()
        self.build_espace4()

    def build_espace1(self):
        espace1 = ctk.CTkFrame(self, height=300)
        espace1.configure(fg_color="#ebebeb")
        espace1.pack(fill="x", pady=0, padx=10)

        # Container horizontal qui contiendra dropzone, contrôles, preview
        container = ctk.CTkFrame(espace1)
        container.configure(fg_color="#ebebeb")
        container.pack(fill="x", expand=True)

        # Construire les élements de l'espace 1
        self.build_espace1_dropzone(container)
        self.build_espace1_controls(container)
        self.build_espace1_preview(container)


    def build_espace1_dropzone(self, parent):
        self.dropzone_frame = ctk.CTkFrame(parent, width=300, height=300, fg_color="#dbdbdb")
        self.dropzone_frame.pack(side="left", padx=10, pady=0)
        self.dropzone_frame.pack_propagate(False)  # Fixe la taille du frame

        self.dropzone_label = ctk.CTkLabel(
            self.dropzone_frame,
            text="Glissez un PNG ici\nou cliquez pour choisir",
            justify="center"
        )
        self.dropzone_label.pack(expand=True)

        # Clic sur dropzone pour ouvrir dialog fichier
        self.dropzone_frame.bind("<Button-1>", self.load_image)
        self.dropzone_label.bind("<Button-1>", self.load_image)

        # Activation du drag-and-drop
        self.dropzone_frame.drop_target_register(DND_FILES)
        self.dropzone_frame.dnd_bind("<<Drop>>", self.on_file_drop)


    def build_espace1_controls(self, parent):
        controls_frame = ctk.CTkFrame(parent, width=300, fg_color="#ebebeb")
        controls_frame.pack(side="left", fill="y", padx=10, pady=0)
        controls_frame.pack_propagate(False)

        # Slider 1 : Seuil (Threshold)
        label3 = ctk.CTkLabel(controls_frame, text="Seuil (Threshold)")
        label3.pack(anchor="w", pady=(5,0))
        self.slider_threshold = ctk.CTkSlider(controls_frame, from_=0, to=255, number_of_steps=255)
        self.slider_threshold.set(128)
        self.slider_threshold.pack(fill="x", pady=(0,10))
        self.slider_threshold.bind("<ButtonRelease-1>", lambda e: self.update_preview())

        # Checkbox 1 : Seuil automatique
        self.checkbox_auto_threshold = ctk.CTkCheckBox(controls_frame, text="Seuil automatique")
        self.checkbox_auto_threshold.pack(anchor="w", pady=5)
        self.checkbox_auto_threshold.configure(command=self.update_preview)

        # Checkbox 2 : Inverser les couleurs
        self.checkbox_invert = ctk.CTkCheckBox(controls_frame, text="Inverser les couleurs")
        self.checkbox_invert.pack(anchor="w", pady=5)
        self.checkbox_invert.configure(command=self.update_preview)

        # Slider 2 : Taille minimale (Turdsize)
        label1 = ctk.CTkLabel(controls_frame, text="Taille minimale (Turdsize)")
        label1.pack(anchor="w", pady=(45,0))
        self.slider_turdsize = ctk.CTkSlider(controls_frame, from_=0, to=10, number_of_steps=100)
        self.slider_turdsize.set(2)
        self.slider_turdsize.pack(fill="x", pady=(0,10))

        # Slider 3 : Lissage (Alphamax)
        label2 = ctk.CTkLabel(controls_frame, text="Lissage (Alphamax)")
        label2.pack(anchor="w", pady=(5,0))
        self.slider_alphamax = ctk.CTkSlider(controls_frame, from_=0, to=1.334, number_of_steps=1000)
        self.slider_alphamax.set(1)
        self.slider_alphamax.pack(fill="x", pady=(0,10))


    def build_espace1_preview(self, parent):
        preview_frame = ctk.CTkFrame(parent, width=300, height=300, fg_color="#dbdbdb")
        preview_frame.pack(side="left", padx=10, pady=0)
        preview_frame.pack_propagate(False)

        self.preview_label = ctk.CTkLabel(preview_frame, text="Prévisualisation")
        self.preview_label.pack(expand=True)


    def load_image_from_path(self, filepath):
        if not filepath:
            return

        self.loaded_image_path = filepath

        # Charger l'image et conserver le ratio
        image = Image.open(filepath)
        image = image.convert("RGBA")
        image.thumbnail((280, 280), Image.Resampling.LANCZOS)

        # Créer un fond pour centrer l'image
        bg = Image.new("RGBA", (280, 280), (219, 219, 219, 255))  # couleur dropzone
        x = (280 - image.width) // 2
        y = (280 - image.height) // 2
        bg.paste(image, (x, y), image)
        self.tk_image = ImageTk.PhotoImage(bg)

        # Mettre à jour la dropzone avec l'image
        self.dropzone_label.configure(image=self.tk_image, text="")

        # Créer un fichier temporaire pour la sortie PBM
        self.temp_pbm_path = os.path.join(self.app_temp_dir, f"{uuid.uuid4().hex}.pbm")
        with open(self.temp_pbm_path, "wb") as f:
            pass

        self.update_preview()

    def load_image(self, event=None):
        filepath = filedialog.askopenfilename(filetypes=[("PNG files", "*.png")])
        self.load_image_from_path(filepath)

    def on_file_drop(self, event):
        # Nettoie le chemin de fichier
        filepath = event.data.strip("{}")

        if filepath.lower().endswith(".png"):
            # Remplace le filedialog : injecte manuellement le path
            self.load_image_from_path(filepath)
        else:
            self.error_label.configure(text="Seuls les fichiers PNG sont acceptés")

    def update_preview(self):
        if not self.loaded_image_path or not self.temp_pbm_path:
            return

        # Récupérer les paramètres actuels depuis sliders/checks
        threshold = self.slider_threshold.get()
        auto_threshold = self.checkbox_auto_threshold.get()
        invert_colors = self.checkbox_invert.get()

        threshold_param = "auto" if auto_threshold else threshold

        png_to_pbm(
            png_path=self.loaded_image_path,
            pbm_path=self.temp_pbm_path,
            threshold=threshold_param,
            invert=invert_colors,
            preview=True
        )

        # Charger l'image PBM de sortie et afficher dans preview
        if os.path.exists(self.temp_pbm_path):
            img = Image.open(self.temp_pbm_path)
            img = img.convert("L")
            img.thumbnail((280, 280), Image.Resampling.LANCZOS)

            # Créer un fond pour centrer l'image
            bg = Image.new("L", (280, 280), 219)
            x = (280 - img.width) // 2
            y = (280 - img.height) // 2
            bg.paste(img, (x, y))
            self.tk_preview_image = ImageTk.PhotoImage(bg)
            self.preview_label.configure(image=self.tk_preview_image, text="")

    def build_espace2(self):
        espace2 = ctk.CTkFrame(self)
        espace2.configure(fg_color="#ebebeb")
        espace2.pack(fill="x", padx=20, pady=30, anchor="w")

        # Bouton centré
        convert_button = ctk.CTkButton(
            espace2,
            text="Convertir en SVG",
            height=40,
            width=200,
            command=self.convert_to_svg 
        )
        convert_button.pack(pady=0, anchor="w")

    def convert_to_svg(self):
        if not self.temp_pbm_path:
            self.error_label.configure(text="Aucun fichier PBM à convertir.")
            return
        
        # Récupérer les paramètres actuels depuis sliders/checks
        turdsize = self.slider_turdsize.get()
        alphamax = self.slider_alphamax.get()

        # Fichier SVG temporaire
        self.temp_svg_path = os.path.join(self.app_temp_dir, f"{uuid.uuid4().hex}.pbm")
        with open(self.temp_svg_path, "wb") as f:
            pass

        self.potrace_path = resource_path("bin/potrace-bin/potrace.exe")

        cmd = [
            self.potrace_path,
            '--svg',
            '--output', self.temp_svg_path,
            '--turdsize', str(turdsize),
            '--alphamax', str(alphamax),
            '--tight',
            self.temp_pbm_path
        ]

        # Exécuter la commande potrace
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.error_label.configure(text=f"Erreur durant la vectorisation.")
            return

        status_optimisation = optimize_svg(self.temp_svg_path)
        if not status_optimisation:
            self.error_label.configure(text="Erreur lors de l'optimisation du SVG.")
            return

        # Afficher le SVG dans l'espace 3
        self.render_svg_preview()

    def build_espace3(self):
        espace3 = ctk.CTkFrame(self)
        espace3.configure(fg_color="#ebebeb")
        espace3.pack(fill="x", expand=False, padx=20, pady=0, anchor="w")

        # Label pour afficher l'aperçu PNG généré depuis le SVG
        self.svg_preview_label = ctk.CTkLabel(espace3, text="Aperçu SVG non disponible")
        self.svg_preview_label.pack(expand=True, pady=0, anchor="w")

        # Bouton de téléchargement
        download_button = ctk.CTkButton(
            espace3,
            text="Télécharger le SVG",
            command=self.download_svg,
            width=180,
            height=36
        )
        download_button.pack(pady=15, anchor="w")

    def render_svg_preview(self):
        if not self.temp_svg_path:
            self.svg_preview_label.configure(image=None, text="Aucun SVG généré")
            return

        try:
            # Convertir le SVG en PNG temporaire avec cairosvg
            temp_png_path = os.path.join(self.app_temp_dir, f"{uuid.uuid4().hex}.pbm")
            with open(temp_png_path, "wb") as f:
                cairosvg.svg2png(url=self.temp_svg_path, write_to=temp_png_path)
                pass

            # Charger le PNG et le redimensionner sans déformer
            img = Image.open(temp_png_path)
            img.thumbnail((280, 280), Image.Resampling.LANCZOS)

            # Centrer sur un fond gris si besoin
            bg = Image.new("RGBA", (280, 280), (219, 219, 219, 255))
            x = (280 - img.width) // 2
            y = (280 - img.height) // 2
            bg.paste(img, (x, y), img if img.mode == "RGBA" else None)

            self.tk_svg_preview = ImageTk.PhotoImage(bg)
            self.svg_preview_label.configure(image=self.tk_svg_preview, text="")

            # Nettoyer le PNG temporaire
            os.remove(temp_png_path)
        except Exception as e:
            self.svg_preview_label.configure(image=None, text=f"Erreur SVG : {e}")


    def download_svg(self):
        if not hasattr(self, 'temp_svg_path') or not self.temp_svg_path:
            self.error_label.configure(text="Aucun SVG généré à télécharger.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("Fichiers SVG", "*.svg")],
            title="Enregistrer sous..."
        )

        if save_path:
            shutil.copyfile(self.temp_svg_path, save_path)


    def build_espace4(self):
        espace4 = ctk.CTkFrame(self)
        espace4.configure(fg_color="#ebebeb")
        espace4.pack(fill="x", padx=20, pady=30, anchor="w")

        # Message d'erreur
        self.error_label = ctk.CTkLabel(espace4, text="", text_color="red")
        self.error_label.pack(expand=True, pady=0, anchor="w")

        