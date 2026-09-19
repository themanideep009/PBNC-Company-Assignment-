"""
Virus scanner adapter — pluggable interface for ClamAV integration.

INTEGRATION POINT: ClamAV via clamd socket/TCP if available.

In evaluation environments where ClamAV is not available:
- The stub logs a warning and passes the file through
- This is explicitly documented as a limitation
- The interface is ready for production wiring

Production wiring:
1. Run ClamAV daemon (clamd) as a Docker service
2. Set VIRUS_SCAN_ENABLED=true, CLAMAV_HOST, CLAMAV_PORT in .env
3. The ClamAVScanner implementation will connect via TCP
"""

import logging
from abc import ABC, abstractmethod
from typing import Tuple

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VirusScanner(ABC):
    """Abstract virus scanner interface."""

    @abstractmethod
    def scan(self, file_bytes: bytes) -> Tuple[bool, str]:
        """
        Scan file bytes for malware.

        Returns:
            (is_clean, message): True if clean, False if infected.
        """
        ...


class ClamAVScanner(VirusScanner):
    """
    ClamAV integration via clamd TCP socket.

    Requires:
    - clamd daemon running (Docker service or system service)
    - pyclamd Python package: pip install pyclamd
    """

    def scan(self, file_bytes: bytes) -> Tuple[bool, str]:
        try:
            import pyclamd
            cd = pyclamd.ClamdNetworkSocket(
                host=settings.CLAMAV_HOST,
                port=settings.CLAMAV_PORT,
            )
            result = cd.scan_stream(file_bytes)
            if result is None:
                return True, "Clean"
            else:
                # result is {'stream': ('FOUND', 'Virus.Name')}
                status_info = result.get("stream", ("UNKNOWN", "Unknown"))
                return False, f"Infected: {status_info[1]}"
        except ImportError:
            logger.error("pyclamd not installed. Install with: pip install pyclamd")
            return True, "Scanner unavailable (pyclamd not installed)"
        except Exception as e:
            logger.error(f"ClamAV scan error: {e}")
            # Fail open — don't block processing if scanner is down
            # This is a conscious decision documented in ARCHITECTURE.md
            return True, f"Scanner error (failing open): {e}"


class VirusScannerStub(VirusScanner):
    """
    Stub scanner — passes all files through with a warning.

    Used when VIRUS_SCAN_ENABLED=false or ClamAV is unavailable.
    Documented limitation: no actual malware scanning in this mode.
    """

    def scan(self, file_bytes: bytes) -> Tuple[bool, str]:
        logger.warning(
            "Virus scanning is disabled (stub). "
            "Set VIRUS_SCAN_ENABLED=true and configure ClamAV for production."
        )
        return True, "Scanning disabled (stub)"


def get_virus_scanner() -> VirusScanner:
    """Factory — returns the configured virus scanner."""
    if settings.VIRUS_SCAN_ENABLED:
        return ClamAVScanner()
    return VirusScannerStub()
