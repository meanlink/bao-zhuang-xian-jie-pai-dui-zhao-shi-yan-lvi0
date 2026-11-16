import time
from fastapi import HTTPException
from redis import Redis
from src.config.settings import REDIS_URL
from src.models import Dataset, Job
from src.services.business import metadata
from src.services.parameters import normalize_params
from src.services import engine_versions


def create(db, data, user):
    if not db.get(Dataset, data.dataset_id):
        raise HTTPException(404, '数据批次不存在')
    allowed = {p['key']: p for p in metadata().get('parameters', [])}
    if set(data.params) - set(allowed):
        raise HTTPException(422, '包含未知分析参数')
    try:
        params = normalize_params(data.params)
    except ValueError as e:
        raise HTTPException(422, str(e))
    # 接单瞬间固定版本：未指定则取当前默认；退役版本拒绝。排队/重启均沿用此值。
    version = engine_versions.resolve_for_order(db, data.engine_version)
    j = Job(name=data.name, dataset_id=data.dataset_id, params=params,
            engine_version=version, created_by=user.id,
            created_at=time.time(), status='queued')
    db.add(j)
    db.flush()
    return j


def enqueue(job_id):
    try:
        r = Redis.from_url(REDIS_URL)
        r.rpush('analysis:queue', job_id)
        r.close()
    except Exception:
        pass  # SQL queued status is the durable fallback
