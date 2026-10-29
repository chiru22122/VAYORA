from backend.database import engine, Base
import backend.models
from sqlalchemy import inspect

insp = inspect(engine)
tables = insp.get_table_names()

print("Checking schema consistency...")
for t in sorted(tables):
    pg_cols = {c['name']: c for c in insp.get_columns(t)}
    model_table = Base.metadata.tables.get(t)
    if model_table is None:
        print(f"Table {t} in DB but NOT in Base.metadata!")
        continue
    model_cols = {c.name: c for c in model_table.columns}
    
    # Check columns in DB but not in Model
    for c_name, c_info in pg_cols.items():
        if c_name not in model_cols:
            print(f"MISMATCH in {t}: column '{c_name}' is in PostgreSQL (nullable={c_info['nullable']}, default={c_info.get('default')}) but NOT in SQLAlchemy model!")
        elif not c_info['nullable'] and c_info.get('default') is None and model_cols[c_name].nullable:
            print(f"NULLABLE MISMATCH in {t}.{c_name}: DB is NOT NULL without default, but model thinks nullable!")

print("Check finished.")
