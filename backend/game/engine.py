from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations


MIN_BUY_IN = 30
MIN_RAISE = 1
ANTE = 1

SUITS = ["Corazones", "Diamantes", "Treboles", "Picas"]
RANKS = list(range(2, 15))

RANK_LABELS = {
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    10: "10",
    11: "J",
    12: "Q",
    13: "K",
    14: "A",
}

HAND_NAMES = {
    9: "Escalera real",
    8: "Escalera de color",
    7: "Poker",
    6: "Full house",
    5: "Color",
    4: "Escalera",
    3: "Trio",
    2: "Doble pareja",
    1: "Pareja",
    0: "Carta alta",
}

SUIT_SYMBOLS = {
    "Corazones": "♥",
    "Diamantes": "♦",
    "Treboles": "♣",
    "Picas": "♠",
}


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    def label(self) -> str:
        return RANK_LABELS[self.rank]

    def symbol(self) -> str:
        return SUIT_SYMBOLS[self.suit]

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "label": self.label(),
            "suit": self.suit,
            "symbol": self.symbol(),
        }

    def __str__(self) -> str:
        return f"{self.label()} de {self.suit}"


@dataclass
class Player:
    name: str
    stack: int
    is_bot: bool = False
    cards: list[Card] = field(default_factory=list)
    in_hand: bool = False
    folded: bool = False
    all_in: bool = False
    round_bet: int = 0
    total_bet: int = 0

    def reset_for_hand(self) -> None:
        self.cards.clear()
        self.in_hand = self.stack > 0
        self.folded = False
        self.all_in = False
        self.round_bet = 0
        self.total_bet = 0

    def put_chips(self, amount: int) -> int:
        amount = min(amount, self.stack)
        self.stack -= amount
        self.round_bet += amount
        self.total_bet += amount

        if self.stack == 0:
            self.all_in = True

        return amount

    def public_state(self) -> dict:
        return {
            "name": self.name,
            "stack": self.stack,
            "is_bot": self.is_bot,
            "in_hand": self.in_hand,
            "folded": self.folded,
            "all_in": self.all_in,
            "round_bet": self.round_bet,
            "total_bet": self.total_bet,
        }


def money(units: int) -> str:
    return f"S/{units / 10:.2f}"


def create_deck() -> list[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in RANKS]


def shuffled_deck() -> list[Card]:
    deck = create_deck()
    random.shuffle(deck)
    return deck


def straight_high(ranks: list[int]) -> int | None:
    unique = sorted(set(ranks))

    if 14 in unique:
        unique.insert(0, 1)

    best: int | None = None

    for index in range(len(unique) - 4):
        window = unique[index:index + 5]

        if window == list(range(window[0], window[0] + 5)):
            best = window[-1]

    return best


def score_five(cards: tuple[Card, ...]) -> tuple[int, tuple[int, ...]]:
    ranks = sorted((card.rank for card in cards), reverse=True)
    suits = [card.suit for card in cards]
    counts = Counter(ranks)

    flush = len(set(suits)) == 1
    straight = straight_high(ranks)

    if flush and straight:
        if straight == 14:
            return (9, (14,))
        return (8, (straight,))

    four = [rank for rank, count in counts.items() if count == 4]
    if four:
        four_rank = max(four)
        kicker = max(rank for rank in ranks if rank != four_rank)
        return (7, (four_rank, kicker))

    three = sorted((rank for rank, count in counts.items() if count == 3), reverse=True)
    pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)

    if three and pairs:
        return (6, (three[0], pairs[0]))

    if flush:
        return (5, tuple(ranks))

    if straight:
        return (4, (straight,))

    if three:
        kickers = tuple(rank for rank in ranks if rank != three[0])
        return (3, (three[0],) + kickers)

    if len(pairs) >= 2:
        top_pairs = tuple(pairs[:2])
        kicker = max(rank for rank in ranks if rank not in top_pairs)
        return (2, top_pairs + (kicker,))

    if len(pairs) == 1:
        pair = pairs[0]
        kickers = tuple(rank for rank in ranks if rank != pair)
        return (1, (pair,) + kickers)

    return (0, tuple(ranks))


def best_hand(cards: list[Card]) -> tuple[tuple[int, tuple[int, ...]], tuple[Card, ...]]:
    best_score: tuple[int, tuple[int, ...]] | None = None
    best_cards: tuple[Card, ...] | None = None

    for combo in combinations(cards, 5):
        score = score_five(combo)

        if best_score is None or score > best_score:
            best_score = score
            best_cards = combo

    if best_score is None or best_cards is None:
        raise ValueError("Se necesitan al menos 5 cartas para evaluar la mano.")

    return best_score, best_cards


def hand_name(score: tuple[int, tuple[int, ...]]) -> str:
    return HAND_NAMES[score[0]]
