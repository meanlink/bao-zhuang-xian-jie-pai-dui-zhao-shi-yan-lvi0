"""计算版本试发布与双算对照。

关键规则：
- 试发布锁定历史批次（id + 指纹）、参数组合、基线改善量与区间容差；
- 每个批次×参数一条 ReleaseCheck，双算（基线版/候选版）对照，幂等可恢复；
- 缺项（基线或候选无法计算）或超差即拒绝上线；全部通过才可切换默认版本；
- 竞争上线按起始默认版本裁决；校验过期拒绝发布；
- 回滚只影响新单；旧版本有在途任务时拒绝退役。
"""
import time
from fastapi import HTTPException
from sqlalchemy import select
from src.engines import ENGINES, analyze as engine_analyze
from src.models import AlgorithmVersion, Release, ReleaseCheck, Dataset
from src.services import engine_versions
from src.services.parameters import normalize_params, PARAM_GRID, hashlib_sha

# 默认区间容差（秒）与相对容差。创建试发布时可覆盖。
DEFAULT_TOLERANCE = {'diff_abs': 0.6, 'bound_abs': 0.9, 'diff_rel': 0.25, 'p_abs': 0.02}
TERMINAL_RELEASE = ('published', 'rolled_back', 'rejected')


def _lock_version_row(db, release_id):
    """行锁读取试发布单，保证并发发布/回滚串行裁决。"""
    return db.scalar(select(Release).where(Release.id == release_id).with_for_update())


def create_release(db, data, user):
    engine_versions.ensure_versions(db)
    candidate = data.candidate_version
    if candidate not in ENGINES:
        raise HTTPException(422, f'候选计算版本不存在：{candidate}')
    cand_row = db.scalar(select(AlgorithmVersion).where(AlgorithmVersion.version == candidate))
    if cand_row and cand_row.retired:
        raise HTTPException(409, '候选版本已退役，不能试发布')
    baseline = engine_versions.get_default(db)
    if candidate == baseline:
        raise HTTPException(409, '候选版本已是当前默认版本，无需试发布')
    # 同一候选只能有一个在途试发布
    busy = db.scalar(select(Release.id).where(Release.candidate_version == candidate,
                                              Release.status.in_(('pending', 'ready'))).limit(1))
    if busy:
        raise HTTPException(409, '该候选版本已有进行中的试发布单')

    datasets = list(db.scalars(select(Dataset).where(Dataset.id.in_(data.dataset_ids)).order_by(Dataset.id)))
    found = {d.id: d for d in datasets}
    missing = [i for i in data.dataset_ids if i not in found]
    if missing:
        raise HTTPException(404, f'历史批次不存在：{missing}')
    if not datasets:
        raise HTTPException(422, '试发布至少锁定一个历史批次')

    param_list = data.params_list or PARAM_GRID
    if not isinstance(param_list, list) or not param_list:
        raise HTTPException(422, '至少锁定一组分析参数')
    locked_params, seen_fp = [], set()
    for raw in param_list:
        try:
            params = normalize_params(raw)
        except ValueError as e:
            raise HTTPException(422, str(e))
        fp = hashlib_sha(params)
        if fp in seen_fp:
            continue
        seen_fp.add(fp)
        locked_params.append(params)

    tolerance = dict(DEFAULT_TOLERANCE)
    if data.tolerance:
        for k in DEFAULT_TOLERANCE:
            if k in data.tolerance:
                v = data.tolerance[k]
                if not isinstance(v, (int, float)) or v < 0:
                    raise HTTPException(422, f'容差 {k} 必须为非负数')
                tolerance[k] = float(v)

    now = time.time()
    checksums = {str(d.id): d.checksum for d in datasets}
    release = Release(name=data.name, candidate_version=candidate, baseline_version=baseline,
                      status='pending', dataset_ids=[d.id for d in datasets],
                      dataset_checksums=checksums, locked_params=locked_params,
                      baseline_metrics={}, tolerance=tolerance,
                      start_default_version=baseline,
                      expires_at=now + max(1, min(data.validity_hours, 720)) * 3600,
                      created_by=user.id, created_at=now)
    db.add(release)
    db.flush()

    # 锁定基线快照（改善量/区间），并预建全部对照条目（pending = 未算批次）
    baseline_metrics = {}
    for d in datasets:
        for params in locked_params:
            fp = hashlib_sha(params)
            check = ReleaseCheck(release_id=release.id, dataset_id=d.id, params=params,
                                 params_fingerprint=fp, status='pending', attempts=0,
                                 created_at=now, updated_at=now)
            db.add(check)
            try:
                base = engine_analyze(baseline, d.records, params)
                baseline_metrics[f'{d.id}:{fp}'] = base['headline']
            except Exception as e:  # 基线缺项：记录但不阻断建档，核验时判失败
                baseline_metrics[f'{d.id}:{fp}'] = {'error': str(e)[:300]}
    release.baseline_metrics = baseline_metrics
    db.flush()
    return release


def _compare(head_base, head_cand, tolerance):
    """返回 (是否通过, 比较明细, 失败原因列表)。缺项或超差即不通过。"""
    reasons = []
    if not head_base or 'error' in head_base:
        reasons.append('基线版缺项：' + str((head_base or {}).get('error', '无结果')))
    if not head_cand or 'error' in head_cand:
        reasons.append('候选版缺项：' + str((head_cand or {}).get('error', '无结果')))
    if reasons:
        return False, {'reasons': reasons}, reasons
    detail = {
        'baseline_diff': head_base['diff'], 'candidate_diff': head_cand['diff'],
        'diff_delta': head_cand['diff'] - head_base['diff'],
        'baseline_low': head_base['low'], 'candidate_low': head_cand['low'],
        'baseline_high': head_base['high'], 'candidate_high': head_cand['high'],
        'low_delta': head_cand['low'] - head_base['low'],
        'high_delta': head_cand['high'] - head_base['high'],
        'baseline_p': head_base.get('p'), 'candidate_p': head_cand.get('p'),
    }
    if abs(head_base.get('p', 0) - head_cand.get('p', 0)) > tolerance['p_abs']:
        reasons.append(f"p 值变化 {abs(head_base.get('p', 0) - head_cand.get('p', 0)):.4g} 超过容差 {tolerance['p_abs']}")
    if abs(detail['diff_delta']) > tolerance['diff_abs']:
        reasons.append(f"改善量差 {abs(detail['diff_delta']):.4g} 秒超过绝对容差 {tolerance['diff_abs']}")
    base_abs = abs(head_base['diff'])
    if base_abs > 1e-12 and abs(detail['diff_delta']) / base_abs > tolerance['diff_rel']:
        reasons.append(f"改善量相对偏差 {abs(detail['diff_delta']) / base_abs:.3%} 超过相对容差 {tolerance['diff_rel']:.0%}")
    for edge in ('low', 'high'):
        if abs(detail[f'{edge}_delta']) > tolerance['bound_abs']:
            reasons.append(f"区间{edge}界移动 {abs(detail[f'{edge}_delta']):.4g} 秒超过容差 {tolerance['bound_abs']}")
    detail['reasons'] = reasons
    return (not reasons), detail, reasons


def run_check(db, check_id):
    """执行单条双算对照。重试复用同一条目（attempts 累加，不新增对照）。"""
    check = db.get(ReleaseCheck, check_id)
    if not check:
        return None
    release = _lock_version_row(db, check.release_id)
    if release.status in TERMINAL_RELEASE:
        return check
    dataset = db.get(Dataset, check.dataset_id)
    check.attempts += 1
    check.updated_at = time.time()
    now = time.time()
    if now > release.expires_at:
        check.status = 'failed'
        check.last_error = '试发布核验窗口已过期'
        _refresh_status(db, release)
        return check
    if not dataset:
        check.status = 'failed'
        check.last_error = f"历史批次 {check.dataset_id} 缺失"
        _refresh_status(db, release)
        return check
    if release.dataset_checksums.get(str(dataset.id)) != dataset.checksum:
        check.status = 'failed'
        check.last_error = '历史批次指纹与试发布锁定值不一致，批次已被变更'
        _refresh_status(db, release)
        return check
    try:
        base = engine_analyze(release.baseline_version, dataset.records, check.params)
        head_base = base['headline']
    except Exception as e:
        base, head_base = None, {'error': str(e)[:300]}
    try:
        cand = engine_analyze(release.candidate_version, dataset.records, check.params)
        head_cand = cand['headline']
    except Exception as e:
        cand, head_cand = None, {'error': str(e)[:300]}
    check.baseline_result = base or {'error': head_base['error']}
    check.candidate_result = cand or {'error': head_cand['error']}
    ok, detail, reasons = _compare(head_base, head_cand, release.tolerance)
    check.comparison = detail
    if ok:
        check.status = 'passed'
        check.last_error = ''
    else:
        check.status = 'failed'
        check.last_error = '；'.join(reasons)[:900]
    _refresh_status(db, release)
    return check


def _refresh_status(db, release):
    """按对照条目汇总试发布状态；存在失败即拒绝上线。"""
    if release.status in TERMINAL_RELEASE:
        return release.status
    checks = list(db.scalars(select(ReleaseCheck).where(ReleaseCheck.release_id == release.id)))
    failed = [c for c in checks if c.status == 'failed']
    if failed:
        release.status = 'rejected'
        release.failure_reason = f'{len(failed)} 条对照缺项或超差，拒绝上线'
    elif all(c.status == 'passed' for c in checks) and checks:
        release.status = 'ready'
        release.failure_reason = ''
    else:
        release.status = 'pending'
    return release.status


def run_pending(db, limit=5):
    """供 worker 兜底：执行最早的未算/失败对照，中断后从未算批次恢复。"""
    ids = list(db.scalars(select(ReleaseCheck.id)
                          .join(Release, Release.id == ReleaseCheck.release_id)
                          .where(ReleaseCheck.status.in_(('pending', 'failed')),
                                 Release.status.in_(('pending', 'ready')))
                          .order_by(ReleaseCheck.id).limit(limit)))
    done = []
    for cid in ids:
        done.append(run_check(db, cid))
    if done:
        db.commit()
    return done


def publish(db, release_id, user):
    release = _lock_version_row(db, release_id)
    if not release:
        raise HTTPException(404, '试发布单不存在')
    if release.status == 'published':
        raise HTTPException(409, '该版本已上线')
    if release.status in ('rolled_back', 'rejected'):
        raise HTTPException(409, f'试发布单状态为 {release.status}，不能上线')
    if time.time() > release.expires_at:
        raise HTTPException(409, '核验窗口已过期，拒绝发布；请重新建立试发布')
    # 竞争上线裁决：起始默认版本必须仍是当前默认版本
    current_default = engine_versions.get_default(db)
    if current_default != release.start_default_version:
        raise HTTPException(409, f'起始版本 {release.start_default_version} 已不再是默认版本（当前 {current_default}），按起始版本裁决拒绝上线')
    checks = list(db.scalars(select(ReleaseCheck).where(ReleaseCheck.release_id == release.id)))
    if not checks or any(c.status != 'passed' for c in checks):
        raise HTTPException(409, '仍有对照未通过（缺项或超差），全部通过才允许切换默认版本')
    candidate = db.scalar(select(AlgorithmVersion).where(AlgorithmVersion.version == release.candidate_version))
    if not candidate or candidate.retired:
        raise HTTPException(409, '候选版本已退役或未登记，拒绝上线')
    for row in db.scalars(select(AlgorithmVersion).where(AlgorithmVersion.is_default == True)):
        row.is_default = False
    candidate.is_default = True
    candidate.retired = False
    release.status = 'published'
    release.published_at = time.time()
    release.failure_reason = ''
    db.flush()
    return release


def rollback(db, release_id, user):
    release = _lock_version_row(db, release_id)
    if not release:
        raise HTTPException(404, '试发布单不存在')
    if release.status != 'published':
        raise HTTPException(409, '仅已上线的试发布可以回滚')
    baseline = db.scalar(select(AlgorithmVersion).where(AlgorithmVersion.version == release.baseline_version))
    if not baseline:
        raise HTTPException(409, '基线版本已不存在，无法回滚')
    for row in db.scalars(select(AlgorithmVersion).where(AlgorithmVersion.is_default == True)):
        row.is_default = False
    baseline.is_default = True
    baseline.retired = False
    release.status = 'rolled_back'
    release.rolled_back_at = time.time()
    # 注意：不触碰既有 Job.engine_version —— 回滚只影响新单
    db.flush()
    return release
