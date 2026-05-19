import json
import asyncio
import os
import tempfile
import traceback
import dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from config import config
from core.aria import orchestrator
from memory.memory_manager import memory_manager
from modules.system.system_info import sys_monitor
from modules.audio.audio_manager import audio_manager
from modules.audio.voice_pack_manager import voice_pack_manager
from modules.scheduler.scheduler_engine import scheduler
from modules.browser.browser_agent import browser_agent
from modules.devices.device_manager import device_manager, set_main_loop

import modules.vision
import modules.voice
import modules.system.shell
import modules.system.file_manager
import modules.coding.sandbox
import modules.system.input_control
import modules.scheduler
import modules.notifications

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

@app.get("/api/memory/status")
async def get_memory_status():
    """Returns the status of all three memory tiers."""
    return memory_manager.get_memory_status()

# ── Memory Browser Endpoints ──

@app.get("/api/memory/search")
async def search_memory(q: str = "", limit: int = 10):
    # Use Episodic memory recall
    if not q:
        # Just return recent summaries if no query
        items = memory_manager.episodic.get_session_summaries(n=limit)
        return {"results": items}
        
    items = memory_manager.episodic.recall_similar(q, n_results=limit)
    return {"results": items}

@app.delete("/api/memory/sessions/{session_id}")
async def delete_memory_session(session_id: str):
    try:
        # Delete summary and all messages for this session
        memory_manager.episodic.store.delete_from_collection(
            "conversations", where={"session_id": session_id}
        )
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ── Config / Settings Endpoints ──

@app.get("/api/config")
async def get_config():
    """Returns the current configuration."""
    # Convert config to dict
    config_dict = config.model_dump()
            
    return {"config": config_dict}

@app.post("/api/config")
async def update_config(payload: dict):
    """Updates the .env file and the in-memory config object."""
    try:
        env_path = ".env"
        if not os.path.exists(env_path):
            open(env_path, 'a').close() # Create if doesn't exist
            
        for key, value in payload.items():
            if value is None:
                continue
                
            env_key = key.upper()
            
            # Write to .env
            dotenv.set_key(env_path, env_key, str(value))
            
            # Update in memory
            if hasattr(config, key):
                # Handle type conversion based on original type
                orig_val = getattr(config, key)
                if isinstance(orig_val, int):
                    setattr(config, key, int(value))
                elif isinstance(orig_val, float):
                    setattr(config, key, float(value))
                else:
                    setattr(config, key, value)
                    
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class ModeRequest(BaseModel):
    mode: str

@app.post("/api/audio/mode")
async def set_audio_mode(request: ModeRequest):
    if request.mode in ["browser_audio", "raspberrypi_audio"]:
        audio_manager.set_mode(request.mode)
        return {"status": "success", "mode": audio_manager.mode}
    return {"status": "error", "message": "Invalid mode"}

# Voice Pack Endpoints
@app.get("/api/voices")
async def get_voices():
    return {"voices": voice_pack_manager.get_all_voices(), "active_id": voice_pack_manager.active_voice_id}

class VoiceModeRequest(BaseModel):
    voice_id: str

@app.post("/api/voices/active")
async def set_active_voice(request: VoiceModeRequest):
    if voice_pack_manager.set_active_voice(request.voice_id):
        return {"status": "success", "active_id": voice_pack_manager.active_voice_id}
    return {"status": "error", "message": "Voice ID not found"}

@app.get("/api/voices/preview/{voice_id}")
async def preview_voice(voice_id: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        temp_path = temp_audio.name
        
    try:
        await voice_pack_manager.generate_preview(voice_id, temp_path)
        with open(temp_path, "rb") as f:
            audio_data = f.read()
            
        os.remove(temp_path)
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Scheduler REST endpoints
@app.get("/api/scheduler/jobs")
async def get_scheduled_jobs():
    return {"jobs": scheduler.get_jobs_for_api()}

@app.delete("/api/scheduler/jobs/{job_id}")
async def delete_scheduled_job(job_id: str):
    result = await scheduler.cancel_scheduled_task(job_id)
    return {"result": result}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Bidirectional streaming WebSocket for chat and commands."""
    await websocket.accept()
    # Start a new memory session for this connection
    memory_manager.start_session()
    try:
        while True:
            data = await websocket.receive_text()
            
            # Simple ping/pong or json parsing could go here
            try:
                msg = json.loads(data)
                user_input = msg.get("text", "")
            except json.JSONDecodeError:
                user_input = data
                
            if not user_input:
                continue
                
            # Process via orchestrator and stream back
            async def send_event(evt):
                await websocket.send_json(evt)

            try:
                async for chunk in orchestrator.process(user_input, send_event=send_event):
                    await websocket.send_json({"type": "chunk", "content": chunk})
            except Exception as e:
                print(f"Orchestrator error: {e}")
                traceback.print_exc()
                await websocket.send_json({"type": "chunk", "content": f"\n\n**System Error:** `{str(e)}`"})
            finally:
                await websocket.send_json({"type": "done"})
            
    except WebSocketDisconnect:
        # Flush working memory → episodic on disconnect
        await memory_manager.end_session()
        print("Client disconnected — session committed to episodic memory")

# Audio WebSocket functionality
active_audio_sockets = []

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
            active_voice = voice_pack_manager.get_active_voice()
            stt_lang = active_voice.get("stt_language", "en-US")
            
            text = await audio_manager.process_webm_to_text(data, language=stt_lang)
            
            if text and text != "Could not understand audio" and not text.startswith("Error") and not text.startswith("Speech recognition request failed"):
                # Send the transcribed text back so the UI can show it,
                # then process it via orchestrator.
                await websocket.send_json({"type": "transcription", "text": text})
                
                # Let's stream it back via the main socket architecture by 
                # creating a background task that uses the audio websocket to send the text chunks.
                async def send_event(evt):
                    await websocket.send_json(evt)

                async def process_and_respond():
                    try:
                        async for chunk in orchestrator.process(text, send_event=send_event):
                            await websocket.send_json({"type": "chunk", "content": chunk})
                    except Exception as e:
                        print(f"Orchestrator audio error: {e}")
                        traceback.print_exc()
                        await websocket.send_json({"type": "chunk", "content": f"\n\n**System Error:** `{str(e)}`"})
                    finally:
                        await websocket.send_json({"type": "done"})
                
                asyncio.create_task(process_and_respond())

    except WebSocketDisconnect:
        active_audio_sockets.remove(websocket)
        print("Audio client disconnected")

@app.websocket("/ws/device")
async def device_websocket_endpoint(websocket: WebSocket):
    """Endpoint for Android ARIA Agents to connect."""
    await websocket.accept()
    device_name = None
    try:
        # Expect register payload first
        data = await websocket.receive_text()
        payload = json.loads(data)
        if payload.get("type") == "register":
            device_name = await device_manager.register_device(websocket, payload)
            
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if payload.get("type") == "pong":
                continue
            elif payload.get("type") == "result":
                await device_manager.handle_response(payload)
                
    except WebSocketDisconnect:
        if device_name:
            device_manager.remove_device(device_name)
        print(f"Device disconnected: {device_name}")

# Start scheduler on server startup
@app.on_event("startup")
async def startup_event():
    set_main_loop(asyncio.get_event_loop())
    await scheduler.start()

# Ensure playwright closes gracefully and memory is flushed
@app.on_event("shutdown")
async def shutdown_event():
    # Shut down the scheduler
    await scheduler.shutdown()
    # Flush any active memory session
    await memory_manager.end_session()
    # Consolidate old memories on shutdown
    await memory_manager.consolidate_old_memories()
    await browser_agent.shutdown()
