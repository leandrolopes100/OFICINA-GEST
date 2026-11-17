import subprocess
from datetime import datetime
from functools import lru_cache

from django.conf import settings
from django.utils import timezone


@lru_cache(maxsize=1)
def versao_sistema():
    try:
        saida = subprocess.run(
            ['git', 'log', '-1', '--format=%cI'],
            cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        return timezone.localtime(datetime.fromisoformat(saida))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
