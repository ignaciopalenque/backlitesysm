from flask import Flask, jsonify
from flask_cors import CORS
from models import MetricsDB
from collectorService import SystemCollector
import threading
import time
from datetime import datetime

app = Flask(__name__)
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
                    'energy_kwh': buffer_kwh,
                    'hours': buffer_horas
                }
                
                db.insert_cost(datos_coste) # Escribimos en disco una sola vez
                
                # RESETEAMOS EL BUFFER
                buffer_kwh = 0.0
                buffer_horas = 0.0
                contador_ciclos = 0
                print("Datos de consumo acumuladosguardados en la base de datos.")



            print(f"[{datetime.now()}] Métricas registradas")
            print("-" * 55)
            print(f"{'PID':<10} {'Nombre':<25} {'CPU %':<10} {'RAM (MB)':<10}")
            print("-" * 55)
            
            # Nota: la primera llamada a cpu_percent suele dar 0.0, 
            # se recomienda llamar a psutil.cpu_percent(interval=1) antes o hacer un loop.
            top = SystemCollector.get_top_process()
            
            for p in top:
                print(f"{p['pid']:<10} {p['name']:<25} {p['cpu_percent']:<10} {p['memory_mb']:<10.2f}")
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

@app.route('/api/status', methods=['GET'])
def get_status():
    """Obtener estado actual del sistema"""
    try:
        latest = db.get_latest_metric()
        
        # Calcular promedios de la última hora
        recent_metrics = db.get_metrics(hours=1)
        
        if recent_metrics:
            avg_cpu = sum(m['cpu_percent'] for m in recent_metrics) / len(recent_metrics)
            avg_ram = sum(m['ram_percent'] for m in recent_metrics) / len(recent_metrics)
            max_temp = max(m['cpu_temp'] for m in recent_metrics)
        else:
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

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

if __name__ == '__main__':
    try:
        # En desarrollo
        app.run(host='0.0.0.0', port=5000, debug=False)
        
        # En producción usar Gunicorn:
        # gunicorn -w 4 -b 0.0.0.0:5000 app:app
    finally:
        collecting = False
