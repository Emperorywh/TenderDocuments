# ADR-013 首版单 Linux Docker Compose 部署

- 状态：Accepted
- 日期：2026-07-22

## 背景

首版部署目标是单台 Linux 服务器，预算与运维能力有限。引入 Kubernetes 或多节点编排
会带来与首版规模不匹配的复杂度与故障面。

## 决策

单台 Linux 服务器使用 Docker Compose 运行全部服务（frontend、nginx、api、worker-
default、worker-ocr、scheduler、postgres、redis、minio、otel-collector），DeepSeek
为外部服务（SPEC.md 第 13.1 节）。API 与 OCR Worker 使用不同镜像层。

## 后果

- 收益：部署、备份、回滚流程简单可控；
- 代价：无横向扩展，单机故障需靠备份与恢复演练兜底；
- 不使用 Kubernetes、独立消息总线或微服务（SPEC.md 第 3.3 节）。

## 重评条件

当单机无法满足吞吐或可用性，且垂直扩展已达上限时，重新评估多节点部署与编排方案。
