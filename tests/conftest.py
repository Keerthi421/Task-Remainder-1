import os
import tempfile

# Must run before any `app` import: point the app at a throwaway DB and disable real email.
_tmp = tempfile.mkdtemp(prefix="task-reminder-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["BREVO_API_KEY"] = ""
os.environ["SENDER_EMAIL"] = ""
os.environ["SECRET_KEY"] = "test-secret"
