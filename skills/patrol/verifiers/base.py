"""Verifier 추상 인터페이스."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path


class BaseVerifier(ABC):
    """모든 verifier의 부모 클래스."""

    target: str = ''

    @abstractmethod
    def verify(self) -> dict:
        """검증 실행. 결과 dict 반환."""

    def _result(self, status, details, severity='info'):
        """표준화된 결과 dict 생성.

        Args:
            status: "pass" | "fail" | "skip" | "error" | "not_run" | "running"
            details: 검증 상세 리스트
            severity: "critical" | "warning" | "info"
        """
        return {
            'target': self.target,
            'status': status,
            'details': details,
            'severity': severity,
            'checked_at': datetime.now().isoformat(),
        }

    def _check_cron_ran(self, logs_dir, date_str):
        """cron 로그로 파이프라인 실행 여부 확인.

        Args:
            logs_dir: 로그 디렉토리 경로
            date_str: 날짜 문자열 (YYYY-MM-DD)

        Returns:
            "ran" | "not_run" | "running"
        """
        log_file = Path(logs_dir) / f'cron_{date_str}.log'
        if not log_file.exists():
            return 'not_run'
        content = log_file.read_text(encoding='utf-8', errors='ignore')
        tail_lines = content.strip().split('\n')[-5:]
        if '크론잡 완료' in content or any('완료' in line for line in tail_lines):
            return 'ran'
        return 'running'

    def _fetch_url(self, url, config):
        """URL fetch + 재시도.

        Args:
            url: 요청 URL
            config: fetch 설정 포함 config dict

        Returns:
            응답 텍스트 또는 None (실패 시)
        """
        import time

        import requests

        fetch_cfg = config.get('fetch', {})
        timeout = fetch_cfg.get('timeout_seconds', 15)
        retries = fetch_cfg.get('max_retries', 2)
        backoff = fetch_cfg.get('backoff_seconds', 5)

        for attempt in range(retries + 1):
            try:
                resp = requests.get(url, timeout=timeout)
                if resp.status_code == 200:
                    return resp.text
                if attempt < retries:
                    time.sleep(backoff * (2 ** attempt))
            except requests.RequestException:
                if attempt < retries:
                    time.sleep(backoff * (2 ** attempt))
        return None
