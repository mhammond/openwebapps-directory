"""Makes updates to the database as necessary
"""
from sqlalchemy import Table, MetaData


meta = MetaData()


def update_database(engine):
    def columns(table):
        t = Table(table, meta, autoload=True)
        return [c.name for c in t.columns]
    meta.bind = engine
    try:
        if 'hide' not in columns('application'):
            engine.execute('''
            ALTER TABLE application ADD COLUMN hide BOOLEAN DEFAULT FALSE
            ''')
        if 'hidden' in columns('keyword'):
            engine.execute('''
            ALTER TABLE keyword ADD COLUMN hide BOOLEAN DEFAULT FALSE
            ''')
            engine.execute('''
            UPDATE keyword SET hide = hidden
            ''')
            ## FIXME: sqlite can't do this:
            engine.execute('''
            ALTER TABLE keyword DROP COLUMN hidden
            ''')
    finally:
        meta.bind = None
