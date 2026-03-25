---
allowed-tools: Bash, Read, Grep, Glob
description: 자동화 파이프라인 산출물 검증. 인자 없이 전체 검증, 대상명 지정 시 개별 검증.
argument-hint: [대상명]
---

# /patrol — 자동화 감시탑

자동화 파이프라인(blog-writer, daangn-biz, product-finder, session)의 산출물 완전성을 검증한다.

## 실행 방법

1. 인자 파싱: 없으면 전체, 있으면 해당 대상만
2. Bash로 실행:
   ```bash
   cd ~/.claude/skills/patrol && python3 patrol_runner.py --target {대상} --dry-run
   ```
   (수동 실행이므로 --dry-run으로 이메일 미발송. 이메일 발송 원하면 --dry-run 제거)
3. 결과를 사용자에게 포맷팅하여 표시
4. 실패 항목 있으면 → pipeline-verifier 에이전트로 원인 분석 제안

## 사용 예시

```
/patrol              # 전체 검증
/patrol blog-writer  # blog-writer만 검증
```

## 검증 대상

| 대상 | 검증 내용 |
|------|----------|
| blog-writer | 네이버+WP 발행 URL fetch → 원본 md 블록 수 대조, 링크/FAQ 확인 |
| daangn-biz | schedule.json 스케줄 확인 → 발행 상태 + 로그 에러 체크 |
| product-finder | 센티넬 파일 → SQLite DB 적재 건수 → 리포트 파일 확인 |
| session | naver_session.json 쿠키 최단 만료 시간 확인 |

## 실패 시

실패 항목이 발견되면:
1. 상세 결과를 표시
2. "pipeline-verifier 에이전트로 원인 분석할까요?" 제안
3. 사용자 승인 시 pipeline-verifier 에이전트 호출
