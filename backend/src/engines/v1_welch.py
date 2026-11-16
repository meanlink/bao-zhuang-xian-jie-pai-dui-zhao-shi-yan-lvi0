"""v1：原始 Welch 比较（历史口径，保持不变）。

改善量=均值(A)−均值(B)；SE=√(sA²/nA+sB²/nB)；Welch–Satterthwaite 自由度；
双侧 t 检验和 t 分布置信区间；Cohen d 用合并标准差。
"""
import math
import numpy as np
from ._common import parse_params, group_records, welch

VERSION = 'v1'
TITLE = 'Welch 原始比较'
DESCRIPTION = '不校正班别构成的历史 Welch 检验，作为试发布对照基线保留。'
METHOD = '改善量=均值(A)−均值(B)；SE=√(sA²/nA+sB²/nB)；Welch–Satterthwaite 自由度；双侧 t 检验和 t 分布置信区间；Cohen d 用合并标准差。'


def analyze(records, params):
    confidence, shift = parse_params(params)
    groups, _ = group_records(records, shift)
    a, b = np.array(groups['A']), np.array(groups['B'])
    w = welch(a, b, confidence)
    diff, se, df, p = w['diff'], w['se'], w['df'], w['p']
    low, high = w['low'], w['high']
    na, nb, va, vb = w['n_a'], w['n_b'], w['var_a'], w['var_b']
    pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    effect = diff / pooled
    statistic = w['statistic']
    rows = [{'arm': k, 'n': len(groups[k]), 'mean': round(float(np.mean(groups[k])), 4),
             'sd': round(float(np.std(groups[k], ddof=1)), 4)} for k in ('A', 'B')]
    return {'engine_version': VERSION,
            'headline': {'diff': round(diff, 6), 'low': round(low, 6), 'high': round(high, 6),
                         'p': p, 'confidence': confidence, 'diff_label': '改善量 A−B'},
            'summary': f'B 相对 A 平均节拍缩短 {diff:.3f} 秒；{confidence*100:g}% 区间为 [{low:.3f}, {high:.3f}] 秒。',
            'metrics': [{'label': '改善量 A−B', 'value': round(diff, 5), 'unit': '秒'},
                        {'label': '双侧 p 值', 'value': float(f'{p:.6g}')},
                        {'label': 'Cohen d', 'value': round(effect, 5)},
                        {'label': 'Welch 自由度', 'value': round(df, 3)}],
            'table': {'columns': [{'key': 'arm', 'label': '实验组'}, {'key': 'n', 'label': '片段数'},
                                  {'key': 'mean', 'label': '均值/秒'}, {'key': 'sd', 'label': '样本标准差/秒'}],
                      'rows': rows},
            'chart': {'type': 'bar', 'labels': ['A 原动作', 'B 改动作'],
                      'series': [{'name': '平均单件节拍/秒', 'values': [round(w['mean_a'], 4), round(w['mean_b'], 4)]}]},
            'findings': [f'区间下界 {low:.4f} 秒，上界 {high:.4f} 秒；{"区间未跨 0" if low > 0 or high < 0 else "区间跨 0"}。',
                         f't={statistic:.4f}，自由度={df:.3f}；分析班次：{shift}。',
                         '仅在分组随机、片段独立的前提下支持实验推断；扩大试验仍须核查质检指标。'],
            'method': METHOD,
            'warnings': ['班次子组比较为探索性分析，未调整多重检验。']}
