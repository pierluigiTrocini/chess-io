import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="chessme-test-")  # cartella temporanea, come nella CLI
os.environ["CHESSME_HOME"] = tempfile.mkdtemp(prefix="chessme-home-")  # mai i dati utente veri
os.environ.setdefault("ANALYSIS_DEPTH", "12")
os.environ.setdefault("THREAT_DEPTH", "8")
os.environ.setdefault("ANALYSIS_THREADS", "2")
