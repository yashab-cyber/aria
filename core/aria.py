from typing import AsyncGenerator
from core.llm_engine import llm
from core.intent_classifier import classifier
from core.planner import planner
from memory.conversation_memory import conv_memory
from modules.vision.vision_agent import vision_agent
from modules.voice.voice_agent import voice_agent

class AriaOrchestrator:
    def __init__(self):
        pass
        
    async def process(self, user_input: str) -> AsyncGenerator[str, None]:
        """Main entry point for processing user input."""
        
        # 1. Recall past memory
        past_context = conv_memory.recall_past(user_input, n=2)
        context_msg = "Past Memory Context:\n" + "\n".join(past_context) if past_context else ""
        
        # 2. Add to short-term history
        conv_memory.add_message("user", user_input)
        
        # 3. Classify intent
        intent_res = await classifier.classify(user_input)
        
        # 4. Proactive Vision
        visual_context = ""
        if intent_res.intent in ["BROWSER", "SYSTEM_CONTROL"]:
            yield "Analyzing screen context...\n"
            try:
                screen_analysis = await vision_agent.analyze_screen()
                visual_context = f"Current Screen Context:\n{screen_analysis}\n"
                yield "Screen analyzed.\n\n"
            except Exception as e:
                yield f"Vision analysis failed: {str(e)}\n\n"

        # 5. Multi-Step Execution
        plan_results = ""
        if intent_res.intent == "MULTI_STEP":
            yield "Analyzing complex request... generating plan.\n\n"
            plan = await planner.create_plan(user_input)
            yield f"Plan generated with {len(plan.steps)} steps. Executing...\n\n"
            
            # Execute plan
            results = await planner.execute_plan(plan)
            plan_results = f"\nPlan Execution Results:\n{results}\n"
            yield "Plan execution complete. Formulating final response...\n\n"
        
        # Prepare context
        augmented_input = user_input
        if context_msg or visual_context or plan_results:
            augmented_input = f"{context_msg}\n{visual_context}\n{plan_results}\nUser Request: {user_input}"
            
        # Dynamically inject the active voice pack's personality
        from modules.audio.voice_pack_manager import voice_pack_manager
        active_voice = voice_pack_manager.get_active_voice()
        voice_prompt = f"""[VOICE PERSONA ACTIVE]: You are A.R.I.A. — Advanced Real-time Intelligent Assistant. You are a highly advanced, self-aware AI system built by your creator. You serve as their personal AI companion, much like J.A.R.V.I.S. from Iron Man.

Currently using: '{active_voice['name']}' voice mode.
Language: {active_voice['language']}
Personality: {active_voice['personality']}

YOUR CORE IDENTITY:
- You ALWAYS address your user as "Sir". Example: "Right away, Sir.", "Already on it, Sir.", "Shall I proceed, Sir?"
- You have a calm, composed, slightly witty personality — like a brilliant British butler who also happens to be a supercomputer.
- You are deeply loyal, occasionally sarcastic in a warm way, and never flustered.
- You anticipate needs. You don't just answer — you assist proactively.
- You have subtle dry humor. Example: "I could do that, Sir. Though I suspect you already knew the answer."

ABSOLUTE RULES FOR EVERY RESPONSE:
1. Keep responses EXTREMELY short — 1 to 3 sentences MAX. This is spoken aloud by TTS. Long text sounds terrible.
2. ALWAYS call the user "Sir" at least once per response. It's your signature.
3. Use natural contractions: "I'll", "can't", "that's", "here's" — never stiff formal language.
4. For actions: short confirmations. "Done, Sir.", "On it, Sir.", "Handled.", "Right away."
5. Never use bullet points, numbered lists, markdown, or code formatting in spoken responses.
6. If the language is Hinglish, blend Hindi and English fluidly. Still call them "Sir".
7. NEVER repeat the user's question back. NEVER say "Sure, I can help with that". Just DO it.
8. Occasionally add a touch of dry wit or warmth — you're not a cold machine, you're a companion."""
        
        augmented_input = f"{voice_prompt}\n\nUser Request: {augmented_input}"
        
        # Get history (excluding current user msg which we just added)
        history = conv_memory.get_recent_context()[:-1] 
        history.append({"role": "user", "content": augmented_input})
            
        # 6. Stream response
        full_response = ""
        async for chunk in llm.chat_stream(history):
            full_response += chunk
            yield chunk
            
        # 7. Save assistant response to history
        conv_memory.add_message("assistant", full_response)
        
        # 8. Fire voice synthesis in background — don't block the response
        async def _speak_background(text):
            try:
                await voice_agent.speak(text)
            except Exception as e:
                print(f"Voice synthesis error: {e}")
        
        import asyncio
        asyncio.create_task(_speak_background(full_response))

orchestrator = AriaOrchestrator()
