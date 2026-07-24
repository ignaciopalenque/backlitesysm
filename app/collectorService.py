import psutil
import socket
import re
import subprocess
import platform
import cpuinfo
import time
from datetime import datetime

class SystemCollector:




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
        cpu_name = cpuinfo.get_cpu_info().get('brand_raw', 'Unknown')
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
    def get_cpu_temperature():
        """Obtener temperatura del CPU (específico para Raspberry Pi)"""
        try:
            # Raspberry Pi
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read()) / 1000.0
            return temp
        except:
            try:
                # Alternativa: comando vcgencmd
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
        print("insert_network_metrics_by_interface")
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
        print(data)

    
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
            cpu_freq = psutil.cpu_freq().current
            cpu_freq_max = psutil.cpu_freq().max
            cpu_freq_factor = 0.35 + 0.65 * (cpu_freq / cpu_freq_max)
            cpu_power = base_power + (max_power - base_power) * (cpu_percent / 100) * cpu_freq_factor

            estimated = pbase + cpu_power 

            #estimated = pbase + base_power + (cpu_percent / 100) * (max_power - base_power) * cpu_freq_factor 
            print("El uso de la CPU es ", cpu_percent ,"% ", "La frecuencia maxima es ", cpu_freq_max, "Hz y la frecuencia actual es ", cpu_freq, "Hz El consumo estimado es ", round(estimated, 2), " W") #print(estimated)
            return round(estimated, 2)
        
    @staticmethod
    def calculate_power_consumption():
        # 1. Obtener datos del hardware
        cpu_name = cpuinfo.get_cpu_info().get('brand_raw', 'Unknown')
        tdp = SystemCollector.get_tdp_smart(cpu_name)
        
        # 2. Parámetros estandarizados basados en TDP
        p_base = 5.0             # Consumo base de placa/RAM (estimado laptop)
        p_idle = tdp * 0.15      # El reposo es aprox 15% del TDP
        p_max = tdp * 1.1        # El máximo es TDP + margen de Turbo
        
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

        print(f"CPU: {cpu_name} | TDP Est: {tdp}W")
        print(f"Uso: {cpu_percent}% | Frec: {freq.current:.0f}/{freq.max:.0f}MHz")
        print(f"Consumo Estimado: {round(estimated_total, 2)} W")
        
        return round(estimated_total, 2) 

    @staticmethod
    def get_top_process():
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
    def collect_all():
        """Recopilar todas las métricas"""
        cpu = SystemCollector.get_cpu_metrics()
        ram = SystemCollector.get_ram_metrics()
        disk = SystemCollector.get_disk_metrics()
        temp = SystemCollector.get_cpu_temperature()
        #power = SystemCollector.get_power_consumption()
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
    

