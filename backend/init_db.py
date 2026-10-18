from app import create_app
from app.extensions import db
from app import models  # noqa: F401  (importing registers the tables)

app = create_app()

with app.app_context():
    db.create_all()
    print("Tables created:")
    for name in sorted(db.metadata.tables):
        print(" -", name)