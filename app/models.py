import sqlite3
from datetime import datetime


class MetricsDB:
    def __init__(self, db_path='litesysm.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Crear tablas si no existen"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                cpu_percent REAL,
                cpu_freq REAL,
                cpu_freq_max REAL,
                cpu_temp REAL,
                ram_percent REAL,
                ram_used INTEGER,
                disk_percent REAL,
                disk_used INTEGER,
                power_consumption REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS network_metrics (
                date TEXT PRIMARY KEY,
                interface TEXT,
                ip_address TEXT,
                mac_address TEXT,
                bytes_sent INTEGER,
                bytes_recv INTEGER,
                upload_bps REAL,
                download_bps REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_info (
                id INTEGER PRIMARY KEY,
                hostname TEXT,
                os TEXT,
                cpu_name TEXT,
                cpu_tpd INTEGER,
                disk_total INTEGER,
                ram_total INTEGER,
                gpu_name TEXT,
                vram_total INTEGER,
                last_update DATETIME
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diary_cost (
                date TEXT PRIMARY KEY,
                energy_kwh REAL DEFAULT 0,
                hours REAL DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()

    
    def is_table_empty(self, table_name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Buscamos solo 1 registro. Si existe, la tabla no está vacía.
        cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        result = cursor.fetchone()
        
        conn.close()
        return result is None  # Retorna True si está vacía, False si tiene datos
    
    def insert_metric(self, data):
        """Insertar una nueva métrica"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO metrics 
            (cpu_percent, cpu_freq, cpu_freq_max,
             cpu_temp, ram_percent, ram_used, 
             disk_percent, disk_used, power_consumption)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['cpu_percent'],
            data['cpu_freq'],
            data['cpu_freq_max'],
            data['cpu_temp'],
            data['ram_percent'],
            data['ram_used'],
            data['disk_percent'],
            data['disk_used'],
            data['power_consumption']
        ))
        
        conn.commit()
        conn.close()


    def insert_cost(self, data):
        """Insertar un coste diario de energía"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO diary_cost (date, energy_kwh, hours)
            VALUES (?, ?, ?) 
            ON CONFLICT(date) 
            DO UPDATE SET 
                energy_kwh = energy_kwh + excluded.energy_kwh,
                hours = hours + excluded.hours
        ''', (
            data['date'],
            data['energy_kwh'],
            data['hours']
        ))
        
        conn.commit()
        conn.close()


    def insert_info(self, data):
        """Insertar una nueva métrica"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO system_info 
            (hostname, os, cpu_name, cpu_tpd, disk_total, 
             ram_total, gpu_name, vram_total, last_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['hostname'],
            data['os'],
            data['cpu_name'],
            data['cpu_tpd'],
            data['disk_total'],
            data['ram_total'],
            data['gpu_name'],
            data['vram_total'],
            data['last_update']
        ))
        
        conn.commit()
        conn.close()


    def insert_network_metrics(self, data):
        """Insertar una nueva métrica"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO network_metrics 
            (date,interface, ip_address, mac_address, bytes_sent, bytes_recv, upload_bps, download_bps)
            VALUES (?,?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) 
                DO UPDATE SET 
                    bytes_sent = excluded.bytes_sent,
                    bytes_recv = excluded.bytes_recv 
        ''', (
            data['date'],
            data['interface'],
            data['ip_address'],
            data['mac_address'],
            data['bytes_sent'],
            data['bytes_recv'],
            data['upload_bps'],
            data['download_bps']
        ))
        
        conn.commit()
        conn.close()
    
    
    def get_metrics(self, hours=24):
        """Obtener métricas de las últimas N horas"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(f'''
            SELECT * FROM metrics 
            WHERE timestamp > datetime('now', '-{hours} hours')
            ORDER BY timestamp DESC
        ''')
        
        metrics = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return metrics
    
    def get_diary_network(self):
           """Obtener la última métrica registrada"""
           conn = sqlite3.connect(self.db_path)
           conn.row_factory = sqlite3.Row
           cursor = conn.cursor()
           
           cursor.execute('SELECT * FROM network_metrics ORDER BY date DESC LIMIT 1')
           diary_network = dict(cursor.fetchone() or {})
           conn.close()
           return diary_network

    

    def get_latest_metric(self):
        """Obtener la última métrica registrada"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM metrics ORDER BY timestamp DESC LIMIT 1')
        metric = dict(cursor.fetchone() or {})
        conn.close()
        return metric
    
    def get_diary_cost(self):
        """Obtener la última métrica registrada"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM diary_cost ORDER BY date DESC LIMIT 1')
        diary_cost = dict(cursor.fetchone() or {})
        conn.close()
        return diary_cost
    
    def get_system_info(self):
        """Obtener la última métrica registrada"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM system_info ')
        info = dict(cursor.fetchone() or {})
        conn.close()
        return info