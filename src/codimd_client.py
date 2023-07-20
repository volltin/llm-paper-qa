import requests
import re
import os
import dotenv

dotenv.load_dotenv()

CODIMD_HOST = os.getenv("CODIMD_HOST")
CODIMD_EMAIL = os.getenv("CODIMD_EMAIL")
CODIMD_PASSWORD = os.getenv("CODIMD_PASSWORD")


class CodimdClient:
    def __init__(self, host, user, password):
        self.host = host
        self.session = self.login(user, password)

    def login(self, user, password):
        """
        login and return session
        """
        session = requests.Session()
        r = session.post(
            self.host + "/login", data={"email": user, "password": password}
        )
        r.raise_for_status()
        return session

    def create_new(self, markdown_content, note_id=None):
        """
        create new and return note id
        """
        header = {"Content-Type": "text/markdown"}
        if note_id is not None:
            endpoint = f"/new/{note_id}"
        else:
            endpoint = "/new"

        r = self.session.post(
            self.host + endpoint,
            headers=header,
            data=markdown_content.encode("utf-8"),
            allow_redirects=False,
        )
        assert r.status_code == 302, r.text
        # Found. Redirecting to /note_id
        note_id = re.search(r"Found. Redirecting to /(.*)", r.text).group(1).strip()
        assert note_id is not None
        return note_id

    def publish_note(self, note_id):
        """
        publish note and return publish url
        """
        r = self.session.get(self.host + f"/{note_id}/publish", allow_redirects=False)
        assert r.status_code == 302
        # Found. Redirecting to /publish_note_id
        publish_url = re.search(r"Found. Redirecting to (.*)", r.text).group(1).strip()
        return publish_url

    def create_and_publish(self, markdown_content):
        """
        create new and publish and return publish url
        """
        note_id = self.create_new(markdown_content)
        publish_url = self.publish_note(note_id)
        return self.host + publish_url

    def history(self):
        """
        get history
        return example:
        {'history': [{'id': 'aaaaaaaaaaaaaaaaaaaaaaaa',
              'tags': [],
              'text': 'Untitled',
              'time': 1681395894713},
              {'id': 'bbbbbbbbbbbbbbbbbbbbbbbb',
              'tags': [],
              'text': 'Untitled',
              'time': 1681397337712}]}
        """
        r = self.session.get(self.host + "/history")
        r.raise_for_status()
        return r.json()


def get_codimd_client():
    if CODIMD_HOST:
        return CodimdClient(CODIMD_HOST, CODIMD_EMAIL, CODIMD_PASSWORD)
    else:
        return None
