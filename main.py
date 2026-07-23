import json
import platform
import psutil
import socket
import uuid
import requests
import sys
import os
from pathlib import Path
from datetime import datetime

try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False


def get_config_path():
    """Retorna o caminho do config.json no mesmo diretório do executável."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "config.json"
    return Path(__file__).parent / "config.json"


def load_config():
    config_path = get_config_path()
    if not config_path.exists():
        print(f"[ERRO] Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def safe_get(obj, attr, default="-"):
    """Obtém atributo de forma segura."""
    try:
        val = getattr(obj, attr, default)
        return str(val) if val else default
    except:
        return default


def collect_machine_info():
    """Coleta informações completas da máquina via WMI e psutil."""
    info = {}
    
    # Inicializa WMI
    wmi_conn = None
    if WMI_AVAILABLE:
        try:
            wmi_conn = wmi.WMI()
        except:
            wmi_conn = None

    # ---------- Sistema Operacional ----------
    try:
        so_parts = [platform.system()]
        if platform.release():
            so_parts.append(platform.release())
        if platform.version():
            so_parts.append(f"Build {platform.version()}")
        info["so"] = " ".join(so_parts)
    except:
        info["so"] = "Windows"

    # ---------- Hostname ----------
    hostname = socket.gethostname()
    info["hostname"] = hostname

    # ---------- IP ----------
    try:
        info["ip"] = socket.gethostbyname(hostname)
    except:
        info["ip"] = "unknown"

    # ---------- MAC ----------
    try:
        mac = uuid.getnode()
        info["mac"] = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
    except:
        info["mac"] = "unknown"

    # ---------- Arquitetura ----------
    info["arquitetura"] = platform.machine()

    # ---------- Processador ----------
    info["processador"] = platform.processor()

    # ---------- WMI - Informações detalhadas ----------
    if wmi_conn:
        try:
            # BIOS
            bios_list = wmi_conn.Win32_BIOS()
            if bios_list:
                info["bios"] = safe_get(bios_list[0], "SMBIOSBIOSVersion")
            
            # Placa-mãe
            mb_list = wmi_conn.Win32_BaseBoard()
            if mb_list:
                info["placa_mae"] = safe_get(mb_list[0], "Product")
                info["fabricante_mb"] = safe_get(mb_list[0], "Manufacturer")
            
            # Sistema (marca, modelo, número de série)
            sys_list = wmi_conn.Win32_ComputerSystem()
            if sys_list:
                info["marca"] = safe_get(sys_list[0], "Manufacturer")
                info["modelo"] = safe_get(sys_list[0], "Model")
                info["num_serie"] = safe_get(sys_list[0], "SystemSKUNumber", safe_get(sys_list[0], "UUID"))
            
            # CPU detalhada
            cpu_list = wmi_conn.Win32_Processor()
            if cpu_list:
                cpu = cpu_list[0]
                info["processador"] = safe_get(cpu, "Name")
                info["nucleos"] = str(safe_get(cpu, "NumberOfCores"))
                info["threads"] = str(safe_get(cpu, "ThreadCount"))
                info["frequencia_max"] = f"{safe_get(cpu, 'MaxClockSpeed')} MHz"
            
            # GPU
            gpu_list = wmi_conn.Win32_VideoController()
            if gpu_list:
                gpu = gpu_list[0]
                info["gpu"] = safe_get(gpu, "Name")
                info["gpu_driver"] = safe_get(gpu, "DriverVersion")
                # VRAM em MB
                try:
                    vram = int(gpu.AdapterRAM or 0)
                    info["gpu_vram"] = f"{vram // (1024*1024)} MB"
                except:
                    info["gpu_vram"] = "-"
            
            # Memória RAM física (slots)
            ram_slots = 0
            ram_total_gb = 0
            ram_speed = "-"
            ram_type = "-"
            for mem in wmi_conn.Win32_PhysicalMemory():
                ram_slots += 1
                try:
                    ram_total_gb += int(mem.Capacity or 0) // (1024**3)
                except:
                    pass
                if ram_speed == "-":
                    ram_speed = f"{safe_get(mem, 'Speed')} MHz"
                if ram_type == "-":
                    ram_type = safe_get(mem, "MemoryType")
                    # MemoryType: 24=DDR3, 26=DDR4, 28=DDR5
                    if ram_type == "26":
                        ram_type = "DDR4"
                    elif ram_type == "24":
                        ram_type = "DDR3"
                    elif ram_type == "28":
                        ram_type = "DDR5"
            
            info["ram_slots"] = str(ram_slots)
            info["ram"] = f"{ram_total_gb} GB" if ram_total_gb > 0 else f"{round(psutil.virtual_memory().total / (1024**3))} GB"
            info["ram_freq"] = ram_speed
            info["ram_velocidade"] = ram_speed
            
            # Armazenamento
            disks = []
            for disk in wmi_conn.Win32_DiskDrive():
                size_gb = int(disk.Size or 0) // (1024**3)
                model = safe_get(disk, "Model")
                media = safe_get(disk, "MediaType")
                disks.append(f"{model} ({size_gb} GB {media})")
            info["armazenamento"] = "; ".join(disks) if disks else "-"
            
            # Monitor
            monitors = []
            for mon in wmi_conn.Win32_DesktopMonitor():
                name = safe_get(mon, "Name")
                if name and name != "Desktop Monitor":
                    monitors.append(name)
            info["monitor"] = "; ".join(monitors) if monitors else "-"
            
            info["potencia"] = "-"
            info["estabilizador"] = "-"
            
            # Data de instalação do SO
            os_list = wmi_conn.Win32_OperatingSystem()
            if os_list:
                install_date = safe_get(os_list[0], "InstallDate")
                if install_date and install_date != "-":
                    # Formato WMI: 20240115103000.000000-180
                    try:
                        info["data_so"] = install_date[:4] + "-" + install_date[4:6] + "-" + install_date[6:8]
                    except:
                        info["data_so"] = datetime.now().strftime("%Y-%m-%d")
                else:
                    info["data_so"] = datetime.now().strftime("%Y-%m-%d")
            else:
                info["data_so"] = datetime.now().strftime("%Y-%m-%d")
                
        except Exception as e:
            print(f"[AVISO] Erro ao coletar via WMI: {e}")

    # Fallbacks para campos que podem ter falhado
    if "ram" not in info:
        info["ram"] = f"{round(psutil.virtual_memory().total / (1024**3))} GB"
    if "nucleos" not in info:
        info["nucleos"] = str(psutil.cpu_count(logical=False))
    if "threads" not in info:
        info["threads"] = str(psutil.cpu_count(logical=True))
    if "frequencia_max" not in info:
        freq = psutil.cpu_freq()
        info["frequencia_max"] = f"{freq.max:.0f} MHz" if freq else "-"
    if "ram_slots" not in info:
        info["ram_slots"] = "-"
    if "ram_freq" not in info:
        info["ram_freq"] = "-"
    if "ram_velocidade" not in info:
        info["ram_velocidade"] = "-"
    if "gpu" not in info:
        info["gpu"] = "-"
    if "gpu_driver" not in info:
        info["gpu_driver"] = "-"
    if "gpu_vram" not in info:
        info["gpu_vram"] = "-"
    if "armazenamento" not in info:
        # Fallback usando psutil
        try:
            system_drive = os.environ.get('SystemDrive', 'C:') + '\\'
            disk = psutil.disk_usage(system_drive)
            info["armazenamento"] = f"Disco C: ({round(disk.total / (1024**3))} GB)"
        except:
            info["armazenamento"] = "-"
    if "monitor" not in info:
        info["monitor"] = "-"
    if "potencia" not in info:
        info["potencia"] = "-"
    if "estabilizador" not in info:
        info["estabilizador"] = "-"
    if "data_so" not in info:
        info["data_so"] = datetime.now().strftime("%Y-%m-%d")
    if "marca" not in info:
        info["marca"] = "-"
    if "modelo" not in info:
        info["modelo"] = "-"
    if "num_serie" not in info:
        info["num_serie"] = "-"
    if "placa_mae" not in info:
        info["placa_mae"] = "-"
    if "fabricante_mb" not in info:
        info["fabricante_mb"] = "-"
    if "bios" not in info:
        info["bios"] = "-"

    # Timestamp da coleta
    info["collected_at"] = datetime.now().isoformat()

    return info


def send_to_api(config, machine_info):
    """Envia as informações para a API Xano."""
    url = f"{config['api_base_url'].rstrip('/')}{config['endpoint']}"
    headers = {
        "Content-Type": "application/json",
        config.get("auth_header", "Authorization"): config.get("auth_value", "")
    }

    # Prepara payload - campo specs + campos adicionais
    specs_field = config.get("specs_field", "specs")
    default_fields = config.get("default_fields", {})
    
    # Auto-preencher nome com hostname se configurado como "AUTO"
    if default_fields.get("nome", "") == "AUTO":
        default_fields["nome"] = machine_info.get("hostname", "UNKNOWN")
    
    payload = {
        specs_field: machine_info
    }
    # Adiciona campos extras (nome, tipo, filial, status)
    payload.update(default_fields)

    print(f"[INFO] Enviando para: {url}")
    print(f"[INFO] Campo specs: {specs_field}")
    print(f"[INFO] Campos extras: {list(default_fields.keys())}")

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=config.get("timeout_seconds", 30)
        )
        response.raise_for_status()
        print(f"[SUCESSO] Resposta da API: {response.status_code}")
        print(f"[SUCESSO] Resposta: {response.text}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[ERRO] Falha ao enviar para API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"[ERRO] Status: {e.response.status_code}")
            print(f"[ERRO] Resposta: {e.response.text}")
        return False


def main():
    print("=" * 50)
    print("Coletor de Informações da Máquina - Versão Completa")
    print("=" * 50)

    config = load_config()
    print(f"[INFO] Configuração carregada: {get_config_path()}")

    print("[INFO] Coletando informações da máquina...")
    machine_info = collect_machine_info()
    
    print("[INFO] Informações coletadas:")
    print(json.dumps(machine_info, indent=2, ensure_ascii=False))

    print("[INFO] Enviando para API...")
    success = send_to_api(config, machine_info)

    if success:
        print("\n[SUCESSO] Coleta e envio concluídos com sucesso!")
        sys.exit(0)
    else:
        print("\n[FALHA] Erro ao enviar dados para a API.")
        sys.exit(1)


if __name__ == "__main__":
    main()