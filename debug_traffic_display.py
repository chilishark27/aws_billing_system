#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试流量费用显示问题
"""

import sqlite3
import json
from database.db_manager import DatabaseManager
from utils.db_config import get_db_config

def debug_traffic_display():
    """调试流量费用显示"""
    print("=== 调试流量费用显示 ===\n")
    
    db_manager = DatabaseManager(get_db_config())
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    # 1. 检查最新时间戳
    cursor.execute('SELECT timestamp FROM cost_summary ORDER BY timestamp DESC LIMIT 1')
    latest_timestamp = cursor.fetchone()
    
    if not latest_timestamp:
        print("没有找到任何成本数据")
        return
    
    timestamp = latest_timestamp[0]
    print(f"最新时间戳: {timestamp}")
    
    # 2. 检查Traffic类型的费用
    cursor.execute('''
        SELECT COALESCE(SUM(daily_cost), 0) as traffic_cost 
        FROM cost_records 
        WHERE timestamp = ? AND service_type = 'Traffic'
    ''', (timestamp,))
    traffic_result = cursor.fetchone()
    traffic_cost = traffic_result[0] if traffic_result else 0
    
    print(f"Traffic费用: ${traffic_cost:.4f}/日")
    
    # 3. 检查总费用
    cursor.execute('''
        SELECT total_daily_cost 
        FROM cost_summary 
        WHERE timestamp = ?
    ''', (timestamp,))
    total_result = cursor.fetchone()
    total_cost = total_result[0] if total_result else 0
    
    print(f"总费用: ${total_cost:.4f}/日")
    
    # 4. 计算百分比
    traffic_percentage = (traffic_cost / total_cost * 100) if total_cost > 0 else 0
    print(f"流量费用占比: {traffic_percentage:.1f}%")
    
    # 5. 检查服务分布
    cursor.execute('SELECT service_breakdown FROM cost_summary WHERE timestamp = ?', (timestamp,))
    breakdown_result = cursor.fetchone()
    if breakdown_result and breakdown_result[0]:
        breakdown = json.loads(breakdown_result[0])
        print(f"\n服务分布:")
        for service, cost in breakdown.items():
            print(f"   {service}: ${cost:.4f}/日")
        
        traffic_in_breakdown = breakdown.get('Traffic', 0)
        print(f"\n服务分布中的Traffic: ${traffic_in_breakdown:.4f}/日")
    
    # 6. 检查具体的Traffic记录
    cursor.execute('''
        SELECT resource_id, daily_cost, details 
        FROM cost_records 
        WHERE timestamp = ? AND service_type = 'Traffic'
        ORDER BY daily_cost DESC
    ''', (timestamp,))
    traffic_records = cursor.fetchall()
    
    print(f"\nTraffic记录详情 ({len(traffic_records)}条):")
    for resource_id, daily_cost, details_json in traffic_records:
        try:
            details = json.loads(details_json)
            service = details.get('service', 'Unknown')
            traffic_type = details.get('details', {}).get('traffic_type', 'Unknown')
            volume_gb = details.get('details', {}).get('volume_gb', 0)
            print(f"   {service} {resource_id}: {traffic_type}, {volume_gb}GB, ${daily_cost:.4f}/日")
        except:
            print(f"   {resource_id}: ${daily_cost:.4f}/日 (解析失败)")
    
    # 7. 模拟API响应
    api_response = {
        'traffic_cost': round(traffic_cost, 4),
        'traffic_percentage': round(traffic_percentage, 1),
        'total_cost': round(total_cost, 4)
    }
    
    print(f"\nAPI应该返回:")
    print(json.dumps(api_response, indent=2))
    
    conn.close()
    
    # 8. 给出建议
    print(f"\n建议:")
    if traffic_cost == 0:
        print("   - 流量费用为0，可能是因为EC2实例流量在免费额度内")
        print("   - 检查EC2实例是否有足够的出站流量")
        print("   - 考虑创建NAT Gateway或其他流量服务进行测试")
    else:
        print("   - 流量费用正常，检查前端JavaScript是否正确调用API")
        print("   - 检查浏览器控制台是否有错误信息")

if __name__ == '__main__':
    debug_traffic_display()