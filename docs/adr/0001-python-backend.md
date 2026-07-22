# ADR-001 后端统一采用 Python

- 状态：Accepted
- 日期：2026-07-22

## 背景

原需求分析曾建议 NestJS、Prisma 等技术栈。但首版需要 PDF/DOCX 解析、PaddleOCR、
文档坐标归一化与 DeepSeek 接入，这些能力在 Python 生态（PyMuPDF、pdfplumber、
PaddleOCR、OpenCV、HTTPX）更成熟且可复现。多语言后端会显著增加首版部署与运维复杂度。

## 决策

后端统一采用 Python 3.12 作为唯一技术基线（SPEC.md 第 1 节）。FastAPI 提供 API，
Celery 提供异步任务，SQLAlchemy 2 + Alembic 提供持久化，不引入第二门后端语言。

## 后果

- 收益：解析、OCR、模型接入在同一运行时内复用，减少跨语言序列化；
- 代价：Web 并发吞吐低于 Node/Go 方案，需要以进程级并发与队列补偿；
- NestJS、Prisma 等旧建议失效，不保留兼容层。

## 重评条件

当出现 Python 生态无法满足的性能或能力瓶颈（例如需要极致并发网关、或特定 SDK
仅在其他语言可用），且无法通过增加进程/队列解决时，重新评估是否引入第二后端语言。
