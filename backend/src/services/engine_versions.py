"""计算版本登记与默认版本解析。"""
import time
from fastapi import HTTPException
from sqlalchemy import select
from src.engines import ENGINES, ORDER, DEFAULT_VERSION
from src.models import AlgorithmVersion, Job


def ensure_versions(db):
    """幂等登记引擎目录（随启动/迁移执行）。"""
    existing = {v.version: v for v in db.scalars(select(AlgorithmVersion))}
    for ver in ORDER:
        if ver not in existing:
            db.add(AlgorithmVersion(version=ver, title=ENGINES[ver].TITLE,
                                    is_default=(ver == DEFAULT_VERSION), retired=False,
                                    created_at=time.time()))
    db.flush()
    defaults = [v for v in db.scalars(select(AlgorithmVersion).where(AlgorithmVersion.is_default == True))]
    if len(defaults) != 1:
        # 异常兜底：保留第一个默认，其余清除，保证默认版本唯一
        keep = next((v for v in defaults if v.version == DEFAULT_VERSION), defaults[0] if defaults else None)
        for v in defaults:
            v.is_default = (v is keep)
        if keep is None:
            first = db.scalar(select(AlgorithmVersion).where(AlgorithmVersion.version == DEFAULT_VERSION))
            if first:
                first.is_default = True
    db.flush()


def get_default(db):
    ensure_versions(db)
    v = db.scalar(select(AlgorithmVersion).where(AlgorithmVersion.is_default == True))
    return v.version if v else DEFAULT_VERSION


def resolve_for_order(db, requested):
    """接单裁决：未指定版本则取当前默认；退役版本拒绝接单。每单在此固定。"""
    ensure_versions(db)
    version = requested or get_default(db)
    if version not in ENGINES:
        raise HTTPException(422, f'未知计算版本：{version}')
    row = db.scalar(select(AlgorithmVersion).where(AlgorithmVersion.version == version))
    if row is None:
        raise HTTPException(422, f'计算版本未登记：{version}')
    if row.retired:
        raise HTTPException(409, f'计算版本 {version} 已退役，不能用于新任务')
    return version


def list_versions(db):
    ensure_versions(db)
    rows = list(db.scalars(select(AlgorithmVersion)))
    order = {v: i for i, v in enumerate(ORDER)}
    rows.sort(key=lambda r: order.get(r.version, 99))
    pending = {v: 0 for v in ORDER}
    for ver, _st in db.execute(select(Job.engine_version, Job.status)
                               .where(Job.status.in_(['queued', 'running']))).all():
        pending[ver] = pending.get(ver, 0) + 1
    return [{'version': r.version, 'title': r.title, 'is_default': r.is_default,
             'retired': r.retired, 'in_flight': pending.get(r.version, 0),
             'method': ENGINES[r.version].METHOD,
             'description': ENGINES[r.version].DESCRIPTION} for r in rows]


def retire(db, version):
    ensure_versions(db)
    if version not in ENGINES:
        raise HTTPException(404, '计算版本不存在')
    row = db.scalar(select(AlgorithmVersion).where(AlgorithmVersion.version == version))
    if row.is_default:
        raise HTTPException(409, '默认版本不能退役，请先切换默认版本')
    open_jobs = db.scalar(select(Job.id).where(Job.engine_version == version,
                                               Job.status.in_(['queued', 'running'])).limit(1))
    if open_jobs:
        raise HTTPException(409, '该版本仍有在途任务（排队/计算中），任务结束前拒绝退役')
    row.retired = True
    return row
