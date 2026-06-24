from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from game.table import create_demo_table

app = FastAPI(title="Poker Online API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = {}
game_tables = {}


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Servidor de poker online activo"
    }


@app.get("/tables/{table_id}")
def get_table(table_id: str):
    if table_id not in game_tables:
        game_tables[table_id] = create_demo_table(table_id)

    return game_tables[table_id].public_state()


@app.websocket("/ws/{table_id}")
async def websocket_table(websocket: WebSocket, table_id: str):
    await websocket.accept()

    if table_id not in active_connections:
        active_connections[table_id] = []

    if table_id not in game_tables:
        game_tables[table_id] = create_demo_table(table_id)

    active_connections[table_id].append(websocket)

    await websocket.send_json({
        "type": "table_state",
        "table": game_tables[table_id].public_state()
    })

    try:
        while True:
            data = await websocket.receive_json()

            for connection in active_connections[table_id]:
                await connection.send_json({
                    "type": "action_received",
                    "table_id": table_id,
                    "action": data,
                    "table": game_tables[table_id].public_state()
                })

    except WebSocketDisconnect:
        active_connections[table_id].remove(websocket)

        if len(active_connections[table_id]) == 0:
            del active_connections[table_id]
