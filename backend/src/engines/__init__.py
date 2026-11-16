"""计算引擎注册与分发。

每个版本一个无状态引擎模块，统一暴露：
- VERSION：版本号
- title/description/method：版本元数据与计算依据（随结果、简报留痕）
- analyze(records, params)：与历史 analyze 同构的结果字典
"""
from . import v1_welch, v2_shift_adjusted

ENGINES = {m.VERSION: m for m in (v1_welch, v2_shift_adjusted)}
ORDER = [v1_welch.VERSION, v2_shift_adjusted.VERSION]
DEFAULT_VERSION = v1_welch.VERSION


def get_engine(version):
    engine = ENGINES.get(version)
    if engine is None:
        raise ValueError(f'未知计算版本：{version}')
    return engine


def analyze(version, records, params):
    return get_engine(version).analyze(records, params)


def version_meta(version):
    m = get_engine(version)
    return {'version': m.VERSION, 'title': m.TITLE, 'description': m.DESCRIPTION, 'method': m.METHOD}


def catalog():
    return [version_meta(v) for v in ORDER]
