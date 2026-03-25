---
name: patrol
description: 자동화 파이프라인 산출물 검증 — blog-writer, daangn-biz, product-finder, session
version: 1.0.0
---

# Patrol — 자동화 감시탑

cron 자동화의 산출물 완전성을 검증하고 실패 시 Gmail 알림.

## 사용법
- `/patrol` — 전체 검증
- `/patrol blog-writer` — 특정 대상
- cron 자동 실행: 10:30(blog+session), 09:00(daangn), 08:30(finder)
