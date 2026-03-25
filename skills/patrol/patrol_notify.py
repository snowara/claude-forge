"""Patrol Gmail 알림 발송."""

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from patrol_config import EMAIL_TO, SMTP_PASS, SMTP_USER

STATUS_ICONS = {
    'pass': '&#9989;',      # ✅
    'fail': '&#10060;',     # ❌
    'error': '&#9888;',     # ⚠️
    'skip': '&#9898;',      # ⚪
    'not_run': '&#128564;', # 💤
    'running': '&#9203;',   # ⏳
}


def send_alert(results):
    """실패/에러/not_run 결과에 대해 Gmail 발송.

    Args:
        results: patrol_runner의 전체 결과 dict

    Returns:
        True if sent, False if skipped or failed
    """
    if not SMTP_USER or not SMTP_PASS:
        print('[PATROL] SMTP 미설정 — 알림 스킵')
        return False

    alertable = [
        r for r in results.get('results', [])
        if r['status'] in ('fail', 'error', 'not_run')
    ]
    if not alertable:
        return False

    date = results.get('date', datetime.now().strftime('%Y-%m-%d'))
    targets = ', '.join(r['target'] for r in alertable)
    subject = f'[PATROL 실패] {targets} ({date})'

    html = _build_html(results, alertable, date)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f'[PATROL] 알림 발송 완료 → {EMAIL_TO}')
        return True
    except Exception as e:
        print(f'[PATROL] 알림 발송 실패: {e}')
        return False


def _build_html(results, alertable, date):
    """알림 이메일 HTML 생성."""
    summary = results.get('summary', {})
    rows = ''
    for r in results.get('results', []):
        icon = STATUS_ICONS.get(r['status'], '?')
        msg_parts = []
        for d in r.get('details', []):
            if isinstance(d, str):
                if r['status'] != 'pass':
                    msg_parts.append(d)
            elif d.get('result') not in ('pass', 'skip') and d.get('message'):
                msg_parts.append(d['message'])
        detail_msgs = ' / '.join(msg_parts)
        bg_color = '#FFF3F3' if r['status'] in ('fail', 'error') else '#FFFFFF'
        rows += (
            f'<tr style="background:{bg_color};border-bottom:1px solid #E0E0E0;">'
            f'<td style="padding:10px 12px;">{icon} {r["target"]}</td>'
            f'<td style="padding:10px 12px;text-align:center;">'
            f'<b>{r["status"].upper()}</b></td>'
            f'<td style="padding:10px 12px;color:#666;">{detail_msgs}</td>'
            f'</tr>'
        )

    return f"""
    <div style="font-family:'Noto Sans KR',sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#1B2A4A;color:white;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h2 style="margin:0;font-size:18px;color:#E8B931;">Patrol 검증 결과</h2>
        <p style="margin:4px 0 0;opacity:0.8;font-size:13px;">{date}</p>
      </div>
      <div style="padding:0;border:1px solid #E0E0E0;border-top:none;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr style="background:#1B2A4A;color:white;">
            <th style="padding:10px 12px;text-align:left;">대상</th>
            <th style="padding:10px 12px;text-align:center;">상태</th>
            <th style="padding:10px 12px;text-align:left;">상세</th>
          </tr>
          {rows}
        </table>
      </div>
      <div style="padding:16px 24px;background:#F8F9FA;border:1px solid #E0E0E0;\
border-top:none;border-radius:0 0 8px 8px;text-align:center;">
        <p style="margin:0;color:#666;font-size:12px;">
          PASS {summary.get('pass', 0)} | FAIL {summary.get('fail', 0)} |
          ERROR {summary.get('error', 0)} | SKIP {summary.get('skip', 0)} |
          NOT_RUN {summary.get('not_run', 0)}
        </p>
        <p style="margin:8px 0 0;color:#999;font-size:11px;">
          Claude Code에서 /patrol 로 상세 확인
        </p>
      </div>
    </div>
    """
