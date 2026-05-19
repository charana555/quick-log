import os
import subprocess
import time
import json
from typing import Dict, List, Optional

# Cache validation results to avoid repeated checks (TTL in seconds)
_validation_cache = {}
VALIDATION_TTL = 30


def _get_from_cache(key: str) -> Optional[Dict]:
    if key in _validation_cache:
        entry = _validation_cache[key]
        if time.time() - entry["timestamp"] < VALIDATION_TTL:
            return entry["result"]
    return None


def _save_to_cache(key: str, result: Dict):
    _validation_cache[key] = {
        "result": result,
        "timestamp": time.time()
    }


def check_colima_memory() -> Dict:
    """
    Check Colima memory allocation.
    Returns: {
        "status": "adequate" | "warning" | "insufficient" | "unknown",
        "memory_gb": float,
        "message": str,
        "restart_command": str
    }
    """
    mem_gb = 0.0
    source = "unknown"
    
    # 1. Try reading from .resources.json (written by manage_stack.sh)
    resource_file = os.path.join(os.getcwd(), ".resources.json")
    if os.path.exists(resource_file):
        try:
            with open(resource_file, 'r') as f:
                data = json.load(f)
                # Check if file is not too old (e.g., within 1 hour)
                if time.time() - data.get("timestamp", 0) < 3600:
                    mem_val = data.get("colima_memory_gb", 0)
                    # Only use if actually set (not 0)
                    if mem_val and int(mem_val) > 0:
                        mem_gb = float(mem_val)
                        source = "resources_file"
        except:
            pass

    # 2. Fallback: Try Docker API info (MemTotal)
    if mem_gb == 0:
        try:
            import docker
            client = docker.from_env()
            info = client.info()
            mem_bytes = info.get('MemTotal', 0)
            if mem_bytes > 0:
                mem_gb = mem_bytes / (1024**3)
                source = "docker_api"
        except:
            pass

    # 3. Inside container without host info - show unknown
    if mem_gb == 0 and os.path.exists("/.dockerenv"):
        return {
            "status": "unknown",
            "memory_gb": 0,
            "message": "Cannot detect host Colima memory from container.",
            "restart_command": "colima stop && colima start --memory 8 --cpu 4",
            "source": "container_fallback"
        }

    # Adaptive thresholds (only if we have actual memory info)
    status = "adequate"
    message = f"Sufficient memory detected ({mem_gb:.1f}GB)."
    
    if mem_gb < 4.0:
        status = "insufficient"
        message = f"Insufficient Memory ({mem_gb:.1f}GB). ELK Stack requires at least 4GB, ideally 8GB."
    elif mem_gb < 7.5:
        status = "warning"
        message = f"Low Memory ({mem_gb:.1f}GB). Performance may be degraded. 8GB is recommended."
    
    return {
        "status": status,
        "memory_gb": round(mem_gb, 1),
        "message": message,
        "restart_command": "colima stop && colima start --memory 8 --cpu 4",
        "source": source
    }


def check_docker() -> Dict:
    """Check if Docker/Colima is available and running."""
    # If running inside a container, assume it's running if ES is reachable 
    # or if we are in 'container' mode. For now, we allow the UI to proceed
    # if we detect we are likely in the 'data-automation' docker stack.
    if os.path.exists("/.dockerenv"):
        return {
            "installed": True,
            "running": True,
            "method": "container-env",
            "error": None
        }

    cached = _get_from_cache("docker_status")
    if cached:
        return cached

    status = {
        "installed": False,
        "running": False,
        "method": None,
        "error": None
    }

    try:
        # Check if docker command exists
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        status["installed"] = True
        
        # Check if daemon is running
        result = subprocess.run(["docker", "ps"], capture_output=True)
        if result.returncode == 0:
            status["running"] = True
            status["method"] = "docker"
        else:
            # Check colima specifically if on Mac
            colima_check = subprocess.run(["colima", "status"], capture_output=True)
            if colima_check.returncode == 0:
                status["running"] = True
                status["method"] = "colima"
            else:
                status["error"] = "Docker daemon not running"
    except FileNotFoundError:
        status["error"] = "Docker command not found"
    except Exception as e:
        status["error"] = str(e)

    _save_to_cache("docker_status", status)
    return status


def check_prerequisites(prereqs: List[str], config: Dict) -> Dict:
    """Check multiple prerequisites and return combined status."""
    results = {}
    all_met = True
    
    for prereq in prereqs:
        if prereq == "docker":
            res = check_docker()
            results[prereq] = res
            if not res["running"]:
                all_met = False
            
    return {"all_met": all_met, "results": results}
