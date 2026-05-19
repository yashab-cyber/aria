#!/usr/bin/env python3
import asyncio
import json
import os
import sys
from dotenv import load_dotenv
import websockets
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.align import Align
from rich.text import Text

# Load environment variables
load_dotenv()
ARIA_HOST = os.getenv("ARIA_HOST", "127.0.0.1")
ARIA_PORT = os.getenv("ARIA_PORT", "8000")
WS_URL = f"ws://{ARIA_HOST}:{ARIA_PORT}/ws"

console = Console()

ASCII_LOGO = """[bold cyan]
    _    ____  ___    _    
   / \\  |  _ \\|_ _|  / \\   
  / _ \\ | |_) || |  / _ \\  
 / ___ \\|  _ < | | / ___ \\ 
/_/   \\_\\_| \\_\\___/_/   \\_\\
[/bold cyan]"""

async def chat_loop(websocket):
    """Handles sending user input and receiving streaming responses."""
    while True:
        try:
            # Get user input
            console.print("")
            user_input = Prompt.ask("[bold cyan]❯ You[/bold cyan]")
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("\n[yellow]Shutting down A.R.I.A. CLI... Goodbye.[/yellow]")
                break
                
            if not user_input.strip():
                continue
                
            # Send to server
            await websocket.send(json.dumps({"text": user_input}))
            
            console.print("\n[bold magenta]❖ A.R.I.A.[/bold magenta]")
            
            full_response = ""
            is_status_active = True
            
            # Start animated spinner
            status = console.status("[bold yellow]Processing...[/bold yellow]", spinner="bouncingBar")
            status.start()
            
            # Receive response stream
            while True:
                try:
                    response_text = await websocket.recv()
                    data = json.loads(response_text)
                except json.JSONDecodeError:
                    if is_status_active:
                        status.stop()
                        is_status_active = False
                    console.print(response_text, end="")
                    continue
                except websockets.exceptions.ConnectionClosed:
                    if is_status_active: status.stop()
                    raise
                
                msg_type = data.get("type")
                
                if msg_type == "chunk":
                    chunk_content = data.get("content", "")
                    
                    # Intercept nested tool JSON from chunk text if it slipped in
                    try:
                        if chunk_content.strip().startswith('{"type": "tool_'):
                            tool_data = json.loads(chunk_content)
                            if tool_data.get("type") == "tool_start":
                                if not is_status_active:
                                    print("\n")
                                    status.start()
                                    is_status_active = True
                                status.update(f"[bold yellow]⚡ Executing:[/bold yellow] {tool_data.get('tool')}")
                            elif tool_data.get("type") == "tool_end":
                                if is_status_active:
                                    status.stop()
                                    is_status_active = False
                                console.print(f"[bold green]✓ Tool Completed:[/bold green] {tool_data.get('tool')}")
                                status.start()
                                is_status_active = True
                            continue
                    except:
                        pass
                        
                    if is_status_active:
                        status.stop()
                        is_status_active = False
                        
                    full_response += chunk_content
                    print(chunk_content, end="", flush=True)
                    
                elif msg_type == "tool_start":
                    if not is_status_active:
                        print("\n")
                        status.start()
                        is_status_active = True
                    status.update(f"[bold yellow]⚡ Executing Tool:[/bold yellow] {data.get('tool')}")
                    
                elif msg_type == "tool_end":
                    if is_status_active:
                        status.stop()
                        is_status_active = False
                    console.print(f"[bold green]✓ Completed:[/bold green] {data.get('tool')}")
                    status.start()
                    is_status_active = True
                    
                elif msg_type == "done":
                    if is_status_active:
                        status.stop()
                    print("\n")
                    break
                    
        except websockets.exceptions.ConnectionClosed:
            console.print("\n[bold red]✕ Connection lost to server.[/bold red]")
            break
        except Exception as e:
            if 'status' in locals() and is_status_active:
                status.stop()
            console.print(f"\n[bold red]✕ Error:[/bold red] {str(e)}")
            break

from rich.box import ROUNDED

async def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Beautiful ASCII Logo Panel
    logo_panel = Panel(
        Align.center(f"{ASCII_LOGO}\n[dim]Advanced Terminal Interface v1.0[/dim]", vertical="middle"),
        box=ROUNDED,
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(logo_panel)
    console.print(Align.center("[dim]Type 'exit' or 'quit' to terminate the session.[/dim]\n"))
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            console.print(f" [green]●[/green] Connected to A.R.I.A. Backend ([dim]{WS_URL}[/dim])")
            await chat_loop(websocket)
    except ConnectionRefusedError:
        console.print(f"\n[bold red]✕ Failed to connect to {WS_URL}[/bold red]")
        console.print("[yellow]Please ensure the main server is running: `python main.py`[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]✕ Critical Error:[/bold red] {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Session aborted by user. Exiting...[/yellow]")
        sys.exit(0)
