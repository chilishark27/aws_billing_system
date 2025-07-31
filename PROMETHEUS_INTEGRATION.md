# AWS成本监控 - Prometheus集成

## 概述

本项目提供了完整的Prometheus集成，将AWS成本数据以标准Prometheus指标格式暴露，支持监控、告警和可视化。

## 暴露的指标

### 核心成本指标
- `aws_cost_daily_total_usd` - AWS每日总成本(美元)
- `aws_cost_hourly_total_usd` - AWS每小时总成本(美元)  
- `aws_cost_monthly_total_usd` - AWS当月总成本(美元)

### 详细成本指标
- `aws_cost_daily_by_service_usd{service}` - 按服务分类的每日成本
- `aws_cost_daily_by_resource_usd{service,resource_id,region}` - 按资源分类的每日成本

### 信息指标
- `aws_cost_collection_info` - 成本收集状态信息

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动服务
```bash
# 启动包含Prometheus导出器的完整服务
python start_with_prometheus.py

# 或者单独启动Prometheus导出器
python prometheus_exporter.py
```

### 3. 访问指标
- 指标端点: http://localhost:9090/metrics
- Web界面: http://localhost

## Prometheus配置

将以下配置添加到您的 `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'aws-cost-monitor'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 60s
```

## 告警规则

使用提供的 `aws_cost_alerts.yml` 文件设置成本告警:

- 每日成本超过$100告警
- 月度成本超过$1000告警  
- 单个服务成本过高告警
- 数据收集失败告警

## Grafana仪表板

导入 `grafana_dashboard.json` 创建成本监控仪表板，包含:

- 每日/月度成本统计
- 服务成本分布饼图
- 成本趋势图表
- 资源成本排行表

## 示例查询

### PromQL查询示例

```promql
# 当前每日总成本
aws_cost_daily_total_usd

# 成本最高的5个服务
topk(5, aws_cost_daily_by_service_usd)

# EC2服务的总成本
sum(aws_cost_daily_by_service_usd{service="EC2"})

# 成本增长率(与昨天比较)
(aws_cost_daily_total_usd - aws_cost_daily_total_usd offset 1d) / aws_cost_daily_total_usd offset 1d * 100
```

## 配置选项

### 环境变量
- `PROMETHEUS_PORT` - Prometheus导出器端口(默认9090)
- `METRICS_UPDATE_INTERVAL` - 指标更新间隔秒数(默认60)

### 自定义指标
可以在 `prometheus_exporter.py` 中添加更多自定义指标。

## 故障排除

### 常见问题
1. **指标端点无法访问**: 检查端口9090是否被占用
2. **指标数据为空**: 确保AWS成本数据收集正常运行
3. **告警不触发**: 检查Prometheus规则文件配置

### 日志查看
```bash
# 查看Prometheus导出器日志
python prometheus_exporter.py
```

## 集成架构

```
AWS成本监控系统
├── 数据收集器 (cost_collector.py)
├── Web界面 (app.py)
└── Prometheus导出器 (prometheus_exporter.py)
    ├── 指标暴露 (:9090/metrics)
    ├── 告警规则 (aws_cost_alerts.yml)
    └── Grafana仪表板 (grafana_dashboard.json)
```