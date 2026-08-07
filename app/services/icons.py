"""Jeu d'icônes vectorielles de l'interface.

Les gabarits utilisaient des emojis (🛍️, ⚠️, 🟢…). Ils sont rendus par la
police du système : le dessin change d'un appareil à l'autre, le style est
daté sur beaucoup d'entre eux, ils ignorent la couleur du texte et ne
s'alignent pas sur la grille typographique.

Ces tracés sont dessinés sur une grille de 24, au trait, et héritent de
``currentColor`` : une icône prend donc la couleur de son contexte. Le SVG est
inséré dans la page (aucune requête réseau, compatible avec la politique de
sécurité du contenu qui interdit les ressources externes) et pèse environ
150 octets une fois compressé.
"""
from __future__ import annotations

from markupsafe import Markup

# Tracés : seul le contenu intérieur du <svg>, sur une grille 0 0 24 24.
_PATHS: dict[str, str] = {
    # --- Commerce ---
    "bag": '<path d="M6 2h12l2 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8l2-6Z"/><path d="M4 8h16"/><path d="M9 12a3 3 0 0 0 6 0"/>',
    "store": '<path d="M3 9 4.5 4h15L21 9"/><path d="M3 9h18v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9Z"/><path d="M9 21v-6h6v6"/>',
    "cart": '<circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/><path d="M2 3h3l2.4 11.2a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 2-1.55L21 7H6"/>',
    "package": '<path d="M21 8 12 3 3 8v8l9 5 9-5V8Z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>',
    "tag": '<path d="M20.6 13.4 12 22l-9-9V3h10l7.6 7.6a2 2 0 0 1 0 2.8Z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
    "receipt": '<path d="M5 2h14v20l-2.8-1.6L13.4 22l-2.8-1.6L7.8 22 5 20.4V2Z"/><path d="M9 7h6M9 11h6M9 15h4"/>',
    # --- Argent ---
    "wallet": '<path d="M3 7a2 2 0 0 1 2-2h13v4"/><path d="M3 7v11a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2H5"/><circle cx="16.5" cy="13.5" r="1.2"/>',
    "credit-card": '<rect x="2" y="5" width="20" height="14" rx="2.5"/><path d="M2 10h20"/><path d="M6 15h4"/>',
    "coins": '<ellipse cx="9" cy="6" rx="6.5" ry="3"/><path d="M2.5 6v5c0 1.7 2.9 3 6.5 3s6.5-1.3 6.5-3V6"/><path d="M8.5 14v4c0 1.7 2.9 3 6.5 3s6.5-1.3 6.5-3v-5"/><ellipse cx="15" cy="13" rx="6.5" ry="3"/>',
    "trending-up": '<path d="M22 7 13.5 15.5l-4-4L2 19"/><path d="M16 7h6v6"/>',
    # --- Communication ---
    "message": '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.9 8.9 0 0 1-4-.9L3 21l1.9-4.6A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z"/>',
    "phone": '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18.5h2"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7L11.5 5"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7L12.5 19"/>',
    # --- Média ---
    "image": '<rect x="3" y="3" width="18" height="18" rx="2.5"/><circle cx="8.5" cy="8.5" r="1.6"/><path d="m21 15-5-5L5 21"/>',
    "camera": '<path d="M3 8h3l2-3h8l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13.5" r="3.8"/>',
    "palette": '<path d="M12 21a9 9 0 1 1 9-9c0 2-1.6 2.6-3 2.6h-1.6a2 2 0 0 0-1.3 3.5 1.8 1.8 0 0 1-1.2 3Z"/><circle cx="7.5" cy="12" r="1.2"/><circle cx="10" cy="7.5" r="1.2"/><circle cx="15" cy="8" r="1.2"/>',
    # --- Système ---
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    "shield": '<path d="M12 22s8-3.5 8-9.5V5.5L12 2 4 5.5V12.5C4 18.5 12 22 12 22Z"/><path d="m9 12 2 2 4-4"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1v.3a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-2.8-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3.5 14H3a2 2 0 1 1 0-4h.2A1.6 1.6 0 0 0 4.3 7.2l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 10 3.5V3a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7h.4a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.4 1.2Z"/>',
    "trash": '<path d="M4 6h16"/><path d="M9 6V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V6"/><path d="M6.5 6 7.5 20a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 6"/><path d="M10 11v6M14 11v6"/>',
    "save": '<path d="M4 4h12l4 4v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4Z"/><path d="M8 4v6h7V4"/><path d="M8 21v-6h8v6"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    # --- Retours d'information ---
    "alert": '<path d="M10.3 3.9 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="9.5"/><path d="M12 16v-4.5"/><path d="M12 8h.01"/>',
    "bulb": '<path d="M9 18h6"/><path d="M10 21.5h4"/><path d="M12 2.5a6.5 6.5 0 0 0-3.8 11.8c.5.4.8 1 .8 1.7h6c0-.7.3-1.3.8-1.7A6.5 6.5 0 0 0 12 2.5Z"/>',
    "check": '<path d="m4 12.5 5 5L20 6.5"/>',
    "check-circle": '<circle cx="12" cy="12" r="9.5"/><path d="m8 12.2 2.8 2.8L16 9.5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "help": '<circle cx="12" cy="12" r="9.5"/><path d="M9.2 9.3a2.9 2.9 0 0 1 5.6 1c0 1.9-2.8 2.9-2.8 2.9"/><path d="M12 17h.01"/>',
    "star": '<path d="m12 2.8 2.9 5.9 6.5.95-4.7 4.6 1.1 6.5-5.8-3.1-5.8 3.1 1.1-6.5-4.7-4.6 6.5-.95L12 2.8Z"/>',
    "award": '<circle cx="12" cy="9" r="6"/><path d="m8.2 14.3-1.4 7.2 5.2-2.8 5.2 2.8-1.4-7.2"/>',
    # --- Navigation ---
    "arrow-left": '<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "chevron-right": '<path d="m9 6 6 6-6 6"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3.2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    "home": '<path d="M3 10.5 12 4l9 6.5"/><path d="M5 10v9h14v-9"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    # --- Réseaux ---
    # Glyphe officiel, en aplat : la version au trait devenait illisible sous
    # 16 px, le combiné se refermant sur la bulle.
    "whatsapp": (
        '<path d="M17.47 14.38c-.29-.15-1.7-.84-1.97-.93-.26-.1-.45-.15-.64.14'
        '-.19.29-.73.93-.9 1.12-.17.19-.33.21-.61.07-1.66-.83-2.75-1.48-3.84-3.36'
        '-.29-.5.29-.46.83-1.53.09-.19.05-.35-.02-.5-.07-.14-.64-1.55-.88-2.12'
        '-.23-.55-.47-.48-.64-.49h-.55c-.19 0-.5.07-.76.36-.26.29-1 .98-1 2.38'
        's1.02 2.76 1.17 2.95c.14.19 2.01 3.08 4.88 4.32 1.82.78 2.53.85 3.44.71'
        '.55-.08 1.7-.69 1.94-1.37.24-.67.24-1.25.17-1.37-.07-.12-.26-.19-.55-.33Z"/>'
        '<path d="M12 2.04a9.9 9.9 0 0 0-8.5 15.02L2.05 22l5.06-1.32A9.9 9.9 0 1 0 12 2.04Z'
        'm0 18.05c-1.6 0-3.1-.43-4.4-1.18l-.32-.19-3.02.79.8-2.94-.2-.31a8.2 8.2 0 1 1 7.14 3.83Z"/>'
    ),
}

# Icônes en aplat plutôt qu'au trait (logos, pictogrammes pleins).
_SOLID = {"whatsapp"}

# Alias : plusieurs noms parlants pointent vers le même tracé.
_ALIASES = {
    "shop": "store", "basket": "cart", "money": "wallet", "chat": "message",
    "warning": "alert", "photo": "image", "stats": "chart", "delete": "trash",
    "back": "arrow-left", "next": "arrow-right", "ok": "check-circle",
}


def icon(name: str, size: int = 20, cls: str = "", stroke: float = 1.8) -> Markup:
    """SVG en ligne, hérite de ``currentColor``.

    Un nom inconnu ne rend rien plutôt que de faire échouer la page : une icône
    manquante ne justifie pas une erreur 500.
    """
    key = _ALIASES.get(name, name)
    path = _PATHS.get(key)
    if path is None:
        return Markup("")
    classes = f"ic-svg {cls}".strip()
    if key in _SOLID:
        paint = 'fill="currentColor" stroke="none"'
    else:
        paint = (
            f'fill="none" stroke="currentColor" stroke-width="{stroke}" '
            'stroke-linecap="round" stroke-linejoin="round"'
        )
    return Markup(
        f'<svg class="{classes}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'{paint} aria-hidden="true" focusable="false">{path}</svg>'
    )


def icon_names() -> list[str]:
    """Noms disponibles, alias compris (utilisé par les tests)."""
    return sorted(set(_PATHS) | set(_ALIASES))
