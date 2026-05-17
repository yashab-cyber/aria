from pydantic import BaseModel, Field
from typing import Optional
import json
from core.llm_engine import llm
from config import config
import litellm
from litellm import acompletion

class IntentResult(BaseModel):
    intent: str = Field(description="One of: CHAT, SYSTEM_CONTROL, BROWSER, CODE, RESEARCH, EMAIL, MEMORY_QUERY, VISION, MULTI_STEP")
    confidence: float = Field(default=1.0, description="Confidence score between 0.0 and 1.0")
    entities: dict = Field(default_factory=dict, description="Extracted entities from the user prompt")
    requires_tools: bool = Field(default=False, description="Whether this intent likely requires calling external tools")

class IntentClassifier:
    async def classify(self, user_input: str) -> IntentResult:
        """Classifies the user's input into an intent category."""
        prompt = f"""Analyze the user's input and classify their intent.
Available categories:
- CHAT: General conversation, greetings, simple questions.
- SYSTEM_CONTROL: Running shell commands, managing files, processes, volume, etc.
- BROWSER: Opening websites, clicking, typing, scraping.
- CODE: Writing scripts, fixing errors, running code blocks.
- RESEARCH: Searching the web for information.
- EMAIL: Reading or sending emails.
- MEMORY_QUERY: Asking A.R.I.A about past conversations or stored facts.
- VISION: Analyzing the screen, reading text from screen, finding UI elements, analyzing images, comparing screenshots, monitoring screen changes, UI/UX analysis.
- MULTI_STEP: A complex request requiring multiple different modules to work together.

User input: "{user_input}"
"""
        
        response = await acompletion(
            model=llm.model,
            messages=[{"role": "user", "content": prompt}],
            functions=[{
                "name": "report_intent",
                "description": "Report the classified intent",
                "parameters": IntentResult.model_json_schema()
            }],
            function_call={"name": "report_intent"},
            temperature=0.1,
            api_base=config.api_base
        )
        
        args = response.choices[0].message.function_call.arguments
        return IntentResult(**json.loads(args))

classifier = IntentClassifier()
