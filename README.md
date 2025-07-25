# AWS成本实时监控系统

企业级AWS成本监控解决方案，提供实时价格获取、多服务监控和现代化Web界面。

## 🚀 核心特性

- 💰 **AWS官方实时价格** - 直接调用AWS Pricing API获取准确价格
- 🌐 **12种服务监控** - EC2、RDS、Lambda、S3、EBS、VPC、FSx、CloudWatch、WAF、Amazon Q、CloudFront
- ⏰ **每小时自动收集** - 定时扫描所有区域的AWS资源
- 📊 **现代化Web界面** - 响应式设计，左侧导航，实时数据可视化
- 📈 **月度计费重置** - 自动按月重置计费，保留历史账单
- 🔄 **智能缓存机制** - 4小时价格缓存，减少API调用
- 🐳 **Docker部署** - 支持容器化部署，80端口访问

## 📦 支持的AWS服务

| 服务 | 监控内容 | 计费方式 |
|------|----------|----------|
| **EC2** | 运行中实例 | 按实例类型/小时 |
| **RDS** | 可用数据库 | 按实例类型/小时 |
| **Lambda** | 有调用的函数 | 按调用次数+执行时间 |
| **S3** | 存储桶大小 | 按存储量/月 (前5GB免费) |
| **EBS** | 挂载的卷 | 按卷类型和大小/月 |
| **VPC** | NAT网关、未使用EIP | 按小时 |
| **FSx** | 文件系统 | 按存储容量/月 |
| **CloudWatch** | 自定义指标、日志 | 按指标数量和存储 |
| **WAF** | Web ACL | 按WebACL数量/月 |
| **Amazon Q** | 活跃用户 | 按用户数/月 |
| **CloudFront** | 分发 | 免费额度内为$0 |

## 🌍 支持的AWS区域

- `us-east-1` (美国东部-弗吉尼亚)
- `us-west-2` (美国西部-俄勒冈)
- `ap-southeast-1` (亚太-新加坡)
- `ap-east-1` (亚太-香港)
- `eu-west-1` (欧洲-爱尔兰)
- `ap-northeast-1` (亚太-东京)

## 🎯 快速启动

### 方式1: Docker部署 (推荐)

```bash
# 克隆项目
git clone <repository>
cd aws_cost_monitor

# 启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

访问: http://localhost

### 方式2: 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python start.py
```

访问: http://localhost:80

## 💡 价格获取机制

1. **实时获取**: 直接调用AWS Pricing API获取官方价格
2. **智能缓存**: 价格缓存4小时，避免重复API调用
3. **备用价格**: API失败时使用预设价格确保系统稳定
4. **自动更新**: 获取实时价格后5秒内更新数据库记录

## 📊 Web界面功能

### 总览页面
- 实时成本统计卡片
- 24小时成本趋势图
- 月度成本趋势图
- 资源详情表格

### 服务专页
- 每个AWS服务独立页面
- 服务特定的资源列表
- 成本分析和趋势

### 月度计费
- 自动按月重置计费
- 保留历史月度账单
- 当月实际成本追踪

## 🔧 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AWS_DEFAULT_REGION` | `us-east-1` | 默认AWS区域 |
| `PYTHONUNBUFFERED` | `1` | Python无缓冲输出 |

### 监控区域调整

编辑 `cost_collector.py` 中的 `self.regions` 列表:

```python
self.regions = ['us-east-1', 'us-west-2', 'ap-southeast-1']
```

## 🐳 Docker部署详情

### 构建和运行

```bash
# 停止现有容器
docker-compose down

# 重新构建
docker-compose build --no-cache

# 启动服务
docker-compose up -d
```

### 数据持久化

- 数据库文件: `./data/cost_history.db`
- AWS凭据: 挂载主机的 `~/.aws` 目录

### 日志查看

```bash
# 实时日志
docker-compose logs -f

# 特定服务日志
docker logs <container_name>
```

## 📈 数据库结构

- **cost_records**: 详细资源成本记录
- **cost_summary**: 每小时成本汇总
- **lambda_records**: Lambda函数专用记录
- **monthly_summary**: 月度成本统计

## 🔍 故障排除

### 清理价格缓存

```bash
python clear_cache.py
```

### 常见问题

1. **价格显示为0**: 检查AWS凭据和Pricing API权限
2. **服务未显示**: 确认资源在监控区域内且状态正常
3. **Docker日志不显示**: 检查PYTHONUNBUFFERED环境变量

## 📄 许可证

MIT License