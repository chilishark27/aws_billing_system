#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的月度成本修复脚本
"""

from database.db_manager import DatabaseManager
from utils.db_config import get_db_config
import json
from datetime import datetime
from collections import defaultdict

def fix_monthly_costs():
    """修复月度成本计算"""
    db_manager = DatabaseManager(get_db_config())
    
    print("=== 修复月度成本计算 ===\n")
    
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    # 获取所有月份
    cursor.execute('''
        SELECT DISTINCT substr(timestamp, 1, 7) as year_month 
        FROM cost_summary 
        ORDER BY year_month
    ''')
    months = cursor.fetchall()
    
    if not months:
        print("没有找到成本数据，请先运行数据收集")
        conn.close()
        return
    
    for month_row in months:
        year_month = month_row[0]
        print(f"处理月份: {year_month}")
        
        # 获取该月每日的最大成本（避免重复计算）
        cursor.execute('''
            SELECT DATE(timestamp) as date, MAX(total_daily_cost) as daily_cost
            FROM cost_summary 
            WHERE timestamp LIKE ?
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''', (f'{year_month}%',))
        
        daily_records = cursor.fetchall()
        
        # 计算实际月度总成本
        actual_monthly_total = 0
        
        for record in daily_records:
            date, daily_cost = record
            actual_monthly_total += daily_cost
            print(f"  {date}: ${daily_cost:.4f}")
        
        print(f"  月度总计: ${actual_monthly_total:.4f}")
        
        # 获取最新的服务分解
        cursor.execute('''
            SELECT service_breakdown FROM cost_summary 
            WHERE timestamp LIKE ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (f'{year_month}%',))
        
        latest_breakdown = cursor.fetchone()
        service_breakdown = "{}"
        if latest_breakdown and latest_breakdown[0]:
            service_breakdown = latest_breakdown[0]
        
        # 更新或插入月度汇总
        cursor.execute('SELECT id FROM monthly_summary WHERE year_month = ?', (year_month,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE monthly_summary 
                SET total_monthly_cost = ?, service_breakdown = ?
                WHERE year_month = ?
            ''', (actual_monthly_total, service_breakdown, year_month))
            print(f"  已更新月度汇总")
        else:
            cursor.execute('''
                INSERT INTO monthly_summary 
                (year_month, total_monthly_cost, service_breakdown, created_at)
                VALUES (?, ?, ?, ?)
            ''', (year_month, actual_monthly_total, service_breakdown, datetime.now().isoformat()))
            print(f"  已创建月度汇总")
        
        print()
    
    conn.commit()
    conn.close()
    print("修复完成！")

def verify_results():
    """验证修复结果"""
    db_manager = DatabaseManager(get_db_config())
    
    print("=== 验证修复结果 ===\n")
    
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT year_month, total_monthly_cost, service_breakdown 
        FROM monthly_summary 
        ORDER BY year_month DESC
    ''')
    
    monthly_data = cursor.fetchall()
    
    for row in monthly_data:
        year_month, total_cost, breakdown_json = row
        print(f"月份: {year_month}")
        print(f"总成本: ${total_cost:.4f}")
        
        if breakdown_json:
            try:
                breakdown = json.loads(breakdown_json)
                print("服务分解:")
                for service, cost in breakdown.items():
                    print(f"  {service}: ${cost:.4f}")
            except:
                print("  服务分解数据解析失败")
        print()
    
    conn.close()

if __name__ == '__main__':
    fix_monthly_costs()
    verify_results()