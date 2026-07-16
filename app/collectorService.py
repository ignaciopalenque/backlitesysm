import psutil
import socket
import os
import re
import subprocess
import platform
import cpuinfo
import GPUtil
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
        if "RASPBERRY" in cpu_name_upper or "ARM" in cpu_name_upper: return 7.0
        
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

          # Información de GPU (NVIDIA)
        gpus = GPUtil.getGPUs()
        gpu_name = "N/A"
        vram_total = 0
        os_name = platform.system()
        if gpus:
            gpu_name = gpus[0].name
            vram_total = gpus[0].memoryTotal
        else:
            if os_name == "Windows":
            # Comando WMIC para obtener el nombre del controlador de video
                comand = "wmic path win32_VideoController get name"
                output = subprocess.check_output(comand, shell=True).decode('utf-8')
                # Limpiamos el resultado (quitamos la cabecera 'Name' y espacios)
                lines = [line.strip() for line in output.split('\n') if line.strip()]
                if len(lines) > 1:
                    gpu_name = lines[1] # La primera línea es el título "Name"

            elif os_name == "Linux":
                # Comando lspci para buscar dispositivos VGA o 3D
                comand = "lspci | grep -Ei 'vga|3d|display'"
                output = subprocess.check_output(comand, shell=True).decode('utf-8')
                
                if output:
                    # Tomamos la primera línea y extraemos el nombre después de ':'
                    gpu_name = output.split('r:', 1)[1].strip()


        # Recolección de datos
        data = {
            'hostname': socket.gethostname(),
            'os': f"{platform.system()} {platform.release()}",
            'cpu_name': cpuinfo.get_cpu_info().get('brand_raw', "Unknown"),
            'disk_total': psutil.disk_usage('/').total, # Bytes
            'ram_total': psutil.virtual_memory().total,   # Bytes
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
