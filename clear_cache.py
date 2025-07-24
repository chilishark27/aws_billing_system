#!/usr/bin/env python3
"""
清理价格缓存脚本
"""

import sqlite3
import os

def clear_price_cache():
    """清理价格缓存，强制重新获取价格"""
    
    # 删除数据库中最近的记录
    if os.path.exists('data/cost_history.db'):
        conn = sqlite3.connect('data/cost_history.db')
        cursor = conn.cursor()
        
        # 删除最近1小时的记录
        cursor.execute('''
            DELETE FROM cost_records 
            WHERE datetime(timestamp) >= datetime('now', '-1 hour')
        ''')
        
        cursor.execute('''
            DELETE FROM cost_summary 
            WHERE datetime(timestamp) >= datetime('now', '-1 hour')
        ''')
        
        cursor.execute('''
            DELETE FROM lambda_records 
            WHERE datetime(timestamp) >= datetime('now', '-1 hour')
        ''')
        
        conn.commit()
        conn.close()
        print("✓ 已清理数据库中的最近记录")
    
    print("✓ 缓存清理完成，请重新启动应用")

if __name__ == '__main__':
    clear_price_cache()