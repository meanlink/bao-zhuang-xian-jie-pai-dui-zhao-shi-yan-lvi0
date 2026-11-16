"""分析参数规范化：工作台建任务与试发布锁参复用同一口径。"""
import json
from src.services.business import metadata

PARAM_GRID = [{'confidence': c, 'shift': s}
              for s in ('全部', '早班', '晚班')
              for c in (0.9, 0.95, 0.99)]


def normalize_params(raw):
    """按元数据选项校验参数并转成规范类型；非法参数抛 ValueError。"""
    allowed = {p['key']: p for p in metadata().get('parameters', [])}
    params = {k: p['default'] for k, p in allowed.items()}
    params.update(raw or {})
    for key, p in allowed.items():
        v = params[key]
        if p['type'] == 'number':
            try:
                v = float(v)
                if not (p.get('min', -1e9) <= v <= p.get('max', 1e9)):
                    raise ValueError()
                params[key] = v
            except (ValueError, TypeError):
                raise ValueError(f'{p["label"]} 超出范围或非数值')
        elif str(v) not in [str(o['value']) for o in p.get('options', [])]:
            raise ValueError(f'{p["label"]} 不是有效选项')
    return params


def fingerprint(params):
    return hashlib_sha(params)


def hashlib_sha(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
