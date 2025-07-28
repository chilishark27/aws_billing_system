# 数据库配置说明

## 支持的数据库类型

### 1. SQLite (默认)
```bash
# 环境变量
export DB_TYPE=sqlite
export DB_PATH=data/cost_history.db

# Docker启动
docker-compose up -d
```

### 2. PostgreSQL (外部数据库)
```bash
# 需要先启动PostgreSQL服务器
# 环境变量
export DB_TYPE=postgresql
export DB_HOST=your-postgres-host
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=password
export DB_NAME=aws_cost_monitor

# Docker启动
docker-compose up -d
```

### 3. MySQL (外部数据库)
```bash
# 需要先启动MySQL服务器
# 环境变量
export DB_TYPE=mysql
export DB_HOST=your-mysql-host
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=password
export DB_NAME=aws_cost_monitor

# Docker启动
docker-compose up -d
```

## 数据库表结构

### cost_records
- 详细资源成本记录
- 包含服务类型、资源ID、区域、成本等信息

### cost_summary
- 每小时成本汇总
- 总成本和服务分解

### lambda_records
- Lambda函数专用记录
- 按调用次数计费

### monthly_summary
- 月度成本统计
- 自动按月重置

## 迁移数据库

### 从SQLite迁移到PostgreSQL
```bash
# 1. 导出SQLite数据
sqlite3 data/cost_history.db .dump > backup.sql

# 2. 启动PostgreSQL
docker-compose -f docker-compose.postgres.yml up -d postgres

# 3. 转换并导入数据 (需要手动调整SQL语法)
```

### 从SQLite迁移到MySQL
```bash
# 1. 导出SQLite数据
sqlite3 data/cost_history.db .dump > backup.sql

# 2. 启动MySQL
docker-compose -f docker-compose.mysql.yml up -d mysql

# 3. 转换并导入数据 (需要手动调整SQL语法)
```

## 性能优化

### PostgreSQL
- 适合大量数据和复杂查询
- 支持并发访问
- 推荐用于生产环境

### MySQL
- 适合高并发读写
- 良好的性能表现
- 广泛的生态支持

### SQLite
- 适合单用户或小规模部署
- 无需额外配置
- 开发和测试环境推荐