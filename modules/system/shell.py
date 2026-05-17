import asyncio
from core.tool_registry import aria_tool

class ShellExecutor:
    @aria_tool(name="execute_shell", description="Executes a shell command on the host system.")
    async def execute_shell(self, command: str, timeout: int = 15) -> str:
        """Executes a shell command and returns stdout and stderr."""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                output = stdout.decode().strip()
                error = stderr.decode().strip()
                
                result = f"Exit Code: {process.returncode}\n"
                if output:
                    result += f"Output:\n{output}\n"
                if error:
                    result += f"Error:\n{error}\n"
                    
                return result
            except asyncio.TimeoutError:
                process.kill()
                return f"Command timed out after {timeout} seconds."
        except Exception as e:
            return f"Failed to execute command: {str(e)}"

shell = ShellExecutor()
