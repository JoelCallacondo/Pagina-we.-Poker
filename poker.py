# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import random
import sys
import tkinter as tk
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations
from tkinter import messagebox, ttk


MIN_BUY_IN = 30
MIN_RAISE = 1
ANTE = 1
CARD_W = 64
CARD_H = 90
TURN_SECONDS = 60
SUITS = ["Corazones", "Diamantes", "Tréboles", "Picas"]
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
    7: "Póker",
    6: "Full house",
    5: "Color",
    4: "Escalera",
    3: "Trío",
    2: "Doble pareja",
    1: "Pareja",
    0: "Carta alta",
}
SUIT_SYMBOLS = {
    "Corazones": "♥",
    "Diamantes": "♦",
    "Tréboles": "♣",
    "Picas": "♠",
}
RED_SUITS = {"Corazones", "Diamantes"}


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    def __str__(self) -> str:
        return f"{RANK_LABELS[self.rank]} de {self.suit}"


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


def money(units: int) -> str:
    return f"S/{units / 10:.2f}"


def parse_money_to_units(text: str) -> int:
    clean = text.strip().lower().replace("s/", "").replace(",", ".")
    value = Decimal(clean)
    units = value * Decimal("10")
    if units != units.to_integral_value():
        raise ValueError("La cantidad debe estar en múltiplos de S/0.10.")
    return int(units)


def create_deck() -> list[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in RANKS]


def straight_high(ranks: list[int]) -> int | None:
    unique = sorted(set(ranks))
    if 14 in unique:
        unique.insert(0, 1)

    best: int | None = None
    for index in range(len(unique) - 4):
        window = unique[index : index + 5]
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

    assert best_score is not None
    assert best_cards is not None
    return best_score, best_cards


def hand_name(score: tuple[int, tuple[int, ...]]) -> str:
    return HAND_NAMES[score[0]]


def card_list(cards: list[Card] | tuple[Card, ...]) -> str:
    return ", ".join(str(card) for card in cards)


class PokerVisualApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Póker sin ciegas")
        self.geometry("1180x760")
        self.minsize(980, 680)

        self.players: list[Player] = []
        self.dealer_index = 0
        self.hand_number = 0
        self.deck = []
        self.community = []
        self.current_bet = 0
        self.acted: set[int] = set()
        self.pointer = 0
        self.current_actor: int | None = None
        self.street = ""
        self.showdown_visible = False
        self.hand_over = False
        self.timer_after_id: str | None = None
        self.turn_seconds_left = TURN_SECONDS
        self.turn_serial = 0

        self.player_count_var = tk.IntVar(value=2)
        self.name_vars = [tk.StringVar(value=f"Jugador {i}") for i in range(1, 9)]
        self.stack_vars = [tk.StringVar(value="3.00") for _ in range(8)]
        self.bot_vars = [tk.StringVar(value="Humano" if i == 0 else "Bot") for i in range(8)]
        self.amount_var = tk.StringVar(value="0.10")

        self._configure_style()
        self._build_setup()

    def _configure_style(self) -> None:
        self.configure(bg="#10251f")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#10251f")
        style.configure("Panel.TFrame", background="#162f28")
        style.configure("TLabel", background="#10251f", foreground="#f5f1df", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#162f28", foreground="#f5f1df", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#10251f", foreground="#fff8d6", font=("Segoe UI", 22, "bold"))
        style.configure("Sub.TLabel", background="#10251f", foreground="#d6ceb4", font=("Segoe UI", 10))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=(10, 8))
        style.configure("TButton", font=("Segoe UI", 10), padding=(8, 6))
        style.configure("TEntry", padding=5)
        style.configure("TSpinbox", padding=5)

    def _clear_root(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def _build_setup(self) -> None:
        self._clear_root()

        wrap = ttk.Frame(self, padding=28)
        wrap.pack(fill="both", expand=True)

        title = ttk.Label(wrap, text="Póker sin ciegas", style="Title.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(
            wrap,
            text="Entrada mínima S/3.00 · Ante obligatorio S/0.10 · Subida mínima S/0.10 · 2 a 8 jugadores",
            style="Sub.TLabel",
        )
        subtitle.pack(anchor="w", pady=(4, 22))

        body = ttk.Frame(wrap, style="Panel.TFrame", padding=18)
        body.pack(fill="x")

        top = ttk.Frame(body, style="Panel.TFrame")
        top.pack(fill="x", pady=(0, 14))

        ttk.Label(top, text="Jugadores", style="Panel.TLabel").pack(side="left")
        count = ttk.Spinbox(
            top,
            from_=2,
            to=8,
            textvariable=self.player_count_var,
            width=5,
            command=self._refresh_setup_rows,
        )
        count.pack(side="left", padx=(10, 0))
        count.bind("<KeyRelease>", lambda _event: self._refresh_setup_rows())

        self.rows_frame = ttk.Frame(body, style="Panel.TFrame")
        self.rows_frame.pack(fill="x")
        self._refresh_setup_rows()

        start = ttk.Button(wrap, text="Iniciar partida", style="Action.TButton", command=self._start_game)
        start.pack(anchor="e", pady=22)

    def _refresh_setup_rows(self) -> None:
        for child in self.rows_frame.winfo_children():
            child.destroy()

        try:
            count = int(self.player_count_var.get())
        except tk.TclError:
            count = 2
        count = max(2, min(8, count))

        headings = ttk.Frame(self.rows_frame, style="Panel.TFrame")
        headings.pack(fill="x", pady=(0, 6))
        ttk.Label(headings, text="Nombre", style="Panel.TLabel", width=24).pack(side="left")
        ttk.Label(headings, text="Tipo", style="Panel.TLabel", width=12).pack(side="left", padx=(12, 0))
        ttk.Label(headings, text="Fichas iniciales", style="Panel.TLabel", width=18).pack(side="left", padx=(12, 0))

        for index in range(count):
            row = ttk.Frame(self.rows_frame, style="Panel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Entry(row, textvariable=self.name_vars[index], width=24).pack(side="left")
            ttk.Combobox(
                row,
                textvariable=self.bot_vars[index],
                values=("Humano", "Bot"),
                width=10,
                state="readonly",
            ).pack(side="left", padx=(12, 0))
            ttk.Entry(row, textvariable=self.stack_vars[index], width=16).pack(side="left", padx=(12, 0))
            ttk.Label(row, text="soles", style="Panel.TLabel").pack(side="left", padx=(6, 0))

    def _start_game(self) -> None:
        try:
            count = int(self.player_count_var.get())
        except tk.TclError:
            messagebox.showerror("Dato inválido", "Ingresa una cantidad de jugadores entre 2 y 8.")
            return

        if count < 2 or count > 8:
            messagebox.showerror("Dato inválido", "Pueden jugar de 2 a 8 jugadores.")
            return

        players: list[Player] = []
        used_names: set[str] = set()
        for index in range(count):
            name = self.name_vars[index].get().strip() or f"Jugador {index + 1}"
            if name in used_names:
                name = f"{name} {index + 1}"
            used_names.add(name)
            try:
                stack = parse_money_to_units(self.stack_vars[index].get())
            except Exception:
                messagebox.showerror("Dato inválido", f"Las fichas de {name} no son válidas.")
                return
            if stack < MIN_BUY_IN:
                messagebox.showerror("Entrada mínima", f"{name} debe iniciar con al menos {money(MIN_BUY_IN)}.")
                return
            players.append(Player(name=name, stack=stack, is_bot=self.bot_vars[index].get() == "Bot"))

        self.players = players
        self.dealer_index = 0
        self.hand_number = 0
        self._build_table()
        self._new_hand()

    def _build_table(self) -> None:
        self._clear_root()

        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(main, bg="#113428", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.canvas.bind("<Configure>", lambda _event: self._draw_table())

        side = ttk.Frame(main, style="Panel.TFrame", padding=14, width=320)
        side.grid(row=0, column=1, sticky="ns")
        side.grid_propagate(False)

        self.hand_label = ttk.Label(side, text="", style="Panel.TLabel", font=("Segoe UI", 14, "bold"))
        self.hand_label.pack(anchor="w")

        self.street_label = ttk.Label(side, text="", style="Panel.TLabel")
        self.street_label.pack(anchor="w", pady=(3, 0))

        self.actor_label = ttk.Label(side, text="", style="Panel.TLabel", font=("Segoe UI", 11, "bold"))
        self.actor_label.pack(anchor="w", pady=(14, 0))

        self.timer_label = ttk.Label(side, text="Tiempo: --", style="Panel.TLabel", font=("Segoe UI", 18, "bold"))
        self.timer_label.pack(anchor="w", pady=(6, 0))

        self.private_canvas = tk.Canvas(side, width=188, height=104, bg="#162f28", highlightthickness=0)
        self.private_canvas.pack(anchor="w", pady=(8, 8))

        amount_row = ttk.Frame(side, style="Panel.TFrame")
        amount_row.pack(fill="x", pady=(8, 8))
        ttk.Label(amount_row, text="Monto", style="Panel.TLabel").pack(side="left")
        ttk.Entry(amount_row, textvariable=self.amount_var, width=10).pack(side="left", padx=(8, 4))
        ttk.Label(amount_row, text="S/", style="Panel.TLabel").pack(side="left")

        actions = ttk.Frame(side, style="Panel.TFrame")
        actions.pack(fill="x", pady=(4, 8))
        actions.columnconfigure((0, 1), weight=1)
        self.buttons: dict[str, ttk.Button] = {}
        specs = [
            ("check", "Pasar"),
            ("bet", "Apostar"),
            ("call", "Igualar"),
            ("raise", "Aumentar"),
            ("fold", "Retirarse"),
            ("allin", "All-in"),
        ]
        for idx, (key, text) in enumerate(specs):
            btn = ttk.Button(actions, text=text, style="Action.TButton", command=lambda k=key: self._handle_action(k))
            btn.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=4, pady=4)
            self.buttons[key] = btn

        self.next_button = ttk.Button(side, text="Nueva mano", style="Action.TButton", command=self._new_hand)
        self.next_button.pack(fill="x", pady=(10, 8))

        self.log = tk.Text(
            side,
            height=18,
            width=36,
            bg="#0d211c",
            fg="#f4ecd2",
            insertbackground="#f4ecd2",
            relief="flat",
            wrap="word",
            font=("Segoe UI", 9),
        )
        self.log.pack(fill="both", expand=True, pady=(8, 0))
        self.log.configure(state="disabled")

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _players_with_chips(self) -> list[int]:
        return [index for index, player in enumerate(self.players) if player.stack > 0]

    def _active_indices(self) -> list[int]:
        return [index for index, player in enumerate(self.players) if player.in_hand and not player.folded]

    def _actor_indices(self) -> list[int]:
        return [
            index
            for index, player in enumerate(self.players)
            if player.in_hand and not player.folded and not player.all_in and player.stack > 0
        ]

    def _clockwise_indices(self, start_index: int, only_in_hand: bool = False) -> list[int]:
        indices: list[int] = []
        total = len(self.players)
        for offset in range(total):
            index = (start_index + offset) % total
            if only_in_hand and not self.players[index].in_hand:
                continue
            indices.append(index)
        return indices

    def _next_index_with_chips(self, start_index: int) -> int:
        for index in self._clockwise_indices(start_index):
            if self.players[index].stack > 0:
                return index
        return start_index

    def _normalize_dealer(self) -> None:
        if self.players[self.dealer_index].stack <= 0:
            self.dealer_index = self._next_index_with_chips((self.dealer_index + 1) % len(self.players))

    def _move_dealer(self) -> None:
        self.dealer_index = self._next_index_with_chips((self.dealer_index + 1) % len(self.players))

    def _pot_size(self) -> int:
        return sum(player.total_bet for player in self.players)

    def _new_hand(self) -> None:
        self._cancel_turn_timer()
        if len(self._players_with_chips()) < 2:
            winner = next((player.name for player in self.players if player.stack > 0), "nadie")
            messagebox.showinfo("Juego terminado", f"No quedan dos jugadores con fichas. Gana {winner}.")
            self._update_controls()
            return

        self.hand_number += 1
        self._normalize_dealer()
        self.deck = create_deck()
        random.shuffle(self.deck)
        self.community = []
        self.current_bet = 0
        self.acted = set()
        self.current_actor = None
        self.street = ""
        self.showdown_visible = False
        self.hand_over = False

        for player in self.players:
            player.reset_for_hand()

        self._log("")
        self._log("=" * 34)
        self._log(f"Mano {self.hand_number}. Dealer: {self.players[self.dealer_index].name}")
        self._collect_antes()
        self._deal_private_cards()
        self._log("Se repartieron dos cartas privadas.")
        self._reveal(3, "Flop")
        self._start_betting_round("Flop")
        self._draw_table()

    def _collect_antes(self) -> None:
        self._log(f"Ante obligatorio: {money(ANTE)} por jugador.")
        for player in self.players:
            if not player.in_hand:
                continue
            paid = min(ANTE, player.stack)
            player.stack -= paid
            player.total_bet += paid
            if player.stack == 0:
                player.all_in = True
            if paid < ANTE:
                self._log(f"{player.name} entra all-in con {money(paid)}.")
        self._log(f"Pozo inicial: {money(self._pot_size())}.")

    def _deal_private_cards(self) -> None:
        order = self._clockwise_indices(self.dealer_index, only_in_hand=True)
        for _round in range(2):
            for index in order:
                self.players[index].cards.append(self.deck.pop())

    def _burn_card(self):
        return self.deck.pop()

    def _reveal(self, amount: int, street: str) -> None:
        burned = self._burn_card()
        new_cards = [self.deck.pop() for _ in range(amount)]
        self.community.extend(new_cards)
        self._log(f"{street}: se quema {burned}.")
        self._log(f"Comunitarias: {card_list(self.community)}")

    def _start_betting_round(self, street: str) -> None:
        self.street = street
        self.current_bet = 0
        self.acted = set()
        self.pointer = (self.dealer_index + 1) % len(self.players)
        for player in self.players:
            player.round_bet = 0
        self._log(f"Ronda de apuestas: {street}.")
        self._advance_turn()

    def _round_is_complete(self) -> bool:
        actors = self._actor_indices()
        if not actors:
            return True
        if self.current_bet == 0:
            return all(index in self.acted for index in actors)
        return all(self.players[index].round_bet == self.current_bet and index in self.acted for index in actors)

    def _find_next_actor(self, start_index: int) -> int | None:
        for index in self._clockwise_indices(start_index):
            player = self.players[index]
            if player.in_hand and not player.folded and not player.all_in and player.stack > 0:
                return index
        return None

    def _set_timer_text(self, text: str) -> None:
        if hasattr(self, "timer_label"):
            self.timer_label.configure(text=text)

    def _cancel_turn_timer(self) -> None:
        if self.timer_after_id is not None:
            try:
                self.after_cancel(self.timer_after_id)
            except tk.TclError:
                pass
        self.timer_after_id = None
        self.turn_serial += 1

    def _start_turn_timer(self, actor: int) -> None:
        self._cancel_turn_timer()
        self.turn_seconds_left = TURN_SECONDS
        serial = self.turn_serial
        self._set_timer_text(f"Tiempo: {self.turn_seconds_left}s")
        self.timer_after_id = self.after(1000, lambda: self._tick_turn_timer(actor, serial))

    def _tick_turn_timer(self, actor: int, serial: int) -> None:
        if serial != self.turn_serial or self.hand_over or self.current_actor != actor:
            return

        self.turn_seconds_left -= 1
        self._set_timer_text(f"Tiempo: {self.turn_seconds_left}s")

        if self.turn_seconds_left <= 0:
            self.timer_after_id = None
            self._timeout_turn(actor, serial)
            return

        self.timer_after_id = self.after(1000, lambda: self._tick_turn_timer(actor, serial))

    def _timeout_turn(self, actor: int, serial: int) -> None:
        if serial != self.turn_serial or self.hand_over or self.current_actor != actor:
            return

        player = self.players[actor]
        if player.is_bot:
            return

        self._cancel_turn_timer()
        to_call = max(0, self.current_bet - player.round_bet)
        if to_call == 0:
            self.acted.add(actor)
            self._log(f"Tiempo agotado: {player.name} pasa automáticamente.")
        else:
            player.folded = True
            self.acted.add(actor)
            self._log(f"Tiempo agotado: {player.name} se retira automáticamente.")

        self.pointer = (actor + 1) % len(self.players)
        self._advance_turn()

    def _advance_turn(self) -> None:
        self._cancel_turn_timer()
        if self.hand_over:
            self._update_controls()
            self._draw_table()
            return

        if len(self._active_indices()) <= 1:
            self._award_without_showdown()
            return

        if self._round_is_complete():
            self._finish_street()
            return

        actor = self._find_next_actor(self.pointer)
        if actor is None:
            self._finish_street()
            return

        self.current_actor = actor
        self._update_controls()
        self._draw_table()
        if self.players[actor].is_bot:
            self._set_timer_text("Bot pensando...")
            self.after(700, self._bot_take_turn)
        else:
            self._start_turn_timer(actor)

    def _bot_strength(self, player: Player) -> tuple[int, int]:
        score, _combo = best_hand(player.cards + self.community)
        category = score[0]
        main_rank = score[1][0] if score[1] else 0
        return category, main_rank

    def _bot_bet_amount(self, player: Player, category: int) -> int:
        if category >= 3:
            target = max(MIN_RAISE * 2, self._pot_size() // 3)
        elif category >= 1:
            target = max(MIN_RAISE, self._pot_size() // 5)
        else:
            target = MIN_RAISE
        return max(MIN_RAISE, min(player.stack, target))

    def _bot_take_turn(self) -> None:
        if self.current_actor is None or self.hand_over:
            return

        actor = self.current_actor
        player = self.players[actor]
        if not player.is_bot:
            return

        to_call = max(0, self.current_bet - player.round_bet)
        category, main_rank = self._bot_strength(player)
        strong = category >= 2 or (category == 1 and main_rank >= 10)
        very_strong = category >= 3

        if to_call == 0:
            wants_bet = very_strong or strong and random.random() < 0.55 or random.random() < 0.08
            if wants_bet and player.stack >= MIN_RAISE:
                amount = self._bot_bet_amount(player, category)
                paid = player.put_chips(amount)
                self.current_bet = player.round_bet
                self.acted = {actor}
                self._log(f"{player.name} (bot) apuesta {money(paid)}.")
            else:
                self.acted.add(actor)
                self._log(f"{player.name} (bot) pasa.")
        else:
            can_raise = player.stack >= to_call + MIN_RAISE
            small_call = to_call <= max(MIN_RAISE, player.stack // 8)

            if very_strong and can_raise and random.random() < 0.45:
                raise_extra = self._bot_bet_amount(player, category)
                amount = min(player.stack, to_call + raise_extra)
                player.put_chips(amount)
                self.current_bet = player.round_bet
                self.acted = {actor}
                self._log(f"{player.name} (bot) aumenta a {money(self.current_bet)}.")
            elif strong or small_call or random.random() < 0.12:
                paid = player.put_chips(to_call)
                self.acted.add(actor)
                if paid < to_call:
                    self._log(f"{player.name} (bot) va all-in parcial con {money(paid)}.")
                else:
                    self._log(f"{player.name} (bot) iguala {money(paid)}.")
            else:
                player.folded = True
                self.acted.add(actor)
                self._log(f"{player.name} (bot) se retira.")

        self.pointer = (actor + 1) % len(self.players)
        self._advance_turn()

    def _finish_street(self) -> None:
        if len(self._active_indices()) <= 1:
            self._award_without_showdown()
            return

        actors = self._actor_indices()
        if not actors and len(self.community) < 5:
            while len(self.community) < 5:
                if len(self.community) == 3:
                    self._reveal(1, "Turn")
                else:
                    self._reveal(1, "River")
            self._showdown()
            return

        if self.street == "Flop":
            self._reveal(1, "Turn")
            self._start_betting_round("Turn")
        elif self.street == "Turn":
            self._reveal(1, "River")
            self._start_betting_round("River")
        else:
            self._showdown()

    def _parse_amount(self) -> int | None:
        try:
            amount = parse_money_to_units(self.amount_var.get())
        except Exception:
            messagebox.showerror("Monto inválido", "Ingresa un monto en múltiplos de S/0.10. Ejemplo: 0.10 o 1.50.")
            return None
        if amount <= 0:
            messagebox.showerror("Monto inválido", "El monto debe ser mayor que S/0.00.")
            return None
        return amount

    def _handle_action(self, action: str) -> None:
        if self.current_actor is None or self.hand_over:
            return

        player = self.players[self.current_actor]
        to_call = max(0, self.current_bet - player.round_bet)

        if action == "check":
            if to_call != 0:
                return
            self.acted.add(self.current_actor)
            self._log(f"{player.name} pasa.")

        elif action == "bet":
            if to_call != 0:
                return
            amount = self._parse_amount()
            if amount is None:
                return
            if amount < MIN_RAISE:
                messagebox.showerror("Apuesta mínima", f"La apuesta mínima es {money(MIN_RAISE)}.")
                return
            if amount > player.stack:
                messagebox.showerror("Fichas insuficientes", f"{player.name} solo tiene {money(player.stack)}.")
                return
            paid = player.put_chips(amount)
            self.current_bet = player.round_bet
            self.acted = {self.current_actor}
            self._log(f"{player.name} apuesta {money(paid)}.")

        elif action == "call":
            if to_call <= 0:
                return
            paid = player.put_chips(to_call)
            self.acted.add(self.current_actor)
            if paid < to_call:
                self._log(f"{player.name} va all-in parcial con {money(paid)}.")
            else:
                self._log(f"{player.name} iguala {money(paid)}.")

        elif action == "raise":
            if to_call <= 0:
                return
            minimum = to_call + MIN_RAISE
            amount = self._parse_amount()
            if amount is None:
                return
            if amount < minimum:
                messagebox.showerror("Subida mínima", f"Debes agregar al menos {money(minimum)}.")
                return
            if amount > player.stack:
                messagebox.showerror("Fichas insuficientes", f"{player.name} solo tiene {money(player.stack)}.")
                return
            player.put_chips(amount)
            self.current_bet = player.round_bet
            self.acted = {self.current_actor}
            self._log(f"{player.name} aumenta. Nueva apuesta: {money(self.current_bet)}.")

        elif action == "fold":
            if to_call <= 0:
                return
            player.folded = True
            self.acted.add(self.current_actor)
            self._log(f"{player.name} se retira.")

        elif action == "allin":
            paid = player.put_chips(player.stack)
            if player.round_bet > self.current_bet:
                self.current_bet = player.round_bet
                self.acted = {self.current_actor}
                self._log(f"{player.name} va all-in con apuesta total {money(player.round_bet)}.")
            else:
                self.acted.add(self.current_actor)
                self._log(f"{player.name} va all-in con {money(paid)}.")

        self.pointer = (self.current_actor + 1) % len(self.players)
        self._advance_turn()

    def _side_pots(self) -> list[tuple[int, list[int]]]:
        levels = sorted({player.total_bet for player in self.players if player.total_bet > 0})
        pots: list[tuple[int, list[int]]] = []
        previous = 0
        for level in levels:
            contributors = [index for index, player in enumerate(self.players) if player.total_bet >= level]
            amount = (level - previous) * len(contributors)
            eligible = [
                index
                for index in contributors
                if self.players[index].in_hand and not self.players[index].folded
            ]
            if amount > 0 and eligible:
                pots.append((amount, eligible))
            previous = level
        return pots

    def _distribute_pot(self, amount: int, winners: list[int]) -> None:
        share = amount // len(winners)
        remainder = amount % len(winners)
        ordered = [index for index in self._clockwise_indices(self.dealer_index) if index in winners]
        for index in winners:
            self.players[index].stack += share
        for index in ordered[:remainder]:
            self.players[index].stack += 1

    def _award_without_showdown(self) -> None:
        active = self._active_indices()
        if len(active) != 1:
            return
        winner = self.players[active[0]]
        pot = self._pot_size()
        winner.stack += pot
        self._log(f"{winner.name} gana {money(pot)} porque los demás se retiraron.")
        self._end_hand()

    def _showdown(self) -> None:
        self.current_actor = None
        self.showdown_visible = True
        self._log("Showdown.")
        scores = {}
        for index in self._active_indices():
            player = self.players[index]
            score, combo = best_hand(player.cards + self.community)
            scores[index] = score
            self._log(f"{player.name}: {hand_name(score)} ({card_list(combo)})")

        for number, (amount, eligible) in enumerate(self._side_pots(), start=1):
            best_score = max(scores[index] for index in eligible)
            winners = [index for index in eligible if scores[index] == best_score]
            self._distribute_pot(amount, winners)
            names = ", ".join(self.players[index].name for index in winners)
            self._log(f"Pozo {number} {money(amount)}: gana {names} con {hand_name(best_score)}.")

        self._end_hand()

    def _end_hand(self) -> None:
        self._cancel_turn_timer()
        self.hand_over = True
        self.current_actor = None
        self._move_dealer()
        self._log("Fichas: " + " · ".join(f"{p.name} {money(p.stack)}" for p in self.players))
        self._update_controls()
        self._draw_table()

    def _update_controls(self) -> None:
        self.hand_label.configure(text=f"Mano {self.hand_number}")
        self.street_label.configure(
            text=f"{self.street or 'Preparando'} · Pozo {money(self._pot_size())} · Apuesta {money(self.current_bet)}"
        )

        for button in self.buttons.values():
            button.configure(state="disabled")

        self.next_button.configure(state="normal" if self.hand_over else "disabled")

        if self.hand_over:
            self.actor_label.configure(text="Mano terminada")
            self._set_timer_text("Tiempo: --")
            self._draw_private_cards(None)
            return

        if self.current_actor is None:
            self.actor_label.configure(text="Avanzando...")
            self._set_timer_text("Tiempo: --")
            self._draw_private_cards(None)
            return

        player = self.players[self.current_actor]
        to_call = max(0, self.current_bet - player.round_bet)
        if player.is_bot:
            self.actor_label.configure(text=f"Turno: {player.name} (bot)")
            self._set_timer_text("Bot pensando...")
            self._draw_private_cards(None)
            return

        self.actor_label.configure(text=f"Turno: {player.name}")
        self._set_timer_text(f"Tiempo: {TURN_SECONDS}s")
        self._draw_private_cards(player)

        if to_call == 0:
            self.buttons["check"].configure(state="normal")
            self.buttons["bet"].configure(state="normal" if player.stack >= MIN_RAISE else "disabled")
            self.buttons["allin"].configure(state="normal" if player.stack > 0 else "disabled")
        else:
            self.buttons["call"].configure(state="normal")
            self.buttons["fold"].configure(state="normal")
            can_raise = player.stack >= to_call + MIN_RAISE
            self.buttons["raise"].configure(state="normal" if can_raise else "disabled")
            self.buttons["allin"].configure(state="normal" if player.stack > 0 else "disabled")

    def _draw_private_cards(self, player: Player | None) -> None:
        self.private_canvas.delete("all")
        if player is None:
            self.private_canvas.create_text(
                92,
                48,
                text="Cartas privadas",
                fill="#d6ceb4",
                font=("Segoe UI", 10, "bold"),
            )
            return
        self._draw_card(self.private_canvas, 8, 7, player.cards[0], True, 1)
        self._draw_card(self.private_canvas, 82, 7, player.cards[1], True, 1)

    def _draw_table(self) -> None:
        if not hasattr(self, "canvas"):
            return

        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 900)
        height = max(canvas.winfo_height(), 620)

        canvas.create_rectangle(0, 0, width, height, fill="#113428", outline="")
        canvas.create_oval(
            width * 0.08,
            height * 0.12,
            width * 0.92,
            height * 0.86,
            fill="#19513f",
            outline="#c8a94d",
            width=4,
        )
        canvas.create_oval(
            width * 0.14,
            height * 0.19,
            width * 0.86,
            height * 0.79,
            fill="#123c30",
            outline="#2f6b55",
            width=2,
        )

        canvas.create_text(
            width / 2,
            height * 0.24,
            text=f"Pozo {money(self._pot_size())}",
            fill="#fff8d6",
            font=("Segoe UI", 18, "bold"),
        )
        canvas.create_text(
            width / 2,
            height * 0.29,
            text=f"{self.street or 'Mesa'} · Ante {money(ANTE)}",
            fill="#dccfa8",
            font=("Segoe UI", 10, "bold"),
        )
        canvas.create_text(
            width / 2,
            height * 0.33,
            text=f"Apuesta actual {money(self.current_bet)}",
            fill="#f2d46b",
            font=("Segoe UI", 11, "bold"),
        )

        start_x = width / 2 - (5 * CARD_W + 4 * 12) / 2
        y = height * 0.38
        for index in range(5):
            card = self.community[index] if index < len(self.community) else None
            self._draw_card(canvas, start_x + index * (CARD_W + 12), y, card, card is not None, 1)

        self._draw_players(canvas, width, height)

    def _draw_players(self, canvas: tk.Canvas, width: int, height: int) -> None:
        if not self.players:
            return

        count = len(self.players)
        cx, cy = width / 2, height * 0.51
        rx, ry = width * 0.39, height * 0.35

        for index, player in enumerate(self.players):
            angle = -math.pi / 2 + (2 * math.pi * index / count)
            x = cx + rx * math.cos(angle)
            y = cy + ry * math.sin(angle)
            self._draw_player_seat(canvas, index, player, x, y)

    def _draw_player_seat(self, canvas: tk.Canvas, index: int, player: Player, x: float, y: float) -> None:
        w, h = 196, 128
        left, top = x - w / 2, y - h / 2

        if index == self.current_actor:
            fill = "#f2d46b"
            text_fill = "#1b211d"
            outline = "#fff2a6"
        elif player.folded:
            fill = "#2a3935"
            text_fill = "#9ba49b"
            outline = "#3f514b"
        elif player.all_in and player.in_hand:
            fill = "#234b63"
            text_fill = "#ecf7ff"
            outline = "#75bce0"
        else:
            fill = "#efe8d0"
            text_fill = "#16241f"
            outline = "#d6c28a"

        canvas.create_rectangle(left, top, left + w, top + h, fill=fill, outline=outline, width=2)
        label = player.name
        if player.is_bot:
            label += "  BOT"
        if index == self.dealer_index:
            label += "  D"
        canvas.create_text(left + 12, top + 12, anchor="nw", text=label, fill=text_fill, font=("Segoe UI", 10, "bold"))

        status = "fuera"
        if player.in_hand and not player.folded:
            status = "all-in" if player.all_in else "activo"
        elif player.folded:
            status = "retirado"

        canvas.create_text(
            left + 12,
            top + 35,
            anchor="nw",
            text=f"Fichas {money(player.stack)} · {status}",
            fill=text_fill,
            font=("Segoe UI", 9),
        )
        canvas.create_text(
            left + 12,
            top + 56,
            anchor="nw",
            text=f"En mano {money(player.total_bet)}",
            fill=text_fill,
            font=("Segoe UI", 9, "bold"),
        )
        round_fill = "#fff8d6" if player.round_bet > 0 else text_fill
        canvas.create_text(
            left + 12,
            top + 76,
            anchor="nw",
            text=f"Ronda {money(player.round_bet)}",
            fill=round_fill,
            font=("Segoe UI", 9),
        )

        face_up = self.showdown_visible or (index == self.current_actor and not player.is_bot)
        chip_fill = "#d8b84a" if player.total_bet > 0 else "#9aa39b"
        canvas.create_oval(left + w - 68, top + 48, left + w - 16, top + 88, fill=chip_fill, outline="#6e5a1d")
        canvas.create_text(
            left + w - 43,
            top + 61,
            text="Puso",
            fill="#1b211d",
            font=("Segoe UI", 8, "bold"),
        )
        canvas.create_text(
            left + w - 43,
            top + 78,
            text=money(player.total_bet),
            fill="#1b211d",
            font=("Segoe UI", 8, "bold"),
        )

        card_y = top + 94
        if len(player.cards) == 2:
            self._draw_mini_card(canvas, left + 118, card_y, player.cards[0], face_up)
            self._draw_mini_card(canvas, left + 148, card_y, player.cards[1], face_up)

    def _draw_mini_card(self, canvas: tk.Canvas, x: float, y: float, card, face_up: bool) -> None:
        if face_up:
            color = "#c83131" if card.suit in RED_SUITS else "#151515"
            canvas.create_rectangle(x, y, x + 24, y + 32, fill="#fffdf5", outline="#d4c89c")
            canvas.create_text(
                x + 12,
                y + 10,
                text=RANK_LABELS[card.rank],
                fill=color,
                font=("Segoe UI", 7, "bold"),
            )
            canvas.create_text(
                x + 12,
                y + 23,
                text=SUIT_SYMBOLS[card.suit],
                fill=color,
                font=("Segoe UI", 8, "bold"),
            )
        else:
            canvas.create_rectangle(x, y, x + 24, y + 32, fill="#27466a", outline="#8fb4dd")
            canvas.create_line(x + 5, y + 7, x + 19, y + 25, fill="#8fb4dd")
            canvas.create_line(x + 19, y + 7, x + 5, y + 25, fill="#8fb4dd")

    def _draw_card(self, canvas: tk.Canvas, x: float, y: float, card, face_up: bool, scale: float) -> None:
        w, h = CARD_W * scale, CARD_H * scale
        if not face_up or card is None:
            canvas.create_rectangle(x, y, x + w, y + h, fill="#24466d", outline="#a8c9e6", width=2)
            canvas.create_rectangle(x + 8, y + 8, x + w - 8, y + h - 8, outline="#a8c9e6")
            canvas.create_text(x + w / 2, y + h / 2, text="?", fill="#d8ecff", font=("Segoe UI", int(20 * scale), "bold"))
            return

        color = "#c83131" if card.suit in RED_SUITS else "#151515"
        canvas.create_rectangle(x, y, x + w, y + h, fill="#fffdf5", outline="#d4c89c", width=2)
        canvas.create_text(
            x + 10 * scale,
            y + 10 * scale,
            anchor="nw",
            text=RANK_LABELS[card.rank],
            fill=color,
            font=("Segoe UI", int(12 * scale), "bold"),
        )
        canvas.create_text(
            x + w / 2,
            y + h / 2,
            text=SUIT_SYMBOLS[card.suit],
            fill=color,
            font=("Segoe UI", int(28 * scale), "bold"),
        )
        canvas.create_text(
            x + w - 10 * scale,
            y + h - 10 * scale,
            anchor="se",
            text=RANK_LABELS[card.rank],
            fill=color,
            font=("Segoe UI", int(12 * scale), "bold"),
        )


def run_self_test() -> None:
    app = PokerVisualApp.__new__(PokerVisualApp)
    app.players = [Player("Ana", 30), Player("Luis", 30)]
    app.dealer_index = 0
    app.hand_number = 0
    app.deck = create_deck()
    app.community = []
    app.current_bet = 0
    app.acted = set()
    app.pointer = 0
    app.current_actor = None
    app.street = ""
    app.showdown_visible = False
    app.hand_over = False
    assert len(app._players_with_chips()) == 2
    assert app._pot_size() == 0
    print("Prueba visual interna OK.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_self_test()
    else:
        PokerVisualApp().mainloop()
