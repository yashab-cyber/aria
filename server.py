from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from core.aria import orchestrator
from modules.system.system_info import sys_monitor
import modules.vision
import modules.voice
import modules.system.shell
import modules.system.file_manager
import modules.coding.sandbox
import modules.system.input_control
import json
import asyncio

app = FastAPI(title="A.R.I.A. API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev, restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
async def get_status():
    """Returns current system status for the dashboard."""
    status = await sys_monitor.get_system_status()
    return status

from pydantic import BaseModel
class ModeRequest(BaseModel):
    mode: str

@app.post("/api/audio/mode")
async def set_audio_mode(request: ModeRequest):
    from modules.audio.audio_manager import audio_manager
    if request.mode in ["browser_audio", "raspberrypi_audio"]:
        audio_manager.set_mode(request.mode)
        return {"status": "success", "mode": audio_manager.mode}
    return {"status": "error", "message": "Invalid mode"}

# Voice Pack Endpoints
@app.get("/api/voices")
async def get_voices():
    from modules.audio.voice_pack_manager import voice_pack_manager
    return {"voices": voice_pack_manager.get_all_voices(), "active_id": voice_pack_manager.active_voice_id}

class VoiceModeRequest(BaseModel):
    voice_id: str

@app.post("/api/voices/active")
async def set_active_voice(request: VoiceModeRequest):
    from modules.audio.voice_pack_manager import voice_pack_manager
    if voice_pack_manager.set_active_voice(request.voice_id):
        return {"status": "success", "active_id": voice_pack_manager.active_voice_id}
    return {"status": "error", "message": "Voice ID not found"}

@app.get("/api/voices/preview/{voice_id}")
async def preview_voice(voice_id: str):
    from modules.audio.voice_pack_manager import voice_pack_manager
    from fastapi.responses import FileResponse
    import tempfile
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        temp_path = temp_audio.name
        
    try:
        await voice_pack_manager.generate_preview(voice_id, temp_path)
        # Fastapi background tasks can be used to delete the file, but for simplicity
        # we can just return it. Actually it's better to read it and return Response.
        # But FileResponse handles it fine if we just leave the temp file around briefly or clean it up.
        from fastapi import BackgroundTasks
        from fastapi.responses import Response
        import os
        
        with open(temp_path, "rb") as f:
            audio_data = f.read()
            
        os.remove(temp_path)
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Bidirectional streaming WebSocket for chat and commands."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            
            # Simple ping/pong or json parsing could go here
            try:
                msg = json.loads(data)
                user_input = msg.get("text", "")
            except:
                user_input = data
                
            if not user_input:
                continue
                
            # Process via orchestrator and stream back
            async for chunk in orchestrator.process(user_input):
                await websocket.send_json({"type": "chunk", "content": chunk})
                
            await websocket.send_json({"type": "done"})
            
    except WebSocketDisconnect:
        print("Client disconnected")

# Audio WebSocket functionality
active_audio_sockets = []

from modules.audio.audio_manager import audio_manager

async def browser_audio_callback(audio_bytes: bytes):
    for ws in active_audio_sockets:
        try:
            await ws.send_bytes(audio_bytes)
        except Exception as e:
            print(f"Error sending audio to browser: {e}")

audio_manager.register_browser_audio_callback(browser_audio_callback)

@app.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    """Dedicated endpoint for streaming audio binary chunks."""
    await websocket.accept()
    active_audio_sockets.append(websocket)
    try:
        while True:
            # Receive audio chunk (usually webm from browser)
            data = await websocket.receive_bytes()
            if not data:
                continue
            
            # Since the user might be using push-to-talk, one chunk might contain
            # the full recorded audio blob.
            from modules.audio.voice_pack_manager import voice_pack_manager
            active_voice = voice_pack_manager.get_active_voice()
            stt_lang = active_voice.get("stt_language", "en-US")
            
            text = audio_manager.process_webm_to_text(data, language=stt_lang)
            
            if text and text != "Could not understand audio" and not text.startswith("Error") and not text.startswith("Speech recognition request failed"):
                # Send the transcribed text back so the UI can show it,
                # then process it via orchestrator.
                await websocket.send_json({"type": "transcription", "text": text})
                
                # Send a signal to the main chat socket that processing started?
                # Actually, the best way is to process it here and stream text back
                # via the audio socket or just let the main socket handle it.
                # Let's stream it back via the main socket architecture by 
                # creating a background task that uses the audio websocket to send the text chunks.
                
                async def process_and_respond():
                    async for chunk in orchestrator.process(text):
                        await websocket.send_json({"type": "chunk", "content": chunk})
                    await websocket.send_json({"type": "done"})
                
                asyncio.create_task(process_and_respond())

    except WebSocketDisconnect:
        active_audio_sockets.remove(websocket)
        print("Audio client disconnected")



# Ensure playwright closes gracefully
@app.on_event("shutdown")
async def shutdown_event():
    from modules.browser.browser_agent import browser_agent
    await browser_agent.shutdown()
