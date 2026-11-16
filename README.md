# 包装线节拍对照实验

Welch 实验检验的真实业务分析小型项目。完整模拟客户、痛点、上下游、算法公式与一天工作剧本见 [BUSINESS.md](BUSINESS.md)。

## 模块与业务流程
数据接入（JSON/CSV、字段验证、批次指纹）→ 参数化分析（异步 Python worker，接单钉版）→ 结果复核（指标、图形、明细、解释、批准）→ 定时分发（本地收件箱、CSV/JSON、SHA256、版本与计算依据）；另有业务总览、审计轨迹与计算版本试发布（双算对照、容差裁决、灰度切换/回滚）。
三个贯穿全栈的实体：Dataset 数据批次、Job 分析任务、Report 分发计划；辅助 User、Audit、Delivery，以及版本治理实体 AlgorithmVersion、Release、ReleaseCheck。

## 计算版本试发布
- 引擎在 `backend/src/engines/`：`v1_welch` 为历史 Welch（默认，口径不变），`v2_shift_adjusted` 为候选版，按全样本班别构成直接标准化校正均值差。
- 试发布锁定历史批次（id+指纹）、9 组参数网格、基线改善量与四类容差；逐批次×参数双算，缺项或超差拒绝上线；核验中断从未算批次恢复，重试不新增对照条目。
- 全部通过且未过期才切换默认版本；竞争上线按起始默认版本裁决。Job 在接单瞬间固定 `engine_version`，排队/重启沿用；回滚只影响新单，旧版有在途任务时拒绝退役。
- 前端「版本试发布」页展示待核验/超差/可上线/已上线及每单版本；工作台可选择版本，结果页与分发简报保留版本和计算依据。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18203；后端文档 http://localhost:19203/docs；数据库宿主端口 17703。
`SEED_DEMO=true` 自动幂等 seed；不覆盖用户修改。手动 seed 命令可重复执行。

## 演示账号与权限
|账号|密码|真实权限|
|---|---|---|
|admin@demo.local|Demo123!|接入、执行、批准、分发、暂停、读取与下载|
|analyst@demo.local|Demo123!|接入、执行、读取与下载；不能批准或安排分发|
|viewer@demo.local|Demo123!|只读与下载|

## 技术与本地开发
Python 3.12 / FastAPI / SQLAlchemy / NumPy / SciPy / scikit-learn；MySQL 8.0；Redis 7；Nginx；原生 HTML CSS JavaScript ES modules（用户指定）。后端所有校验、持久化和算法在服务端。无前端打包步骤。
后端：安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL、JWT_SECRET、ARTIFACT_DIR 后在 backend/ 执行 `python -m migrations.initial`（幂等建表，为旧库补 jobs.engine_version 列并登记引擎版本）、`python -m scripts.seed_demo`、`uvicorn src.main:app`，另开 `python -m src.worker`。前端使用带 /api 反向代理的 Nginx，直接打开 index.html 不支持 API。

## 目录与工程约定
backend/src/{models,schemas,services,routes,controllers,middlewares,engines,constants,config,utils}；backend/scripts/seed_demo.py；backend/migrations/initial.py。engines 内每个计算版本一个无状态模块，统一 `analyze(records, params)` 出口与 headline 结构，经 `src.engines.ENGINES` 注册分发。
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。
Role 枚举：admin/analyst/viewer；JobStatus：queued/running/completed/failed。后端 backend/src/constants/enums.py，前端 frontend/src/constants/enums.js；路由权限在 middlewares/auth.py；页面按相同角色控制操作入口。

## 环境变量与 Docker
COMPOSE_PROJECT_NAME=pack-welch；FRONTEND_PORT=18203；BACKEND_PORT=19203；DB_PORT=17703；DB_PASSWORD、JWT_SECRET 见 .env.example；SEED_DEMO 默认 true。共享命名产物卷供后端下载与 worker 写入，数据库/Redis 各持久卷。
恰好五服务均有健康检查。Redis 队列加 SQL 排队状态兜底；worker 按 next_run 生成本地收件箱文件。周期 60 秒至 30 天。分发结果为批准分析的固定快照；若需新数据重新计算并建立新计划。当前不连接邮件或企业聊天。
错误响应、请求编号、Redis 每 IP 每分钟 240 次限流、JWT 和数据库操作审计。演示密钥与密码仅供本机模拟；生产部署前配置独立密钥与账号。

## 数据与验收
所有数据为固定随机种子生成的模拟业务数据，不能作为实际生产决策证据。项目独立算法、输入边界及业务局限详见 BUSINESS.md。测试与截图统一存放 ../../test-artifacts/gb-1004/，源码不含日志/截图/测试报告。
清理本项目演示数据：`docker compose down -v --remove-orphans`（会删除本项目命名卷）。

## License
MIT，见 LICENSE。
