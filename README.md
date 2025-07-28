# AWS成本实时监控系统 - 模块化版本

企业级AWS成本监控解决方案，采用模块化架构，提供实时价格获取、多服务监控和现代化Web界面。

## 🏗️ 架构特性

### 模块化设计
- **collectors/**: 资源收集器模块 (EC2, VPC, RDS等)
- **pricing/**: 价格管理模块 (统一价格获取和缓存)
- **database/**: 数据库管理模块 (多数据库支持)
- **utils/**: 工具和常量模块

### 多数据库支持
- 🗄️ **SQLite** (默认) - 无需配置，适合开发测试
- 🐘 **PostgreSQL** - 高性能，适合生产环境
- 🐬 **MySQL** - 高并发，广泛支持

### Public IP收费更新 (2024年2月1日起)
- ✅ 已更新支持AWS Public IP新收费标准
- ✅ 包含EIP、临时IP、NAT Gateway IP等所有类型
- ✅ 每小时$0.005，每日$0.12，每月$3.6

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
| **VPC** | NAT网关、EIP、Public IP | 按小时 |
| **ELB** | 负载均衡器 | 按类型/小时 |
| **CloudFront** | 分发 | 免费额度内为$0 |
| **Route53** | 托管区域 | $0.50/月 |
| **DynamoDB** | 数据库表 | 按需/预置容量 |
| **SNS** | 主题 | 按量付费 (前1000万次免费) |
| **SQS** | 队列 | 按量付费 (前100万次免费) |

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

# 复制环境变量文件
cp .env.example .env

# 编辑.env文件配置数据库 (可选)
# 默认使用SQLite，无需修改

# 启动容器
docker-compose up -d
```

访问: http://localhost

### 方式2: 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 配置数据库 (可选)
export DB_TYPE=sqlite  # 或 postgresql, mysql

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

### 数据库配置

#### SQLite (默认)
```bash
export DB_TYPE=sqlite
export DB_PATH=data/cost_history.db
```

#### PostgreSQL
```bash
export DB_TYPE=postgresql
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=password
export DB_NAME=aws_cost_monitor
```

#### MySQL
```bash
export DB_TYPE=mysql
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=password
export DB_NAME=aws_cost_monitor
```

### 其他环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AWS_DEFAULT_REGION` | `us-east-1` | 默认AWS区域 |
| `DB_TYPE` | `sqlite` | 数据库类型 |
| `LOG_PATH` | - | 日志文件路径 (可选) |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `PYTHONUNBUFFERED` | `1` | Python无缓冲输出 |

### 监控区域调整

编辑 `cost_collector.py` 中的 `self.regions` 列表:

```python
self.regions = ['us-east-1', 'us-west-2', 'ap-southeast-1']
```

## 🐳 Docker部署详情

### 不同数据库配置

```bash
# SQLite (默认)
docker-compose up -d

# PostgreSQL (需要外部PostgreSQL服务)
DB_TYPE=postgresql DB_HOST=your-postgres-host docker-compose up -d

# MySQL (需要外部MySQL服务)
DB_TYPE=mysql DB_HOST=your-mysql-host docker-compose up -d
```

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

- **SQLite**: `./data/cost_history.db`
- **PostgreSQL/MySQL**: 外部数据库服务器
- **AWS凭据**: 挂载主机的 `~/.aws` 目录

### 日志查看

```bash
# 实时日志
docker-compose logs -f

# 特定服务日志
docker logs <container_name>
```

## 📈 数据库结构

### 表结构 (支持SQLite/PostgreSQL/MySQL)
- **cost_records**: 详细资源成本记录
- **cost_summary**: 每小时成本汇总
- **lambda_records**: Lambda函数专用记录
- **monthly_summary**: 月度成本统计

### 数据库选择建议
- **开发/测试**: SQLite (无需配置)
- **生产环境**: PostgreSQL (高性能，ACID支持)
- **高并发场景**: MySQL (优秀的读写性能)

详细配置请参考: [DATABASE.md](DATABASE.md)

## 🔍 故障排除

### 常见问题

1. **价格显示为0**: 检查AWS凭据和Pricing API权限
2. **服务未显示**: 确认资源在监控区域内且状态正常
3. **数据库连接失败**: 检查数据库配置和连接参数
4. **Docker启动失败**: 确认端口未被占用，检查环境变量
5. **PostgreSQL/MySQL连接超时**: 确认数据库服务已启动

### 数据库迁移

```bash
# 从SQLite迁移到PostgreSQL
# 1. 备份现有数据
sqlite3 data/cost_history.db .dump > backup.sql

# 2. 启动PostgreSQL版本
docker-compose -f docker-compose.postgres.yml up -d

# 3. 系统会自动创建新表结构
```

## 📁 项目结构

```
aws_cost_monitor/
├── collectors/          # 资源收集器模块
│   ├── base_collector.py
│   ├── ec2_collector.py
│   ├── vpc_collector.py
│   └── rds_collector.py
├── database/           # 数据库管理模块
│   └── db_manager.py
├── pricing/            # 价格管理模块
│   └── price_manager.py
├── utils/              # 工具模块
│   ├── constants.py
│   └── db_config.py
├── static/             # 静态资源
├── templates/          # HTML模板
├── data/               # 数据文件
├── app.py              # Web应用
├── cost_collector.py   # 成本收集器
├── start.py            # 启动脚本
├── docker-compose.yml  # SQLite版本
├── docker-compose.postgres.yml  # PostgreSQL版本
├── docker-compose.mysql.yml     # MySQL版本
└── DATABASE.md         # 数据库配置说明
```

## 📄 许可证

MIT License