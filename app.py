#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS成本监控Web界面 V2 - 模块化版本
"""

from flask import Flask, render_template, jsonify, Response
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

# Prometheus集成
try:
    from prometheus_client import generate_latest, Gauge, Info, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("警告: prometheus_client未安装，Prometheus功能不可用")
    print("安装命令: pip install prometheus_client")

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

# Prometheus指标定义
if PROMETHEUS_AVAILABLE:
    aws_cost_daily_total = Gauge('aws_cost_daily_total_usd', 'AWS每日总成本(美元)')
    aws_cost_hourly_total = Gauge('aws_cost_hourly_total_usd', 'AWS每小时总成本(美元)')
    aws_cost_monthly_total = Gauge('aws_cost_monthly_total_usd', 'AWS当月总成本(美元)')
    aws_cost_by_service = Gauge('aws_cost_daily_by_service_usd', 'AWS每日服务成本(美元)', ['service'])
    aws_cost_by_resource = Gauge('aws_cost_daily_by_resource_usd', 'AWS每日资源成本(美元)', ['service', 'resource_id', 'region'])
    aws_cost_info = Info('aws_cost_collection_info', 'AWS成本收集信息')

def update_prometheus_metrics():
    """更新Prometheus指标"""
    if not PROMETHEUS_AVAILABLE:
        return
    
    try:
        summary = db_manager.get_latest_summary()
        if not summary:
            return
        
        # 更新基础指标
        aws_cost_daily_total.set(summary['total_daily_cost'])
        aws_cost_hourly_total.set(summary['total_hourly_cost'])
        
        # 更新服务分解
        if summary.get('service_breakdown'):
            try:
                service_breakdown = json.loads(summary['service_breakdown'])
                for service, cost in service_breakdown.items():
                    aws_cost_by_service.labels(service=service).set(cost)
            except:
                pass
        
        # 获取月度成本
        current_month_str = datetime.now().strftime('%Y-%m')
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT total_monthly_cost FROM monthly_summary WHERE year_month = ?', (current_month_str,))
        monthly_result = cursor.fetchone()
        if monthly_result:
            aws_cost_monthly_total.set(monthly_result[0])
        
        # 获取资源详情
        cursor.execute('''
            SELECT service_type, resource_id, region, daily_cost 
            FROM cost_records WHERE timestamp = ?
        ''', (summary['timestamp'],))
        resources = cursor.fetchall()
        
        for resource in resources:
            service_type, resource_id, region, daily_cost = resource
            aws_cost_by_resource.labels(
                service=service_type,
                resource_id=resource_id,
                region=region
            ).set(daily_cost)
        
        conn.close()
        
        # 更新信息指标
        aws_cost_info.info({
            'last_update': summary['timestamp'],
            'total_resources': str(len(resources)),
            'collection_status': 'success'
        })
        
    except Exception as e:
        logger.error(f"更新Prometheus指标失败: {e}")
        if PROMETHEUS_AVAILABLE:
            aws_cost_info.info({
                'collection_status': 'error',
                'error_message': str(e)
            })

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

@app.route('/traffic')
def traffic_page():
    """流量费用页面"""
    # 返回空数据的页面，由前端异步加载数据
    return render_template('traffic.html', 
                         traffic_data=[],
                         summary={'total_cost': 0, 'total_resources': 0, 'total_volume_gb': 0, 'active_regions': 0},
                         service_breakdown={})

@app.route('/api/traffic_data')
def traffic_data_api():
    """获取流量费用数据 API"""
    try:
        from collectors.traffic_collector import TrafficCollector
        from pricing.price_manager import PriceManager
        
        traffic_collector = TrafficCollector(price_manager=PriceManager())
        traffic_data = traffic_collector.scan_all_regions()
        
        # 计算汇总信息
        summary = {
            'total_cost': sum([item.get('monthly_cost', 0) for item in traffic_data]),
            'total_resources': len(traffic_data),
            'total_volume_gb': sum([item.get('details', {}).get('volume_gb', 0) for item in traffic_data]),
            'active_regions': len(set([item.get('region', '') for item in traffic_data if item.get('region')]))
        }
        
        # 按服务分组
        service_breakdown = {}
        for item in traffic_data:
            service = item['service']
            if service not in service_breakdown:
                service_breakdown[service] = {
                    'total_cost': 0,
                    'resource_count': 0,
                    'total_volume_gb': 0
                }
            service_breakdown[service]['total_cost'] += item.get('monthly_cost', 0)
            service_breakdown[service]['resource_count'] += 1
            service_breakdown[service]['total_volume_gb'] += item.get('details', {}).get('volume_gb', 0)
        
        return jsonify({
            'traffic_data': traffic_data,
            'summary': summary,
            'service_breakdown': service_breakdown
        })
    except Exception as e:
        logger.error(f"获取流量费用数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/all-resources')
def all_resources_page():
    return render_template('all_resources.html')

@app.route('/test-dashboard')
def test_dashboard():
    return render_template('../test_dashboard.html')

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
        
        # 数据收集完成后更新Prometheus指标
        try:
            update_prometheus_metrics()
        except Exception as e:
            logger.warning(f"Prometheus指标更新失败: {e}")
        
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

@app.route('/api/traffic_summary')
def traffic_summary():
    """获取流量费用汇总信息"""
    try:
        # 直接从数据库查询Traffic类型的费用
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # 获取最新时间戳
        cursor.execute('SELECT timestamp FROM cost_summary ORDER BY timestamp DESC LIMIT 1')
        latest_timestamp = cursor.fetchone()
        
        if not latest_timestamp:
            conn.close()
            return jsonify({'traffic_cost': 0, 'traffic_percentage': 0, 'total_cost': 0})
        
        timestamp = latest_timestamp[0]
        
        # 查询Traffic类型的费用
        cursor.execute('''
            SELECT COALESCE(SUM(daily_cost), 0) as traffic_cost 
            FROM cost_records 
            WHERE timestamp = ? AND service_type = 'Traffic'
        ''', (timestamp,))
        traffic_result = cursor.fetchone()
        traffic_cost = traffic_result[0] if traffic_result else 0
        
        # 查询总费用
        cursor.execute('''
            SELECT total_daily_cost 
            FROM cost_summary 
            WHERE timestamp = ?
        ''', (timestamp,))
        total_result = cursor.fetchone()
        total_cost = total_result[0] if total_result else 0
        
        conn.close()
        
        traffic_percentage = (traffic_cost / total_cost * 100) if total_cost > 0 else 0
        
        return jsonify({
            'traffic_cost': round(traffic_cost, 4),
            'traffic_percentage': round(traffic_percentage, 1),
            'total_cost': round(total_cost, 4)
        })
    except Exception as e:
        logger.error(f"获取流量费用汇总失败: {e}")
        return jsonify({'traffic_cost': 0, 'traffic_percentage': 0, 'total_cost': 0}), 500

@app.route('/metrics')
def prometheus_metrics():
    """暴露Prometheus指标"""
    if not PROMETHEUS_AVAILABLE:
        return "Prometheus client not available. Install with: pip install prometheus_client", 503
    
    # 更新指标
    update_prometheus_metrics()
    
    # 返回Prometheus格式的指标
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route('/api/prometheus_status')
def prometheus_status():
    """获取Prometheus集成状态"""
    return jsonify({
        'prometheus_available': PROMETHEUS_AVAILABLE,
        'metrics_endpoint': '/metrics' if PROMETHEUS_AVAILABLE else None,
        'install_command': 'pip install prometheus_client' if not PROMETHEUS_AVAILABLE else None
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)