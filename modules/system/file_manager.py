import os
import asyncio
from core.tool_registry import aria_tool

class FileManager:
    @aria_tool(name="read_file", description="Reads the contents of a file.")
    async def read_file(self, filepath: str) -> str:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    @aria_tool(name="write_file", description="Writes content to a file, overwriting existing content.")
    async def write_file(self, filepath: str, content: str) -> str:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {filepath}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    @aria_tool(name="list_directory", description="Lists contents of a directory.")
    async def list_directory(self, path: str = ".") -> str:
        try:
            items = os.listdir(path)
            return "\n".join(items)
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    @aria_tool(name="replace_in_file", description="Replaces exact occurrences of target_text with replacement_text in a file.")
    async def replace_in_file(self, filepath: str, target_text: str, replacement_text: str) -> str:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            if target_text not in content:
                return f"Error: target_text not found in {filepath}."
            content = content.replace(target_text, replacement_text)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully replaced text in {filepath}"
        except Exception as e:
            return f"Error modifying file: {str(e)}"

    @aria_tool(name="search_code", description="Searches for a string pattern across files in a directory using grep.")
    async def search_code(self, pattern: str, path: str = ".") -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                "grep", "-rnIE", pattern, path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            output = stdout.decode().strip()
            
            if not output:
                return f"No matches found for '{pattern}' in {path}."
                
            # Limit output length to prevent overflowing context
            if len(output) > 2000:
                output = output[:2000] + "\n...[truncated due to length]..."
            return output
        except asyncio.TimeoutError:
            if process:
                process.kill()
            return "Search timed out."
        except Exception as e:
            return f"Error searching code: {str(e)}"

file_manager = FileManager()
