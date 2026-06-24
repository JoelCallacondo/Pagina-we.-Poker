from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Poker Online API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_tables = {}

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Servidor de poker online activo"
    }

@app.websocket("/ws/{table_id}")
async def websocket_table(websocket: WebSocket, table_id: str):
    await websocket.accept()

    if table_id not in active_tables:
        active_tables[table_id] = []

    active_tables[table_id].append(websocket)

    await websocket.send_json({
        "type": "connected",
        "table_id": table_id,
        "message": "Conectado a la mesa"
    })

    try:
        while True:
            data = await websocket.receive_json()

            for connection in active_tables[table_id]:
                await connection.send_json({
                    "type": "table_update",
                    "table_id": table_id,
                    "data": data
                })

    except WebSocketDisconnect:
        active_tables[table_id].remove(websocket)

        if len(active_tables[table_id]) == 0:
            del active_tables[table_id]
