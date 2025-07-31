#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示月度成本计算问题和修复
"""

from database.db_manager import DatabaseManager
from utils.db_config import get_db_config
import json

def demo_monthly_calculation_issue():
    """演示月度成本计算问题"""
    print("=== 月度成本计算问题演示 ===\n")
    
    db_manager = DatabaseManager(get_db_config())
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    # 1. 显示原始每日数据
    print("1. 原始每日数据（每天多次收集）:")
    cursor.execute('''
        SELECT DATE(timestamp) as date, timestamp, total_daily_cost 
        FROM cost_summary 
        ORDER BY timestamp
    ''')
    records = cursor.fetchall()
    
    daily_totals = {}
    for record in records:
        date, timestamp, daily_cost = record
        if date not in daily_totals:
            daily_totals[date] = []
        daily_totals[date].append(daily_cost)
        print(f"  {timestamp}: ${daily_cost:.4f}")
    
    # 2. 显示每日最大值（正确的每日成本）
    print(f"\n2. 每日实际成本（取每日最大值）:")
    correct_monthly_total = 0
    for date, costs in daily_totals.items():
        max_cost = max(costs)
        correct_monthly_total += max_cost
        print(f"  {date}: ${max_cost:.4f} (共{len(costs)}次记录)")
    
    print(f"\n正确的月度总成本应该是: ${correct_monthly_total:.4f}")
    
    # 3. 显示修复后的月度汇总
    print(f"\n3. 修复后的月度汇总:")
    cursor.execute('SELECT year_month, total_monthly_cost FROM monthly_summary')
    monthly_records = cursor.fetchall()
    
    for record in monthly_records:
        year_month, total_cost = record
        print(f"  {year_month}: ${total_cost:.4f}")
    
    # 4. 解释问题
    print(f"\n=== 问题解释 ===")
    print("问题: 原来的update_monthly_summary方法每次都简单累加daily_cost")
    print("这导致同一天的成本被重复计算多次（每小时收集一次就累加一次）")
    print("\n修复: 新的方法按日期分组，取每日的最大成本值")
    print("这样确保每天的成本只计算一次，得到正确的月度总计")
    
    # 5. 显示服务分解
    print(f"\n=== 服务成本分解 ===")
    cursor.execute('SELECT service_breakdown FROM monthly_summary ORDER BY year_month DESC LIMIT 1')
    breakdown_record = cursor.fetchone()
    
    if breakdown_record and breakdown_record[0]:
        try:
            breakdown = json.loads(breakdown_record[0])
            for service, cost in breakdown.items():
                percentage = (cost / correct_monthly_total) * 100
                print(f"  {service}: ${cost:.4f} ({percentage:.1f}%)")
        except:
            print("  服务分解数据解析失败")
    
    conn.close()

if __name__ == '__main__':
    demo_monthly_calculation_issue()