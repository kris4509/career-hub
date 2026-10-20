"""Uploads a tiny test file, checks it is private, then deletes it."""
import requests

from app import create_app
from app.utils import storage

app = create_app()
with app.app_context():
    data = b"%PDF-1.4\n% storage test file\n"

    path, shown = storage.upload_resume(0, "test cv.pdf", data)
    print("Uploaded:", path, "| shown as:", shown)

    link = storage.signed_url(path, expires=60)
    got = requests.get(link, timeout=20)
    print("Signed link status:", got.status_code, "| content matches:", got.content == data)

    public = f"{app.config['SUPABASE_URL']}/storage/v1/object/public/{app.config['SUPABASE_BUCKET']}/{path}"
    print("Public link status (must NOT be 200):", requests.get(public, timeout=20).status_code)

    storage.delete_file(path)
    print("Deleted. Signed link now (must NOT be 200):", requests.get(link, timeout=20).status_code)

    # Bad files must be refused before anything is uploaded
    for name, content in [("virus.exe", b"MZ..."), ("fake.pdf", b"not really a pdf"), ("empty.pdf", b"")]:
        try:
            storage.upload_resume(0, name, content)
            print("PROBLEM: accepted", name)
        except ValueError as err:
            print("Refused", name, "->", err)