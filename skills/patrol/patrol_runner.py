#!/usr/bin/env python3
"""Patrol 오케스트레이터 — 자동화 산출물 검증 CLI."""

import argparse
import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from patrol_config import PATROL_DATA_DIR, ensure_data_dir, load_config
from verifiers import VERIFIERS


def setup_logging():
    """로그 설정: RotatingFileHandler + StreamHandler."""
    ensure_data_dir()
    log_path = PATROL_DATA_DIR / 'patrol.log'
    handler = RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=3, encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S',
    ))
    logger = logging.getLogger('patrol')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    return logger


def run_patrol(targets=None, dry_run=False):
    """검증 실행 오케스트레이터.

    Args:
        targets: 검증 대상 리스트 (None이면 config에서 enabled 대상 전부)
        dry_run: True면 알림 미발송

    Returns:
        exit code: 0=all pass, 1=any fail, 2=any error
    """
    log = setup_logging()
    config = load_config()
    today = datetime.now().strftime('%Y-%m-%d')

    if targets is None:
        targets = [
            t for t, cfg in config.get('targets', {}).items()
            if cfg.get('enabled')
        ]

    log.info('Patrol 시작: %s', ', '.join(targets))
    results = []

    for target in targets:
        verifier_cls = VERIFIERS.get(target)
        if not verifier_cls:
            log.warning('미등록 대상: %s', target)
            continue
        try:
            result = verifier_cls().verify()
            results.append(result)
            log.info('%s: %s', target, result['status'].upper())
        except Exception as e:
            log.error('%s 검증 중 예외: %s', target, e)
            results.append({
                'target': target,
                'status': 'error',
                'details': [
                    {'check': '검증 실행', 'result': 'error', 'message': str(e)},
                ],
                'severity': 'warning',
                'checked_at': datetime.now().isoformat(),
            })

    # 요약 계산
    summary = _build_summary(results)

    output = {
        'date': today,
        'results': results,
        'summary': summary,
        'notified': False,
    }

    # 결과 저장 (target 단위 merge)
    ensure_data_dir()
    result_path = PATROL_DATA_DIR / 'results' / f'{today}.json'
    if result_path.exists():
        with open(result_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        existing_by_target = {
            r['target']: r for r in existing.get('results', [])
        }
        for r in results:
            existing_by_target[r['target']] = r
        output['results'] = list(existing_by_target.values())
        output['summary'] = _build_summary(output['results'])
        summary = output['summary']

    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info('결과 저장: %s', result_path)

    # 알림
    notify_statuses = config.get('notify_on', ['fail', 'error', 'not_run'])
    alertable = [r for r in results if r['status'] in notify_statuses]

    if alertable and not dry_run:
        from patrol_notify import send_alert
        if send_alert(output):
            output['notified'] = True
            output['notified_at'] = datetime.now().isoformat()
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

    # 터미널 요약
    _print_summary(output, summary, today)

    # 종료 코드
    if summary.get('fail', 0) > 0:
        return 1
    if summary.get('error', 0) > 0:
        return 2
    return 0


def _build_summary(results):
    """결과 리스트에서 상태별 카운트 요약 dict 생성."""
    summary = {'total': len(results)}
    for status in ('pass', 'fail', 'error', 'skip', 'not_run', 'running'):
        summary[status] = sum(1 for r in results if r['status'] == status)
    return summary


def _print_summary(output, summary, today):
    """터미널에 결과 테이블 출력."""
    status_labels = {
        'pass': 'PASS',
        'fail': 'FAIL',
        'error': 'ERR ',
        'skip': 'SKIP',
        'not_run': 'NRUN',
        'running': 'RUN ',
    }
    print(f'\n{"=" * 50}')
    print(f'  Patrol 결과 — {today}')
    print(f'{"=" * 50}')
    for r in output['results']:
        label = status_labels.get(r['status'], '????')
        print(f'  {r["target"]:20s} {label}')
        for d in r.get('details', []):
            if isinstance(d, str):
                if r['status'] != 'pass':
                    print(f'    → {d}')
            elif d.get('result') not in ('pass',) and d.get('message'):
                print(f'    → {d["message"]}')
    print(f'{"=" * 50}')
    print(
        f'  PASS={summary["pass"]} FAIL={summary["fail"]}'
        f' ERR={summary.get("error", 0)} SKIP={summary.get("skip", 0)}'
    )
    print(f'{"=" * 50}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Patrol — 자동화 산출물 검증')
    parser.add_argument('--target', help='검증 대상 (쉼표 구분)')
    parser.add_argument('--dry-run', action='store_true', help='알림 미발송')
    args = parser.parse_args()

    targets = args.target.split(',') if args.target else None
    sys.exit(run_patrol(targets=targets, dry_run=args.dry_run))
