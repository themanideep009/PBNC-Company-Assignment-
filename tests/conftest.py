"""
Test configuration and fixtures.

Provides:
- Test database (separate from production)
- Test client with httpx
- Pre-created user + JWT for authenticated requests
- Sample file fixtures
"""

import os
import uuid
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment before importing app
db_user = os.environ.get("POSTGRES_USER", "pragati")
db_pass = os.environ.get("POSTGRES_PASSWORD", "change_me_in_production")
db_host = os.environ.get("POSTGRES_HOST", "postgres" if os.path.exists("/.dockerenv") else "localhost")
db_port = os.environ.get("POSTGRES_PORT", "5432")
db_name = os.environ.get("POSTGRES_TEST_DB", "pragati_bharati_test")

default_test_db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", default_test_db_url)

redis_host = "redis" if os.path.exists("/.dockerenv") else "localhost"
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", f"redis://{redis_host}:6379/1")
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["STORAGE_BASE_PATH"] = os.environ.get("TEST_STORAGE_PATH", "/tmp/pragati_test_storage")
os.environ["VIRUS_SCAN_ENABLED"] = "false"

from app.core.config import get_settings, Settings
from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.main import app
from app.models.user import User


# Clear cached settings for tests
get_settings.cache_clear()
settings = get_settings()

# Test database engine
test_engine = create_engine(settings.DATABASE_URL, echo=False)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def mock_celery_task():
    """Mock Celery delay call by default so unit tests don't require live Celery workers."""
    with patch("app.workers.tasks.process_document.delay") as mock_delay:
        yield mock_delay


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once for the test session."""
    try:
        Base.metadata.create_all(bind=test_engine)
    except Exception as e:
        pytest.skip(f"Database unavailable: {e}")
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session():
    """Provide a transactional database session for each test."""
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db_session):
    """FastAPI test client with overridden DB dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("testpassword123"),
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user) -> dict:
    """JWT authorization headers for authenticated requests."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_pdf_bytes() -> bytes:
    """Generate a minimal valid PDF for testing."""
    # Minimal valid PDF (single blank page)
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""
    return pdf_content


@pytest.fixture()
def sample_png_bytes() -> bytes:
    """Generate a minimal valid PNG for testing."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def sample_jpeg_bytes() -> bytes:
    """Generate a minimal valid JPEG for testing."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="white")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def malformed_pdf_bytes() -> bytes:
    """Generate deliberately malformed PDF bytes."""
    return b"%PDF-1.4\nthis is not a valid pdf\n%%EOF"


@pytest.fixture()
def fake_exe_as_pdf() -> bytes:
    """Generate an EXE file disguised with PDF extension for MIME spoofing tests."""
    # MZ header = Windows executable
    return b"MZ" + b"\x00" * 100
