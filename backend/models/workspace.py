"""
Workspace Database Models — Peewee ORM for user accounts, watchlist, notes, and report history.
"""

import datetime
from pathlib import Path
from peewee import (
    Model,
    SqliteDatabase,
    CharField,
    IntegerField,
    DateTimeField,
    TextField,
    ForeignKeyField,
    BooleanField,
)

workspace_db = SqliteDatabase(None)

class BaseModel(Model):
    class Meta:
        database = workspace_db

class User(BaseModel):
    username = CharField(unique=True, index=True)
    hashed_password = CharField()
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.utcnow)

class WatchlistEntry(BaseModel):
    user = ForeignKeyField(User, backref='watchlist', on_delete='CASCADE')
    ticker = CharField(index=True)
    company_name = CharField(null=True)
    added_at = DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        indexes = (
            (('user', 'ticker'), True), # Unique constraint
        )

class AnalystNote(BaseModel):
    user = ForeignKeyField(User, backref='notes', on_delete='CASCADE')
    ticker = CharField(index=True)
    content = TextField()
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)

class ReportVersion(BaseModel):
    report_id = CharField(unique=True, primary_key=True)
    user = ForeignKeyField(User, backref='reports', on_delete='CASCADE', null=True)
    ticker = CharField(index=True)
    company = CharField()
    model = CharField()
    version = IntegerField(default=1)
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    report_json = TextField() # The full 12-section report + charts JSON
    pdf_path = CharField(null=True) # Optional cached PDF

_DB_INITIALIZED = False

def initialize_workspace_db(db_path: str = None):
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return

    if db_path is None:
        db_path = str(Path(__file__).resolve().parent.parent / "data" / "workspace.db")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    workspace_db.init(db_path)
    workspace_db.connect(reuse_if_open=True)
    workspace_db.create_tables([User, WatchlistEntry, AnalystNote, ReportVersion], safe=True)
    _DB_INITIALIZED = True

def close_workspace_db():
    global _DB_INITIALIZED
    if not workspace_db.is_closed():
        workspace_db.close()
    _DB_INITIALIZED = False
