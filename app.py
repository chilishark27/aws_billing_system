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
from cost_collector import CostCollectorV2
import sqlite3
import json

app = Flask(__name__)
CORS(app)

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

@app.route('/fsx')
def fsx_page():
    return render_template('fsx.html')

@app.route('/cloudwatch')
def cloudwatch_page():
    return render_template('cloudwatch.html')

@app.route('/waf')
def waf_page():
    return render_template('waf.html')

@app.route('/amazonq')
def amazonq_page():
    return render_template('amazonq.html')

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
    import sqlite3
    import json
    
    conn = sqlite3.connect('data/cost_history.db')
    conn.row_factory = sqlite3.Row
    
    latest_timestamp = conn.execute('''
        SELECT timestamp FROM cost_summary 
        ORDER BY timestamp DESC LIMIT 1
    ''').fetchone()
    
    if not latest_timestamp:
        conn.close()
        return jsonify([])
    
    if service_type.upper() == 'LAMBDA':
        resources = conn.execute('''
            SELECT *, 'LAMBDA' as service_type FROM lambda_records 
            WHERE timestamp = ?
            ORDER BY daily_cost DESC
        ''', (latest_timestamp['timestamp'],)).fetchall()
    else:
        resources = conn.execute('''
            SELECT * FROM cost_records 
            WHERE timestamp = ? AND service_type = ?
            ORDER BY daily_cost DESC
        ''', (latest_timestamp['timestamp'], service_type.upper())).fetchall()
    
    conn.close()
    return jsonify([dict(row) for row in resources])

@app.route('/api/resource_details')
def resource_details():
    """获取资源详细信息"""
    import sqlite3
    
    conn = sqlite3.connect('data/cost_history.db')
    conn.row_factory = sqlite3.Row
    
    latest_timestamp = conn.execute('''
        SELECT timestamp FROM cost_summary 
        ORDER BY timestamp DESC LIMIT 1
    ''').fetchone()
    
    if not latest_timestamp:
        conn.close()
        return jsonify([])
    
    resources = conn.execute('''
        SELECT *, json_extract(details, '$.instance_type') as instance_type
        FROM cost_records 
        WHERE timestamp = ?
        ORDER BY service_type, daily_cost DESC
    ''', (latest_timestamp['timestamp'],)).fetchall()
    
    conn.close()
    return jsonify([dict(row) for row in resources])

@app.route('/api/monthly_summary')
def monthly_summary():
    """获取月度成本汇总"""
    import sqlite3
    
    conn = sqlite3.connect('data/cost_history.db')
    conn.row_factory = sqlite3.Row
    
    monthly_data = conn.execute('''
        SELECT * FROM monthly_summary 
        ORDER BY year_month DESC LIMIT 6
    ''').fetchall()
    
    conn.close()
    return jsonify([dict(row) for row in monthly_data])

@app.route('/api/current_month')
def current_month():
    """获取当月成本统计"""
    import sqlite3
    import json
    from datetime import datetime
    
    current_month = datetime.now().strftime('%Y-%m')
    
    conn = sqlite3.connect('data/cost_history.db')
    conn.row_factory = sqlite3.Row
    
    month_data = conn.execute('''
        SELECT * FROM monthly_summary 
        WHERE year_month = ?
    ''', (current_month,)).fetchone()
    
    if not month_data:
        conn.close()
        return jsonify({
            'year_month': current_month,
            'total_monthly_cost': 0.0,
            'service_breakdown': {},
            'days_in_month': datetime.now().day
        })
    
    result = dict(month_data)
    result['service_breakdown'] = json.loads(result['service_breakdown']) if result['service_breakdown'] else {}
    result['days_in_month'] = datetime.now().day
    
    conn.close()
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)