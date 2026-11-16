"""计算版本治理：引擎版本、试发布单与逐批次双算对照。"""
from sqlalchemy import String, JSON, Double, ForeignKey, Boolean, Text, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class AlgorithmVersion(Base):
    """引擎版本登记。默认版本唯一；退役版本不可再分配给新任务。"""
    __tablename__ = 'algorithm_versions'
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    retired: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[float] = mapped_column(Double)


class Release(Base):
    """计算版本试发布单：锁定历史批次、参数、基线改善量与区间容差。"""
    __tablename__ = 'releases'
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_version: Mapped[str] = mapped_column(String(20))
    baseline_version: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    # 锁定快照：数据集 id/指纹、参数、基线（改善量/区间）、容差、起始版本
    dataset_ids: Mapped[list] = mapped_column(JSON, default=list)
    dataset_checksums: Mapped[dict] = mapped_column(JSON, default=dict)
    locked_params: Mapped[list] = mapped_column(JSON, default=list)
    baseline_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    tolerance: Mapped[dict] = mapped_column(JSON, default=dict)
    # 竞争上线裁决依据：发布起始时的默认版本；过期时间戳
    start_default_version: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[float] = mapped_column(Double)
    published_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    rolled_back_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)


class ReleaseCheck(Base):
    """逐批次×参数的双算对照条目。重试复用同一条目，不新增对照。"""
    __tablename__ = 'release_checks'
    __table_args__ = (UniqueConstraint('release_id', 'dataset_id', 'params_fingerprint', name='uq_release_check'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey('releases.id'))
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    params_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default='')
    # 双算结果快照与差值（缺项/超差时也留痕，便于复核）
    baseline_result: Mapped[dict] = mapped_column(JSON, default=dict)
    candidate_result: Mapped[dict] = mapped_column(JSON, default=dict)
    comparison: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Double)
    updated_at: Mapped[float] = mapped_column(Double)
