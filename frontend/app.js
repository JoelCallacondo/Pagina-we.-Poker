const statusText = document.getElementById("status");
const playersContainer = document.getElementById("players");
const communityCards = document.getElementById("community-cards");
const potText = document.getElementById("pot");
const phaseText = document.getElementById("phase");
const currentBetText = document.getElementById("current-bet");

let socket = new WebSocket("ws://127.0.0.1:8000/ws/mesa1");

socket.onopen = () => {
    statusText.textContent = "Conectado al servidor WebSocket";
};

socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "table_state" || message.type === "action_received") {
        renderTable(message.table);
    }
};

socket.onerror = () => {
    statusText.textContent = "Error de conexión";
};

socket.onclose = () => {
    statusText.textContent = "Conexión cerrada";
};

function sendAction(action) {
    socket.send(JSON.stringify({
        type: "action",
        player_id: 1,
        action: action,
        amount: 1
    }));
}

function suitSymbol(suit) {
    if (suit === "Corazones") return "♥";
    if (suit === "Diamantes") return "♦";
    if (suit === "Treboles") return "♣";
    if (suit === "Picas") return "♠";
    return "";
}

function isRedSuit(suit) {
    return suit === "Corazones" || suit === "Diamantes";
}

function renderCard(card) {
    if (!card) {
        return `<div class="card back">?</div>`;
    }

    const symbol = suitSymbol(card.suit);
    const redClass = isRedSuit(card.suit) ? "red" : "";

    return `
        <div class="card ${redClass}">
            <div>${card.label}</div>
            <div>${symbol}</div>
        </div>
    `;
}

function renderMiniCard(card, hidden = false) {
    if (hidden || !card) {
        return `<div class="mini-card back">X</div>`;
    }

    const symbol = suitSymbol(card.suit);
    const redClass = isRedSuit(card.suit) ? "red" : "";

    return `<div class="mini-card ${redClass}">${card.label}${symbol}</div>`;
}

function renderTable(table) {
    potText.textContent = `Pozo ${table.pot_text}`;
    phaseText.textContent = `${table.phase.toUpperCase()} · Ante S/0.10`;
    currentBetText.textContent = `Apuesta actual ${table.current_bet_text}`;

    communityCards.innerHTML = table.community_cards.map(renderCard).join("");

    playersContainer.innerHTML = table.players.map(player => {
        const title = player.is_dealer
            ? `${player.name}  D`
            : `${player.name} ${player.is_bot ? "BOT" : ""}`;

        const hiddenCards = player.seat !== 1;

        return `
            <article class="player seat-${player.seat}">
                <h3>${title}</h3>
                <p>Fichas ${player.stack_text} - ${player.in_hand ? "activo" : "fuera"}</p>
                <p><strong>En mano ${player.total_bet_text}</strong></p>
                <p><strong>Ronda ${player.round_bet_text}</strong></p>

                <div class="badge">Puso<br>${player.round_bet_text}</div>

                <div class="hole-cards">
                    ${
                        player.cards.length > 0
                            ? player.cards.map(card => renderMiniCard(card, hiddenCards)).join("")
                            : `${renderMiniCard(null, true)}${renderMiniCard(null, true)}`
                    }
                </div>
            </article>
        `;
    }).join("");
}
