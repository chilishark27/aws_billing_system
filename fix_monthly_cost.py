#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复月度成本计算脚本
"""

import sqlite3
import json
from datetime import datetime
from collections import defaultdict

def fix_monthly_costs():
    """修复月度成本计算"""
    import os
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'cost_history.db')
    print(f'使用数据库路径: {db_path}')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== 修复月度成本计算 ===\n")
    
    # 获取所有月份
    cursor.execute('''
        SELECT DISTINCT substr(timestamp, 1, 7) as year_month 
        FROM cost_summary 
        ORDER BY year_month
    ''')
    months = cursor.fetchall()
    
    for month_row in months:
        year_month = month_row[0]
        print(f"处理月份: {year_month}")
        
        # 获取该月每日的最大成本（避免重复计算）
        cursor.execute('''
            SELECT DATE(timestamp) as date, MAX(total_daily_cost) as daily_cost,
                   (SELECT service_breakdown FROM cost_summary 
                    WHERE DATE(timestamp) = DATE(cs.timestamp) 
                    ORDER BY timestamp DESC LIMIT 1) as breakdown
            FROM cost_summary cs
            WHERE timestamp LIKE ?
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''', (f'{year_month}%',))
        
        daily_records = cursor.fetchall()
        
        # 计算实际月度总成本
        actual_monthly_total = 0
        service_totals = defaultdict(float)
        
        for record in daily_records:
            date, daily_cost, breakdown_json = record
            actual_monthly_total += daily_cost
            
            # 解析服务分解
            if breakdown_json:
                try:
                    breakdown = json.loads(breakdown_json)
                    for service, cost in breakdown.items():
                        service_totals[service] += cost
                except:
                    pass
            
            print(f"  {date}: ${daily_cost:.4f}")
        
        print(f"  月度总计: ${actual_monthly_total:.4f}")
        
        # 更新或插入月度汇总
        cursor.execute('SELECT id FROM monthly_summary WHERE year_month = ?', (year_month,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE monthly_summary 
                SET total_monthly_cost = ?, service_breakdown = ?
                WHERE year_month = ?
            ''', (actual_monthly_total, json.dumps(dict(service_totals)), year_month))
            print(f"  已更新月度汇总")
        else:
            cursor.execute('''
                INSERT INTO monthly_summary 
                (year_month, total_monthly_cost, service_breakdown, created_at)
                VALUES (?, ?, ?, ?)
            ''', (year_month, actual_monthly_total, json.dumps(dict(service_totals)), datetime.now().isoformat()))
            print(f"  已创建月度汇总")
        
        print()
    
    conn.commit()
    conn.close()
    print("修复完成！")

def verify_monthly_costs():
    """验证修复结果"""
    import os
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'cost_history.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== 验证修复结果 ===\n")
    
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
    verify_monthly_costs()