#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建测试数据来验证月度成本计算修复
"""

from database.db_manager import DatabaseManager
from utils.db_config import get_db_config
from datetime import datetime, timedelta
import json

def create_test_data():
    """创建测试数据"""
    db_manager = DatabaseManager(get_db_config())
    
    print("=== 创建测试数据 ===\n")
    
    # 模拟过去几天的数据
    base_date = datetime.now() - timedelta(days=5)
    
    test_services = [
        {
            'service': 'EC2',
            'resource_id': 'i-test123',
            'region': 'us-east-1',
            'hourly_cost': 0.1,
            'daily_cost': 2.4,
            'details': {'instance_type': 't3.medium'}
        },
        {
            'service': 'RDS',
            'resource_id': 'db-test456',
            'region': 'us-east-1',
            'hourly_cost': 0.05,
            'daily_cost': 1.2,
            'details': {'engine': 'mysql'}
        },
        {
            'service': 'Traffic',
            'resource_id': 'traffic-test',
            'region': 'us-east-1',
            'hourly_cost': 0.02,
            'daily_cost': 0.48,
            'details': {'traffic_type': 'Data Transfer Out'}
        }
    ]
    
    # 创建5天的数据
    for day in range(5):
        current_date = base_date + timedelta(days=day)
        timestamp = current_date.isoformat()
        
        print(f"创建 {current_date.strftime('%Y-%m-%d')} 的数据...")
        
        # 每天创建几次数据（模拟每小时收集）
        for hour in [6, 12, 18, 23]:
            hour_timestamp = current_date.replace(hour=hour).isoformat()
            
            # 稍微变化成本
            daily_multiplier = 1 + (day * 0.1)  # 每天成本略有增长
            
            adjusted_services = []
            for service in test_services:
                adjusted_service = service.copy()
                adjusted_service['daily_cost'] *= daily_multiplier
                adjusted_service['hourly_cost'] *= daily_multiplier
                adjusted_services.append(adjusted_service)
            
            # 保存数据
            total_hourly, total_daily, service_breakdown = db_manager.save_cost_data(
                adjusted_services, hour_timestamp
            )
            
            print(f"  {hour:02d}:00 - 每日成本: ${total_daily:.4f}")
    
    print("\n测试数据创建完成！")
    
    # 显示创建的数据
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM cost_summary')
    count = cursor.fetchone()[0]
    print(f"cost_summary表记录数: {count}")
    
    cursor.execute('SELECT timestamp, total_daily_cost FROM cost_summary ORDER BY timestamp')
    records = cursor.fetchall()
    print("\n所有记录:")
    for record in records:
        print(f"  {record[0]}: ${record[1]:.4f}")
    
    conn.close()

if __name__ == '__main__':
    create_test_data()