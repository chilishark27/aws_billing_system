#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS成本监控启动器 - 包含Prometheus集成
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
    time.sleep(2)
    try:
        subprocess.run(['python', 'app.py'])
    except Exception as e:
        print(f"Web界面启动失败: {e}")

def start_prometheus_exporter():
    """启动Prometheus指标导出器"""
    print("启动Prometheus指标导出器...")
    time.sleep(1)
    try:
        subprocess.run(['python', 'prometheus_exporter.py'])
    except Exception as e:
        print(f"Prometheus导出器启动失败: {e}")

def main():
    print("=== AWS成本监控系统启动 (包含Prometheus集成) ===")
    
    os.makedirs('data', exist_ok=True)
    
    # 启动各个组件
    collector_thread = threading.Thread(target=start_collector, daemon=True)
    prometheus_thread = threading.Thread(target=start_prometheus_exporter, daemon=True)
    
    collector_thread.start()
    prometheus_thread.start()
    
    print("\n[Web] Web界面: http://localhost")
    print("[Prometheus] 指标端点: http://localhost:9090/metrics")
    print("[数据] 数据收集器每小时运行")
    print("[指标] Prometheus指标每分钟更新")
    
    start_web_app()

if __name__ == '__main__':
    main()