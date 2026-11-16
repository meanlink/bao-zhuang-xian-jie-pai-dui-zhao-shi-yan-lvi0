"""建表与增量列迁移。

项目以 create_all 管理表结构；对既有表的新增列采用显式 ADD COLUMN，
保证旧环境升级不丢数据（本批为 jobs.engine_version）。
"""
from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models

# 既有表上的增量列：表名 -> [(列名, 列 DDL 片段)]
_ADDED_COLUMNS = {
    'jobs': [('engine_version', "VARCHAR(20) NOT NULL DEFAULT 'v1'")],
}


def migrate():
    Base.metadata.create_all(engine)


def ensure_schema():
    migrate()
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {c['name'] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in present:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
    # 幂等登记引擎版本目录
    from src.config.database import Session
    from src.services.engine_versions import ensure_versions
    with Session() as db:
        ensure_versions(db)
        db.commit()


if __name__ == '__main__':
    ensure_schema()
