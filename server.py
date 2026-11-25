"""Relay de pantalla para PC CHECK SCANNER (estilo AnyDesk, solo ver).

Privacidad: los dos PCs solo se conectan a ESTE servidor. Nunca se reenvia la IP de uno al otro
y el servidor no guarda IPs en disco. Solo existe en memoria la sala de cada codigo.

Protocolo (WebSocket):
  jugador -> {"t":"host"}                 <- {"t":"code","code":"123456789"}
  staff   -> {"t":"join","code","who"}    jugador recibe {"t":"request","who"}
  jugador -> {"t":"accept"} / {"t":"deny"} staff recibe {"t":"ok"} / {"t":"error"}
  jugador -> bytes (JPEG)                 staff recibe los bytes
  cualquiera cierra -> el otro recibe {"t":"ended"} y la sala se borra (codigo de un solo uso).
"""
import asyncio
import json
import os
import secrets
import time

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

CODE_TTL = 600          # el codigo vence a los 10 min si nadie se conecta
ACCEPT_TIMEOUT = 60     # el jugador tiene 60 s para aceptar
MAX_FAILS = 10          # codigos incorrectos por IP cada 10 min
ROOMS = {}              # code -> {"host": ws, "viewer": ws|None, "created": t, "accepted": Event}
FAILS = {}              # ip -> [count, first_time]  (solo en memoria, para frenar fuerza bruta)


def _ip(ws):
    fwd = ws.request.headers.get("X-Forwarded-For", "") if ws.request else ""
    return fwd.split(",")[0].strip() or (ws.remote_address or ("?",))[0]


def _limited(ip) -> bool:
    c = FAILS.get(ip)
    if c and time.time() - c[1] > 600:
        FAILS.pop(ip, None)
        return False
    return bool(c and c[0] >= MAX_FAILS)


def _fail(ip):
    c = FAILS.setdefault(ip, [0, time.time()])
    c[0] += 1


async def _send(ws, obj):
    try:
        await ws.send(json.dumps(obj))
    except ConnectionClosed:
        pass


async def host(ws):
    code = "".join(secrets.choice("0123456789") for _ in range(9))
    while code in ROOMS:
        code = "".join(secrets.choice("0123456789") for _ in range(9))
    room = ROOMS[code] = {"host": ws, "viewer": None, "created": time.time(), "accepted": asyncio.Event()}
    await _send(ws, {"t": "code", "code": code, "ttl": CODE_TTL})
    try:
        async for msg in ws:
            v = room["viewer"]
            if isinstance(msg, bytes):
                if v and room["accepted"].is_set():
                    try:
                        await v.send(msg)
                    except ConnectionClosed:
                        break
                continue
            t = json.loads(msg).get("t")
            if t == "accept" and v:
                room["accepted"].set()
                await _send(v, {"t": "ok"})
            elif t in ("deny", "stop") and v:
                await _send(v, {"t": "error" if t == "deny" else "ended", "msg": "The player denied the request." if t == "deny" else "The player stopped sharing."})
                await v.close()
                break
    except (ConnectionClosed, ValueError):
        pass
    finally:
        ROOMS.pop(code, None)
        if room["viewer"]:
            await _send(room["viewer"], {"t": "ended", "msg": "The player disconnected."})
            await room["viewer"].close()


async def join(ws, code, who):
    ip = _ip(ws)
    room = ROOMS.get(code)
    if _limited(ip):
        return await _send(ws, {"t": "error", "msg": "Too many wrong codes. Try again in 10 minutes."})
    if not room or room["viewer"] or time.time() - room["created"] > CODE_TTL:
        _fail(ip)
        return await _send(ws, {"t": "error", "msg": "Invalid, used or expired code."})
    room["viewer"] = ws
    await _send(room["host"], {"t": "request", "who": str(who)[:80]})
    try:
        await asyncio.wait_for(room["accepted"].wait(), ACCEPT_TIMEOUT)
    except asyncio.TimeoutError:
        await _send(ws, {"t": "error", "msg": "The player did not accept in time."})
        await room["host"].close()
        return
    try:
        async for msg in ws:  # el staff solo puede pedir cortar; no hay control remoto
            if isinstance(msg, str) and json.loads(msg).get("t") == "stop":
                break
    except (ConnectionClosed, ValueError):
        pass
    if ROOMS.get(code) is room:
        await _send(room["host"], {"t": "ended", "msg": "Staff disconnected."})
        await room["host"].close()


async def handler(ws):
    try:
        hello = json.loads(await asyncio.wait_for(ws.recv(), 20))
    except (asyncio.TimeoutError, ConnectionClosed, ValueError, TypeError):
        return
    if hello.get("t") == "host":
        await host(ws)
    elif hello.get("t") == "join":
        await join(ws, "".join(ch for ch in str(hello.get("code", "")) if ch.isdigit()), hello.get("who", ""))


def health(connection, request):
    # Render / navegador: un GET normal (sin WebSocket) responde "ok".
    if request.headers.get("Upgrade", "").lower() != "websocket":
        return connection.respond(200, "PC CHECK SCANNER relay ok\n")


async def main():
    port = int(os.environ.get("PORT", "8765"))
    async with serve(handler, "0.0.0.0", port, process_request=health, max_size=4 * 1024 * 1024, ping_interval=20):
        print(f"relay escuchando en puerto {port}", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
