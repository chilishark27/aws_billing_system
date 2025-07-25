#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS成本监控Web界面
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from cost_collector import CostCollector

app = Flask(__name__)
CORS(app)  # 启用CORS支持异步请求

# 全局扫描状态
scan_status = {'running': False, 'progress': 0, 'results': None, 'error': None}

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect('data/cost_history.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def dashboard():
    """主仪表板"""
    return render_template('dashboard.html')

@app.route('/ec2')
def ec2_page():
    """主仪表板"""
    return render_template('ec2.html')

@app.route('/rds')
def rds_page():
    """主仪表板"""
    return render_template('rds.html')

@app.route('/lambda')
def lambda_page():
    """主仪表板"""
    return render_template('lambda.html')

@app.route('/s3')
def s3_page():
    """主仪表板"""
    return render_template('s3.html')

@app.route('/ebs')
def ebs_page():
    """主仪表板"""
    return render_template('ebs.html')

@app.route('/vpc')
def vpc_page():
    """主仪表板"""
    return render_template('vpc.html')

@app.route('/fsx')
def fsx_page():
    """主仪表板"""
    return render_template('fsx.html')

@app.route('/cloudwatch')
def cloudwatch_page():
    """主仪表板"""
    return render_template('cloudwatch.html')

@app.route('/waf')
def waf_page():
    """主仪表板"""
    return render_template('waf.html')

@app.route('/amazonq')
def amazonq_page():
    """主仪表板"""
    return render_template('amazonq.html')

@app.route('/cloudfront')
def cloudfront_page():
    """主仪表板"""
    return render_template('cloudfront.html')

@app.route('/all-resources')
def all_resources_page():
    """所有资源扫描页面"""
    return render_template('all_resources.html')

@app.route('/api/current_cost')
def current_cost():
    """获取当前成本数据（排除Lambda）"""
    conn = get_db_connection()
    
    # 获取最新的汇总数据
    summary = conn.execute('''
        SELECT * FROM cost_summary 
        ORDER BY timestamp DESC LIMIT 1
    ''').fetchone()
    
    if not summary:
        return jsonify({'error': '暂无数据'})
    
    # 获取最新的详细数据（不包含Lambda）
    details = conn.execute('''
        SELECT * FROM cost_records 
        WHERE timestamp = ?
        ORDER BY daily_cost DESC
    ''', (summary['timestamp'],)).fetchall()
    
    # 重新计算成本（排除Lambda）
    total_hourly = sum(row['hourly_cost'] for row in details)
    total_daily = sum(row['daily_cost'] for row in details)
    
    # 重新计算服务分解（排除Lambda）
    service_breakdown = {}
    for row in details:
        service = row['service_type']
        if service not in service_breakdown:
            service_breakdown[service] = 0
        service_breakdown[service] += row['daily_cost']
    
    conn.close()
    
    return jsonify({
        'timestamp': summary['timestamp'],
        'total_hourly': total_hourly,
        'total_daily': total_daily,
        'service_breakdown': service_breakdown,
        'details': [dict(row) for row in details]
    })

@app.route('/api/cost_history')
def cost_history():
    """获取成本历史数据（排除Lambda）"""
    conn = get_db_connection()
    
    # 获取过去24小时的数据，重新计算排除Lambda
    history_data = []
    timestamps = conn.execute('''
        SELECT DISTINCT timestamp 
        FROM cost_summary 
        WHERE datetime(timestamp) >= datetime('now', '-24 hours')
        ORDER BY timestamp ASC
    ''').fetchall()
    
    for ts_row in timestamps:
        timestamp = ts_row['timestamp']
        # 获取该时间点的非Lambda成本
        costs = conn.execute('''
            SELECT SUM(hourly_cost) as total_hourly, SUM(daily_cost) as total_daily
            FROM cost_records 
            WHERE timestamp = ? AND service_type != 'LAMBDA'
        ''', (timestamp,)).fetchone()
        
        history_data.append({
            'timestamp': timestamp,
            'total_hourly_cost': costs['total_hourly'] or 0,
            'total_daily_cost': costs['total_daily'] or 0
        })
    
    conn.close()
    
    return jsonify(history_data)

@app.route('/api/service_trends')
def service_trends():
    """获取服务成本趋势"""
    conn = get_db_connection()
    
    trends = conn.execute('''
        SELECT timestamp, service_breakdown 
        FROM cost_summary 
        WHERE datetime(timestamp) >= datetime('now', '-24 hours')
        ORDER BY timestamp ASC
    ''').fetchall()
    
    conn.close()
    
    result = []
    for row in trends:
        breakdown = json.loads(row['service_breakdown'])
        result.append({
            'timestamp': row['timestamp'],
            'services': breakdown
        })
    
    return jsonify(result)

@app.route('/api/resource_details')
def resource_details():
    """获取资源详细信息"""
    conn = get_db_connection()
    
    # 获取最新时间戳的所有资源
    latest_timestamp = conn.execute('''
        SELECT timestamp FROM cost_summary 
        ORDER BY timestamp DESC LIMIT 1
    ''').fetchone()
    
    if not latest_timestamp:
        return jsonify([])
    
    resources = conn.execute('''
        SELECT *, json_extract(details, '$.instance_type') as instance_type
        FROM cost_records 
        WHERE timestamp = ?
        ORDER BY service_type, daily_cost DESC
    ''', (latest_timestamp['timestamp'],)).fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in resources])

@app.route('/api/daily_breakdown')
def daily_breakdown():
    """获取每日成本分解"""
    conn = get_db_connection()
    
    # 获取过去7天的数据
    daily_data = conn.execute('''
        SELECT 
            date(timestamp) as date,
            service_type,
            SUM(daily_cost) as total_cost,
            COUNT(*) as resource_count
        FROM cost_records 
        WHERE datetime(timestamp) >= datetime('now', '-7 days')
        GROUP BY date(timestamp), service_type
        ORDER BY date DESC, total_cost DESC
    ''').fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in daily_data])

@app.route('/api/monthly_summary')
def monthly_summary():
    """获取月度成本汇总"""
    conn = get_db_connection()
    
    # 获取最近6个月的数据
    monthly_data = conn.execute('''
        SELECT * FROM monthly_summary 
        ORDER BY year_month DESC LIMIT 6
    ''').fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in monthly_data])

@app.route('/api/current_month')
def current_month():
    """获取当月成本统计"""
    from datetime import datetime
    current_month = datetime.now().strftime('%Y-%m')
    
    conn = get_db_connection()
    
    # 获取当月数据
    month_data = conn.execute('''
        SELECT * FROM monthly_summary 
        WHERE year_month = ?
    ''', (current_month,)).fetchone()
    
    if not month_data:
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

@app.route('/api/service_data/<service_type>')
def service_data(service_type):
    """获取特定服务的数据"""
    conn = get_db_connection()
    
    # 获取最新时间戳
    latest_timestamp = conn.execute('''
        SELECT timestamp FROM cost_summary 
        ORDER BY timestamp DESC LIMIT 1
    ''').fetchone()
    
    if not latest_timestamp:
        return jsonify([])
    
    # Lambda使用单独的表
    if service_type.upper() == 'LAMBDA':
        resources = conn.execute('''
            SELECT *, 'LAMBDA' as service_type FROM lambda_records 
            WHERE timestamp = ?
            ORDER BY daily_cost DESC
        ''', (latest_timestamp['timestamp'],)).fetchall()
    else:
        # 其他服务使用主表
        resources = conn.execute('''
            SELECT * FROM cost_records 
            WHERE timestamp = ? AND service_type = ?
            ORDER BY daily_cost DESC
        ''', (latest_timestamp['timestamp'], service_type.upper())).fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in resources])

@app.route('/api/scan-all-resources')
def scan_all_resources():
    """异步扫描所有AWS资源"""
    if scan_status['running']:
        return jsonify({'error': '扫描正在进行中'}), 400
    
    threading.Thread(target=async_scan_resources, daemon=True).start()
    return jsonify({'success': True, 'message': '扫描已启动'})

@app.route('/api/scan-status')
def scan_status_api():
    """获取扫描状态"""
    return jsonify(scan_status)

def async_scan_resources():
    """异步扫描资源和成本"""
    global scan_status
    scan_status = {'running': True, 'progress': 0, 'results': None, 'error': None}
    
    try:
        import boto3
        collector = CostCollector()
        collector.session = boto3.Session()
        
        scan_status['progress'] = 20
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            resource_future = executor.submit(collector.get_all_resources)
            cost_future = executor.submit(collector.get_running_services)
            
            scan_status['progress'] = 60
            
            resources = resource_future.result()
            cost_services = cost_future.result()
            
            scan_status['progress'] = 80
        
        # 合并成本数据
        resource_costs = {}
        for service in cost_services:
            key = f"{service['region']}_{service['service']}_{service['resource_id']}"
            resource_costs[key] = {
                'hourly_cost': service['hourly_cost'],
                'daily_cost': service['daily_cost']
            }
        
        for resource in resources:
            key = f"{resource['region']}_{resource['service']}_{resource['resource_id']}"
            if key in resource_costs:
                resource.update(resource_costs[key])
            else:
                resource['hourly_cost'] = 0.0
                resource['daily_cost'] = 0.0
        
        # 分组结果
        grouped_resources = {}
        total_daily_cost = 0
        
        for resource in resources:
            service = resource['service']
            region = resource['region']
            
            if region not in grouped_resources:
                grouped_resources[region] = {}
            if service not in grouped_resources[region]:
                grouped_resources[region][service] = []
            
            grouped_resources[region][service].append(resource)
            total_daily_cost += resource.get('daily_cost', 0)
        
        # 导出文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/aws_all_resources_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'resources': grouped_resources,
                'summary': {
                    'total_resources': len(resources),
                    'total_daily_cost': total_daily_cost,
                    'scan_time': datetime.now().isoformat()
                }
            }, f, indent=2, ensure_ascii=False, default=str)
        
        scan_status = {
            'running': False,
            'progress': 100,
            'results': {
                'resources': grouped_resources,
                'export_file': filename,
                'total_resources': len(resources),
                'total_daily_cost': total_daily_cost,
                'timestamp': datetime.now().isoformat()
            },
            'error': None
        }
        
    except Exception as e:
        scan_status = {
            'running': False,
            'progress': 0,
            'results': None,
            'error': str(e)
        }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)