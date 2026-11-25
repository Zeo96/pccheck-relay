# Relay de "Connect SS" — subirlo gratis a Render

El relay es el servidor intermedio entre el jugador y el staff. Ninguno ve la IP del otro: los dos solo
hablan con este servidor, que no guarda IPs.

## Pasos (una sola vez, ~10 min)

1. Crea una cuenta gratis en https://github.com y un repositorio nuevo (privado) llamado `pccheck-relay`.
2. Sube a ese repositorio los 2 archivos de esta carpeta: `server.py` y `requirements.txt`
   (en GitHub: *Add file → Upload files*).
3. Crea una cuenta gratis en https://render.com (podes entrar con GitHub).
4. En Render: **New → Web Service** → elegi el repo `pccheck-relay` y completa:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Instance Type:** Free
5. Cuando termine, Render te da una URL tipo `https://pccheck-relay.onrender.com`.
   Abrila en el navegador: tiene que decir `PC CHECK SCANNER relay ok`.
6. En `python/scanner/config.py` pone la URL cambiando `https` por `wss`:
   ```python
   RELAY_URL = "wss://pccheck-relay.onrender.com"
   ```
7. Recompila con `python/build.bat` y reparte el nuevo `PC_CHECK_SCANNER.exe`.

## A tener en cuenta

- El plan gratis de Render **se duerme** tras 15 min sin uso. La primera conexion tarda hasta ~1 minuto
  (el scanner muestra "Waking up the server..." y reintenta solo).
- Probar en local: `python relay/server.py` y abrir el scanner con la variable `PCCHECK_RELAY=ws://127.0.0.1:8765`.
