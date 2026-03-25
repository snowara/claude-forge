"""Patrol 설정 로드 + 경로 상수."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

PATROL_SKILL_DIR = Path(__file__).parent
PATROL_DATA_DIR = Path(os.environ.get(
    'PATROL_DATA_DIR',
    os.path.expanduser('~/.claude/patrol'),
))

PATHS = {
    'blog-writer': Path.home() / 'e-commerce' / 'automation' / 'blog-writer',
    'daangn-biz': Path.home() / 'e-commerce' / 'automation' / 'daangn-biz',
    'product-finder': Path.home() / 'e-commerce' / 'automation' / 'product-finder',
    'ad-video-crew': Path.home() / 'e-commerce' / 'automation' / 'ad-video-crew',
}

# .env 로드
load_dotenv(PATROL_SKILL_DIR / '.env')

SMTP_USER = os.getenv('PATROL_SMTP_USER', '')
SMTP_PASS = os.getenv('PATROL_SMTP_PASS', '')
EMAIL_TO = os.getenv('PATROL_EMAIL_TO', 'snowara@snowara.com')


def _default_config():
    """기본 설정 반환."""
    return {
        'email_to': EMAIL_TO,
        'notify_on': ['fail', 'error', 'not_run'],
        'thresholds': {
            'blog_block_ratio_min': 0.7,
            'session_expiry_warning_hours': 24,
            'finder_min_daily_count': 1,
        },
        'targets': {
            'blog-writer': {'enabled': True},
            'daangn-biz': {'enabled': True},
            'product-finder': {'enabled': True},
            'session': {'enabled': True},
            'ad-video-crew': {'enabled': True},
        },
        'fetch': {
            'timeout_seconds': 15,
            'max_retries': 2,
            'backoff_seconds': 5,
        },
    }


def load_config():
    """config.json 로드. 파일 없으면 기본 설정 반환."""
    config_path = PATROL_SKILL_DIR / 'config.json'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return _default_config()


def ensure_data_dir():
    """PATROL_DATA_DIR/results/ 디렉토리 생성."""
    (PATROL_DATA_DIR / 'results').mkdir(parents=True, exist_ok=True)
