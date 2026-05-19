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
from rich.live import Live
from rich.spinner import Spinner

# Load environment variables
load_dotenv()
ARIA_HOST = os.getenv("ARIA_HOST", "127.0.0.1")
ARIA_PORT = os.getenv("ARIA_PORT", "8000")
WS_URL = f"ws://{ARIA_HOST}:{ARIA_PORT}/ws"

console = Console()

async def chat_loop(websocket):
    """Handles sending user input and receiving streaming responses."""
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("[yellow]Exiting ARIA CLI...[/yellow]")
                break
                
            if not user_input.strip():
                continue
                
            # Send to server
            await websocket.send(json.dumps({"text": user_input}))
            
            console.print("\n[bold magenta]A.R.I.A.[/bold magenta]")
            
            full_response = ""
            current_tool_spinner = None
            
            # Receive response stream
            while True:
                response_text = await websocket.recv()
                
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError:
                    # Raw text fallback
                    console.print(response_text, end="")
                    continue
                
                msg_type = data.get("type")
                
                if msg_type == "chunk":
                    chunk_content = data.get("content", "")
                    
                    # Some chunks might actually be JSON tool logs if not parsed perfectly, 
                    # but server.py should send them as tool_start type directly now.
                    try:
                        if chunk_content.strip().startswith('{"type": "tool_'):
                            tool_data = json.loads(chunk_content)
                            if tool_data.get("type") == "tool_start":
                                console.print(f"\n[bold yellow]⚡ Executing Tool:[/bold yellow] {tool_data.get('tool')}")
                                console.print(f"[dim]{json.dumps(tool_data.get('args', {}), indent=2)}[/dim]")
                            elif tool_data.get("type") == "tool_end":
                                console.print(f"[bold green]✓ Tool Completed:[/bold green] {tool_data.get('tool')}\n")
                            continue
                    except:
                        pass
                        
                    full_response += chunk_content
                    # Print raw chunks as they come for immediate feedback
                    print(chunk_content, end="", flush=True)
                    
                elif msg_type == "tool_start":
                    console.print(f"\n[bold yellow]⚡ Executing Tool:[/bold yellow] {data.get('tool')}")
                    console.print(f"[dim]{json.dumps(data.get('args', {}), indent=2)}[/dim]")
                    
                elif msg_type == "tool_end":
                    console.print(f"[bold green]✓ Tool Completed:[/bold green] {data.get('tool')}\n")
                    
                elif msg_type == "done":
                    # Optionally, we could clear the raw text and render nice markdown here,
                    # but for terminal, streaming is usually better.
                    print("\n")
                    break
                    
        except websockets.exceptions.ConnectionClosed:
            console.print("[bold red]Connection lost to server.[/bold red]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            break

from rich.box import ROUNDED
from rich.align import Align

async def main():
    # Sleek, minimalist startup panel similar to Claude Code
    logo_panel = Panel(
        Align.center("[bold cyan]A . R . I . A[/bold cyan]\n[dim]Terminal Interface[/dim]", vertical="middle"),
        box=ROUNDED,
        border_style="cyan",
        width=40,
        padding=(1, 2)
    )
    console.print(logo_panel)
    console.print("[dim]Type 'exit' to quit.[/dim]\n")
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            console.print(f"[green]Connected to ARIA Backend at {WS_URL}[/green]")
            await chat_loop(websocket)
    except ConnectionRefusedError:
        console.print(f"[bold red]Failed to connect to {WS_URL}. Is the server running?[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
        sys.exit(0)
