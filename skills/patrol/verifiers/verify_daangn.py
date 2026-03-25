"""당근 비즈프로필 자동 포스팅 검증."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .base import BaseVerifier
try:
    from ..patrol_config import PATHS
except ImportError:
    from patrol_config import PATHS


class DaangnVerifier(BaseVerifier):
    """당근 비즈프로필 스케줄 및 포스팅 상태 검증."""

    target = 'daangn-biz'

    def __init__(self):
        base = PATHS.get('daangn-biz', Path.home() / 'e-commerce' / 'automation' / 'daangn-biz')
        self.schedule_path = base / 'schedule.json'
        self.logs_dir = base / 'logs'

    def verify(self) -> dict:
        """검증 실행."""
        today_str = datetime.now().strftime('%Y-%m-%d')

        # 1. schedule.json 읽기
        today_entries = self._load_today_entries(today_str)
        if today_entries is None:
            return self._result('error', ['schedule.json 읽기 실패'], severity='warning')

        # 2. 오늘 스케줄 없으면 skip
        if not today_entries:
            return self._result('skip', [f'{today_str}: 포스팅 스케줄 없음'])

        # 3. cron 실행 여부
        cron_status = self._check_cron_ran(self.logs_dir, today_str)
        if cron_status == 'not_run':
            return self._result(
                'not_run',
                [f'{today_str}: cron 미실행 (예정 {len(today_entries)}건)'],
                severity='warning',
            )

        # 4. 각 항목 status 확인
        details = []
        failed_count = 0
        for entry in today_entries:
            title = entry.get('title', entry.get('product_name', '제목 없음'))
            status = entry.get('status', 'unknown')
            if status == 'posted':
                details.append(f'[PASS] {title}')
            else:
                details.append(f'[FAIL] {title} (status={status})')
                failed_count += 1

        # 5. cron 로그에서 ERROR 키워드 확인
        error_lines = self._scan_log_errors(today_str)
        if error_lines:
            details.append(f'cron 로그 ERROR {len(error_lines)}건 발견')
            for line in error_lines[:3]:
                details.append(f'  > {line.strip()[:120]}')

        # 6. 종합 판정
        if cron_status == 'running':
            return self._result('running', details, severity='info')

        if failed_count > 0:
            return self._result('fail', details, severity='critical')

        severity = 'warning' if error_lines else 'info'
        return self._result('pass', details, severity=severity)

    def _load_today_entries(self, today_str: str) -> list | None:
        """schedule.json에서 오늘 날짜 항목만 추출."""
        if not self.schedule_path.exists():
            return None
        try:
            content = self.schedule_path.read_text(encoding='utf-8')
            schedule = json.loads(content)
            return [
                entry for entry in schedule
                if entry.get('scheduled_at', '').startswith(today_str)
            ]
        except (json.JSONDecodeError, OSError):
            return None

    def _scan_log_errors(self, date_str: str) -> list:
        """cron 로그에서 ERROR 라인 수집."""
        log_file = self.logs_dir / f'cron_{date_str}.log'
        if not log_file.exists():
            return []
        try:
            lines = log_file.read_text(encoding='utf-8', errors='ignore').split('\n')
            return [line for line in lines if 'ERROR' in line]
        except OSError:
            return []
