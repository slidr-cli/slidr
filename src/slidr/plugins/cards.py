"""Card auto-grouping: consecutive Card nodes → Grid."""

from slidr.parser.ast import Card, Grid, Node


def group_cards(nodes: list[Node]) -> list[Node]:
    """Auto-group consecutive Card nodes into a Grid."""
    result = []
    i = 0
    while i < len(nodes):
        if isinstance(nodes[i], Card):
            cards = [nodes[i]]
            j = i + 1
            while j < len(nodes) and isinstance(nodes[j], Card):
                cards.append(nodes[j])
                j += 1
            if len(cards) >= 2:
                result.append(Grid(cols=len(cards), children=list(cards)))
            else:
                result.append(cards[0])
            i = j
        else:
            result.append(nodes[i])
            i += 1
    return result
