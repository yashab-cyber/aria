import os
import base64
import pyautogui
from io import BytesIO
from core.tool_registry import aria_tool
from config import config
from PIL import Image
import litellm
from litellm import acompletion

class VisionAgent:
    def __init__(self):
        pass

    @aria_tool(name="analyze_screen", description="Captures the screen and uses Vision AI to describe what is currently visible.")
    async def analyze_screen(self, prompt: str = "What is on my screen?") -> str:
        try:
            # Capture the screen using pyautogui
            screenshot = pyautogui.screenshot()
            
            # Convert PIL Image to Base64
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            # Send to LLM
            response = await acompletion(
                model=config.aria_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_str}"
                                }
                            }
                        ]
                    }
                ],
                api_base=config.api_base,
                max_tokens=300,
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error analyzing screen: {str(e)}"

vision_agent = VisionAgent()
