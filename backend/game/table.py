from __future__ import annotations

from dataclasses import dataclass, field

from .engine import Card, Player, money


@dataclass
class PokerTable:
    table_id: str
    players: list[Player] = field(default_factory=list)
    community_cards: list[Card | None] = field(default_factory=list)
    pot: int = 0
    current_bet: int = 0
    phase: str = "waiting"
    dealer_seat: int = 1
    active_seat: int = 1
    last_action: str = ""

    def public_state(self) -> dict:
        return {
            "table_id": self.table_id,
            "phase": self.phase,
            "pot": self.pot,
            "pot_text": money(self.pot),
            "current_bet": self.current_bet,
            "current_bet_text": money(self.current_bet),
            "dealer_seat": self.dealer_seat,
            "active_seat": self.active_seat,
            "last_action": self.last_action,
            "community_cards": [
                card.to_dict() if card else None
                for card in self.community_cards
            ],
            "players": [
                {
                    "seat": index + 1,
                    "name": player.name,
                    "stack": player.stack,
                    "stack_text": money(player.stack),
                    "is_bot": player.is_bot,
                    "in_hand": player.in_hand,
                    "folded": player.folded,
                    "all_in": player.all_in,
                    "round_bet": player.round_bet,
                    "round_bet_text": money(player.round_bet),
                    "total_bet": player.total_bet,
                    "total_bet_text": money(player.total_bet),
                    "cards": [
                        card.to_dict()
                        for card in player.cards
                    ],
                    "is_dealer": index + 1 == self.dealer_seat,
                    "is_active": index + 1 == self.active_seat,
                }
                for index, player in enumerate(self.players)
            ],
        }

    def apply_action(self, seat: int, action: str, amount: int = 1) -> dict:
        if seat < 1 or seat > len(self.players):
            return {
                "ok": False,
                "message": "Asiento inválido."
            }

        player = self.players[seat - 1]

        if not player.in_hand or player.folded:
            return {
                "ok": False,
                "message": f"{player.name} no está activo en la mano."
            }

        action = action.lower().strip()

        if action == "check":
            self.last_action = f"{player.name} pasó."
            self.move_turn()
            return {
                "ok": True,
                "message": self.last_action
            }

        if action == "fold":
            player.folded = True
            player.in_hand = False
            self.last_action = f"{player.name} se retiró."
            self.move_turn()
            return {
                "ok": True,
                "message": self.last_action
            }

        if action == "call":
            needed = max(self.current_bet - player.round_bet, 0)
            paid = player.put_chips(needed)
            self.pot += paid
            self.last_action = f"{player.name} igualó {money(paid)}."
            self.move_turn()
            return {
                "ok": True,
                "message": self.last_action
            }

        if action == "bet":
            amount = max(int(amount), 1)
            new_bet = self.current_bet + amount
            needed = max(new_bet - player.round_bet, 0)
            paid = player.put_chips(needed)
            self.pot += paid
            self.current_bet = max(self.current_bet, player.round_bet)
            self.last_action = f"{player.name} apostó {money(paid)}."
            self.move_turn()
            return {
                "ok": True,
                "message": self.last_action
            }

        return {
            "ok": False,
            "message": "Acción no reconocida."
        }

    def move_turn(self) -> None:
        if not self.players:
            return

        total_players = len(self.players)

        for step in range(1, total_players + 1):
            next_seat = ((self.active_seat - 1 + step) % total_players) + 1
            next_player = self.players[next_seat - 1]

            if next_player.in_hand and not next_player.folded and not next_player.all_in:
                self.active_seat = next_seat
                return


def create_demo_table(table_id: str = "mesa1") -> PokerTable:
    players = [
        Player("Jugador 1", 29, is_bot=False),
        Player("Jugador 2", 29, is_bot=True),
        Player("Jugador 3", 28, is_bot=True),
        Player("Jugador 4", 28, is_bot=True),
        Player("Jugador 5", 28, is_bot=True),
        Player("Jugador 6", 28, is_bot=True),
        Player("Jugador 7", 28, is_bot=True),
        Player("Jugador 8", 28, is_bot=True),
    ]

    for player in players:
        player.reset_for_hand()

    players[0].cards = [
        Card(14, "Treboles"),
        Card(9, "Diamantes"),
    ]

    for index, player in enumerate(players):
        if index == 0 or index == 1:
            player.put_chips(1)
        else:
            player.put_chips(2)

    community_cards = [
        Card(12, "Diamantes"),
        Card(11, "Diamantes"),
        Card(8, "Picas"),
        None,
        None,
    ]

    return PokerTable(
        table_id=table_id,
        players=players,
        community_cards=community_cards,
        pot=14,
        current_bet=1,
        phase="flop",
        dealer_seat=1,
        active_seat=1,
        last_action="Mesa demo iniciada.",
    )
