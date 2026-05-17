import uvicorn
from rich.console import Console
from config import config

console = Console()

def main():
    console.print("[bold cyan]A.R.I.A. Initialization Sequence Started...[/bold cyan]")
    console.print(f"[green]Starting server on {config.aria_host}:{config.aria_port}...[/green]")
    
    # We will import the FastAPI app here later once server.py is built
    uvicorn.run("server:app", host=config.aria_host, port=config.aria_port, reload=True)

if __name__ == "__main__":
    main()
