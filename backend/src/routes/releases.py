from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Release, ReleaseCheck
from src.schemas.release import ReleaseInput, RetireVersionInput
from src.middlewares.auth import current_user, admin_only
from src.services import releases, engine_versions
from src.services.audit import record
from src.utils.serialization import release_dict, release_check_dict

router = APIRouter(prefix='/releases')


@router.get('/versions')
def versions(db=Depends(get_db), u=Depends(current_user)):
    return engine_versions.list_versions(db)


@router.post('/versions/retire')
def retire(data: RetireVersionInput, db=Depends(get_db), u=Depends(admin_only)):
    row = engine_versions.retire(db, data.version)
    record(db, u.email, 'engine.retire', {'version': row.version})
    db.commit()
    return {'version': row.version, 'retired': row.retired}


@router.get('')
def listing(db=Depends(get_db), u=Depends(current_user)):
    rows = list(db.scalars(select(Release).order_by(Release.id.desc())))
    checks = list(db.scalars(select(ReleaseCheck).order_by(ReleaseCheck.id)))
    grouped = {}
    for c in checks:
        grouped.setdefault(c.release_id, []).append(c)
    return [release_dict(r, grouped.get(r.id, [])) for r in rows]


@router.post('', status_code=201)
def create(data: ReleaseInput, db=Depends(get_db), u=Depends(admin_only)):
    r = releases.create_release(db, data, u)
    record(db, u.email, 'release.create', {'id': r.id, 'candidate': r.candidate_version,
                                           'datasets': r.dataset_ids, 'params': len(r.locked_params)})
    db.commit()
    return _detail(db, r.id)


@router.get('/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    return _detail(db, id)


def _detail(db, release_id):
    r = db.get(Release, release_id)
    if not r:
        raise HTTPException(404, '试发布单不存在')
    checks = list(db.scalars(select(ReleaseCheck).where(ReleaseCheck.release_id == release_id)
                             .order_by(ReleaseCheck.id)))
    return release_dict(r, checks)


@router.post('/{id}/verify')
def verify(id: int, db=Depends(get_db), u=Depends(admin_only)):
    r = db.get(Release, id)
    if not r:
        raise HTTPException(404, '试发布单不存在')
    if r.status in ('published', 'rolled_back'):
        raise HTTPException(409, '试发布已终结，不能再核验')
    done = releases.run_pending(db, limit=50)
    record(db, u.email, 'release.verify', {'id': id, 'ran': len(done)})
    db.commit()
    return _detail(db, id)


@router.post('/{id}/publish')
def publish(id: int, db=Depends(get_db), u=Depends(admin_only)):
    r = releases.publish(db, id, u)
    record(db, u.email, 'release.publish', {'id': id, 'default': r.candidate_version})
    db.commit()
    return _detail(db, id)


@router.post('/{id}/rollback')
def rollback(id: int, db=Depends(get_db), u=Depends(admin_only)):
    r = releases.rollback(db, id, u)
    record(db, u.email, 'release.rollback', {'id': id, 'default': r.baseline_version})
    db.commit()
    return _detail(db, id)


@router.get('/{id}/checks/{check_id}')
def check_detail(id: int, check_id: int, db=Depends(get_db), u=Depends(current_user)):
    c = db.get(ReleaseCheck, check_id)
    if not c or c.release_id != id:
        raise HTTPException(404, '对照条目不存在')
    return release_check_dict(c)
