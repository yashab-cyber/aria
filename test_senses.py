import asyncio
from dotenv import load_dotenv
load_dotenv()
from modules.vision.vision_agent import vision_agent
from modules.voice.voice_agent import voice_agent

async def test_senses():
    print("Testing Text-to-Speech (Talk)...")
    res1 = await voice_agent.speak("Hello, I am ARIA. I can now speak!")
    print(res1)
    
    print("\nTesting Screen Capture (See)...")
    # We won't actually hit the API without keys, just check if screenshot logic doesn't crash
    # Instead of analyze_screen, let's just make sure it imported successfully and we can take a screenshot
    import pyautogui
    try:
        s = pyautogui.screenshot()
        print(f"Screenshot successful! Size: {s.size}")
    except Exception as e:
        print(f"Screenshot failed: {e}")
        
    print("\nTesting Speech-to-Text (Listen)...")
    print("Please say something clearly into the microphone...")
    res3 = await voice_agent.listen()
    print("You said:", res3)

if __name__ == "__main__":
    asyncio.run(test_senses())
