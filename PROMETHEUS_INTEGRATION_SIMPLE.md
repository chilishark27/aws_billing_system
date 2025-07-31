# AWS成本监控 - Prometheus集成 (集成版本)

## 快速开始

### 1. 安装Prometheus客户端
```bash
pip install prometheus_client
```

### 2. 启动应用
```bash
python app.py
```

### 3. 访问指标
- **Web界面**: http://localhost
- **Prometheus指标**: http://localhost/metrics
- **集成状态**: http://localhost/api/prometheus_status

## 可用指标

```
# 核心成本指标
aws_cost_daily_total_usd          # 每日总成本
aws_cost_hourly_total_usd         # 每小时总成本  
aws_cost_monthly_total_usd        # 当月总成本

# 详细成本指标
aws_cost_daily_by_service_usd{service="EC2"}     # 按服务分类
aws_cost_daily_by_resource_usd{service="EC2",resource_id="i-123",region="us-east-1"}  # 按资源分类

# 状态信息
aws_cost_collection_info{last_update="2025-01-31T10:00:00"}  # 收集状态
```

## Prometheus配置

在您的 `prometheus.yml` 中添加：

```yaml
scrape_configs:
  - job_name: 'aws-cost-monitor'
    static_configs:
      - targets: ['localhost:80']  # 注意端口是80
    metrics_path: /metrics
    scrape_interval: 60s
```

## 示例查询

```promql
# 当前每日成本
aws_cost_daily_total_usd

# 成本最高的服务
topk(5, aws_cost_daily_by_service_usd)

# EC2总成本
sum(aws_cost_daily_by_service_usd{service="EC2"})
```

## 特性

- ✅ 与现有Web界面完全集成
- ✅ 数据收集后自动更新指标
- ✅ 优雅降级（未安装prometheus_client时仍可正常使用）
- ✅ 实时指标更新
- ✅ 完整的标签支持