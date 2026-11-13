import os
import tempfile

# keep test traces out of ~/junction-data; must run before server.config is imported
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="junction-test-"))
os.environ.setdefault("SERVER_ENGINE", "fake")
