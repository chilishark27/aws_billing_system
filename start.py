#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS成本监控启动器
同时启动数据收集器和Web界面
"""

import subprocess
import threading
import time
import os

def start_collector():
    """启动成本数据收集器"""
    print("启动成本数据收集器...")
    try:
        subprocess.run(['python', 'cost_collector.py'])
    except Exception as e:
        print(f"数据收集器启动失败: {e}")

def start_web_app():
    """启动Web界面"""
    print("启动Web界面...")
    time.sleep(2)  # 等待数据库初始化
    try:
        subprocess.run(['python', 'app.py'])
    except Exception as e:
        print(f"Web界面启动失败: {e}")

def main():
    print("=== AWS成本监控系统启动 (模块化版本) ===")
    
    # 确保数据目录存在
    os.makedirs('data', exist_ok=True)
    
    # 在后台启动数据收集器
    collector_thread = threading.Thread(target=start_collector, daemon=True)
    collector_thread.start()
    
    # 启动Web应用
    print("\n[Web] Web界面将在 http://localhost 启动")
    print("[数据] 数据收集器每小时自动运行")
    print("[刷新] 页面每5分钟自动刷新")
    print("[架构] 模块化 (collectors/, pricing/, database/)")
    
    start_web_app()

if __name__ == '__main__':
    main()