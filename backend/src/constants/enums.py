from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
class ReleaseStatus(str, Enum):
    pending = 'pending'        # 待核验：尚有对照批次未算或未通过
    ready = 'ready'            # 可上线：全部对照通过，等待切换默认版本
    rejected = 'rejected'      # 拒绝上线：存在缺项或超差
    published = 'published'    # 已上线：候选版已成为默认版本
    rolled_back = 'rolled_back'  # 已回滚：默认版本切回基线，仅影响新单
class CheckStatus(str, Enum):
    pending = 'pending'        # 未算批次，中断后从这里恢复
    passed = 'passed'          # 双算对照通过
    failed = 'failed'          # 缺项或超差，条目保留可重试
