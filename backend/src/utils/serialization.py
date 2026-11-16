import hashlib, json


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def dataset_dict(d):
    return {'id': d.id, 'name': d.name, 'source': d.source, 'rows': len(d.records), 'checksum': d.checksum, 'created_at': d.created_at}


def job_dict(j):
    return {k: getattr(j, k) for k in ['id', 'name', 'dataset_id', 'params', 'status', 'result',
                                       'error', 'approved', 'engine_version', 'created_at', 'finished_at']}


def report_dict(r):
    return {k: getattr(r, k) for k in ['id', 'name', 'job_id', 'destination', 'interval_seconds', 'next_run', 'enabled']}


def delivery_dict(d):
    return {k: getattr(d, k) for k in ['id', 'report_id', 'created_at', 'checksum', 'filename', 'destination']}


def release_check_dict(c):
    return {'id': c.id, 'release_id': c.release_id, 'dataset_id': c.dataset_id, 'params': c.params,
            'status': c.status, 'attempts': c.attempts, 'last_error': c.last_error,
            'comparison': c.comparison,
            'baseline_headline': (c.baseline_result or {}).get('headline'),
            'candidate_headline': (c.candidate_result or {}).get('headline'),
            'updated_at': c.updated_at}


def release_dict(r, checks=None):
    counts = {'pending': 0, 'passed': 0, 'failed': 0, 'total': 0}
    if checks is None:
        checks = []
    for c in checks:
        counts['total'] += 1
        counts[c.status] = counts.get(c.status, 0) + 1
    return {'id': r.id, 'name': r.name, 'candidate_version': r.candidate_version,
            'baseline_version': r.baseline_version, 'status': r.status,
            'dataset_ids': r.dataset_ids, 'dataset_checksums': r.dataset_checksums,
            'locked_params': r.locked_params, 'baseline_metrics': r.baseline_metrics,
            'tolerance': r.tolerance, 'start_default_version': r.start_default_version,
            'expires_at': r.expires_at, 'published_at': r.published_at,
            'rolled_back_at': r.rolled_back_at, 'failure_reason': r.failure_reason,
            'created_at': r.created_at, 'checks_count': counts,
            'checks': [release_check_dict(c) for c in checks]}
