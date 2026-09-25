#!/usr/bin/env python3
"""
System Spec Sheet Generator — Pathfinder God
Run on the hub laptop to capture: hardware, models, network, env, tooling.
Output: JSON + human-readable Markdown.
"""

import json
import platform
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

def run_cmd(cmd, shell=True):
    try:
        return subprocess.check_output(cmd, shell=shell, stderr=subprocess.STDOUT, text=True, timeout=10).strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.output.strip()}"
    except Exception as e:
        return f"ERROR: {e}"

def get_hardware():
    info = {}
    info["platform"] = platform.platform()
    info["processor"] = platform.processor()
    info["architecture"] = platform.architecture()
    info["python_version"] = platform.python_version()
    
    # CPU
    try:
        import psutil
        info["cpu_count_logical"] = psutil.cpu_count(logical=True)
        info["cpu_count_physical"] = psutil.cpu_count(logical=False)
        info["cpu_freq_mhz"] = psutil.cpu_freq().current if psutil.cpu_freq() else "N/A"
        info["ram_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        info["ram_available_gb"] = round(psutil.virtual_memory().available / (1024**3), 1)
        
        # Disk
        for part in psutil.disk_partitions():
            if part.fstype:
                usage = psutil.disk_usage(part.mountpoint)
                info[f"disk_{part.device.replace(':', '').replace('\\', '')}"] = {
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "mount": part.mountpoint
                }
    except ImportError:
        info["psutil"] = "not installed"
    
    # GPU (Windows)
    if platform.system() == "Windows":
        gpu = run_cmd('wmic path win32_VideoController get Name,AdapterRAM,DriverVersion /format:csv')
        info["gpu"] = gpu
    
    return info

def get_ollama_models():
    # Try default port first, then custom
    for port in [11434, 11450]:
        out = run_cmd(f'curl -s http://localhost:{port}/api/tags 2>&1')
        if out and not out.startswith("ERROR"):
            try:
                data = json.loads(out)
                models = []
                for m in data.get("models", []):
                    models.append({
                        "name": m.get("name"),
                        "size_bytes": m.get("size"),
                        "size_gb": round(m.get("size", 0) / (1024**3), 2),
                        "modified_at": m.get("modified_at"),
                        "digest": m.get("digest")[:12] if m.get("digest") else None
                    })
                return {"port": port, "models": models}
            except:
                pass
    return {"port": None, "models": [], "error": "Ollama not reachable on 11434 or 11450"}

def get_network():
    info = {}
    # Local IPs
    out = run_cmd('ipconfig')
    info["ipconfig"] = out
    
    # Tailscale
    tailscale = run_cmd('tailscale ip 2>&1')
    info["tailscale_ip"] = tailscale if "ERROR" not in tailscale else "Not installed/running"
    
    # Hotspot check
    hotspot = run_cmd('netsh wlan show hostednetwork 2>&1')
    info["hotspot"] = hotspot
    
    # Firewall rules for Ollama
    fw = run_cmd('netsh advfirewall firewall show rule name=all dir=in | findstr /i ollama 2>&1')
    info["firewall_ollama"] = fw if fw else "No specific rule"
    
    return info

def get_python_env():
    info = {}
    venv_path = Path(r"C:\venv-hub")
    if venv_path.exists():
        info["venv_hub_exists"] = True
        info["venv_hub_python"] = str(venv_path / "venv" / "Scripts" / "python.exe")
        # Check version
        py = run_cmd(f'"{info["venv_hub_python"]}" --version')
        info["venv_hub_python_version"] = py
        # Check packages
        pkgs = run_cmd(f'"{info["venv_hub_python"]}" -m pip list --format=json 2>&1')
        try:
            info["venv_hub_packages"] = json.loads(pkgs) if not pkgs.startswith("ERROR") else []
        except:
            info["venv_hub_packages"] = "parse error"
    else:
        info["venv_hub_exists"] = False
    
    # System python
    info["system_python"] = run_cmd("python --version")
    info["system_pip_list"] = run_cmd("pip list --format=json 2>&1")
    
    return info

def get_android():
    info = {}
    sdk = Path(r"C:\android\sdk")
    if sdk.exists():
        info["android_sdk_path"] = str(sdk)
        # Build tools
        bt = list(sdk.glob("build-tools/*"))
        info["build_tools"] = [str(p.name) for p in bt]
        # Platforms
        pl = list(sdk.glob("platforms/*"))
        info["platforms"] = [str(p.name) for p in pl]
    else:
        info["android_sdk_path"] = "Not found at C:\\android\\sdk"
    
    # Gradle wrapper
    gw = Path(r"C:\pathfinder_god\spoke\android\gradle\wrapper\gradle-wrapper.properties")
    if gw.exists():
        info["gradle_wrapper"] = gw.read_text()
    
    return info

def get_git():
    info = {}
    info["git_version"] = run_cmd("git --version")
    info["git_status"] = run_cmd("cd C:\\pathfinder_god && git status --short")
    info["git_log"] = run_cmd("cd C:\\pathfinder_god && git log --oneline -5")
    return info

def main():
    print("[INFO] Gathering system specs...")
    
    spec = {
        "generated_at": datetime.now().isoformat(),
        "project": "Pathfinder God",
        "hardware": get_hardware(),
        "ollama": get_ollama_models(),
        "network": get_network(),
        "python_env": get_python_env(),
        "android": get_android(),
        "git": get_git(),
    }
    
    # Write JSON
    out_json = Path(r"C:\pathfinder_god\SPEC_SHEET.json")
    out_json.write_text(json.dumps(spec, indent=2))
    print(f"[OK] JSON written to {out_json}")
    
    # Write Markdown
    out_md = Path(r"C:\pathfinder_god\SPEC_SHEET.md")
    md = f"""# System Spec Sheet — Pathfinder God
*Generated: {spec['generated_at']}*

## Hardware
```json
{json.dumps(spec['hardware'], indent=2)}
```

## Ollama Models (port {spec['ollama'].get('port', '?')})
| Model | Size (GB) | Modified |
|-------|-----------|----------|
"""
    for m in spec['ollama'].get('models', []):
        md += f"| {m['name']} | {m['size_gb']} | {m['modified_at'][:19].replace('T', ' ')} |\n"
    
    md += f"\n## Python Environment (venv-hub)\n"
    py = spec['python_env']
    md += f"- **venv-hub exists**: {py.get('venv_hub_exists')}\n"
    if py.get('venv_hub_exists'):
        md += f"- **Python**: {py.get('venv_hub_python_version')}\n"
        md += f"- **Path**: {py.get('venv_hub_python')}\n"
        pkgs = py.get('venv_hub_packages', [])
        if isinstance(pkgs, list):
            md += f"- **Packages ({len(pkgs)})**: " + ", ".join([f"{p['name']}=={p['version']}" for p in pkgs[:20]]) + ("..." if len(pkgs) > 20 else "") + "\n"
    
    md += f"\n## Android Tooling\n"
    android = spec['android']
    md += f"- **SDK**: {android.get('android_sdk_path')}\n"
    md += f"- **Build Tools**: {', '.join(android.get('build_tools', []))}\n"
    md += f"- **Platforms**: {', '.join(android.get('platforms', []))}\n"
    
    md += f"\n## Network\n"
    net = spec['network']
    md += f"- **Tailscale IP**: {net.get('tailscale_ip')}\n"
    md += f"- **Hotspot**: {net.get('hotspot', '').split(chr(10))[0] if net.get('hotspot') else 'N/A'}\n"
    md += f"- **Firewall Ollama**: {net.get('firewall_ollama', '').split(chr(10))[0] if net.get('firewall_ollama') else 'None'}\n"
    
    md += f"\n## Git\n"
    git = spec['git']
    md += f"- **Version**: {git.get('git_version')}\n"
    md += f"- **Status**: {git.get('git_status') or 'clean'}\n"
    md += f"- **Recent commits**:\n```\n{git.get('git_log')}\n```\n"
    
    out_md.write_text(md, encoding='utf-8')
    print(f"[OK] Markdown written to {out_md}")
    
    return spec

if __name__ == "__main__":
    main()