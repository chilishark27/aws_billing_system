@echo off

echo 构建并启动AWS成本监控容器...

REM 构建镜像
docker-compose build

REM 启动服务
docker-compose up -d

echo 容器已启动，访问 http://localhost
echo 查看日志: docker-compose logs -f
echo 停止服务: docker-compose down

pause