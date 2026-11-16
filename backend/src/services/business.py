"""包装节拍对照实验：对外元数据与历史入口。

统计实现已迁移到 src.engines：
- v1_welch：原始 Welch（本模块 analyze 的默认行为，保持历史口径）
- v2_shift_adjusted：班别构成校正候选版（试发布用）
本模块保留 metadata/seed_records/analyze 三个历史入口，旧调用方无需改动。
"""
import random
from src.engines import catalog as engine_catalog
from src.engines.v1_welch import analyze as v1_analyze, METHOD as V1_METHOD


def metadata():
    return {"name": "包装线节拍对照实验", "short": "pack-welch", "tagline": "把工艺调整的节拍差，放进可复查的实验区间。", "client": "榆川包装 · 52 人食品外包装车间，工艺组比较两种封装动作", "workflow": "工艺员用秒表登记每段节拍，把两列平均值截图交给生产经理。", "pains": ["忽略两组方差差异", "只报改善秒数没有不确定区间", "班次混杂未单独观察"], "upstream": "随机分配试运行片段 YC_pack_trial.csv", "downstream": "工艺经理决定是否继续扩大试验",
            "entities": ["实验片段", "节拍比较", "工艺评审简报"], "dataset_name": "A 原动作 / B 改动作 · 160 段观测",
            "columns": [{"key": "run", "label": "片段", "type": "string"}, {"key": "arm", "label": "实验组", "type": "string"}, {"key": "shift", "label": "班次", "type": "string"}, {"key": "seconds", "label": "单件节拍/秒", "type": "number"}],
            "parameters": [{"key": "confidence", "label": "区间置信度", "type": "select", "default": "0.95", "options": [{"value": str(v), "label": f"{v*100:g}%"} for v in [.9, .95, .99]]}, {"key": "shift", "label": "实验班次", "type": "select", "default": "全部", "options": [{"value": n, "label": n} for n in ["全部", "早班", "晚班"]]}],
            "workbench_title": "节拍效果核验", "action_label": "执行 Welch 比较", "unit": "秒", "accent": "oklch(58% 0.16 69)", "style": "industrial",
            "engines": engine_catalog(),
            "seed_story": ["08:20 工艺员导入 YC_pack_trial.csv，A/B 各 80 段。", "08:30 核查片段按班次交错随机分配。", "08:40 分析员选择 95% 置信度和全部班次。", "08:45 执行 Welch 检验，查看 A−B 改善秒数。", "09:00 检查置信区间是否跨 0。", "09:20 改为晚班重算，查看异方差影响。", "09:45 导出工艺评审简报，交经理安排扩大试验。"],
            "method": V1_METHOD, "limitations": ["假定观测片段近似独立", "未校正多个班次的探索性比较", "显著节拍差不能证明成品质检合格"]}


def seed_records():
    rng = random.Random(1004)
    rows = []
    for arm, mu, sigma in [("A", 19.5, 1.4), ("B", 18.2, 2.1)]:
        for i in range(80):
            shift = "早班" if i % 2 == 0 else "晚班"
            rows.append({"run": f"YC-{arm}{i+1:03}", "arm": arm, "shift": shift, "seconds": round(max(1, rng.gauss(mu + (.8 if shift == "晚班" else 0), sigma)), 3)})
    return rows


def analyze(records, params):
    """历史入口：固定 v1 原始 Welch，行为与升级前完全一致。"""
    return v1_analyze(records, params)
