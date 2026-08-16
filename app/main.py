from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from models import MetricsDB
from collectorService import SystemCollector
import threading
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import subprocess


load_dotenv()

FRONTEND_PATH = os.getenv("FRONTEND_PATH")
APP_MODE = os.getenv("APP_MODE")


'''
Con este código comprobamos si FRONTEND_PATH no esta definida
if not FRONTEND_PATH:
    raise RuntimeError("FRONTEND_PATH no está definida")

if not os.path.isdir(FRONTEND_PATH):
    raise RuntimeError(f"FRONTEND_PATH no existe o no es un directorio: {FRONTEND_PATH}")

'''

app = Flask(__name__,static_folder=FRONTEND_PATH, static_url_path="")
CORS(app)

# Inicializar base de datos
db = MetricsDB('litesysm.db')

# Variable global para el thread de recopilación
collecting = True
# Variables  para el buffer de contador de consumo
buffer_kwh = 0.0
buffer_horas = 0.0
contador_ciclos = 0
intervalo_escritura = 12


def collect_metrics_loop(interval=5):
    """Ejecutar recopilación de métricas en background"""
    global collecting, buffer_kwh, buffer_horas, contador_ciclos
    device_info = SystemCollector.get_device_info()


    if db.is_table_empty('system_info'):
        db.insert_info(device_info)

    while collecting:
        try:
         

            metrics = SystemCollector.collect_all()
            db.insert_metric(metrics)
            kwh_intervalo = (metrics['power_consumption'] * (5 / 3600)) / 1000
            horas_intervalo = 5 / 3600
            
            # 2. SUMAMOS AL BUFFER (en memoria RAM, que es instantáneo)
            buffer_kwh += kwh_intervalo
            buffer_horas += horas_intervalo
            contador_ciclos += 1
            
            # 3. ¿Ha pasado el tiempo de guardar en la DB? --> Es decir los datos se acumulan y solo se guardan en la base de datos cada 5 minutos
            if contador_ciclos >= intervalo_escritura:
                datos_coste = {
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'energy_kwh': round(buffer_kwh, 6), 
                    'hours': round(buffer_horas, 2)
                    
                }
                
                db.insert_cost(datos_coste) # Escribimos en disco una sola vez
                
                # RESETEAMOS EL BUFFER
                buffer_kwh = 0.0
                buffer_horas = 0.0
                contador_ciclos = 0
                
                SystemCollector.insert_network_metrics_by_interface(db)
                if APP_MODE == "dev":
                    print("Datos de consumo y red acumuladosguardados en la base de datos.")


            if APP_MODE == "dev":
                print(f"[{datetime.now()}] Métricas registradas")
                print("-" * 55)
                print(f"{'PID':<10} {'Nombre':<25} {'CPU %':<10} {'RAM (MB)':<10}")
                print("-" * 55)
            
            # Nota: la primera llamada a cpu_percent suele dar 0.0, 
            # se recomienda llamar a psutil.cpu_percent(interval=1) antes o hacer un loop.
            top = SystemCollector.get_top_process()
            
            for p in top:
                if APP_MODE == "dev":
                    print(f"{p['pid']:<10} {p['name']:<25} {p['cpu_percent']:<10} {p['memory_mb']:<10.2f}")




            if APP_MODE == "dev":
                print("-" * 55)

            time.sleep(interval)

        except Exception as e:
            print(f"Error en recopilación: {e}")
            time.sleep(interval)

# Iniciar thread de recopilación
collector_thread = threading.Thread(target=collect_metrics_loop, daemon=True)
collector_thread.start()

# RUTAS API

@app.route('/api/metrics/latest', methods=['GET'])
def get_latest_metrics():
    """Obtener la última métrica"""
    metric = db.get_latest_metric()
    if metric:
        return jsonify(metric)
    return jsonify({'error': 'No metrics available'}), 404

@app.route('/api/diary/cost', methods=['GET'])
def get_diary_cost():
    """Obtener la última métrica"""
    diary_cost = db.get_diary_cost()

    if diary_cost:

        with open('config_cost.json', 'r') as f:
            config_cost = json.load(f)
        
        if config_cost is None:
            return jsonify(diary_cost)
        
        if config_cost['p1'] == 0 and config_cost['p2'] == 0 and config_cost['p3'] == 0:
            
            precio_kwh = config_cost["precio_kwh"]
            coste_base = diary_cost["energy_kwh"] * precio_kwh               
            iva = config_cost["iva"]
            coste_con_iva = coste_base * (1 + iva)

            coste_hora = coste_base / diary_cost["hours"]
          

            """Coste diario estimado con 24h"""
            coste_base_24 = coste_hora * 24 
            coste_con_iva_24 = coste_base_24 * (1 + iva)

            """Coste mensual estimado"""
            coste_base_mensual = coste_base_24 * 30
            coste_con_iva_mensual = coste_base_mensual * (1 + iva)

            """Coste anual estimado"""
            coste_base_anual = coste_base_24 * 365
            coste_con_iva_anual = coste_base_anual * (1 + iva) 

            cost={"cost":(f"{coste_con_iva:.8f}")}
            cost_24={"cost_24":(f"{coste_con_iva_24:.8f}")}
            cost_mensual={"cost_mensual":(f"{coste_con_iva_mensual:.8f}")}
            cost_anual={"cost_anual":(f"{coste_con_iva_anual:.8f}")}


            diary_cost.update(cost)
            diary_cost.update(cost_24)
            diary_cost.update(cost_mensual)
            diary_cost.update(cost_anual)

            boot_time_h, boot_time_m = SystemCollector.get_boot_time()

            diary_cost.update({"boot_time_h": boot_time_h})
            diary_cost.update({"boot_time_m":boot_time_m})

            return jsonify(diary_cost)

        

        


        return jsonify(diary_cost)
    return jsonify({'error': 'No diary cost available'}), 404


@app.route('/api/diary/network', methods=['GET'])
def get_diary_network():

    '''Obtener el histórico de red desde la base de datos'''
    '''diary_network = db.get_diary_network()'''


    '''Obtener el histórico de red desde el servidor'''
    diary_network = SystemCollector.get_network_metrics_by_interface()
    if diary_network:
        return jsonify(diary_network)


@app.route('/api/network/discovery/hosts', methods=['GET'])
def get_discovery_hosts():
    if SystemCollector.nampIsIntall():
        hosts = SystemCollector.discover_hosts()
        return jsonify(hosts)
    else:
        return jsonify(mensaje="No se ha encontrado nmap instalado. Para instalarlo -> *Deb : sudo apt install nmap *Arch : sudo pacman -Sy nmap")
    

@app.route('/api/network/discovery/services', methods=['GET'])
def get_discovery_services():
    if SystemCollector.nampIsIntall():
        hosts = SystemCollector.scan_services()
        return jsonify(hosts)
    else:
        return jsonify(mensaje="No se ha encontrado nmap instalado. Para instalarlo -> *Deb : sudo apt install nmap *Arch : sudo pacman -Sy nmap")

@app.route('/api/system/info', methods=['GET'])
def get_system_info():
    """Obtener la última métrica"""
    info = db.get_system_info()
    if info:
        return jsonify(info)
    return jsonify({'error': 'No info available'}), 404

@app.route('/api/metrics/history', methods=['GET'])
def get_metrics_history():
    """Obtener histórico de métricas (últimas 24 horas)"""
    metrics = db.get_metrics(hours=24)
    return jsonify(metrics)

@app.route('/api/metrics/history/<int:hours>', methods=['GET'])
def get_metrics_history_custom(hours):
    """Obtener histórico de N horas"""
    if hours < 1 or hours > 720:  # Máximo 30 días
        return jsonify({'error': 'Invalid hours range'}), 400
    
    metrics = db.get_metrics(hours=hours)
    return jsonify(metrics)

@app.route('/api/metrics/network/history/<int:hours>', methods=['GET'])
def get_metrics_network_history_custom(hours):
    """Obtener histórico de N horas"""
    if hours < 1 or hours > 720:  # Máximo 30 días
        return jsonify({'error': 'Invalid hours range'}), 400
    
    metrics = db.get_metrics_network_filter_wl_eth(hours=hours)
    return jsonify(metrics)

@app.route('/api/metrics/network/history/iface/<int:hours>', methods=['GET'])
def get_metrics_network_history_iface(hours):
    """Obtener histórico de N horas"""
    if hours < 1 or hours > 720:  # Máximo 30 días
        return jsonify({'error': 'Invalid hours range'}), 400
    
    iface = SystemCollector.get_default_interface(SystemCollector.get_local_ip())
    print(iface)
    metrics = db.get_metrics_network_filter_iface(hours=hours, iface=iface)
    return jsonify(metrics)

@app.route('/api/status', methods=['GET'])
def get_status():
    """Obtener estado actual del sistema"""
    try:
        latest = db.get_latest_metric()
        """latest = SystemCollector.collect_all()"""
        energy_plan = {"energy_plan":SystemCollector.get_energy_plan()}

        latest.update(energy_plan)
        # Calcular promedios de la última hora
        
        '''
        recent_metrics = db.get_metrics(hours=1)
    
        if recent_metrics:
            avg_cpu = sum(m['cpu_percent'] for m in recent_metrics) / len(recent_metrics)
            avg_ram = sum(m['ram_percent'] for m in recent_metrics) / len(recent_metrics)
            max_temp = max(m['cpu_temp'] for m in recent_metrics)
        else:
            avg_cpu = latest['cpu_percent']
            avg_ram = latest['ram_percent']
            max_temp = latest['cpu_temp']

        '''

        avg_cpu = latest['cpu_percent']
        avg_ram = latest['ram_percent']
        max_temp = latest['cpu_temp']
        
        return jsonify({
            'current': latest,
            'averages': {
                'cpu_1h': round(avg_cpu, 2),
                'ram_1h': round(avg_ram, 2),
                'max_temp_1h': round(max_temp, 2)
            }
        })
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/processtop', methods=['GET'])
def get_process_top():
    """Obtener estado actual del sistema"""
    try:
            top = SystemCollector.get_top_process()
            
            process_format = []
            for p in top:
                process_format.append({
                    'pid': p['pid'],
                    'name': p['name'],
                    'cpu_percent': p['cpu_percent'],
                    'memory_mb': round(p['memory_mb'], 2) # Redondeamos para que el JSON sea más limpio
                })

            return jsonify(process_format) # Devolvemos la lista completa
    except Exception as e:
            return jsonify({'error': str(e)}), 500
    

@app.route('/api/network/counter/speed', methods=['GET'])
def get_network_counter_speed():
    try:
        speed = SystemCollector.get_network_counter_speed()
        return jsonify(speed)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    try:


        app.run(host='0.0.0.0', port=5000, debug=False)

       

 
        
        # En producción usar Gunicorn:
        # gunicorn -w 4 -b 0.0.0.0:5000 app:app
    finally:
        collecting = False
