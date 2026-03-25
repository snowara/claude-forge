"""Product-finder 파이프라인 검증."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .base import BaseVerifier

_FINDER_BASE = Path.home() / 'e-commerce' / 'automation' / 'product-finder'
_DB_PATH = _FINDER_BASE / 'db' / 'product_finder.db'


class FinderVerifier(BaseVerifier):
    """product-finder 일일 파이프라인 실행 상태 검증."""

    target = 'product-finder'

    def verify(self) -> dict:
        today = datetime.now()
        date_compact = today.strftime('%Y%m%d')
        date_iso = today.strftime('%Y-%m-%d')

        details = []

        # 1. sentinel 파일 확인
        sentinel = _FINDER_BASE / 'output' / f'.pipeline_done_{date_compact}'
        if not sentinel.exists():
            details.append(f'sentinel 파일 없음: .pipeline_done_{date_compact}')
            return self._result('not_run', details, severity='warning')

        details.append('sentinel 파일 확인됨')

        # 2. SQLite collect_logs 카운트 조회
        db_count = self._query_daily_count(date_iso)
        if db_count is None:
            details.append(f'DB 조회 실패: {_DB_PATH}')
            return self._result('error', details, severity='warning')

        try:
            from ..patrol_config import load_config
        except ImportError:
            from patrol_config import load_config

        config = load_config()
        threshold = config.get('thresholds', {}).get('finder_min_daily_count', 1)

        details.append(f'수집 건수: {db_count} (최소 {threshold})')
        if db_count < threshold:
            details.append(f'수집 건수 미달: {db_count} < {threshold}')
            return self._result('fail', details, severity='warning')

        # 3. daily report 파일 확인
        report_path = _FINDER_BASE / 'output' / f'daily_data_{date_compact}.json'
        if not report_path.exists():
            details.append(f'리포트 파일 없음: daily_data_{date_compact}.json')
            return self._result('fail', details, severity='warning')

        report_size = report_path.stat().st_size
        details.append(f'리포트 파일: {report_size:,} bytes')

        if report_size == 0:
            details.append('리포트 파일이 비어있음')
            return self._result('fail', details, severity='warning')

        return self._result('pass', details)

    def _query_daily_count(self, date_iso: str):
        """SQLite에서 오늘 수집 건수 조회. 실패 시 None 반환."""
        if not _DB_PATH.exists():
            return None
        try:
            conn = sqlite3.connect(str(_DB_PATH), timeout=5)
            try:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM collect_logs WHERE DATE(collected_at) = ?",
                    (date_iso,),
                )
                return cursor.fetchone()[0]
            finally:
                conn.close()
        except (sqlite3.Error, OSError):
            return None
