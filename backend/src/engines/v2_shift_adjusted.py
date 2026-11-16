"""v2 候选：按全样本班别构成校正均值差。

校正方式为直接标准化（direct standardization）：
- 以全样本中各班次的观测占比作为固定标准构成 w_s（A、B 合并计数）；
- 校正均值 mX* = Σ_s w_s · mean(X_s)，X ∈ {A,B}；
- 校正改善量 diff* = mA* − mB*；
- 各班次独立，校正均值方差 var(mX*) = Σ_s w_s² · sX_s²/nX_s，
  SE* = √(var(mA*) + var(mB*))，自由度用 Welch–Satterthwaite 分解到班次项；
- 双侧 t 检验与 t 分布置信区间口径与 v1 一致；Cohen d 仍用全样本合并标准差，保证两版可比。

单班次参数下没有构成差异，结果退化为该子样本上的 Welch（与 v1 同值），但仍标记为 v2。
"""
import math
import numpy as np
from scipy import stats
from ._common import parse_params, group_records, welch
from .v1_welch import METHOD as V1_METHOD

VERSION = 'v2'
TITLE = '班别构成校正均值差'
DESCRIPTION = '候选算法：以全样本班别占比做直接标准化，消除早晚班混杂后的 A−B 改善量与区间。'
METHOD = ('按全样本班别构成直接标准化：w_s 为各班次全样本占比，校正均值=Σ w_s·组内班次均值，'
          '校正改善量=校正均值(A)−校正均值(B)；SE=√(Σ w_s²·sA_s²/nA_s + Σ w_s²·sB_s²/nB_s)，'
          'Welch–Satterthwaite 自由度按班次方差项分解；双侧 t 检验与 t 区间；Cohen d 用全样本合并标准差。')


def _standardize(records, confidence):
    cells = {}
    for r in records:
        s = str(r['shift'])
        cells.setdefault(s, {'A': [], 'B': []})[str(r['arm'])].append(float(r['seconds']))
    common = [s for s in cells if len(cells[s]['A']) >= 2 and len(cells[s]['B']) >= 2]
    skipped = [s for s in cells if s not in common]
    if not common:
        raise ValueError('没有同时包含 A/B 且可估计方差的班次，无法做班别构成校正')
    total = sum(len(cells[s]['A']) + len(cells[s]['B']) for s in common)
    weights, comp_a, comp_b = {}, [], []
    var_a = var_b = 0.0
    denom = 0.0
    rows = []
    for s in common:
        a, b = np.array(cells[s]['A']), np.array(cells[s]['B'])
        na, nb = len(a), len(b)
        w = (na + nb) / total
        weights[s] = w
        ma, mb = float(a.mean()), float(b.mean())
        va, vb = float(a.var(ddof=1)), float(b.var(ddof=1))
        comp_a.append(w * ma)
        comp_b.append(w * mb)
        ca, cb = w * w * va / na, w * w * vb / nb
        var_a += ca
        var_b += cb
        denom += ca * ca / (na - 1) + cb * cb / (nb - 1)
        rows.append({'shift': s, 'weight': round(w, 5), 'n_a': na, 'n_b': nb,
                     'mean_a': round(ma, 4), 'mean_b': round(mb, 4),
                     'diff': round(ma - mb, 5)})
    se2 = var_a + var_b
    if se2 <= 1e-15:
        raise ValueError('校正后均值无变异，班别构成校正无法估计误差')
    df = se2 * se2 / denom
    se = math.sqrt(se2)
    mean_a, mean_b = sum(comp_a), sum(comp_b)
    diff = mean_a - mean_b
    statistic = diff / se
    p = float(2 * stats.t.sf(abs(statistic), df))
    margin = float(stats.t.ppf((1 + confidence) / 2, df)) * se
    return {'diff': diff, 'se': se, 'df': df, 'statistic': statistic, 'p': p,
            'low': diff - margin, 'high': diff + margin,
            'mean_a': mean_a, 'mean_b': mean_b,
            'weights': weights, 'rows': rows, 'skipped': skipped,
            'var_a': var_a, 'var_b': var_b}


def analyze(records, params):
    confidence, shift = parse_params(params)
    groups, kept = group_records(records, shift)
    a_all, b_all = np.array(groups['A']), np.array(groups['B'])
    raw = welch(a_all, b_all, confidence)
    pooled = math.sqrt(((raw['n_a'] - 1) * raw['var_a'] + (raw['n_b'] - 1) * raw['var_b'])
                       / (raw['n_a'] + raw['n_b'] - 2))
    warnings = ['班别构成校正为直接标准化估计，假定各班次内观测近似独立。']
    if shift == '全部':
        z = _standardize(kept, confidence)
        diff, low, high, df, p, statistic, se = z['diff'], z['low'], z['high'], z['df'], z['p'], z['statistic'], z['se']
        adj_a, adj_b = z['mean_a'], z['mean_b']
        weight_text = '、'.join(f'{s} 占比 {z["weights"][s] * 100:.1f}%' for s in z['weights'])
        if z['skipped']:
            warnings.append('班次 ' + '、'.join(z['skipped']) + ' 缺少 A/B 双侧或样本不足，未纳入标准化构成。')
        adjustment = {'columns': [{'key': 'shift', 'label': '班次'}, {'key': 'weight', 'label': '全样本构成权重'},
                                  {'key': 'n_a', 'label': 'A 片段数'}, {'key': 'n_b', 'label': 'B 片段数'},
                                  {'key': 'mean_a', 'label': 'A 班次均值/秒'}, {'key': 'mean_b', 'label': 'B 班次均值/秒'},
                                  {'key': 'diff', 'label': '班次内 A−B/秒'}],
                      'rows': z['rows'], 'weights': z['weights']}
        findings = [f'按全样本班别构成（{weight_text}）标准化后，区间下界 {low:.4f} 秒，上界 {high:.4f} 秒；'
                    f'{"区间未跨 0" if low > 0 or high < 0 else "区间跨 0"}。',
                    f'校正改善量 {diff:.4f} 秒，原始未校正改善量 {raw["diff"]:.4f} 秒，混杂修正 {diff - raw["diff"]:+.4f} 秒。',
                    f't={statistic:.4f}，校正自由度={df:.3f}；分析班次：{shift}。',
                    '仅在分组随机、片段独立的前提下支持实验推断；扩大试验仍须核查质检指标。']
    else:
        diff, low, high, df, p, statistic, se = (raw['diff'], raw['low'], raw['high'], raw['df'],
                                                  raw['p'], raw['statistic'], raw['se'])
        adj_a, adj_b = raw['mean_a'], raw['mean_b']
        adjustment = None
        warnings.append(f'仅选择 {shift} 时无构成差异，校正退化为该子样本 Welch，数值与原始口径一致。')
        findings = [f'区间下界 {low:.4f} 秒，上界 {high:.4f} 秒；{"区间未跨 0" if low > 0 or high < 0 else "区间跨 0"}。',
                    f't={statistic:.4f}，自由度={df:.3f}；分析班次：{shift}（单班次，标准化退化）。',
                    '仅在分组随机、片段独立的前提下支持实验推断；扩大试验仍须核查质检指标。']
    effect = diff / pooled
    rows = [{'arm': k, 'n': len(groups[k]), 'mean': round(float(np.mean(groups[k])), 4),
             'sd': round(float(np.std(groups[k], ddof=1)), 4)} for k in ('A', 'B')]
    return {'engine_version': VERSION,
            'headline': {'diff': round(diff, 6), 'low': round(low, 6), 'high': round(high, 6),
                         'p': p, 'confidence': confidence, 'diff_label': '校正改善量 A−B',
                         'raw_diff': round(raw['diff'], 6)},
            'summary': (f'班别构成校正后 B 相对 A 平均节拍缩短 {diff:.3f} 秒；{confidence * 100:g}% 区间为 '
                        f'[{low:.3f}, {high:.3f}] 秒（未校正 {raw["diff"]:.3f} 秒）。'),
            'metrics': [{'label': '校正改善量 A−B', 'value': round(diff, 5), 'unit': '秒'},
                        {'label': '原始改善量 A−B', 'value': round(raw['diff'], 5), 'unit': '秒'},
                        {'label': '双侧 p 值', 'value': float(f'{p:.6g}')},
                        {'label': 'Cohen d', 'value': round(effect, 5)},
                        {'label': 'Welch 自由度', 'value': round(df, 3)}],
            'table': {'columns': [{'key': 'arm', 'label': '实验组'}, {'key': 'n', 'label': '片段数'},
                                  {'key': 'mean', 'label': '均值/秒'}, {'key': 'sd', 'label': '样本标准差/秒'}],
                      'rows': rows},
            'adjustment': adjustment,
            'chart': {'type': 'bar', 'labels': ['A 原动作', 'B 改动作'],
                      'series': [{'name': '原始平均节拍/秒', 'values': [round(raw['mean_a'], 4), round(raw['mean_b'], 4)]},
                                 {'name': '班别校正均值/秒', 'values': [round(adj_a, 4), round(adj_b, 4)]}]},
            'findings': findings,
            'method': METHOD,
            'warnings': warnings,
            'baseline_method': V1_METHOD}
