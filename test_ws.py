import asyncio
import websockets

async def test():
    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws") as ws:
            print("Connected to main ws")
    except Exception as e:
        print("Main WS Error:", e)

    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws/audio") as ws:
            print("Connected to audio ws")
    except Exception as e:
        print("Audio WS Error:", e)

asyncio.run(test())
