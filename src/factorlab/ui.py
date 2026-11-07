"""Compatibilidade dos pontos de entrada; estilo centralizado em ui/."""

from factorlab.security import require_login
from ui.components import context_strip, top_bar, welcome_cards
from ui.theme import apply_theme

__all__ = ["setup_terminal", "context_strip", "welcome_cards"]


def setup_terminal(section):
    apply_theme()
    require_login()
    top_bar(section)
