import asyncio
from core.tool_registry import aria_tool

class ShellExecutor:
    def __init__(self):
        self.jobs = {}
        self.counter = 0

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

    @aria_tool(name="execute_shell_background", description="Spawns a shell command in the background. Returns a job ID immediately. Use get_background_job_status to query status and outputs.")
    async def execute_shell_background(self, command: str) -> str:
        try:
            self.counter += 1
            job_id = f"job_{self.counter}"
            
            # Start process with pipes
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Use lists to accumulate output lines asynchronously without blocking
            stdout_data = []
            stderr_data = []
            
            async def read_stream(stream, storage):
                try:
                    while True:
                        line = await stream.readline()
                        if not line:
                            break
                        storage.append(line.decode(errors='replace'))
                except Exception:
                    pass

            stdout_task = asyncio.create_task(read_stream(process.stdout, stdout_data))
            stderr_task = asyncio.create_task(read_stream(process.stderr, stderr_data))
            
            self.jobs[job_id] = {
                "process": process,
                "command": command,
                "stdout": stdout_data,
                "stderr": stderr_data,
                "tasks": [stdout_task, stderr_task],
                "status": "running"
            }
            
            return f"Background job started. ID: {job_id} | Command: {command}"
        except Exception as e:
            return f"Failed to start background job: {e}"

    @aria_tool(name="get_background_job_status", description="Checks status, stdout, and stderr of a background job. action: 'status' (default) or 'terminate'.")
    async def get_background_job_status(self, job_id: str, action: str = "status") -> str:
        if job_id not in self.jobs:
            return f"Job ID {job_id} not found."
            
        job = self.jobs[job_id]
        proc = job["process"]
        
        if action == "terminate":
            if proc.returncode is None:
                try:
                    proc.terminate()
                    job["status"] = "terminated"
                    return f"Job {job_id} terminated."
                except Exception as e:
                    return f"Failed to terminate job: {e}"
            return f"Job {job_id} has already finished."

        ret = proc.returncode
        if ret is not None:
            job["status"] = f"finished (exit code {ret})"
        else:
            job["status"] = "running"
            
        stdout_txt = "".join(job["stdout"])
        stderr_txt = "".join(job["stderr"])
        
        # Guard against context limit flooding by taking the last 2000 chars
        if len(stdout_txt) > 2000:
            stdout_txt = "[...truncated...]\n" + stdout_txt[-2000:]
        if len(stderr_txt) > 2000:
            stderr_txt = "[...truncated...]\n" + stderr_txt[-2000:]
            
        res = f"Job ID: {job_id}\nCommand: {job['command']}\nStatus: {job['status']}\n"
        if stdout_txt:
            res += f"\n--- STDOUT ---\n{stdout_txt}"
        if stderr_txt:
            res += f"\n--- STDERR ---\n{stderr_txt}"
            
        return res

    @aria_tool(name="send_background_job_input", description="Sends standard input (stdin) text to a running background job.")
    async def send_background_job_input(self, job_id: str, input_text: str) -> str:
        if job_id not in self.jobs:
            return f"Job ID {job_id} not found."
            
        job = self.jobs[job_id]
        proc = job["process"]
        
        if proc.returncode is not None:
            return f"Job {job_id} has already finished."
            
        try:
            if not input_text.endswith('\n'):
                input_text += '\n'
            proc.stdin.write(input_text.encode())
            await proc.stdin.drain()
            return f"Successfully sent input to job {job_id}."
        except Exception as e:
            return f"Failed to send input to job {job_id}: {e}"

shell = ShellExecutor()
