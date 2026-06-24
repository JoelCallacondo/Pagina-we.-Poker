const estado = document.getElementById("estado");
const mensajes = document.getElementById("mensajes");

const socket = new WebSocket("ws://127.0.0.1:8000/ws/mesa1");

socket.onopen = () => {
    estado.textContent = "Conectado al servidor WebSocket";
};

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    mensajes.textContent += JSON.stringify(data, null, 2) + "\n\n";
};

socket.onerror = () => {
    estado.textContent = "Error de conexión";
};

socket.onclose = () => {
    estado.textContent = "Conexión cerrada";
};

function enviarAccion() {
    socket.send(JSON.stringify({
        type: "action",
        player_id: 1,
        action: "bet",
        amount: 0.10
    }));
}
