import os
import shutil
from typing import List

from django.core.management.base import CommandError


def find_executable(
    name: str,
    common_paths: List[str],
    not_found_message: str,
) -> str:
    path = shutil.which(name)
    if not path:
        for p in common_paths:
            if os.path.exists(p) and os.access(p, os.X_OK):
                path = p
                break
    if not path:
        raise CommandError(not_found_message)
    return path
