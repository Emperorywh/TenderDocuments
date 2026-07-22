# infra

基础设施与部署配置目录。

## 职责

承载开发与生产环境的基础设施定义：Docker Compose 服务图、Dockerfile、Nginx 配置、备份与恢复脚本、OpenTelemetry Collector 配置等。

## 技术基线

依据 `PLAN.md` 第 2.4、13 节：PostgreSQL 17、Redis 7、MinIO、Docker 与 Docker Compose、Nginx、OpenTelemetry、Prometheus 与 Grafana、structlog。

## 边界

- 单台 Linux 服务器使用 Docker Compose 部署；不使用 Kubernetes 或微服务（`SPEC.md` 第 3.3 节）；
- 内部基础设施端口（对象存储、PostgreSQL、Redis、Worker、管理端口）不得公开（`SPEC.md` 第 4.2 节）；
- 部署参数通过强类型配置注入，不散落为魔法常量（`SPEC.md` 第 17 章）。

具体内容由 `TASKS.md` 阶段 A（开发服务）与阶段 K（Linux 部署）按依赖逐步补充。
