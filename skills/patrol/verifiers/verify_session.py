"""네이버 세션 쿠키 만료 검증."""

import json
import time
from pathlib import Path

from .base import BaseVerifier

_SESSION_PATH = (
    Path.home() / 'e-commerce' / 'automation' / 'blog-writer' / 'naver_session.json'
)


class SessionVerifier(BaseVerifier):
    """네이버 세션 쿠키 유효성 검증."""

    target = 'session'

    def verify(self) -> dict:
        details = []

        # 1. 파일 존재 확인
        if not _SESSION_PATH.exists():
            details.append(f'세션 파일 없음: {_SESSION_PATH}')
            return self._result('fail', details, severity='critical')

        # 2. JSON 파싱
        try:
            data = json.loads(_SESSION_PATH.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            details.append(f'세션 파일 파싱 실패: {e}')
            return self._result('error', details, severity='critical')

        cookies = data.get('cookies', [])
        if not cookies:
            details.append('쿠키 목록이 비어있음')
            return self._result('fail', details, severity='critical')

        # 3. .naver.com 도메인 + expires > 0 필터
        naver_cookies = [
            c for c in cookies
            if '.naver.com' in c.get('domain', '')
            and c.get('expires', 0) > 0
        ]

        if not naver_cookies:
            details.append('.naver.com 도메인의 만료 쿠키 없음')
            return self._result('fail', details, severity='critical')

        details.append(f'네이버 쿠키 수: {len(naver_cookies)}')

        # 4. 가장 빨리 만료되는 쿠키 확인
        now = time.time()
        earliest = min(naver_cookies, key=lambda c: c['expires'])
        expires_at = earliest['expires']
        remaining_hours = (expires_at - now) / 3600

        try:
            from ..patrol_config import load_config
        except ImportError:
            from patrol_config import load_config

        config = load_config()
        warning_hours = config.get('thresholds', {}).get(
            'session_expiry_warning_hours', 24,
        )

        # 5. 만료 여부 판정
        if expires_at <= now:
            details.append(
                f'세션 만료됨: {earliest.get("name", "?")} '
                f'({remaining_hours:.1f}시간 전 만료)'
            )
            return self._result('fail', details, severity='critical')

        if remaining_hours <= warning_hours:
            details.append(
                f'세션 곧 만료: {earliest.get("name", "?")} '
                f'({remaining_hours:.1f}시간 남음, 기준 {warning_hours}시간)'
            )
            return self._result('fail', details, severity='warning')

        details.append(f'최단 만료까지 {remaining_hours:.1f}시간 남음')
        return self._result('pass', details)
