"""Palette de thème dérivée de la couleur choisie par le commerçant.

Le commerçant ne choisit qu'une couleur principale : toutes les nuances et les
couleurs de texte en sont calculées, avec un contraste garanti. Laisser
choisir librement la couleur du texte produisait des combinaisons illisibles
(texte blanc sur fond blanc) et ne remplaçait que trois variables sur les huit
utilisées par la feuille de style, d'où des boutons restés verts.
"""
from __future__ import annotations

DEFAULT_BRAND = "#16824c"

# Texte foncé plutôt que noir pur : plus doux, contraste équivalent.
DARK_INK = "#12211b"
LIGHT_INK = "#ffffff"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"Couleur hexadécimale invalide : {value!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(c))) for c in rgb))


def _mix(color: tuple[int, int, int], target: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    """Rapproche ``color`` de ``target`` de ``ratio`` (0 = inchangé, 1 = target)."""
    return tuple(c + (t - c) * ratio for c, t in zip(color, target))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Luminance relative WCAG, base du calcul de contraste."""
    channels = []
    for c in rgb:
        s = c / 255
        channels.append(s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """Rapport de contraste WCAG entre deux couleurs (1 = identiques, 21 = max)."""
    la = _relative_luminance(_hex_to_rgb(a))
    lb = _relative_luminance(_hex_to_rgb(b))
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def readable_ink(background: str) -> str:
    """Choisit entre encre claire et foncée celle qui contraste le mieux."""
    return LIGHT_INK if contrast_ratio(background, LIGHT_INK) >= contrast_ratio(background, DARK_INK) else DARK_INK


def _ensure_contrast(base: tuple[int, int, int], ink: str, target: float = 4.5) -> tuple[int, int, int]:
    """Assombrit ou éclaircit ``base`` jusqu'à lire ``ink`` dessus.

    La couleur porte le texte des boutons et de la barre supérieure. Beaucoup
    de teintes moyennes plaisantes (turquoise, rose) n'atteignent le seuil avec
    aucune encre : on les décale du minimum nécessaire, la teinte reste
    reconnaissable.
    """
    toward = (0, 0, 0) if ink == LIGHT_INK else (255, 255, 255)
    adjusted = base
    for _ in range(20):
        if contrast_ratio(_rgb_to_hex(adjusted), ink) >= target:
            break
        adjusted = _mix(adjusted, toward, 0.06)
    return adjusted


def build_palette(brand: str | None) -> dict[str, str]:
    """Décline une couleur de marque en palette complète et lisible."""
    try:
        base = _hex_to_rgb(brand or DEFAULT_BRAND)
    except ValueError:
        base = _hex_to_rgb(DEFAULT_BRAND)

    white = (255, 255, 255)
    black = (0, 0, 0)

    # L'encre est choisie sur la couleur demandée, puis celle-ci est ajustée
    # pour que ce choix soit effectivement lisible.
    base = _ensure_contrast(base, readable_ink(_rgb_to_hex(base)))
    brand_hex = _rgb_to_hex(base)

    palette = {
        "brand": brand_hex,
        "brand-600": _rgb_to_hex(_mix(base, black, 0.15)),
        "brand-700": _rgb_to_hex(_mix(base, black, 0.30)),
        "brand-100": _rgb_to_hex(_mix(base, white, 0.80)),
        "brand-050": _rgb_to_hex(_mix(base, white, 0.90)),
        "brand-light": _rgb_to_hex(_mix(base, white, 0.90)),
        "on-brand": readable_ink(brand_hex),
        "accent": brand_hex,
        "grad": (
            f"linear-gradient(135deg, {_rgb_to_hex(_mix(base, white, 0.10))} 0%, "
            f"{_rgb_to_hex(_mix(base, black, 0.25))} 100%)"
        ),
    }

    # Les teintes claires servent de fond à du texte « brand-700 » : si le
    # contraste est insuffisant (couleur très pâle), on assombrit le texte.
    if contrast_ratio(palette["brand-050"], palette["brand-700"]) < 4.5:
        palette["brand-700"] = DARK_INK
    return palette


def theme_style(shop) -> str:
    """Bloc ``<style>`` à injecter dans les pages d'une boutique."""
    brand = getattr(shop, "theme_color", None) if shop is not None else None
    palette = build_palette(brand)
    declarations = " ".join(f"--{name}: {value};" for name, value in palette.items())
    return f"<style>:root{{{declarations}}}</style>"
