import os
import asyncio
from core.tool_registry import aria_tool
from core.state import state_manager

class DevTools:
    @aria_tool(name="run_syntax_check", description="Performs syntax/compilation checks on a file based on its extension (supports Python, JavaScript, TypeScript, Go, Rust).")
    async def run_syntax_check(self, filepath: str) -> str:
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
            
        ext = os.path.splitext(filepath)[1].lower()
        
        try:
            if ext == '.py':
                process = await asyncio.create_subprocess_exec(
                    "python3", "-m", "py_compile", filepath,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            elif ext in ['.js', '.jsx']:
                process = await asyncio.create_subprocess_exec(
                    "node", "--check", filepath,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            elif ext in ['.ts', '.tsx']:
                process = await asyncio.create_subprocess_exec(
                    "npx", "tsc", "--noEmit", filepath,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            elif ext == '.go':
                process = await asyncio.create_subprocess_exec(
                    "go", "vet", filepath,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            elif ext == '.rs':
                process = await asyncio.create_subprocess_exec(
                    "rustc", "--crate-type", "lib", filepath,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:
                return f"Unsupported file type for syntax check: {ext}"
                
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
            out = stdout.decode().strip()
            err = stderr.decode().strip()
            
            if process.returncode == 0:
                return f"Syntax check passed successfully for {filepath}."
            else:
                return f"Syntax check failed for {filepath}.\nError:\n{err or out}"
        except Exception as e:
            return f"Error running syntax check: {str(e)}"

    @aria_tool(name="run_project_tests", description="Detects the workspace project type and runs the corresponding test suite (pytest, npm test, cargo test, go test).")
    async def run_project_tests(self, cwd: str = ".") -> str:
        try:
            cmd = None
            if os.path.exists(os.path.join(cwd, "package.json")):
                cmd = ["npm", "test"]
            elif os.path.exists(os.path.join(cwd, "pytest.ini")) or os.path.exists(os.path.join(cwd, "conftest.py")) or any(f.endswith(".py") for f in os.listdir(cwd) if "test" in f):
                cmd = ["pytest"]
            elif os.path.exists(os.path.join(cwd, "Cargo.toml")):
                cmd = ["cargo", "test"]
            elif any(f.endswith("_test.go") for f in os.listdir(cwd)):
                cmd = ["go", "test", "./..."]
                
            if not cmd:
                return "Could not auto-detect a test runner in the specified directory."
                
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            out = stdout.decode().strip()
            err = stderr.decode().strip()
            
            res = f"Ran command: {' '.join(cmd)}\nExit Code: {process.returncode}\n"
            if out:
                res += f"\nStdout:\n{out[:3000]}\n"
            if err:
                res += f"\nStderr:\n{err[:3000]}\n"
            return res
        except Exception as e:
            return f"Error executing tests: {str(e)}"

    @aria_tool(name="git_status", description="Shows the working tree status.")
    async def git_status(self) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return stdout.decode().strip() or stderr.decode().strip()
        except Exception as e:
            return f"Git error: {str(e)}"

    @aria_tool(name="git_diff", description="Shows changes between commits, commit and working tree, etc.")
    async def git_diff(self, filepath: str = "") -> str:
        try:
            cmd = ["git", "diff"]
            if filepath:
                cmd.append(filepath)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            diff_out = stdout.decode().strip()
            if not diff_out:
                return "No changes found."
            if len(diff_out) > 5000:
                diff_out = diff_out[:5000] + "\n...[truncated due to length]..."
            return diff_out
        except Exception as e:
            return f"Git error: {str(e)}"

    @aria_tool(name="git_commit", description="Record changes to the repository with a commit message.")
    async def git_commit(self, message: str, stage_all: bool = True) -> str:
        try:
            if stage_all:
                process_add = await asyncio.create_subprocess_exec(
                    "git", "add", "-A",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process_add.communicate()
                
            process_commit = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process_commit.communicate()
            return stdout.decode().strip() or stderr.decode().strip()
        except Exception as e:
            return f"Git error: {str(e)}"

    @aria_tool(name="git_log", description="Shows the commit logs.")
    async def git_log(self, limit: int = 5) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "log", f"-n", str(limit), "--oneline",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return stdout.decode().strip() or stderr.decode().strip()
        except Exception as e:
            return f"Git error: {str(e)}"

    @aria_tool(name="get_code_outline", description="Extracts classes, functions, and method definitions from a code file to understand its structure.")
    async def get_code_outline(self, filepath: str) -> str:
        if not os.path.exists(filepath):
            return f"Error: File not found: {filepath}"
            
        ext = os.path.splitext(filepath)[1].lower()
        if ext != '.py':
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                outline = []
                import re
                for i, line in enumerate(lines, 1):
                    match = re.search(r'\b(class|function|func|fn)\b\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
                    if match:
                        outline.append(f"Line {i}: {line.strip()}")
                return "\n".join(outline) or "No definitions found."
            except Exception as e:
                return f"Error parsing file: {str(e)}"
                
        try:
            import ast
            with open(filepath, 'r', encoding='utf-8') as f:
                node = ast.parse(f.read(), filename=filepath)
            
            outline = []
            for item in node.body:
                if isinstance(item, ast.ClassDef):
                    outline.append(f"Class: {item.name} (Line {item.lineno})")
                    for subitem in item.body:
                        if isinstance(subitem, ast.FunctionDef):
                            args = [arg.arg for arg in subitem.args.args]
                            outline.append(f"  - Method: {subitem.name}({', '.join(args)}) (Line {subitem.lineno})")
                elif isinstance(item, ast.FunctionDef):
                    args = [arg.arg for arg in item.args.args]
                    outline.append(f"Function: {item.name}({', '.join(args)}) (Line {item.lineno})")
            return "\n".join(outline) or "No Python classes or functions found."
        except Exception as e:
            return f"Error parsing AST: {str(e)}"

dev_tools = DevTools()
