# 事务事件模块（outbox）

> 事务性事件投递（阶段 D）。实现事务 Outbox 模式，保证业务变更与事件原子写入，
> Scheduler 异步领取投递；PostgreSQL 是唯一事实来源（ADR-004）。

## 职责

- 在业务事务内写入事件记录（与业务变更同事务提交或回滚）；
- 由 Scheduler 带行锁领取并投递到 Celery/Redis；
- 允许重复投递，Worker 必须幂等消费；
- 失败退避与补偿重投（D-011）。

## 入口

- ORM Model：`OutboxEventModel`（infrastructure）；
- 写入端口：事务内 Outbox 写入（D-008）；
- 领取用例：带行锁的事件领取（D-009）；
- 投递端口：`OutboxBroker`（D-010），Celery 适配器 `CeleryOutboxBroker`；
- 投递编排：`dispatch_outbox_events`（领取→投递→确认 DELIVERED，D-010）。

## 状态

- 投递状态：PENDING / DELIVERED / FAILED（与业务状态分离，不承载业务事实）；
- 业务状态机见各业务模块（analysis 等），不在 outbox 表达。

## 依赖

- 上游：所有需要发事件的业务模块（analysis 任务投递、report 过期传播等）；
- 下游：Celery/Redis（投递通道，非事实来源）；
- 共享内核：orm、identifiers、business_time。

## 禁区

- domain 不导入 ORM/队列/供应商 SDK（A-006 守护）；
- 业务状态不得放入 outbox 或 Redis；outbox 只承载事件消息信封（稳定 ID + 参数），
  不存放正式领域模型整体（SPEC.md 第 7.2 节）；
- 不引入身份/权限/租户字段或兼容分支。
