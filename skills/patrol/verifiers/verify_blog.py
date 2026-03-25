"""blog-writer 산출물 검증."""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from .base import BaseVerifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from patrol_config import PATHS, load_config


class BlogVerifier(BaseVerifier):
    """blog-writer 파이프라인 산출물 완전성 검증.

    검증 흐름:
    1. cron 실행 여부
    2. 메타 파일 존재 + 발행 완료 센티넬
    3. 원본 md 콘텐츠 품질 (h2, FAQ, 상품 링크)
    4. 네이버 블로그 발행물 블록 비율 + 링크/FAQ
    5. WP 발행물 h2 + 상품 링크
    """

    target = 'blog-writer'

    def verify(self):
        config = load_config()
        today = datetime.now().strftime('%Y-%m-%d')
        base = PATHS['blog-writer']
        details = []

        # 1. cron 실행 여부
        cron_status = self._check_cron_ran(base / 'logs', today)
        if cron_status == 'not_run':
            return self._result('not_run', [
                {'check': '파이프라인 실행', 'result': 'not_run',
                 'message': '오늘 cron 로그 없음 (mac 슬립?)'},
            ], 'warning')
        if cron_status == 'running':
            return self._result('running', [
                {'check': '파이프라인 실행', 'result': 'running',
                 'message': '아직 실행 중'},
            ], 'info')

        details.append({'check': '파이프라인 실행', 'result': 'pass'})

        # 2. 메타 파일 찾기
        output_dir = base / today / 'output'
        meta_files = (
            list(output_dir.glob('*_blog_meta.json'))
            if output_dir.exists()
            else []
        )
        if not meta_files:
            return self._result('fail', [
                *details,
                {'check': '메타 파일', 'result': 'fail',
                 'message': f'output 디렉토리에 meta 없음: {output_dir}'},
            ], 'critical')

        meta_path = meta_files[0]
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        p_idx = meta.get('p_idx', '')

        # 3. 센티넬: published_at, wp_published_at 둘 다 없으면 running
        if not meta.get('published_at') and not meta.get('wp_published_at'):
            return self._result('running', [
                *details,
                {'check': '발행 완료', 'result': 'running',
                 'message': 'published_at 없음 - 아직 발행 중'},
            ], 'info')

        details.append({'check': '메타 파일', 'result': 'pass',
                        'message': f'p_idx={p_idx}'})

        # 4. 원본 블록 수 + 콘텐츠 품질 검사
        md_path = output_dir / f'{p_idx}_blog_post.md'
        if not md_path.exists():
            return self._result('fail', [
                *details,
                {'check': '원본 파일', 'result': 'fail',
                 'message': f'원본 md 없음: {md_path.name}'},
            ], 'critical')

        md_content = md_path.read_text(encoding='utf-8')
        source_blocks = _count_blocks(md_content)
        source_has_h2 = bool(re.findall(r'^## ', md_content, re.MULTILINE))
        source_has_link = 'snowgift.co.kr' in md_content
        source_has_faq = 'FAQ' in md_content or 'Q.' in md_content

        source_issues = []
        if not source_has_h2:
            source_issues.append('h2 소제목 없음')
        if not source_has_faq:
            source_issues.append('FAQ 없음')
        if not source_has_link:
            source_issues.append('상품 링크(snowgift.co.kr) 없음')

        if source_issues:
            details.append({'check': '원본 품질', 'result': 'fail',
                            'message': ' / '.join(source_issues)})
        else:
            details.append({'check': '원본 품질', 'result': 'pass',
                            'message': f'{source_blocks}블록, h2+FAQ+링크 정상'})

        # 5. 네이버 블로그 검증
        blog_url = meta.get('blog_url', '')
        naver_result = {'check': '네이버 발행', 'result': 'skip',
                        'message': 'URL 없음'}

        if blog_url:
            log_no = meta.get('log_no', '')
            if not log_no:
                log_no_match = re.search(r'logNo=(\d+)', blog_url)
                log_no = log_no_match.group(1) if log_no_match else ''

            if log_no:
                mobile_url = f'https://m.blog.naver.com/snowgift07/{log_no}'
                html = self._fetch_url(mobile_url, config)
                if html is None:
                    naver_result = {
                        'check': '네이버 발행', 'result': 'error',
                        'message': 'URL fetch 실패 (네트워크 오류)',
                    }
                else:
                    naver_result = _check_naver_html(
                        html, source_blocks, source_has_link,
                        source_has_faq, config,
                    )

        details.append(naver_result)

        # 6. WP 검증
        wp_url = meta.get('wp_url', '')
        wp_result = {'check': 'WP 발행', 'result': 'skip',
                     'message': 'URL 없음'}

        if wp_url:
            html = self._fetch_url(wp_url, config)
            if html is None:
                wp_result = {
                    'check': 'WP 발행', 'result': 'error',
                    'message': 'URL fetch 실패 (네트워크 오류)',
                }
            else:
                wp_result = _check_wp_html(
                    html, source_has_h2, source_has_link,
                )

        details.append(wp_result)

        # 7. 최종 판정
        has_fail = any(d['result'] == 'fail' for d in details)
        has_error = any(d['result'] == 'error' for d in details)
        if has_fail:
            return self._result('fail', details, 'critical')
        if has_error:
            return self._result('error', details, 'warning')
        return self._result('pass', details, 'info')


def _count_blocks(md_text):
    """원본 md의 콘텐츠 블록 수 (빈 줄/구분선/테이블 구분자 제외)."""
    count = 0
    for line in md_text.strip().split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == '---':
            continue
        if all(c in '-| :' for c in stripped):
            continue
        count += 1
    return count


def _count_published_blocks(html_text):
    """발행된 HTML에서 의미 있는 텍스트 블록 수 (len > 10)."""
    text = re.sub(r'<[^>]+>', '', html_text)
    count = 0
    for line in text.split('\n'):
        if len(line.strip()) > 10:
            count += 1
    return count


def _check_naver_html(html, source_blocks, source_has_link,
                      source_has_faq, config):
    """네이버 발행물 HTML 검증."""
    pub_blocks = _count_published_blocks(html)
    ratio = pub_blocks / max(source_blocks, 1)
    pub_has_link = 'snowgift.co.kr' in html

    issues = []
    threshold = config.get('thresholds', {}).get('blog_block_ratio_min', 0.7)
    if ratio < threshold:
        issues.append(f'블록 {ratio:.0%} ({pub_blocks}/{source_blocks})')
    if source_has_link and not pub_has_link:
        issues.append('상품 링크 누락')
    if source_has_faq and 'FAQ' not in html and 'Q.' not in html:
        issues.append('FAQ 누락')

    if issues:
        return {
            'check': '네이버 발행', 'result': 'fail',
            'expected': source_blocks, 'actual': pub_blocks,
            'message': ' / '.join(issues),
        }
    return {
        'check': '네이버 발행', 'result': 'pass',
        'message': f'블록 {ratio:.0%} - 정상',
    }


def _check_wp_html(html, source_has_h2, source_has_link):
    """WP 발행물 HTML 검증."""
    wp_has_h2 = bool(re.findall(r'<h2', html))
    wp_has_link = 'snowgift.co.kr' in html

    issues = []
    if source_has_h2 and not wp_has_h2:
        issues.append('h2 소제목 없음')
    if source_has_link and not wp_has_link:
        issues.append('상품 링크 누락')

    if issues:
        return {
            'check': 'WP 발행', 'result': 'fail',
            'message': ' / '.join(issues),
        }
    return {'check': 'WP 발행', 'result': 'pass', 'message': '정상'}
