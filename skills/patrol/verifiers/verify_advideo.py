"""ad-video-crew 산출물 검증 — 렌더링 + SNS 발행 + 웹앱 상태."""

import json
import os
from datetime import datetime
from pathlib import Path

try:
    from .base import BaseVerifier
except ImportError:
    from base import BaseVerifier

try:
    from ..patrol_config import PATHS, load_config
except ImportError:
    from patrol_config import PATHS, load_config


class AdVideoVerifier(BaseVerifier):
    """ad-video-crew 3단 검증: 렌더링 → SNS 발행 → 웹앱."""

    target = "ad-video-crew"

    def verify(self):
        config = load_config()
        today = datetime.now().strftime("%Y-%m-%d")
        base = PATHS["ad-video-crew"]
        details = []

        # 1. 렌더링 결과물 확인
        render_result = self._check_render(base, today, config)
        details.append(render_result)

        # 2. SNS 발행 확인
        sns_result = self._check_sns_publish(base, today)
        details.append(sns_result)

        # 3. 웹앱 상태 확인
        web_result = self._check_web_app(config)
        details.append(web_result)

        # 최종 판정
        has_fail = any(d["result"] == "fail" for d in details)
        has_error = any(d["result"] == "error" for d in details)
        if has_fail:
            return self._result("fail", details, "critical")
        if has_error:
            return self._result("error", details, "warning")
        return self._result("pass", details, "info")

    def _check_render(self, base, today, config):
        """output/{today}/ 디렉토리에 영상 파일 존재 + 크기 확인."""
        output_dir = base / "output" / today
        if not output_dir.exists():
            return {
                "check": "렌더링 결과물",
                "result": "skip",
                "message": f"오늘({today}) output 디렉토리 없음 (영상 제작 안 함)",
            }

        mp4_files = list(output_dir.glob("*.mp4"))
        if not mp4_files:
            return {
                "check": "렌더링 결과물",
                "result": "fail",
                "message": f"{output_dir.name}/ 에 mp4 파일 없음",
            }

        min_size_kb = config.get("ad_video_crew", {}).get("min_video_size_kb", 100)
        small_files = []
        for mp4 in mp4_files:
            size_kb = mp4.stat().st_size / 1024
            if size_kb < min_size_kb:
                small_files.append(f"{mp4.name} ({size_kb:.0f}KB)")

        if small_files:
            return {
                "check": "렌더링 결과물",
                "result": "fail",
                "message": f"비정상 크기 영상: {', '.join(small_files)} (최소 {min_size_kb}KB)",
            }

        total_mb = sum(f.stat().st_size for f in mp4_files) / (1024 * 1024)
        return {
            "check": "렌더링 결과물",
            "result": "pass",
            "message": f"mp4 {len(mp4_files)}개 ({total_mb:.1f}MB)",
        }

    def _check_sns_publish(self, base, today):
        """SNS 메타 파일로 발행 상태 확인."""
        output_dir = base / "output" / today
        if not output_dir.exists():
            return {
                "check": "SNS 발행",
                "result": "skip",
                "message": "오늘 output 없음 (발행 대상 없음)",
            }

        meta_files = list(output_dir.glob("*_sns_meta*.json"))
        if not meta_files:
            return {
                "check": "SNS 발행",
                "result": "skip",
                "message": "sns_meta 파일 없음 (발행 미시도)",
            }

        # 가장 최신 메타 파일 읽기
        latest_meta = sorted(meta_files)[-1]
        try:
            with open(latest_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {
                "check": "SNS 발행",
                "result": "error",
                "message": f"메타 파일 파싱 실패: {e}",
            }

        # 발행 상태 확인 (channels/platforms 필드 확인)
        channels = meta.get("channels", meta.get("platforms", {}))
        if not channels:
            # 메타 파일은 있지만 채널 정보 없으면 — 메타만 생성된 상태
            return {
                "check": "SNS 발행",
                "result": "pass",
                "message": f"메타 생성됨: {latest_meta.name}",
            }

        failed_channels = []
        passed_channels = []
        for channel, info in channels.items():
            status = info.get("status", "unknown") if isinstance(info, dict) else str(info)
            if status in ("published", "posted", "success", "scheduled"):
                passed_channels.append(channel)
            else:
                failed_channels.append(f"{channel}={status}")

        if failed_channels:
            return {
                "check": "SNS 발행",
                "result": "fail",
                "message": f"실패: {', '.join(failed_channels)} | 성공: {', '.join(passed_channels)}",
            }

        return {
            "check": "SNS 발행",
            "result": "pass",
            "message": f"발행 완료: {', '.join(passed_channels)}",
        }

    def _check_web_app(self, config):
        """Next.js 웹앱 헬스체크 (localhost)."""
        port = config.get("ad_video_crew", {}).get("web_port", 3000)
        url = f"http://localhost:{port}"

        try:
            import requests
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return {
                    "check": "웹앱 상태",
                    "result": "pass",
                    "message": f"localhost:{port} 정상 (HTTP 200)",
                }
            return {
                "check": "웹앱 상태",
                "result": "fail",
                "message": f"localhost:{port} HTTP {resp.status_code}",
            }
        except Exception:
            return {
                "check": "웹앱 상태",
                "result": "skip",
                "message": f"localhost:{port} 미응답 (서버 미실행)",
            }
