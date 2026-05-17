import asyncio
import tempfile
import os
from core.tool_registry import aria_tool

class CodeSandbox:
    @aria_tool(name="run_python_code", description="Executes Python code in a temporary file and returns the output.")
    async def run_python(self, code: str) -> str:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
            
        try:
            process = await asyncio.create_subprocess_exec(
                "python3", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            output = stdout.decode().strip()
            error = stderr.decode().strip()
            
            result = ""
            if output:
                result += f"Output:\n{output}\n"
            if error:
                result += f"Error:\n{error}\n"
                
            return result or "Executed successfully with no output."
            
        except asyncio.TimeoutError:
            process.kill()
            return "Execution timed out."
        finally:
            os.unlink(temp_path)

    @aria_tool(name="run_javascript", description="Executes Node.js code in a temporary file and returns the output.")
    async def run_javascript(self, code: str) -> str:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            temp_path = f.name
            
        try:
            process = await asyncio.create_subprocess_exec(
                "node", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            output = stdout.decode().strip()
            error = stderr.decode().strip()
            
            result = ""
            if output:
                result += f"Output:\n{output}\n"
            if error:
                result += f"Error:\n{error}\n"
                
            return result or "Executed successfully with no output."
            
        except asyncio.TimeoutError:
            process.kill()
            return "Execution timed out."
        finally:
            os.unlink(temp_path)

sandbox = CodeSandbox()
