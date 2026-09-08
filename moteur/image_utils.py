"""Presets de conversion — données seules.

Les valeurs sont les kwargs bruts du moteur désigné par « colormode » :
vtracer pour « color », Potrace (turdsize/alphamax/opttolerance) pour
« binary ». La conversion effective vit dans core/convert_service
(dispatch unique interface / batch / hot folder / CLI).
"""

PRESETS = {
    # bw : Potrace exclusivement (le moteur binaire) — kwargs potrace.
    "bw": dict(
        colormode="binary",
        turdsize=2,
        alphamax=1.0,
        opttolerance=0.2,
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