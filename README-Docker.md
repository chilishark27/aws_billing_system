# Docker 部署指南

## 快速启动

### 使用 Docker Compose（推荐）

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 使用脚本启动

**Linux/Mac:**
```bash
chmod +x run-docker.sh
./run-docker.sh
```

**Windows:**
```cmd
run-docker.bat
```

## 手动构建

```bash
# 构建镜像
docker build -t aws-cost-monitor .

# 运行容器
docker run -d \
  -p 80:80 \
  -v $(pwd)/data:/app/data \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_DEFAULT_REGION=us-east-1 \
  --name aws-cost-monitor \
  aws-cost-monitor
```

## 访问应用

- 应用地址：http://localhost
- 数据持久化：./data 目录
- AWS凭据：使用主机的 ~/.aws 配置

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AWS_DEFAULT_REGION` | `us-east-1` | 默认AWS区域 |

## 注意事项

- 确保主机已配置AWS凭据
- 数据库文件保存在 ./data 目录
- 容器会自动重启（除非手动停止）