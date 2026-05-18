"""
A.R.I.A. System Intelligence — Deep system awareness.

Full hardware/OS/network/process monitoring and control.
"""

import psutil
import asyncio
import os
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
            "disk_free_gb": round(disk.free / (1024**3), 2),
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
        processes = sorted(processes, key=lambda p: p.get('cpu_percent', 0) or 0, reverse=True)[:20]
        result = "Top Processes:\nPID | Name | CPU% | MEM%\n" + "-"*40 + "\n"
        for p in processes:
            result += f"{p['pid']} | {p['name']} | {p['cpu_percent']}% | {round(p['memory_percent'] or 0, 1)}%\n"
        return result

    @aria_tool(name="kill_process", description="Kill a process by PID or by name. Use force=True for SIGKILL.")
    async def kill_process(self, pid: int = 0, name: str = "", force: bool = False) -> str:
        import signal
        try:
            if pid > 0:
                p = psutil.Process(pid)
                pname = p.name()
                if force:
                    p.kill()
                else:
                    p.terminate()
                return f"{'Killed' if force else 'Terminated'} process {pname} (PID {pid})."
            elif name:
                killed = []
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if name.lower() in proc.info['name'].lower():
                            if force:
                                proc.kill()
                            else:
                                proc.terminate()
                            killed.append(f"{proc.info['name']} (PID {proc.info['pid']})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                if killed:
                    return f"{'Killed' if force else 'Terminated'}: {', '.join(killed)}"
                return f"No process found matching: {name}"
            else:
                return "Provide either pid or name."
        except psutil.NoSuchProcess:
            return f"Process {pid} not found."
        except psutil.AccessDenied:
            return f"Access denied. Try running ARIA with elevated privileges."
        except Exception as e:
            return f"Kill failed: {e}"

    @aria_tool(name="get_network_info", description="Gets network information: IP addresses, interfaces, active connections, and WiFi SSID.")
    async def get_network_info(self) -> str:
        lines = ["Network Info:\n"]
        # Interfaces and IPs
        addrs = psutil.net_if_addrs()
        for iface, addr_list in addrs.items():
            for addr in addr_list:
                if addr.family.name == "AF_INET":
                    lines.append(f"  {iface}: {addr.address} (netmask: {addr.netmask})")
        # Stats
        stats = psutil.net_if_stats()
        for iface, stat in stats.items():
            if stat.isup:
                speed = f"{stat.speed}Mbps" if stat.speed else "unknown speed"
                lines.append(f"  {iface}: UP | {speed}")
        # WiFi SSID (Linux)
        try:
            proc = await asyncio.create_subprocess_shell(
                "iwgetid -r 2>/dev/null || nmcli -t -f active,ssid dev wifi | grep '^yes' | cut -d: -f2",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            ssid = stdout.decode().strip()
            if ssid:
                lines.append(f"  WiFi SSID: {ssid}")
        except Exception:
            pass
        # Active connections count
        conns = psutil.net_connections(kind='inet')
        established = len([c for c in conns if c.status == 'ESTABLISHED'])
        listening = len([c for c in conns if c.status == 'LISTEN'])
        lines.append(f"\n  Active connections: {established} established, {listening} listening")
        return "\n".join(lines)

    @aria_tool(name="get_battery_info", description="Gets battery percentage, charging status, and estimated time remaining.")
    async def get_battery_info(self) -> str:
        battery = psutil.sensors_battery()
        if not battery:
            return "No battery detected (desktop system or unavailable)."
        pct = battery.percent
        plugged = "Charging" if battery.power_plugged else "Discharging"
        time_left = ""
        if battery.secsleft > 0 and not battery.power_plugged:
            hours = battery.secsleft // 3600
            mins = (battery.secsleft % 3600) // 60
            time_left = f" | {hours}h {mins}m remaining"
        return f"Battery: {pct}% | {plugged}{time_left}"

    @aria_tool(name="get_screen_resolution", description="Gets the current screen resolution and display info.")
    async def get_screen_resolution(self) -> str:
        try:
            import pyautogui
            w, h = pyautogui.size()
            result = f"Screen resolution: {w}x{h}"
            # Try to get more detail from xrandr
            proc = await asyncio.create_subprocess_shell(
                "xrandr --current 2>/dev/null | grep ' connected'",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            xrandr = stdout.decode().strip()
            if xrandr:
                result += f"\nDisplays:\n{xrandr}"
            return result
        except Exception as e:
            return f"Resolution detection failed: {e}"


sys_monitor = SystemMonitor()
