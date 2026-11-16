"""引擎共享：参数与记录校验、分组统计。校验口径与历史实现保持一致。"""
import math
import numpy as np

CONFIDENCES = (.9, .95, .99)
SHIFTS = ('全部', '早班', '晚班')


def parse_params(params):
    try:
        confidence = float(params.get('confidence', .95))
    except (TypeError, ValueError):
        raise ValueError('置信度只接受 0.90/0.95/0.99')
    if confidence not in CONFIDENCES:
        raise ValueError('置信度只接受 0.90/0.95/0.99')
    shift = str(params.get('shift', '全部'))
    if shift not in SHIFTS:
        raise ValueError('未知班次')
    return confidence, shift


def group_records(records, shift):
    """按 A/B 分组（可叠加班次过滤），返回 group -> list[float] 与保留的原始记录。"""
    groups = {'A': [], 'B': []}
    kept = []
    seen = set()
    for r in records:
        try:
            arm, run = str(r['arm']), str(r['run'])
            seconds = float(r['seconds'])
            if arm not in groups or not math.isfinite(seconds) or seconds <= 0 or run in seen:
                raise ValueError()
            seen.add(run)
            if shift == '全部' or r['shift'] == shift:
                groups[arm].append(seconds)
                kept.append(r)
        except (KeyError, TypeError, ValueError):
            raise ValueError('片段号须唯一，组别为 A/B，节拍必须为正有限数')
    if min(map(len, groups.values())) < 3:
        raise ValueError('每组至少需要 3 个独立实验片段')
    return groups, kept


def welch(a, b, confidence):
    """Welch 统计量：返回 diff/se/df/p/[low,high]。a、b 为一维数值序列。"""
    from scipy import stats
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        raise ValueError('每组至少需要 3 个独立实验片段')
    ma, mb = float(a.mean()), float(b.mean())
    va, vb = float(a.var(ddof=1)), float(b.var(ddof=1))
    se2 = va / na + vb / nb
    if se2 <= 1e-15:
        raise ValueError('两组均无变异，Welch 检验无法估计误差')
    df = se2 * se2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    diff, se = ma - mb, math.sqrt(se2)
    statistic = diff / se
    p = float(2 * stats.t.sf(abs(statistic), df))
    margin = float(stats.t.ppf((1 + confidence) / 2, df)) * se
    return {'mean_a': ma, 'mean_b': mb, 'var_a': va, 'var_b': vb, 'n_a': na, 'n_b': nb,
            'diff': diff, 'se': se, 'df': df, 'statistic': statistic, 'p': p,
            'low': diff - margin, 'high': diff + margin}
