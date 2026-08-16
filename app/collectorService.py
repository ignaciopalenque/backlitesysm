import psutil
import socket
import re
import subprocess
import platform
import shutil
import cpuinfo
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import dbus
import ipaddress
import os
import nmap
from nmap import PortScannerError

class SystemCollector:

    load_dotenv()

    APP_MODE = os.getenv("APP_MODE")
    CPU_INFO = cpuinfo.get_cpu_info()
    TEMPS = psutil.sensors_temperatures()

    @staticmethod
    def nampIsIntall():
        if os.path.exists("/usr/bin/nmap"):
            return True
        else:
            return False

    @staticmethod
    def install_nmap_system_deps():
        if shutil.which("nmap") is None:
            if platform.system().lower() == "linux":
                    if shutil.which("apt-get") is not None or shutil.which("apt") is not None:
                        # usa apt-get si existe
                        apt_cmd = "apt-get" if shutil.which("apt-get") else "apt"
                        subprocess.run(["sudo", apt_cmd, "update"])
                        subprocess.run(["sudo", apt_cmd, "install", "-y", "nmap"])
                        return

                    if shutil.which("pacman") is not None:
                        subprocess.run(["sudo", "pacman", "-Sy", "--noconfirm", "nmap"])
                        return
                    else:
                        raise RuntimeError("No detecté apt-get ni pacman. Instala 'nmap' manualmente.")

                 





    @staticmethod
    def get_tdp_smart(cpu_name):

        # Lista de CPUs con TDP específicos
        SPECIFIC_TDP = {
            "Xeon E5-2695 v4": 120.0,
            "Xeon E5-2620 v3": 85.0,
            "Intel Core i5-6300U": 15.0,
            "AMD Ryzen 9 5950X": 105.0,
            }
        
        cpu_name_upper = cpu_name.upper()
        
        # --- NIVEL 1: Búsqueda exacta en el Diccionario de Precisión ---
        for model, tdp in SPECIFIC_TDP.items():
            if model.upper() in cpu_name_upper:
                return tdp

        # --- NIVEL 2: Lógica de Sufijos (Muy precisa para laptops y desktops) ---
        suffix_match = re.search(r'(\d+)([A-Z]+)', cpu_name_upper)
        if suffix_match:
            suffix = suffix_match.group(2)
            sufijos = {
                'U': 15.0, 'Y': 7.0,        # Ultra bajo consumo
                'H': 45.0, 'HS': 35.0, 'HX': 55.0, 'HQ': 45.0, # Alto rendimiento laptop
                'T': 35.0,                 # Desktop bajo consumo
                'K': 125.0, 'KF': 125.0, 'X': 105.0 # Entusiasta / Overclock
            }
            if suffix in sufijos:
                return sufijos[suffix]

        # --- NIVEL 3: Lógica por Familias (Promedios conservadores) ---
        # Para los Xeon, usamos un promedio más realista si no conocemos el modelo
        if "XEON" in cpu_name_upper:
            # Si es un Xeon E3 (entrada), suele ser menos. Si es E5/E7, más.
            if "E3" in cpu_name_upper: return 80.0
            if "E5" in cpu_name_upper or "E7" in cpu_name_upper: return 120.0
            return 130.0 # Promedio general Xeon
        
        if "EPYC" in cpu_name_upper: return 225.0
        

            # ARM / Raspberry Pi
        if "CORTEX-A53" in cpu_name_upper:
            return 4.0   # Raspberry Pi 3

        if "CORTEX-A72" in cpu_name_upper:
            return 5.0   # Raspberry Pi 4 (algunas versiones)

        if "CORTEX-A76" in cpu_name_upper:
            return 10.0  # Raspberry Pi 5

        if "RASPBERRY" in cpu_name_upper or "ARM" in cpu_name_upper or "CORTEX" in cpu_name_upper:
            return 7.0   # ARM genérico
        
        # Gamas estándar
        if "I3" in cpu_name_upper: return 35.0
        if "I5" in cpu_name_upper: return 65.0
        if "I7" in cpu_name_upper: return 95.0
        if "I9" in cpu_name_upper: return 125.0
        if "RYZEN" in cpu_name_upper: return 65.0

        # --- NIVEL 4: Valor por defecto ---
        return 35.0    
   
    @staticmethod
    def get_cpu_metrics():
        """Obtener métricas de CPU"""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = f"{psutil.cpu_freq().current:.0f}"
        cpu_freq_max = psutil.cpu_freq().max
        cpu_count = psutil.cpu_count()
        
        return {
            'percent': cpu_percent,
            'frequency': cpu_freq,
            'frequency_max': cpu_freq_max,
            'count': cpu_count
        }
    
    @staticmethod
    def get_device_info():

        gpu_name = "N/A"
        vram_total = 0
        os_name = platform.system()
        cpu_name = SystemCollector.CPU_INFO.get('brand_raw', 'Unknown')
        tdp = SystemCollector.get_tdp_smart(cpu_name)

        if os_name == "Windows":
            try:
                command = "wmic path win32_VideoController get name"
                output = subprocess.check_output(command, shell=True, stderr=subprocess.DEVNULL).decode("utf-8")
                lines = [line.strip() for line in output.splitlines() if line.strip()]
                if len(lines) > 1:
                    gpu_name = lines[1]
            except subprocess.CalledProcessError:
                pass

        elif os_name == "Linux":
            try:
                output = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
                for line in output.splitlines():
                    lower = line.lower()
                    if "vga compatible controller" in lower or "3d controller" in lower or "display controller" in lower:
                        gpu_name = line.split(": ", 1)[-1].strip()
                        break
            except Exception:
                pass

        data = {
            'hostname': socket.gethostname(),
            'os': f"{platform.system()} {platform.release()}",
            'cpu_name': cpu_name,
            'cpu_tpd': tdp,
            'disk_total': psutil.disk_usage('/').total,
            'ram_total': psutil.virtual_memory().total,
            'gpu_name': gpu_name,
            'vram_total': vram_total,
            'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return data

    @staticmethod
    def get_profile_linux():
        try:
             bus = dbus.SystemBus()
             obj = bus.get_object(
                        "net.hadess.PowerProfiles",
                        "/net/hadess/PowerProfiles"
                    )
            
             iface = dbus.Interface(
                        obj,
                        "org.freedesktop.DBus.Properties"
                    )
             profile = iface.Get(
                "net.hadess.PowerProfiles",
                "ActiveProfile"
            )

            
             return str(iface.Get(
                        "net.hadess.PowerProfiles",
                        "ActiveProfile"
                    ))
                
        except Exception as e:
            print(e)
            return "N/A"
       
    @staticmethod
    def get_cpu_temperature():
        """Obtener temperatura del CPU (específico para Raspberry Pi)"""
        try:
            # Linux
            '''
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read()) / 1000.0
            return temp
            '''
            return float(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000

        except:
            try:
                # Alternativa: psutil y comando vcgencmd
                if SystemCollector.TEMPS is not None:
                    return SystemCollector.TEMPS
                output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
                temp = float(output.split('=')[1].split("'")[0])
                return temp
            except:
                return 0.0
    
    @staticmethod
    def get_ram_metrics():
        """Obtener métricas de RAM"""
        ram = psutil.virtual_memory()
        
        return {
            'percent': ram.percent,
            'used': ram.used,
            'total': ram.total,
            'available': ram.available
        }
    
    @staticmethod
    def get_disk_metrics():
        """Obtener métricas de disco"""
        disk = psutil.disk_usage('/')
        
        return {
            'percent': disk.percent,
            'used': disk.used,
            'total': disk.total,
            'free': disk.free
        }
    
    @staticmethod
    def insert_network_metrics_by_interface(db):

        networks = psutil.net_io_counters(pernic=True)
        ip = SystemCollector.get_local_ip()
        iface = SystemCollector.get_default_interface(ip)
        mac = SystemCollector.get_ip_and_mac_by_interface(iface)[1]

        network_default = networks.get(iface)

        if network_default is None:
            return

        data = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'interface': iface,
                'ip_address': ip,
                'mac_address': mac,
                'bytes_sent': network_default.bytes_sent / (1024 ** 3),
                'bytes_recv': network_default.bytes_recv / (1024 ** 3),
                'upload_bps': network_default.packets_sent,
                'download_bps': network_default.packets_recv
                
            }
        db.insert_network_metrics(data)

        if SystemCollector.APP_MODE == 'dev':
            print("Insertadas metricas de red",data)


    @staticmethod
    def get_network_metrics_by_interface():

        networks = psutil.net_io_counters(pernic=True)
        ip = SystemCollector.get_local_ip()
        iface = SystemCollector.get_default_interface(ip)
        mac = SystemCollector.get_ip_and_mac_by_interface(iface)[1]

        network_default = networks.get(iface)

        if network_default is None:
            return

        data = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'interface': iface,
                'ip_address': ip,
                'mac_address': mac,
                'bytes_sent': network_default.bytes_sent / (1024 ** 3),
                'bytes_recv': network_default.bytes_recv / (1024 ** 3),
                'upload_bps': network_default.packets_sent,
                'download_bps': network_default.packets_recv
                
            }

        return data
    @staticmethod
    def get_boot_time():
        try:
            boot_time = psutil.boot_time()
            uptime = datetime.now() - datetime.fromtimestamp(boot_time)
            mins = int(uptime.total_seconds() // 60)
            hours = mins // 60
            minutes = mins % 60
            return hours, minutes   
        except:
            minutes = 0
            hours = 0
            return hours, minutes


    @staticmethod
    def get_energy_plan():
        try:
            os_name = platform.system()
            cpu_name = SystemCollector.CPU_INFO.get('brand_raw', 'Unknown')

            plan = ""
            if os_name == "Windows":
                output = subprocess.check_output(
                    ["powercfg", "/getactivescheme"],
                    text=True,
                    encoding="utf-8",
                    errors="ignore"
                )
                m = re.search(r"\(([^)]+)\)$", output.strip())
                plan = m.group(1) if m else output.strip()

            elif 'CORTEX-A53' in cpu_name.upper() or 'CORTEX-A72' in cpu_name.upper() or 'CORTEX-A76' in cpu_name.upper():

                 output = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").read_text().strip()
                 plan = output

            elif os_name == "Linux":
                profile = SystemCollector.get_profile_linux()

                if profile is not None:
                    plan = profile
                else:
                    plan = subprocess.check_output(["powerprofilesctl", "get"], text=True).strip()


            """
            Traducción de planes en el backend. Ya implementado en el front
            match plan:
                            case "performance":
                                return plan + " (Rendimiento)"
                            case "balanced":
                                return plan + " (Equilibrado)"
                            case "power-saver":
                                return plan + " (Ahorro de energía)"
                            case _:
                                return plan
            """
            

            return plan

        except:
            plan_energy = 0
            return plan_energy
    @staticmethod
    def get_ip_and_mac_by_interface(interface_name):
        ip = None
        mac = None

        addrs = psutil.net_if_addrs().get(interface_name, [])
        mac_families = {
            getattr(socket, "AF_LINK", None),
            getattr(socket, "AF_PACKET", None),
        }

        for addr in addrs:
            if addr.family == socket.AF_INET:
                ip = addr.address
            elif addr.family in mac_families:
                mac = addr.address

        return ip, mac
    
    @staticmethod
    def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()





    @staticmethod
    def get_local_mac_by_interface(interface=None):
        addrs = psutil.net_if_addrs()

        if interface:
            for addr in addrs.get(interface, []):
                if getattr(addr, "family", None) == psutil.AF_LINK:
                    return addr.address
            return None

        for if_addrs in addrs.values():
            for addr in if_addrs:
                if getattr(addr, "family", None) == psutil.AF_LINK:
                    return addr.address

        return None
        
    @staticmethod
    def get_default_interface(local_ip):
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address == local_ip:
                    return iface
        return None
        
    @staticmethod
    def get_power_consumption():
        """Estimar consumo eléctrico (requiere configuración adicional)"""
        # Opción 1: Lectura de fichero de energía si está disponible
        try:
            cpu_name = platform.processor().upper()
           

            with open('/sys/class/power_supply/mains/power_now', 'r') as f:
                power = int(f.read()) / 1000000  # Convertir a W
            return power
        except:
            # Opción 2: Estimación basada en CPU (aproximado)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            # Consumo típico RPi: 2.5W idle, 6W full load
            '''
            base_power = 2.5
            max_power = 6.0
            '''
            # Ejemplo estimado para un i5-6300u
            base_power = 1
            max_power = 20
            pbase = 5
            freq = psutil.cpu_freq()
            cpu_freq = psutil.cpu_freq().current
            cpu_freq_max = psutil.cpu_freq().max
            cpu_freq_factor = 0.35 + 0.65 * (cpu_freq / cpu_freq_max)


            # Raspberry Pi 3
            if "CORTEX-A53" in cpu_name:
                base_power = 2.5
                max_power = 5.0
                pbase = 0

                if freq and cpu_freq_max > 0 and cpu_freq != cpu_freq_max:
                    cpu_freq_factor = 0.35 + 0.65 * (freq.current / freq.max)
                else:
                    cpu_freq_factor = 1.0

            # Raspberry Pi 4
            elif "CORTEX-A72" in cpu_name:
                base_power = 3.5
                max_power = 7.0
                pbase = 0

                if freq and cpu_freq_max > 0 and cpu_freq != cpu_freq_max:
                    cpu_freq_factor = 0.35 + 0.65 * (freq.current / freq.max)
                else:
                    cpu_freq_factor = 1.0

            # Raspberry Pi 5
            elif "CORTEX-A76" in cpu_name:
                base_power = 4.5
                max_power = 12.0
                pbase = 0
                
                if freq and cpu_freq_max > 0 and cpu_freq != cpu_freq_max:
                    cpu_freq_factor = 0.35 + 0.65 * (freq.current / freq.max)
                else:
                    cpu_freq_factor = 1.0




            cpu_power = base_power + (max_power - base_power) * (cpu_percent / 100) * cpu_freq_factor
            estimated = pbase + cpu_power 

            #estimated = pbase + base_power + (cpu_percent / 100) * (max_power - base_power) * cpu_freq_factor 
            if SystemCollector.APP_MODE == 'dev':
                print("El uso de la CPU es ", cpu_percent ,"% ", "La frecuencia maxima es ", cpu_freq_max, "Hz y la frecuencia actual es ", cpu_freq, "Hz El consumo estimado es ", round(estimated, 2), " W") #print(estimated)


            return round(estimated, 2)
        
    @staticmethod
    def calculate_power_consumption():
        # 1. Obtener datos del hardware
        cpu_name = SystemCollector.CPU_INFO.get('brand_raw', 'Unknown')
        
          # 2. Perfil energético según CPU ARM
        if "CORTEX-A53" in cpu_name:
            # Raspberry Pi 3 B
            p_base = 1.5       # placa, RAM, periféricos
            p_idle = 2.5       # consumo reposo
            p_max = 5.0        # consumo carga máxima

        elif "CORTEX-A72" in cpu_name:
            # Raspberry Pi 4
            p_base = 2.0
            p_idle = 3.5
            p_max = 7.0

        elif "CORTEX-A76" in cpu_name:
            # Raspberry Pi 5
            p_base = 3.0
            p_idle = 5.0
            p_max = 12.0

        else:
            # Equipo genérico
            tdp = SystemCollector.get_tdp_smart(cpu_name)
            p_base = 5.0
            p_idle = tdp * 0.15
            p_max = tdp * 1.1

            
        
        # 3. Métricas actuales
        cpu_percent = psutil.cpu_percent(interval=0.1)
        freq = psutil.cpu_freq()
        
        if freq:
            # Factor de frecuencia: si la CPU baja su velocidad, consume menos aunque el % sea alto
            freq_factor = 0.4 + 0.6 * (freq.current / freq.max)
        else:
            freq_factor = 1.0

        # 4. Fórmula Estandarizada
        # Potencia = Base + Reposo + (Rango de potencia * uso % * factor de frecuencia)
        cpu_power = p_idle + (p_max - p_idle) * (cpu_percent / 100) * freq_factor
        estimated_total = p_base + cpu_power


        if SystemCollector.APP_MODE == 'dev':
            print(f"CPU: {cpu_name} | TDP Est: {tdp}W")
            print(f"Uso: {cpu_percent}% | Frec: {freq.current:.0f}/{freq.max:.0f}MHz")
            print(f"Consumo Estimado: {round(estimated_total, 2)} W")
        
        return round(estimated_total, 2) 

    @staticmethod
    def get_top_process_old():
        """Obtener proceso principal"""
        process = []

        # Iteramos sobre todos los procesos ejecutándose
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                # Obtenemos la información del proceso
                info = proc.info
                # Convertimos la memoria de bytes a MB para que sea legible
                info['memory_mb'] = info['memory_info'].rss / (1024 * 1024)
                process.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Ignoramos procesos que cierran mientras escaneamos o a los que no tenemos acceso
                pass

        # Ordenamos la lista basándonos en el uso de CPU (puedes cambiarlo a 'memory_mb')
        # reverse=True para que los 5 más demandantes queden arriba
        top_process = sorted(process, key=lambda x: x['cpu_percent'], reverse=True)[:5]
        
        return top_process


    @staticmethod
    def get_top_process():
        process = []

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        time.sleep(0.2)
        cpu_count = psutil.cpu_count() or 1

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                cpu_raw = proc.cpu_percent(None)
                mem = proc.memory_info().rss / (1024 * 1024)

                process.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu_percent': round(cpu_raw / cpu_count, 2),
                    'memory_mb': round(mem, 2)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                continue

        return sorted(process, key=lambda x: x['cpu_percent'], reverse=True)[:5]
    @staticmethod
    def get_network_counter_speed():

        ip = SystemCollector.get_local_ip()
        iface = SystemCollector.get_default_interface(ip)
    
        # Primera lectura
        io1 = psutil.net_io_counters(pernic=True)[iface]
        t1 = time.time()

        time.sleep(1)

        # Segunda lectura
        io2 = psutil.net_io_counters(pernic=True)[iface]
        t2 = time.time()

        # Intervalo real
        dt = t2 - t1

        # Velocidad en Bytes/s
        download_bps = (io2.bytes_recv - io1.bytes_recv) / dt
        upload_bps = (io2.bytes_sent - io1.bytes_sent) / dt
    
        return {
            "interface": iface,
            "ip": ip,
            "download_mbps": round(download_bps / (1024 * 1024), 2),
            "upload_mbps": round(upload_bps / (1024 * 1024), 2),
            "total_download_mb":round(io2.bytes_recv / (1024 * 1024), 2),
            "total_upload_mb": round(io2.bytes_sent / (1024 * 1024), 2)
        }

    
    @staticmethod
    def get_network_ip_mask():
        addrs = psutil.net_if_addrs()

        for iface, addr_list in addrs.items():
            for addr in addr_list:
                if addr.family == socket.AF_INET and addr.address and addr.netmask and addr.netmask != '0.0.0.0' and addr.address != '127.0.0.1':
                    network = ipaddress.ip_network(
                        f"{addr.address}/{addr.netmask}",
                        strict=False
                    )

                    return str(network)

        return None

    @staticmethod
    def discover_hosts():
        try:
            network_cidr = SystemCollector.get_network_ip_mask()
            nm = nmap.PortScanner()
            nm.scan(hosts=network_cidr, arguments='-sn -R')

            results = []
            for host in nm.all_hosts():
                results.append({
                    "ip": host,
                    "hostname": nm[host].hostname(),
                    "state": nm[host].state(),
                })

            return results
        except PortScannerError as e:
               msg = str(e)
               if "nmap program was not found" not in msg.lower():
                    raise  # error distinto, no lo manejamos

               print("No está 'nmap' en el sistema. Intentando instalar...")
               SystemCollector.install_nmap_system_deps()
            

    @staticmethod
    def scan_services():

        try:
            network_cidr = SystemCollector.get_network_ip_mask()

            nm = nmap.PortScanner()
            nm.scan(hosts=network_cidr, ports='21,22,80,443,445,3389', arguments='-sV --open -Pn --max-retries 1 --min-rate 1000 --version-light --script vuln')

            results = []

            for host in nm.all_hosts():
                host_info = {
                    "ip": host,
                    "hostname": nm[host].hostname(),
                    "state": nm[host].state(),
                    "protocols": []
                }

                for proto in nm[host].all_protocols():
                    proto_info = {
                        "protocol": proto,
                        "ports": []
                    }

                    for port in sorted(nm[host][proto].keys()):
                        service = nm[host][proto][port]

                        proto_info["ports"].append({
                            "port": port,
                            "state": service["state"],
                            "service": service["name"],
                            "product": service.get("product", ""),
                            "version": service.get("version", ""),
                            "extrainfo": service.get("extrainfo", ""),
                            "scripts": service.get("script", {})
                        })

                    host_info["protocols"].append(proto_info)

                results.append(host_info)

            return results
        except PortScannerError as e:
                       msg = str(e)
                       if "nmap program was not found" not in msg.lower():
                            raise  # error distinto, no lo manejamos
        
                       print("No está 'nmap' en el sistema. Intentando instalar...")
                       SystemCollector.install_nmap_system_deps()
    
    @staticmethod
    def collect_all():
        """Recopilar todas las métricas"""
        cpu = SystemCollector.get_cpu_metrics()
        ram = SystemCollector.get_ram_metrics()
        disk = SystemCollector.get_disk_metrics()
        temp = SystemCollector.get_cpu_temperature()
        power = SystemCollector.calculate_power_consumption()
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': cpu['percent'],
            'cpu_freq': cpu['frequency'],
            'cpu_freq_max': cpu['frequency_max'],
            'cpu_temp': temp,
            'ram_percent': ram['percent'],
            'ram_used': ram['used'],
            'ram_total': ram['total'],
            'disk_percent': disk['percent'],
            'disk_used': disk['used'],
            'disk_total': disk['total'],
            'power_consumption': power
        }
    

