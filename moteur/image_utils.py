import vtracer

PRESETS = {
    "bw": dict(
        colormode="binary",
        mode="spline",
        filter_speckle=4,
        corner_threshold=60,
        length_threshold=4.0,
        splice_threshold=45,
        max_iterations=10,
        path_precision=3,
    ),
    "poster": dict(
        colormode="color",
        hierarchical="stacked",
        mode="spline",
        filter_speckle=4,
        color_precision=8,
        layer_difference=6,
        corner_threshold=60,
        length_threshold=4.0,
        splice_threshold=45,
        max_iterations=10,
        path_precision=3,
    ),
    "photo": dict(
        colormode="color",
        hierarchical="stacked",
        mode="spline",
        filter_speckle=10,
        color_precision=6,
        layer_difference=16,
        corner_threshold=60,
        length_threshold=4.0,
        splice_threshold=45,
        max_iterations=10,
        path_precision=3,
    ),
}


def convert_to_svg(input_path: str, output_path: str, **kwargs) -> None:
    """
    Convertit une image raster en SVG via vtracer.

    Args:
        input_path  : Chemin de l'image source (PNG, JPG, BMP, WebP…)
        output_path : Chemin de sortie .svg
        **kwargs    : Paramètres vtracer :
                        colormode        "color" | "binary"
                        hierarchical     "stacked" | "cutout"   (color seulement)
                        mode             "spline" | "polygon" | "none"
                        filter_speckle   int   (défaut 4)
                        color_precision  int   (défaut 6, color seulement)
                        layer_difference int   (défaut 16, color seulement)
                        corner_threshold int   (défaut 60)
                        length_threshold float (défaut 4.0)
                        max_iterations   int   (défaut 10)
                        splice_threshold int   (défaut 45)
                        path_precision   int   (défaut 3)

    Raises:
        Exception si vtracer échoue.
    """
    vtracer.convert_image_to_svg_py(input_path, output_path, **kwargs)