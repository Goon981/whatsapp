"""Palette de thème dérivée de la couleur choisie par le commerçant.

Le commerçant ne choisit qu'une couleur principale : toutes les nuances et les
couleurs de texte en sont calculées, avec un contraste garanti. Laisser
choisir librement la couleur du texte produisait des combinaisons illisibles
(texte blanc sur fond blanc) et ne remplaçait que trois variables sur les huit
utilisées par la feuille de style, d'où des boutons restés verts.

Chaque jeton porte un rôle unique, et un seul :

==================  ==========================================================
``--brand``         aplat principal (barre supérieure, boutons pleins)
``--on-brand``      texte posé sur ``--brand`` et ``--brand-700``
``--brand-600``     texte et icônes de marque posés sur ``--surface``
``--brand-700``     aplat profond (barre de panier, bouton « dark »)
``--brand-ink``     texte de marque posé sur ``--brand-050`` / ``--brand-100``
``--brand-050/100`` surfaces teintées
==================  ==========================================================

``--brand-700`` cumulait auparavant deux rôles opposés — couleur de texte sur
fond clair *et* couleur de fond sous texte clair. Les deux coïncident tant que
la page est claire, mais s'excluent dès que le fond s'assombrit : d'où
``--brand-ink``, qui isole l'usage « texte ».
"""
from __future__ import annotations

DEFAULT_BRAND = "#16824c"

# Texte foncé plutôt que noir pur : plus doux, contraste équivalent.
DARK_INK = "#12211b"
LIGHT_INK = "#ffffff"

# Neutres du mode sombre, tenus identiques à ceux de la feuille de style : les
# nuances de marque sont mélangées à ces fonds, pas au blanc.
DARK_BG = "#0f1412"
DARK_SURFACE = "#171d1a"

LIGHT_SURFACE = "#ffffff"

# Seuils WCAG 2.1 : 4.5 pour du texte courant, 3.0 pour un aplat d'interface.
TEXT_CONTRAST = 4.5
UI_CONTRAST = 3.0


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


WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def _shift_until(
    color: tuple[int, int, int],
    against: str,
    target: float,
    toward: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Décale ``color`` vers ``toward`` jusqu'à contraster avec ``against``.

    Beaucoup de teintes moyennes agréables (turquoise, rose) n'atteignent le
    seuil avec aucune encre : on les décale du minimum nécessaire, la teinte
    reste reconnaissable. La boucle est bornée — au pire on atteint ``toward``.
    """
    adjusted = color
    for _ in range(40):
        if contrast_ratio(_rgb_to_hex(adjusted), against) >= target:
            break
        adjusted = _mix(adjusted, toward, 0.05)
    return adjusted


def _ensure_contrast(base: tuple[int, int, int], ink: str, target: float = TEXT_CONTRAST) -> tuple[int, int, int]:
    """Assombrit ou éclaircit ``base`` jusqu'à lire ``ink`` dessus."""
    return _shift_until(base, ink, target, BLACK if ink == LIGHT_INK else WHITE)


def _base_rgb(brand: str | None) -> tuple[int, int, int]:
    try:
        return _hex_to_rgb(brand or DEFAULT_BRAND)
    except ValueError:
        return _hex_to_rgb(DEFAULT_BRAND)


def build_palette(brand: str | None) -> dict[str, str]:
    """Décline une couleur de marque en palette claire complète et lisible."""
    base = _base_rgb(brand)

    # L'encre est choisie sur la couleur demandée, puis celle-ci est ajustée
    # pour que ce choix soit effectivement lisible.
    base = _ensure_contrast(base, readable_ink(_rgb_to_hex(base)))
    brand_hex = _rgb_to_hex(base)

    tint_050 = _mix(base, WHITE, 0.92)
    tint_100 = _mix(base, WHITE, 0.82)

    # Texte de marque sur fond blanc, puis sur la teinte la plus soutenue :
    # une seule vérification suffirait pour un vert foncé, pas pour un jaune.
    on_surface = _shift_until(_mix(base, BLACK, 0.15), LIGHT_SURFACE, TEXT_CONTRAST, BLACK)
    on_tint = _shift_until(_mix(base, BLACK, 0.30), _rgb_to_hex(tint_100), TEXT_CONTRAST, BLACK)

    # L'aplat profond porte ``--on-brand``, l'encre calculée pour ``--brand`` :
    # c'est contre celle-ci qu'il doit contraster, et non contre l'encre qu'il
    # appellerait pour lui-même. Un rose vif donnait sinon une barre de panier
    # à 3.5:1, sous le seuil lisible.
    ink = readable_ink(brand_hex)
    deep = _ensure_contrast(_mix(base, BLACK, 0.28), ink)

    return {
        "brand": brand_hex,
        "brand-600": _rgb_to_hex(on_surface),
        "brand-700": _rgb_to_hex(deep),
        "brand-ink": _rgb_to_hex(on_tint),
        "brand-100": _rgb_to_hex(tint_100),
        "brand-050": _rgb_to_hex(tint_050),
        "brand-light": _rgb_to_hex(tint_050),
        "on-brand": ink,
        "accent": brand_hex,
        "grad": (
            f"linear-gradient(135deg, {_rgb_to_hex(_mix(base, WHITE, 0.10))} 0%, "
            f"{_rgb_to_hex(_mix(base, BLACK, 0.25))} 100%)"
        ),
    }


def build_dark_palette(brand: str | None) -> dict[str, str]:
    """Même marque, déclinée pour un fond sombre.

    Les nuances claires sont mélangées à la surface sombre et non au blanc :
    réutiliser la palette claire posait des aplats presque blancs au milieu
    d'une page sombre, et rendait illisible le texte censé s'y inscrire.
    """
    base = _base_rgb(brand)

    # Un vert forêt disparaît sur un fond sombre : on l'éclaircit jusqu'à ce
    # qu'il se détache du fond, avant de choisir son encre.
    base = _shift_until(base, DARK_BG, UI_CONTRAST, WHITE)
    base = _ensure_contrast(base, readable_ink(_rgb_to_hex(base)))
    brand_hex = _rgb_to_hex(base)

    dark_surface = _hex_to_rgb(DARK_SURFACE)
    tint_050 = _mix(base, dark_surface, 0.88)
    tint_100 = _mix(base, dark_surface, 0.76)

    on_surface = _shift_until(_mix(base, WHITE, 0.25), DARK_SURFACE, TEXT_CONTRAST, WHITE)
    on_tint = _shift_until(_mix(base, WHITE, 0.35), _rgb_to_hex(tint_100), TEXT_CONTRAST, WHITE)

    # L'aplat profond doit rester distinct de ``--brand`` sans se rapprocher de
    # son encre : on le décale à l'opposé de celle-ci.
    ink = readable_ink(brand_hex)
    deep = _mix(base, WHITE if ink == DARK_INK else BLACK, 0.12)
    deep = _ensure_contrast(deep, ink)

    return {
        "brand": brand_hex,
        "brand-600": _rgb_to_hex(on_surface),
        "brand-700": _rgb_to_hex(deep),
        "brand-ink": _rgb_to_hex(on_tint),
        "brand-100": _rgb_to_hex(tint_100),
        "brand-050": _rgb_to_hex(tint_050),
        "brand-light": _rgb_to_hex(tint_050),
        "on-brand": ink,
        "accent": brand_hex,
        "grad": (
            f"linear-gradient(135deg, {_rgb_to_hex(_mix(base, WHITE, 0.16))} 0%, "
            f"{_rgb_to_hex(_mix(base, BLACK, 0.30))} 100%)"
        ),
    }


def _declarations(palette: dict[str, str]) -> str:
    return " ".join(f"--{name}: {value};" for name, value in palette.items())


def theme_style(shop) -> str:
    """Bloc ``<style>`` à injecter dans les pages d'une boutique.

    Les deux modes sont émis d'un coup : la palette est calculée côté serveur,
    qui ignore la préférence d'affichage du visiteur.
    """
    brand = getattr(shop, "theme_color", None) if shop is not None else None
    light = _declarations(build_palette(brand))
    dark = _declarations(build_dark_palette(brand))
    return (
        "<style>"
        f":root{{{light}}}"
        f"@media (prefers-color-scheme: dark){{:root{{{dark}}}}}"
        f':root[data-theme="dark"]{{{dark}}}'
        f':root[data-theme="light"]{{{light}}}'
        "</style>"
    )
