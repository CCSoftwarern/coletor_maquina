import json
import platform
import psutil
import socket
import uuid
import sys
import os
import struct
from pathlib import Path
from datetime import datetime
import time

from pymongo import MongoClient
from pymongo.errors import PyMongoError

try:
    import socks
    PYSOCKS_AVAILABLE = True
except ImportError:
    PYSOCKS_AVAILABLE = False

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


def get_system_proxy():
    """Detecta proxy configurado no Windows (Internet Options)."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if not enabled:
            winreg.CloseKey(key)
            return None
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if not server:
            return None
        # Formato: "host:porta" ou "http=host1:port1;https=host2:port2"
        if "=" in server:
            for part in server.split(";"):
                if part.startswith("http="):
                    server = part.split("=", 1)[1]
                    break
        host, port = server.split(":")[0], int(server.split(":")[1])
        print(f"[INFO] Proxy do sistema detectado: {host}:{port}")
        return host, port
    except Exception:
        return None


def _proxy_supports_connect(proxy_host, proxy_port):
    """Verifica se o proxy suporta HTTP CONNECT tunneling (necessario para MongoDB)."""
    if not PYSOCKS_AVAILABLE:
        return False
    try:
        sock = socks.socksocket()
        sock.set_proxy(socks.HTTP, proxy_host, proxy_port)
        sock.settimeout(5)
        sock.connect(("cluster0-shard-00-00.1lh3b.mongodb.net", 443))
        sock.sendall(
            b"CONNECT cluster0-shard-00-00.1lh3b.mongodb.net:443 HTTP/1.1\r\n"
            b"Host: cluster0-shard-00-00.1lh3b.mongodb.net:443\r\n\r\n"
        )
        resp = sock.recv(256)
        sock.close()
        return b"200" in resp
    except Exception:
        return False


def setup_proxy(proxy_host, proxy_port):
    """Configura tunneling HTTP CONNECT via PySocks para todas as conexoes socket."""
    if not PYSOCKS_AVAILABLE:
        print("[AVISO] pysocks nao instalado, proxy ignorado")
        return

    def _proxy_create_connection(address, timeout=None, source_address=None):
        host, port = address
        sock = socks.socksocket()
        sock.set_proxy(socks.HTTP, proxy_host, proxy_port)
        if timeout is not None:
            sock.settimeout(timeout)
        sock.connect((host, port))
        return sock

    socket.create_connection = _proxy_create_connection
    print(f"[INFO] Proxy configurado: {proxy_host}:{proxy_port}")


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


def _rewrite_uri_to_port443(uri):
    """Resolve SRV records de mongodb+srv:// e reescreve para mongodb:// na porta 443."""
    import dns.resolver
    import re

    m = re.match(r"mongodb\+srv://(?:[^:]+:[^@]+@)?([^/?]+)", uri)
    if not m:
        return uri
    hostname = m.group(1)

    # Extrair user:pass se existir
    cred_match = re.match(r"mongodb\+srv://([^:]+):([^@]+)@", uri)
    user = cred_match.group(1) if cred_match else ""
    password = cred_match.group(2) if cred_match else ""

    # Extrair query string se existir
    query_match = re.search(r"\?(.*)$", uri)
    query = query_match.group(1) if query_match else ""

    # Resolver SRV records
    srv_records = dns.resolver.resolve(f"_mongodb._tcp.{hostname}", "SRV")
    hosts = [f"{r.target.to_text().rstrip('.')}:443" for r in srv_records]

    # Resolver TXT records para replica set
    txt_records = dns.resolver.resolve(hostname, "TXT")
    replica_set = None
    auth_source = None
    for r in txt_records:
        for s in r.strings:
            text = s.decode() if isinstance(s, bytes) else s
            if text.startswith("replicaSet="):
                replica_set = text.split("=", 1)[1]
            elif text.startswith("authSource="):
                auth_source = text.split("=", 1)[1]

    # Montar nova URI
    hosts_str = ",".join(hosts)
    parts = [f"mongodb://{hosts_str}/"]
    params = []
    params.append("ssl=true")
    if user and password:
        parts = [f"mongodb://{user}:{password}@{hosts_str}/"]
    if replica_set:
        params.append(f"replicaSet={replica_set}")
    if auth_source:
        params.append(f"authSource={auth_source}")
    if query:
        params.append(query)

    new_uri = parts[0] + "?" + "&".join(params) if params else parts[0]
    print(f"[INFO] URI reescrita para porta 443: {hosts_str}")
    return new_uri


def _build_doc(machine_info, config):
    """Monta o documento no formato esperado pela colecao."""
    specs_field = config.get("specs_field", "specs")
    default_fields = dict(config.get("default_fields", {}))

    if default_fields.get("nome", "") == "AUTO":
        default_fields["nome"] = machine_info.get("hostname", "UNKNOWN")

    doc = {}
    doc["created_at"] = int(time.time() * 1000)
    doc.update(default_fields)
    doc[specs_field] = machine_info

    return doc


def _try_insert(uri, db_name, collection_name, doc, timeout_ms):
    """Tenta inserir no MongoDB. Retorna True se sucesso."""
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    try:
        col = client[db_name][collection_name]
        # Auto-incrementar campo "id"
        last = col.find_one(sort=[("id", -1)])
        doc["id"] = (last.get("id", 0) + 1) if last else 1
        result = col.insert_one(doc)
        doc["id"] = result.inserted_id
        print(f"[SUCESSO] Documento inserido com ID: {result.inserted_id}")
        return True
    finally:
        client.close()


def send_to_mongodb(config, machine_info):
    """Insere as informacoes da maquina no MongoDB Atlas.
    
    Estrategia:
    1. Tenta conexao direta (funciona na maioria dos casos)
    2. Se falhar e proxy suportar CONNECT, tenta via proxy na porta 443
    3. Se proxy nao suportar CONNECT, reporta erro com instrucoes
    """
    uri = config["mongodb_uri"]
    db_name = config["database"]
    collection_name = config["collection"]
    timeout_ms = config.get("timeout_ms", 30000)

    print(f"[INFO] Conectando ao MongoDB: {db_name}.{collection_name}")

    doc = _build_doc(machine_info, config)

    # Salvar socket original antes de qualquer monkey-patch
    _original_create_connection = socket.create_connection

    # Estrategia 1: conexao direta (sem proxy)
    print("[INFO] Tentativa 1: conexao direta...")
    try:
        if _try_insert(uri, db_name, collection_name, doc, timeout_ms):
            return True
    except Exception as e:
        print(f"[AVISO] Conexao direta falhou: {type(e).__name__}")

    # Estrategia 2: via proxy com CONNECT tunneling (porta 443)
    proxy = get_system_proxy()
    if proxy and PYSOCKS_AVAILABLE and _proxy_supports_connect(proxy[0], proxy[1]):
        print(f"[INFO] Tentativa 2: via proxy {proxy[0]}:{proxy[1]} na porta 443...")
        try:
            setup_proxy(proxy[0], proxy[1])
            uri_443 = _rewrite_uri_to_port443(uri)
            if _try_insert(uri_443, db_name, collection_name, doc, timeout_ms):
                return True
        except Exception as e:
            print(f"[AVISO] Via proxy falhou: {type(e).__name__}")
        finally:
            socket.create_connection = _original_create_connection
    else:
        if proxy:
            print("[AVISO] Proxy nao suporta CONNECT tunneling para MongoDB")

    print("[ERRO] Nao foi possivel conectar ao MongoDB Atlas")
    print("[INFO] Verifique se a rede permite acesso a porta 27017 do Atlas")
    print("[INFO] Ou adicione uma rota: route -p add 159.41.51.0 mask 255.255.255.0 GATEWAY")
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

    print("[INFO] Enviando para MongoDB Atlas...")
    success = send_to_mongodb(config, machine_info)

    if success:
        print("\n[SUCESSO] Coleta e envio concluídos com sucesso!")
        sys.exit(0)
    else:
        print("\n[FALHA] Erro ao enviar dados para o MongoDB.")
        sys.exit(1)


if __name__ == "__main__":
    main()