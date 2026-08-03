"""Génération de mini-graphiques SVG (courbe de ventes) sans dépendance JS.

Les points sont calculés côté serveur puis rendus en <polyline>/<path> dans les
templates. Compatible CSP stricte (aucun script, aucune ressource externe).
"""
from __future__ import annotations


def line_chart(values: list[int], width: int = 320, height: int = 90, pad: int = 6) -> dict:
    """Construit les données d'une courbe lissée à partir d'une série de valeurs.

    Retourne un dict prêt à l'emploi dans un template :
    ``{points, area, width, height, last_x, last_y}``.
    """
    n = len(values)
    if n == 0:
        values = [0]
        n = 1
    if n == 1:
        values = values * 2
        n = 2

    vmax = max(values)
    vmin = min(values)
    span = (vmax - vmin) or 1
    inner_w = width - pad * 2
    inner_h = height - pad * 2

    coords: list[tuple[float, float]] = []
    for i, v in enumerate(values):
        x = pad + (inner_w * i / (n - 1))
        # 0 en bas, max en haut
        y = pad + inner_h - (inner_h * (v - vmin) / span)
        coords.append((round(x, 1), round(y, 1)))

    points = " ".join(f"{x},{y}" for x, y in coords)
    # Zone remplie sous la courbe.
    area = (
        f"M {coords[0][0]},{height - pad} "
        + " ".join(f"L {x},{y}" for x, y in coords)
        + f" L {coords[-1][0]},{height - pad} Z"
    )
    return {
        "points": points,
        "area": area,
        "width": width,
        "height": height,
        "last_x": coords[-1][0],
        "last_y": coords[-1][1],
    }
