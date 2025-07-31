#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理器 - 支持多种数据库
"""

import sqlite3
import json
import os
from datetime import datetime
from collections import defaultdict


class DatabaseManager:
    def __init__(self, db_config=None):
        if db_config is None:
            db_config = {'type': 'sqlite', 'path': 'data/cost_history.db'}
        
        self.db_config = db_config
        self.db_type = db_config.get('type', 'sqlite')
        
        if self.db_type == 'sqlite':
            self.db_path = db_config.get('path', 'data/cost_history.db')
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        elif self.db_type in ['postgresql', 'mysql']:
            self.db_url = self._build_db_url(db_config)
            
        self.init_database()
    
    def _build_db_url(self, config):
        """构建数据库连接URL"""
        user = config.get('user', 'root')
        password = config.get('password', '')
        host = config.get('host', 'localhost')
        port = config.get('port', 5432 if self.db_type == 'postgresql' else 3306)
        database = config.get('database', 'aws_cost_monitor')
        
        if self.db_type == 'postgresql':
            return f"postgresql://{user}:{password}@{host}:{port}/{database}"
        elif self.db_type == 'mysql':
            return f"mysql://{user}:{password}@{host}:{port}/{database}"
    
    def get_connection(self):
        """获取数据库连接"""
        if self.db_type == 'sqlite':
            return sqlite3.connect(self.db_path)
        elif self.db_type == 'postgresql':
            import psycopg2
            from urllib.parse import urlparse
            parsed = urlparse(self.db_url)
            return psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:]
            )
        elif self.db_type == 'mysql':
            import pymysql
            from urllib.parse import urlparse
            parsed = urlparse(self.db_url)
            return pymysql.connect(
                host=parsed.hostname,
                port=parsed.port,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:],
                charset='utf8mb4'
            )
    
    def init_database(self):
        """初始化数据库"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 根据数据库类型调整SQL语法
        if self.db_type == 'sqlite':
            id_type = 'INTEGER PRIMARY KEY AUTOINCREMENT'
            text_type = 'TEXT'
            real_type = 'REAL'
        elif self.db_type == 'postgresql':
            id_type = 'SERIAL PRIMARY KEY'
            text_type = 'VARCHAR(255)'
            real_type = 'DECIMAL(10,4)'
        elif self.db_type == 'mysql':
            id_type = 'INT AUTO_INCREMENT PRIMARY KEY'
            text_type = 'VARCHAR(255)'
            real_type = 'DECIMAL(10,4)'
        
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS cost_records (
                id {id_type},
                timestamp {text_type} NOT NULL,
                service_type {text_type} NOT NULL,
                resource_id {text_type} NOT NULL,
                region {text_type} NOT NULL,
                hourly_cost {real_type} NOT NULL,
                daily_cost {real_type} NOT NULL,
                details TEXT
            )
        ''')
        
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS cost_summary (
                id {id_type},
                timestamp {text_type} NOT NULL,
                total_hourly_cost {real_type} NOT NULL,
                total_daily_cost {real_type} NOT NULL,
                service_breakdown TEXT
            )
        ''')
        
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS lambda_records (
                id {id_type},
                timestamp {text_type} NOT NULL,
                resource_id {text_type} NOT NULL,
                region {text_type} NOT NULL,
                hourly_cost {real_type} NOT NULL,
                daily_cost {real_type} NOT NULL,
                details TEXT
            )
        ''')
        
        if self.db_type != 'sqlite':
            try:
                cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_lambda_records_unique ON lambda_records(timestamp, resource_id, region)')
            except:
                pass
        
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS monthly_summary (
                id {id_type},
                year_month {text_type} NOT NULL,
                total_monthly_cost {real_type} NOT NULL,
                service_breakdown TEXT,
                created_at {text_type} NOT NULL
            )
        ''')
        
        if self.db_type == 'mysql':
            try:
                cursor.execute('CREATE UNIQUE INDEX idx_monthly_summary_year_month ON monthly_summary(year_month)')
            except:
                pass
        elif self.db_type == 'postgresql':
            try:
                cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_monthly_summary_year_month ON monthly_summary(year_month)')
            except:
                pass
        
        conn.commit()
        conn.close()
    
    def save_cost_data(self, services, timestamp=None):
        """保存成本数据"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        total_hourly = 0
        total_daily = 0
        service_breakdown = defaultdict(float)
        
        placeholder = '?' if self.db_type == 'sqlite' else '%s'
        
        # 保存详细记录（排除Lambda）
        for service in services:
            if service['service'] != 'Lambda':
                # 对于流量相关服务，使用统一的服务类型
                service_type = service['service']
                if service_type in ['NAT Gateway', 'VPC Endpoint', 'ELB', 'CloudFront', 'Route 53', 'EC2']:
                    # 检查是否为流量相关的EC2记录
                    if service_type == 'EC2':
                        details = service.get('details', {})
                        if details.get('traffic_type') == 'Data Transfer Out':
                            service_type = 'Traffic'
                    else:
                        service_type = 'Traffic'  # 其他流量服务统一归类
                
                cursor.execute(f'''
                    INSERT INTO cost_records 
                    (timestamp, service_type, resource_id, region, hourly_cost, daily_cost, details)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ''', (
                    timestamp,
                    service_type,
                    service['resource_id'],
                    service['region'],
                    service['hourly_cost'],
                    service['daily_cost'],
                    json.dumps(service)
                ))
                
                total_hourly += service['hourly_cost']
                total_daily += service['daily_cost']
                service_breakdown[service_type] += service['daily_cost']
            else:
                # Lambda数据单独保存
                if self.db_type == 'sqlite':
                    cursor.execute(f'''
                        INSERT OR REPLACE INTO lambda_records 
                        (timestamp, resource_id, region, hourly_cost, daily_cost, details)
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                    ''', (
                        timestamp,
                        service['resource_id'],
                        service['region'],
                        service['hourly_cost'],
                        service['daily_cost'],
                        json.dumps(service)
                    ))
                elif self.db_type == 'mysql':
                    cursor.execute(f'''
                        INSERT INTO lambda_records 
                        (timestamp, resource_id, region, hourly_cost, daily_cost, details)
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                        ON DUPLICATE KEY UPDATE 
                        hourly_cost = VALUES(hourly_cost), daily_cost = VALUES(daily_cost), details = VALUES(details)
                    ''', (
                        timestamp,
                        service['resource_id'],
                        service['region'],
                        service['hourly_cost'],
                        service['daily_cost'],
                        json.dumps(service)
                    ))
                else:  # postgresql
                    cursor.execute(f'''
                        INSERT INTO lambda_records 
                        (timestamp, resource_id, region, hourly_cost, daily_cost, details)
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT (timestamp, resource_id, region) DO UPDATE SET
                        hourly_cost = EXCLUDED.hourly_cost, daily_cost = EXCLUDED.daily_cost, details = EXCLUDED.details
                    ''', (
                        timestamp,
                        service['resource_id'],
                        service['region'],
                        service['hourly_cost'],
                        service['daily_cost'],
                        json.dumps(service)
                    ))
        
        # 保存汇总记录
        cursor.execute(f'''
            INSERT INTO cost_summary 
            (timestamp, total_hourly_cost, total_daily_cost, service_breakdown)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
        ''', (
            timestamp,
            total_hourly,
            total_daily,
            json.dumps(dict(service_breakdown))
        ))
        
        conn.commit()
        conn.close()
        
        return total_hourly, total_daily, service_breakdown
    
    def get_latest_summary(self):
        """获取最新的成本汇总"""
        conn = self.get_connection()
        
        if self.db_type == 'sqlite':
            conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM cost_summary 
            ORDER BY timestamp DESC LIMIT 1
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            if self.db_type == 'sqlite':
                return dict(result)
            else:
                columns = ['id', 'timestamp', 'total_hourly_cost', 'total_daily_cost', 'service_breakdown']
                return dict(zip(columns, result))
        return None
    
    def get_cost_history(self, hours=24):
        """获取成本历史数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.db_type == 'sqlite':
            time_filter = f"datetime(timestamp) >= datetime('now', '-{hours} hours')"
        elif self.db_type == 'postgresql':
            time_filter = f"timestamp >= NOW() - INTERVAL '{hours} hours'"
        elif self.db_type == 'mysql':
            time_filter = f"timestamp >= DATE_SUB(NOW(), INTERVAL {hours} HOUR)"
        
        cursor.execute(f'''
            SELECT DISTINCT timestamp 
            FROM cost_summary 
            WHERE {time_filter}
            ORDER BY timestamp ASC
        ''')
        timestamps = cursor.fetchall()
        
        history_data = []
        placeholder = '?' if self.db_type == 'sqlite' else '%s'
        
        for ts_row in timestamps:
            timestamp = ts_row[0]
            
            cursor.execute(f'''
                SELECT SUM(hourly_cost) as total_hourly, SUM(daily_cost) as total_daily
                FROM cost_records 
                WHERE timestamp = {placeholder}
            ''', (timestamp,))
            costs = cursor.fetchone()
            
            history_data.append({
                'timestamp': timestamp,
                'total_hourly_cost': costs[0] or 0,
                'total_daily_cost': costs[1] or 0
            })
        
        conn.close()
        return history_data
    
    def check_monthly_reset(self):
        """检查是否需要重置月度计费"""
        now = datetime.now()
        current_month = now.strftime('%Y-%m')
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        placeholder = '?' if self.db_type == 'sqlite' else '%s'
        
        cursor.execute(f'''
            SELECT year_month FROM monthly_summary 
            WHERE year_month = {placeholder}
        ''', (current_month,))
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.execute(f'''
                INSERT INTO monthly_summary 
                (year_month, total_monthly_cost, service_breakdown, created_at)
                VALUES ({placeholder}, 0.0, '{{}}', {placeholder})
            ''', (current_month, now.isoformat()))
            
            print(f"新月份开始: {current_month}, 月度计费重置为$0.00")
        
        conn.commit()
        conn.close()
    
    def update_monthly_summary(self, daily_cost, service_breakdown):
        """更新月度统计 - 重新计算整个月的实际成本"""
        now = datetime.now()
        current_month = now.strftime('%Y-%m')
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        placeholder = '?' if self.db_type == 'sqlite' else '%s'
        
        # 重新计算当月的实际总成本（基于每日最大值，避免重复计算）
        cursor.execute(f'''
            SELECT DATE(timestamp) as date, MAX(total_daily_cost) as daily_cost 
            FROM cost_summary 
            WHERE timestamp LIKE {placeholder}
            GROUP BY DATE(timestamp)
        ''', (f'{current_month}%',))
        
        daily_records = cursor.fetchall()
        actual_monthly_total = sum(record[1] for record in daily_records)
        
        # 重新计算服务分解（基于最新的每日数据）
        cursor.execute(f'''
            SELECT service_breakdown FROM cost_summary 
            WHERE timestamp LIKE {placeholder}
            ORDER BY timestamp DESC LIMIT 1
        ''', (f'{current_month}%',))
        
        latest_breakdown = cursor.fetchone()
        if latest_breakdown and latest_breakdown[0]:
            try:
                current_services = json.loads(latest_breakdown[0])
            except:
                current_services = {}
        else:
            current_services = {}
        
        # 更新月度汇总
        cursor.execute(f'''
            UPDATE monthly_summary 
            SET total_monthly_cost = {placeholder}, service_breakdown = {placeholder}
            WHERE year_month = {placeholder}
        ''', (actual_monthly_total, json.dumps(current_services), current_month))
        
        conn.commit()
        conn.close()