#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS成本监控Web界面 V2 - 模块化版本
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import threading
from datetime import datetime

from database.db_manager import DatabaseManager
from utils.db_config import get_db_config
from utils.logger import setup_logger, get_log_config
from cost_collector import CostCollectorV2
import sqlite3
import json
import logging

app = Flask(__name__)
CORS(app)

# 设置日志
log_config = get_log_config()
logger = setup_logger('aws_cost_monitor_web', log_config['path'], log_config['level'])

# 全局组件
db_manager = DatabaseManager(get_db_config())
collector = CostCollectorV2()

# 扫描状态
scan_status = {'running': False, 'progress': 0, 'results': None, 'error': None}

@app.route('/')
def dashboard():
    """主仪表板"""
    return render_template('dashboard.html')

@app.route('/ec2')
def ec2_page():
    return render_template('ec2.html')

@app.route('/rds')
def rds_page():
    return render_template('rds.html')

@app.route('/lambda')
def lambda_page():
    return render_template('lambda.html')

@app.route('/s3')
def s3_page():
    return render_template('s3.html')

@app.route('/ebs')
def ebs_page():
    return render_template('ebs.html')

@app.route('/vpc')
def vpc_page():
    return render_template('vpc.html')



@app.route('/cloudfront')
def cloudfront_page():
    return render_template('cloudfront.html')

@app.route('/all-resources')
def all_resources_page():
    return render_template('all_resources.html')

@app.route('/api/current_cost')
def current_cost():
    """获取当前成本数据"""
    summary = db_manager.get_latest_summary()
    
    if not summary:
        return jsonify({'error': '暂无数据'})
    
    return jsonify({
        'timestamp': summary['timestamp'],
        'total_hourly': summary['total_hourly_cost'],
        'total_daily': summary['total_daily_cost'],
        'service_breakdown': summary['service_breakdown']
    })

@app.route('/api/cost_history')
def cost_history():
    """获取成本历史数据"""
    history_data = db_manager.get_cost_history(24)  # 过去24小时
    return jsonify(history_data)

@app.route('/api/trigger_collection')
def trigger_collection():
    """手动触发数据收集"""
    if scan_status['running']:
        return jsonify({'error': '收集正在进行中'}), 400
    
    threading.Thread(target=manual_collect, daemon=True).start()
    return jsonify({'success': True, 'message': '数据收集已启动'})

def manual_collect():
    """手动收集数据"""
    global scan_status
    scan_status = {'running': True, 'progress': 0, 'results': None, 'error': None}
    
    try:
        scan_status['progress'] = 50
        collector.collect_and_save()
        scan_status = {
            'running': False,
            'progress': 100,
            'results': {'message': '数据收集完成'},
            'error': None
        }
    except Exception as e:
        scan_status = {
            'running': False,
            'progress': 0,
            'results': None,
            'error': str(e)
        }

@app.route('/api/scan-status')
def scan_status_api():
    """获取扫描状态"""
    return jsonify(scan_status)

@app.route('/api/service_data/<service_type>')
def service_data(service_type):
    """获取特定服务的数据"""
    try:
        conn = db_manager.get_connection()
        
        if db_manager.db_type == 'sqlite':
            conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        
        # 获取最新时间戳
        cursor.execute('''
            SELECT timestamp FROM cost_summary 
            ORDER BY timestamp DESC LIMIT 1
        ''')
        latest_timestamp = cursor.fetchone()
        
        if not latest_timestamp:
            conn.close()
            return jsonify([])
        
        timestamp = latest_timestamp[0] if db_manager.db_type != 'sqlite' else latest_timestamp['timestamp']
        placeholder = '?' if db_manager.db_type == 'sqlite' else '%s'
        
        if service_type.upper() == 'LAMBDA':
            cursor.execute(f'''
                SELECT * FROM lambda_records 
                WHERE timestamp = {placeholder}
                ORDER BY daily_cost DESC
            ''', (timestamp,))
        else:
            cursor.execute(f'''
                SELECT * FROM cost_records 
                WHERE timestamp = {placeholder} AND service_type = {placeholder}
                ORDER BY daily_cost DESC
            ''', (timestamp, service_type.upper()))
        
        resources = cursor.fetchall()
        conn.close()
        
        if db_manager.db_type == 'sqlite':
            result = [dict(row) for row in resources]
            if service_type.upper() == 'LAMBDA':
                for item in result:
                    item['service_type'] = 'LAMBDA'
            return jsonify(result)
        else:
            if service_type.upper() == 'LAMBDA':
                columns = ['id', 'timestamp', 'resource_id', 'region', 'hourly_cost', 'daily_cost', 'details']
                result = []
                for row in resources:
                    resource_dict = dict(zip(columns, row))
                    resource_dict['service_type'] = 'LAMBDA'
                    result.append(resource_dict)
                return jsonify(result)
            else:
                columns = ['id', 'timestamp', 'service_type', 'resource_id', 'region', 'hourly_cost', 'daily_cost', 'details']
                return jsonify([dict(zip(columns, row)) for row in resources])
            
    except Exception as e:
        logger.error(f"获取服务数据失败: {e}")
        return jsonify({'error': '获取服务数据失败'}), 500

@app.route('/api/resource_details')
def resource_details():
    """获取资源详细信息"""
    try:
        summary = db_manager.get_latest_summary()
        if not summary:
            logger.warning("没有找到最新的成本数据")
            return jsonify([])
        
        conn = db_manager.get_connection()
        if db_manager.db_type == 'sqlite':
            conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        placeholder = '?' if db_manager.db_type == 'sqlite' else '%s'
        
        cursor.execute(f'''
            SELECT * FROM cost_records 
            WHERE timestamp = {placeholder}
            ORDER BY service_type, daily_cost DESC
        ''', (summary['timestamp'],))
        
        resources = cursor.fetchall()
        logger.info(f"找到 {len(resources)} 个资源")
        conn.close()
        
        if db_manager.db_type == 'sqlite':
            return jsonify([dict(row) for row in resources])
        else:
            columns = ['id', 'timestamp', 'service_type', 'resource_id', 'region', 'hourly_cost', 'daily_cost', 'details']
            result = []
            for row in resources:
                resource_dict = dict(zip(columns, row))
                try:
                    details = json.loads(resource_dict['details'])
                    resource_dict['instance_type'] = details.get('instance_type', '')
                except:
                    resource_dict['instance_type'] = ''
                result.append(resource_dict)
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"获取资源详情失败: {e}")
        return jsonify({'error': '获取资源详情失败'}), 500

@app.route('/api/monthly_summary')
def monthly_summary():
    """获取月度成本汇总"""
    try:
        conn = db_manager.get_connection()
        if db_manager.db_type == 'sqlite':
            conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM monthly_summary 
            ORDER BY year_month DESC LIMIT 6
        ''')
        monthly_data = cursor.fetchall()
        conn.close()
        
        if db_manager.db_type == 'sqlite':
            return jsonify([dict(row) for row in monthly_data])
        else:
            columns = ['id', 'year_month', 'total_monthly_cost', 'service_breakdown', 'created_at']
            return jsonify([dict(zip(columns, row)) for row in monthly_data])
    except Exception as e:
        logger.error(f"获取月度数据失败: {e}")
        return jsonify({'error': '获取月度数据失败'}), 500

@app.route('/api/current_month')
def current_month():
    """获取当月成本统计"""
    try:
        current_month_str = datetime.now().strftime('%Y-%m')
        
        conn = db_manager.get_connection()
        if db_manager.db_type == 'sqlite':
            conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        placeholder = '?' if db_manager.db_type == 'sqlite' else '%s'
        
        cursor.execute(f'''
            SELECT * FROM monthly_summary 
            WHERE year_month = {placeholder}
        ''', (current_month_str,))
        month_data = cursor.fetchone()
        conn.close()
        
        if not month_data:
            return jsonify({
                'year_month': current_month_str,
                'total_monthly_cost': 0.0,
                'service_breakdown': {},
                'days_in_month': datetime.now().day
            })
        
        if db_manager.db_type == 'sqlite':
            result = dict(month_data)
        else:
            columns = ['id', 'year_month', 'total_monthly_cost', 'service_breakdown', 'created_at']
            result = dict(zip(columns, month_data))
        
        result['service_breakdown'] = json.loads(result['service_breakdown']) if result['service_breakdown'] else {}
        result['days_in_month'] = datetime.now().day
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取当月数据失败: {e}")
        return jsonify({'error': '获取当月数据失败'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)