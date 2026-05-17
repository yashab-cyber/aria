import psutil
from core.tool_registry import aria_tool

class SystemMonitor:
    @aria_tool(name="get_system_status", description="Gets current CPU, RAM, and Disk usage of the host.")
    async def get_system_status(self) -> dict:
        cpu = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu,
            "ram_percent": memory.percent,
            "ram_used_gb": round(memory.used / (1024**3), 2),
            "ram_total_gb": round(memory.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2)
        }

    @aria_tool(name="list_processes", description="Lists running processes, optionally filtered by name.")
    async def list_processes(self, name_filter: str = "") -> str:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if not name_filter or name_filter.lower() in proc.info['name'].lower():
                    processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        # Sort by CPU usage and return top 20
        processes = sorted(processes, key=lambda p: p.get('cpu_percent', 0) or 0, reverse=True)[:20]
        
        result = "Top Processes:\nPID | Name | CPU% | MEM%\n" + "-"*40 + "\n"
        for p in processes:
            result += f"{p['pid']} | {p['name']} | {p['cpu_percent']}% | {round(p['memory_percent'] or 0, 1)}%\n"
            
        return result

sys_monitor = SystemMonitor()
