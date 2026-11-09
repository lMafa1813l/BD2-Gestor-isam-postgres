"""Local lab credentials. Print paths only; never publish password values."""
import argparse
import os
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parents[1]


def password_path():
    project = os.getenv('DIST_PROJECT', 'bd2_dist')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', project):
        raise ValueError('DIST_PROJECT must be a valid lower-case Compose project name')
    return Path(os.getenv('DIST_PASSWORD_FILE', str(ROOT/'.secrets'/(project+'.password')))).resolve()


def read_password():
    path = password_path()
    if not path.is_file():
        raise RuntimeError('Missing local credential; run distributed/run.sh up first')
    value = path.read_text().strip()
    if len(value) < 24:
        raise ValueError('The local lab password must contain at least 24 characters')
    return value


def create():
    path = password_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w') as fh:
            fh.write(secrets.token_urlsafe(32)+'\n')
    read_password()
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create', action='store_true')
    args = parser.parse_args()
    print(create() if args.create else password_path())
