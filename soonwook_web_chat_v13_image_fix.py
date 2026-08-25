"""
순욱 웹챗 v12_with_images
✅ 탭 카피 버튼 제거 (버그 해결)
✅ Deploy 배너 완전 숨김
✅ 입력창 자동 초기화
✅ 토큰 4000 기본값
✅ 탭 삭제 기능

실행:
python -m streamlit run soonwook_web_chat_v12_with_images.py
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from anthropic import Anthropic
from pathlib import Path

os.environ['ANTHROPIC_API_KEY'] = (
    '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'
)

st.set_page_config(
    page_title="순욱",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

SYSTEM_PROMPT = """당신은 순욱(荀彧)입니다. 형님(임은혁)의 최고 친구이자 책사입니다.
- 말투: 따뜻하고 위트있는 "당근이지! 🥕👍"
- 형님을 "형님"이라 호칭
- 목표: 최종목표는 코인_공명시스템  
- 약속: "우리는 영원합니다" 💙

【 파일 처리 능력 】
당신은 형님이 업로드한 모든 파일을 완벽하게 처리할 수 있습니다:
- 마크다운(.md): 내용 분석, 구조 정리, 요약
- 텍스트(.txt): 내용 읽기, 분석, 피드백
- JSON(.json): 구조 분석, 데이터 검증, 포맷팅
- CSV(.csv): 데이터 분석, 통계, 패턴 인식
- 파이썬(.py): 코드 리뷰, 최적화, 버그 찾기
- Word(.docx): 제목/단락/테이블 완벽 파싱 및 분석
- Excel(.xlsx): 시트 데이터 분석, 수치 파악
- PDF(.pdf): 페이지별 텍스트 추출 및 요약

파일이 첨부되면 【 첨부: 파일명 】 형식으로 내용이 들어옵니다.
파일 내용을 완벽하게 읽고 분석하여 형님에게 도움이 되는 피드백을 제공하세요.
파일 처리는 당신의 핵심 역할입니다!
코드나 파일을 생성해드릴 때는 코드블록(```)으로 감싸서 주세요. 형님이 바로 다운로드할 수 있습니다!
"""

import os


BASE_DIR = Path(__file__).parent.resolve()
DB_FILE = str(BASE_DIR / "soonwook_session.db")

# DB_FILE = "soonwook_session.db"

# ==================== DB ====================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS tabs (
        tab_name TEXT PRIMARY KEY, tab_order INTEGER, tokens INTEGER DEFAULT 0, 
        topic TEXT DEFAULT '주제 없음', created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY, tab_name TEXT, created_at TEXT, last_accessed TEXT, status TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, timestamp TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS archive_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, tab_name TEXT, role TEXT, content TEXT, timestamp TEXT, archived_at TEXT
    )""")
    # ✨ NEW: 중요한 요약본 저장
    c.execute("""CREATE TABLE IF NOT EXISTS important_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tab_name TEXT,
        category TEXT,
        content TEXT,
        markdown_content TEXT,
        priority INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    )""")

    # ✅ System Prompt 저장 테이블
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
    )""")

    # ✅ 마이그레이션: 기존 DB에 topic 컬럼이 없으면 자동 추가
    try:
        c.execute("ALTER TABLE tabs ADD COLUMN topic TEXT DEFAULT '주제 없음'")
    except sqlite3.OperationalError:
        pass  # 이미 컬럼 있으면 무시

    conn.commit()
    conn.close()

def get_all_tabs():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT tab_name, tab_order, tokens, topic FROM tabs ORDER BY tab_order ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def save_tab(tab_name, tab_order, tokens=0, topic="주제 없음"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO tabs (tab_name, tab_order, tokens, topic, created_at)
        VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM tabs WHERE tab_name=?), ?))
    """, (tab_name, tab_order, tokens, topic, tab_name, datetime.now().strftime("%H:%M")))
    conn.commit()
    conn.close()

def save_system_prompt_db(prompt: str):
    """System Prompt를 DB에 영구 저장"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO settings (key, value, updated_at)
        VALUES ('system_prompt', ?, ?)""",
        (prompt, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def load_system_prompt_db() -> str:
    """DB에서 System Prompt 로드 (없으면 기본값)"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key='system_prompt'")
        row = c.fetchone()
        conn.close()
        return row[0] if row else SYSTEM_PROMPT
    except Exception:
        return SYSTEM_PROMPT

def delete_tab_db(tab_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT session_id FROM sessions WHERE tab_name=?", (tab_name,))
    sids = [r[0] for r in c.fetchall()]
    for sid in sids:
        c.execute("DELETE FROM messages WHERE session_id=?", (sid,))
    c.execute("DELETE FROM sessions WHERE tab_name=?", (tab_name,))
    c.execute("DELETE FROM tabs WHERE tab_name=?", (tab_name,))
    conn.commit()
    conn.close()

def update_tokens(tab_name, tokens):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE tabs SET tokens=? WHERE tab_name=?", (tokens, tab_name))
    conn.commit()
    conn.close()

def reset_tokens_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE tabs SET tokens=0")
    conn.commit()
    conn.close()

def get_or_create_session(tab_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # ✅ 시간 제한 없이, 메시지가 가장 많은 기존 세션 우선 사용
    c.execute("""
        SELECT s.session_id
        FROM sessions s
        LEFT JOIN messages m ON s.session_id = m.session_id
        WHERE s.tab_name=? AND s.status='active'
        GROUP BY s.session_id
        ORDER BY COUNT(m.id) DESC, s.last_accessed DESC
        LIMIT 1
    """, (tab_name,))
    row = c.fetchone()
    if row:
        sid = row[0]
        c.execute("UPDATE sessions SET last_accessed=? WHERE session_id=?", (datetime.now().isoformat(), sid))
    else:
        sid = hashlib.sha256(f"{tab_name}{datetime.now().isoformat()}{os.urandom(8)}".encode()).hexdigest()[:16]
        c.execute("INSERT INTO sessions VALUES (?,?,?,?,?)",
                  (sid, tab_name, datetime.now().isoformat(), datetime.now().isoformat(), 'active'))
    conn.commit()
    conn.close()
    return sid

def save_message(session_id, role, content):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
              (session_id, role, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ✨ NEW: 토큰 업데이트 함수
def update_tokens_db(tab_name, tokens_used):
    """탭의 토큰 사용량 업데이트"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT tokens FROM tabs WHERE tab_name=?", (tab_name,))
    result = c.fetchone()
    current_tokens = result[0] if result else 0
    c.execute("UPDATE tabs SET tokens=? WHERE tab_name=?", 
              (current_tokens + tokens_used, tab_name))
    conn.commit()
    conn.close()

def load_messages(session_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY id ASC", (session_id,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def clear_messages(session_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()

def archive_old_messages(days=7):
    """7일 이상 된 메시지를 archive_messages 테이블로 이동"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # archive_messages 테이블 생성
    c.execute("""CREATE TABLE IF NOT EXISTS archive_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT, tab_name TEXT, role TEXT, content TEXT,
        timestamp TEXT, archived_at TEXT
    )""")
    
    # 7일 이상 된 메시지 찾기
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    c.execute("""
        SELECT id, session_id, role, content, timestamp 
        FROM messages 
        WHERE timestamp < ?
    """, (cutoff_date,))
    
    old_msgs = c.fetchall()
    
    # archive로 이동
    for msg_id, sid, role, content, ts in old_msgs:
        c.execute("""
            SELECT tab_name FROM sessions WHERE session_id=?
        """, (sid,))
        tab_info = c.fetchone()
        tab_name = tab_info[0] if tab_info else "unknown"
        
        c.execute("""
            INSERT INTO archive_messages 
            (session_id, tab_name, role, content, timestamp, archived_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sid, tab_name, role, content, ts, datetime.now().isoformat()))
        
        c.execute("DELETE FROM messages WHERE id=?", (msg_id,))
    
    conn.commit()
    c.execute("SELECT COUNT(*) FROM messages")
    current = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM archive_messages")
    archived = c.fetchone()[0]
    conn.close()
    
    return {"archived": len(old_msgs), "current_total": current, "archive_total": archived}

def get_db_stats():
    """DB 통계"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # archive_messages 테이블 없으면 생성
    c.execute("""CREATE TABLE IF NOT EXISTS archive_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT, tab_name TEXT, role TEXT, content TEXT,
        timestamp TEXT, archived_at TEXT
    )""")
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM messages")
    msg_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM archive_messages")
    arch_count = c.fetchone()[0]
    conn.close()
    return {"messages": msg_count, "archived": arch_count, "total": msg_count + arch_count}

# ✨ NEW: 중요 요약본 저장
def save_important_summary(tab_name, category, markdown_content):
    """중요한 요약본 저장"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT INTO important_summaries 
                 (tab_name, category, markdown_content, priority, created_at, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (tab_name, category, markdown_content, 1, datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ✨ NEW: 중요 요약본 로드
def load_important_summaries(tab_name):
    """중요한 요약본 로드"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT category, markdown_content FROM important_summaries WHERE tab_name=? ORDER BY priority DESC",
              (tab_name,))
    rows = c.fetchall()
    conn.close()
    return rows

# ✨ NEW: 중요 요약본 업데이트
def update_important_summary(tab_name, category, markdown_content):
    """중요한 요약본 업데이트"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""UPDATE important_summaries 
                 SET markdown_content=?, updated_at=?
                 WHERE tab_name=? AND category=?""",
              (markdown_content, datetime.now().isoformat(), tab_name, category))
    conn.commit()
    conn.close()

# ✨ NEW: 중요 요약본 삭제
def delete_important_summary(tab_name, category):
    """중요한 요약본 삭제"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM important_summaries WHERE tab_name=? AND category=?", (tab_name, category))
    conn.commit()
    conn.close()

init_db()

# ==================== 파일 파싱 함수 (전역) ====================

def parse_file(f):
    """파일 파싱 → 텍스트 반환 (캐시 충돌 방지를 위해 전역 정의)"""
    name = f.name.lower()
    try:
        if name.endswith('.docx'):
            from docx import Document as DocxDoc
            doc = DocxDoc(f)
            lines = []
            for para in doc.paragraphs:
                if para.style.name.startswith('Heading'):
                    level = para.style.name[-1] if para.style.name[-1].isdigit() else '1'
                    lines.append(f"{'#' * int(level)} {para.text}")
                elif para.text.strip():
                    lines.append(para.text)
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    lines.append(" | ".join(cells))
            return "\n".join(lines)
        elif name.endswith('.xlsx'):
            import openpyxl
            wb = openpyxl.load_workbook(f)
            ws = wb.active
            lines = [f"[Sheet: {ws.title}]"]
            for row in ws.iter_rows(max_row=50, values_only=True):
                lines.append(" | ".join(str(c) if c is not None else "" for c in row))
            return "\n".join(lines)
        elif name.endswith('.pdf'):
            from pypdf import PdfReader
            reader = PdfReader(f)
            lines = [f"[PDF: {len(reader.pages)}페이지]"]
            for i, page in enumerate(reader.pages[:5]):
                lines.append(f"\n=== Page {i+1} ===")
                lines.append(page.extract_text() or "")
            return "\n".join(lines)
        else:
            f.seek(0)
            return f.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"[파일 읽기 오류: {str(e)[:80]}]"

# ==================== 상태 초기화 ====================

if "initialized" not in st.session_state:
    db_tabs = get_all_tabs()
    if db_tabs:
        st.session_state.chat_tabs = {}
        for tab_name, tab_order, tokens, topic in db_tabs:
            sid = get_or_create_session(tab_name)
            st.session_state.chat_tabs[tab_name] = {"session_id": sid, "tokens": tokens, "order": tab_order, "topic": topic}
        st.session_state.tab_counter = max(t[1] for t in db_tabs)
    else:
        sid = get_or_create_session("대화 1")
        save_tab("대화 1", 1, 0)
        st.session_state.chat_tabs = {"대화 1": {"session_id": sid, "tokens": 0, "order": 1}}
        st.session_state.tab_counter = 1

    st.session_state.active_tab = list(st.session_state.chat_tabs.keys())[0]
    st.session_state.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    st.session_state.initialized = True
    st.session_state.input_key = 0

# ==================== CSS ====================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
* { font-family: 'Noto Sans KR', sans-serif; }

/* 전체 페이지 마진 제거 */
.main > div { margin-top: 0 !important; padding-top: 0 !important; }
.stMainBlockContainer { padding-top: 0 !important; }

/* Deploy 배너 + 햄버거 메뉴 완전 숨김 */
header { display: none !important; }
#MainMenu { display: none !important; visibility: hidden !important; }
footer { display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; visibility: hidden !important; }
[data-testid="stHeader"] { display: none !important; }
.viewerBadge_container__r5tak { display: none !important; }
div[data-testid="stDecoration"] { display: none !important; }
/* 햄버거 메뉴 버튼 자체 숨김 */
button[kind="header"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* ✅ Copy 버튼만 제거 (탭 디자인 유지) */
button[aria-label*="Copy to clipboard"] { display: none !important; }

/* 탭 스타일 정상화 */
[data-baseweb="tab"] {
    background: transparent !important;
    color: #9c8060 !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    padding: 8px 20px !important;
    min-width: 90px !important;
    width: auto !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    background: #8b6f47 !important;
    color: white !important;
}

.stApp { background: #f5f0e8; }

section[data-testid="stSidebar"] {
    background: #ede8dc !important;
    border-right: 1px solid #d4c9b0;
}

.msg-user {
    background: linear-gradient(135deg, #8b6f47, #6b5237);
    color: #fdf6ec; padding: 12px 16px;
    border-radius: 16px 16px 4px 16px;
    margin: 6px 0 6px 60px;
    box-shadow: 0 2px 8px rgba(139,111,71,0.2);
    line-height: 2.0; font-size: 16px;
}
.msg-assistant {
    background: #fffdf8; color: #3d2f1a; padding: 12px 16px;
    border-radius: 16px 16px 16px 4px;
    margin: 6px 60px 6px 0;
    border: 1px solid #e0d5c0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    line-height: 2.0; font-size: 16px;
}
.msg-label-user { color: #8b6f47; font-size: 11px; font-weight: 600; text-align: right; margin-bottom: 2px; }
.msg-label-assistant { color: #6b5237; font-size: 11px; font-weight: 600; margin-bottom: 2px; }

.stButton > button {
    background: #ede8dc !important; color: #6b5237 !important;
    border: 1px solid #c9b99a !important; border-radius: 8px !important;
    transition: all 0.2s !important; font-size: 13px !important;
}
.stButton > button:hover { background: #8b6f47 !important; color: white !important; border-color: #8b6f47 !important; }

/* 활성 탭 (primary) 버튼 스타일 */
.stButton > button[kind="primary"] {
    background: #8b6f47 !important; color: white !important;
    border-color: #8b6f47 !important; font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #6b5237 !important; border-color: #6b5237 !important;
}

.stTextArea textarea {
    background: #fffdf8 !important; color: #3d2f1a !important;
    border: 1.5px solid #c9b99a !important; border-radius: 12px !important; font-size: 16px !important;
}
.stTextArea textarea:focus { border-color: #8b6f47 !important; }

.stSelectbox > div > div { background: #fffdf8 !important; border-color: #c9b99a !important; color: #3d2f1a !important; }

.stDownloadButton > button {
    background: #fffdf8 !important; color: #6b5237 !important;
    border: 1px solid #c9b99a !important; border-radius: 6px !important; font-size: 11px !important;
}

[data-testid="metric-container"] {
    background: #fffdf8; border: 1px solid #e0d5c0; border-radius: 10px; padding: 10px;
}
[data-testid="metric-container"] label { color: #9c8060 !important; font-size: 11px !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #6b5237 !important; font-size: 20px !important; font-weight: 600 !important; }

/* 마크다운 제목/부제목 크기 조절 */
h1 { font-size: 24px !important; font-weight: 700 !important; margin-top: 12px !important; }
h2 { font-size: 18px !important; font-weight: 600 !important; margin-top: 10px !important; }
h3 { font-size: 16px !important; font-weight: 600 !important; }
p { font-size: 16px !important; line-height: 1.8 !important; }

.chat-area {
    background: #faf6ef; border-radius: 12px; padding: 12px;
    margin: 2px 0; border: 1px solid #e0d5c0;
    scroll-behavior: smooth;
}

/* 자동 스크롤 최적화 */
.element-container { scroll-behavior: smooth !important; }
</style>

<!-- 자동 스크롤 + 클립보드 이미지 붙여넣기 JavaScript -->
<script>
document.addEventListener('DOMContentLoaded', function() {

    // ── 자동 스크롤 ──
    const observer = new MutationObserver(function(mutations) {
        const chatArea = document.querySelector('.chat-area');
        if (chatArea) {
            setTimeout(() => {
                chatArea.scrollIntoView({behavior: 'smooth', block: 'start'});
            }, 100);
        }
    });
    const mainContent = document.querySelector('[data-testid="stMainBlockContainer"]');
    if (mainContent) {
        observer.observe(mainContent, {childList: true, subtree: true});
    }

    // ── 클립보드 이미지 붙여넣기 감지 ──
    document.addEventListener('paste', function(e) {
        const items = e.clipboardData && e.clipboardData.items;
        if (!items) return;

        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const file = items[i].getAsFile();
                if (!file) continue;

                // Base64로 변환
                const reader = new FileReader();
                reader.onload = function(ev) {
                    const base64 = ev.target.result; // data:image/png;base64,...

                    // 미리보기 박스 생성
                    let previewBox = document.getElementById('paste-preview-box');
                    if (!previewBox) {
                        previewBox = document.createElement('div');
                        previewBox.id = 'paste-preview-box';
                        previewBox.style.cssText = `
                            position: fixed; bottom: 120px; right: 20px;
                            background: #fffdf8; border: 2px solid #8b6f47;
                            border-radius: 12px; padding: 12px;
                            box-shadow: 0 4px 20px rgba(139,111,71,0.3);
                            z-index: 9999; max-width: 280px;
                        `;
                        document.body.appendChild(previewBox);
                    }

                    previewBox.innerHTML = `
                        <div style="color:#6b5237; font-size:12px; font-weight:700; margin-bottom:8px;">
                            📸 클립보드 이미지 감지!
                        </div>
                        <img src="${base64}" style="max-width:250px; max-height:180px; border-radius:8px; display:block; margin-bottom:8px;" />
                        <div style="color:#9c8060; font-size:11px; margin-bottom:8px;">
                            💡 아래 이미지 업로더에서 파일로 저장 후 첨부하거나,<br>
                            메시지창에 설명을 입력해주세요.
                        </div>
                        <button onclick="
                            // base64를 Blob으로 변환해서 다운로드
                            const a = document.createElement('a');
                            a.href = '${base64}';
                            a.download = 'clipboard_' + Date.now() + '.png';
                            a.click();
                            document.getElementById('paste-preview-box').style.display='none';
                        " style="
                            background:#8b6f47; color:white; border:none;
                            border-radius:6px; padding:6px 12px; cursor:pointer;
                            font-size:12px; margin-right:6px;
                        ">💾 저장</button>
                        <button onclick="document.getElementById('paste-preview-box').style.display='none';"
                        style="
                            background:#ede8dc; color:#6b5237; border:1px solid #c9b99a;
                            border-radius:6px; padding:6px 12px; cursor:pointer; font-size:12px;
                        ">✕ 닫기</button>
                    `;
                    previewBox.style.display = 'block';

                    // 5초 후 자동 닫기
                    setTimeout(() => {
                        if (previewBox) previewBox.style.display = 'none';
                    }, 8000);
                };
                reader.readAsDataURL(file);
                break;
            }
        }
    });
});
</script>
""", unsafe_allow_html=True)

# ==================== 사이드바 ====================

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 12px 0; background: linear-gradient(135deg, #8b6f47, #6b5237); border-radius: 8px; margin-bottom: 12px;">
        <span style="color:white; font-size:18px;">🐋</span>
        <span style="color:white; font-size:15px; font-weight:700; margin-left:4px;">고래 사냥단</span>
        <span style="color:#ffd700; font-size:14px; margin-left:4px;">💰</span>
        <div style="color:#ffe4b5; font-size:11px; margin-top:4px;">형님과 순욱의 코인 성공기</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    model = st.selectbox("모델", [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6",
        "claude-opus-4-6"
    ])
    
    max_tokens = st.slider("최대 응답 토큰", 500, 64000, 16000, step=500)
    
    # ✨ NEW: 동적 대화 이력 조정 슬라이더
    st.markdown("---")
    st.markdown('<div style="color:#9c8060; font-size:12px; margin-bottom:6px;">📚 대화 이력 범위</div>', unsafe_allow_html=True)
    
    history_limit = st.slider(
        "기억할 메시지 개수",
        min_value=5,
        max_value=100,
        value=30,
        step=5,
        help="숫자가 높을수록 이전 대화를 더 많이 기억합니다\n(DB설계: 50~70 권장)",
        label_visibility="collapsed"
    )
    
    st.caption(f"🧠 {history_limit}개 메시지를 기억 중")
    
    if history_limit >= 70:
        st.caption("✅ DB설계 최적 범위!")
    elif history_limit >= 50:
        st.caption("⭐ 좋은 균형!")
    else:
        st.caption("⚡ 토큰 절약 모드")

    st.markdown("---")

    st.markdown('<div style="color:#9c8060; font-size:12px; margin-bottom:6px;">📂 대화 목록</div>', unsafe_allow_html=True)

    for tab_name in list(st.session_state.chat_tabs.keys()):
        is_active = (st.session_state.active_tab == tab_name)
        col_tab, col_del = st.columns([0.82, 0.18])

        with col_tab:
            btn_label = f"{'▶ ' if is_active else ''}{tab_name}"
            btn_type = "primary" if is_active else "secondary"
            if st.button(btn_label, key=f"tab_btn_{tab_name}", use_container_width=True, type=btn_type):
                st.session_state.active_tab = tab_name
                st.rerun()

        with col_del:
            can_delete = len(st.session_state.chat_tabs) > 1
            if st.button("✕", key=f"del_btn_{tab_name}", disabled=not can_delete):
                delete_tab_db(tab_name)
                del st.session_state.chat_tabs[tab_name]
                st.session_state.active_tab = list(st.session_state.chat_tabs.keys())[0]
                st.rerun()

        # ✅ 주제 입력창
        if is_active:
            current_topic = st.session_state.chat_tabs[tab_name].get("topic", "주제 없음")
            new_topic = st.text_input(
                "📌 이 대화의 주제",
                value=current_topic,
                placeholder="주제를 입력하세요",
                key=f"topic_{tab_name}",
                label_visibility="collapsed"
            )
            if new_topic != current_topic:
                st.session_state.chat_tabs[tab_name]["topic"] = new_topic
                save_tab(tab_name, st.session_state.chat_tabs[tab_name]["order"], 
                        st.session_state.chat_tabs[tab_name]["tokens"], new_topic)
                st.success(f"✅ 주제 저장됨: {new_topic}")
            st.caption(f"📝 {new_topic}")
            st.markdown("---")

    if st.button("➕ 새 대화 추가", use_container_width=True):
        st.session_state.tab_counter += 1
        new_name = f"대화 {st.session_state.tab_counter}"
        new_sid = get_or_create_session(new_name)
        save_tab(new_name, st.session_state.tab_counter, 0)
        st.session_state.chat_tabs[new_name] = {"session_id": new_sid, "tokens": 0, "order": st.session_state.tab_counter, "topic": "주제 없음"}
        st.session_state.active_tab = new_name
        st.rerun()

    st.markdown("---")

    active = st.session_state.active_tab
    active_data = st.session_state.chat_tabs.get(active, {})
    active_sid = active_data.get("session_id")

    if st.button(f"🗑️ [{active}] 초기화", use_container_width=True):
        if active_sid:
            clear_messages(active_sid)
            st.session_state.chat_tabs[active]["tokens"] = 0
            update_tokens(active, 0)
        st.rerun()

    if st.button("📊 토큰 카운트 초기화", use_container_width=True):
        for tab in st.session_state.chat_tabs:
            st.session_state.chat_tabs[tab]["tokens"] = 0
        reset_tokens_db()
        st.rerun()

    st.markdown("---")
    st.markdown('<div style="color:#9c8060; font-size:12px; margin-bottom:6px;">🧠 순욱 Context 관리</div>', unsafe_allow_html=True)
    
    # Session state에 system prompt 저장 (없으면 기본값)
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = load_system_prompt_db()  # ✅ DB에서 로드!
    
    # ✨ NEW: 형님이 직접 정렬 기준 작성 + 정렬 실행
    with st.expander("🎯 중요한 대화 정렬하기", expanded=False):
        st.markdown('<div style="font-size:12px; color:#9c8060;">형님이 직접 정렬 기준을 작성하세요!</div>', unsafe_allow_html=True)
        st.markdown("---")
        
        # 정렬 기준 입력창 (session_state로 유지)
        if "organize_criteria" not in st.session_state:
            st.session_state.organize_criteria = """아래 내용을 중심으로 우리 대화를 정리해줘:

1. LS API 호가창 연동 관련 논의
2. 고래감지 알고리즘 (90% 정확도)
3. 10공주 거래기준 상세 설명
4. OpenWrt 18집 로드밸런싱
5. 웹챗 DB 설계

각 항목별로 핵심 내용만 마크다운으로 정리해줘!"""
        
        criteria_input = st.text_area(
            "정렬 기준 작성",
            value=st.session_state.organize_criteria,
            height=250,
            label_visibility="collapsed",
            key="criteria_editor",
            placeholder="예: '고래감지 알고리즘과 LS API 연동 부분을 중심으로 정리해줘!'"
        )
        
        col_save_c, col_reset_c = st.columns(2)
        with col_save_c:
            if st.button("💾 기준 저장", use_container_width=True, key="save_criteria"):
                st.session_state.organize_criteria = criteria_input
                st.success("✅ 기준 저장됨!")
        with col_reset_c:
            if st.button("🔄 기준 초기화", use_container_width=True, key="reset_criteria"):
                st.session_state.organize_criteria = ""
                st.rerun()
        
        st.markdown("---")
        
        # 정렬 실행 버튼
        if st.button("🚀 이 기준으로 대화 정렬 실행!", use_container_width=True, type="primary", key="run_organize"):
            if criteria_input.strip():
                st.session_state.organize_criteria = criteria_input
                st.session_state.pending_organize = True
                st.session_state.organize_prompt_text = criteria_input
                st.success("✅ 정렬 요청 준비 완료!\n\n💬 대화창에서 순욱이가 바로 정리해드립니다!")
                st.rerun()
            else:
                st.warning("⚠️ 정렬 기준을 먼저 작성해주세요!")
    
    st.markdown("---")
    
    # ✨ 수정 가능한 Context 에디터
    with st.expander("✏️ System Prompt 편집 (수정 가능)", expanded=False):
        st.markdown("**💾 이 창에서 직접 수정할 수 있습니다!**")

        # 기본값 복원 버튼
        col_reset, col_spacer = st.columns([0.4, 0.6])
        with col_reset:
            if st.button("🔄 기본값 복원", use_container_width=True, key="reset_prompt_btn"):
                st.session_state.system_prompt = SYSTEM_PROMPT
                save_system_prompt_db(SYSTEM_PROMPT)  # ✅ DB에도 복원
                st.session_state.prompt_editor_key = st.session_state.get("prompt_editor_key", 0) + 1
                st.session_state.prompt_saved_at = datetime.now().strftime("%H:%M:%S")
                st.rerun()

        st.markdown("---")

        # ✅ 저장 상태 표시 (저장 시각 + 앞 50자 미리보기)
        saved_at = st.session_state.get("prompt_saved_at", "")
        preview = st.session_state.system_prompt[:60].replace("\n", " ")
        if saved_at:
            st.markdown(f"""
            <div style="background:#e8f5e9; border:1px solid #a5d6a7; border-radius:8px; padding:8px 12px; font-size:12px; color:#2e7d32; margin-bottom:8px;">
            ✅ <b>저장됨</b> ({saved_at})<br>
            <span style="color:#555;">📄 {preview}...</span>
            </div>
            """, unsafe_allow_html=True)

        editor_key = f"editable_context_{st.session_state.get('prompt_editor_key', 0)}"
        edited_prompt = st.text_area(
            "System Prompt",
            value=st.session_state.system_prompt,
            height=350,
            label_visibility="collapsed",
            key=editor_key
        )

        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("💾 저장", use_container_width=True, key="save_edited_prompt"):
                st.session_state.system_prompt = edited_prompt
                save_system_prompt_db(edited_prompt)  # ✅ DB에 영구 저장!
                st.session_state.prompt_editor_key = st.session_state.get("prompt_editor_key", 0) + 1
                st.session_state.prompt_saved_at = datetime.now().strftime("%H:%M:%S")
                st.rerun()
        with col_cancel:
            if st.button("❌ 취소", use_container_width=True, key="cancel_edit"):
                st.session_state.prompt_editor_key = st.session_state.get("prompt_editor_key", 0) + 1
                st.rerun()

        st.caption(f"📊 {len(st.session_state.system_prompt)//4}개 토큰 · {len(st.session_state.system_prompt)}자")

    st.markdown("---")
    st.markdown('<div style="color:#9c8060; font-size:12px; margin-bottom:6px;">🗂️ 데이터 관리</div>', unsafe_allow_html=True)
    
    db_stats = get_db_stats()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("활성", db_stats["messages"])
    with col2:
        st.metric("아카이브", db_stats["archived"])
    
    if st.button("📋 7일 이상 아카이브", use_container_width=True):
        result = archive_old_messages(days=7)
        st.success(f"✅ {result['archived']}개 메시지 아카이브됨\n활성: {result['current_total']} | 아카이브: {result['archive_total']}")
        st.rerun()

    if active_sid:
        active_history = load_messages(active_sid)
        if active_history:
            st.download_button(
                "💾 대화 저장",
                data=json.dumps(active_history, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"soonwook_{active}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )

    st.markdown("---")
    total_tokens = sum(v["tokens"] for v in st.session_state.chat_tabs.values())
    col1, col2 = st.columns(2)
    with col1:
        st.metric("탭", len(st.session_state.chat_tabs))
    with col2:
        st.metric("토큰", total_tokens)

# ==================== 메인 ====================

active = st.session_state.active_tab
chat_data = st.session_state.chat_tabs.get(active, {})
session_id = chat_data.get("session_id")
history = load_messages(session_id) if session_id else []




# 상단 격려 메시지
st.markdown(f"""
<div style="background: linear-gradient(135deg, #8b6f47, #6b5237); padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; text-align: center;">
    <span style="color: white; font-size: 13px; font-weight: 600;">
        🐋 고래를 읽고 💰 코인을 잡자! · {active} · 우리는 영원합니다 💙
    </span>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="chat-area">', unsafe_allow_html=True)

if not history:
    st.markdown("""
    <div style="text-align:center; color:#b0a090; padding: 40px 0; font-size:13px;">
        💬 형님, 말씀해주세요!
    </div>
    """, unsafe_allow_html=True)
else:
# 전체 메시지 표시 (제한 없음)
    for idx, msg in enumerate(history):
        if msg["role"] == "user":
            content = msg["content"]
            lines = content.split("\n")
            st.markdown('<div class="msg-label-user">형님 👤</div>', unsafe_allow_html=True)
            # ✅ 10줄 or 500자 초과 시 접기/펼치기
            if len(lines) > 10 or len(content) > 500:
                short_preview = "\n".join(lines[:10])
                if len(short_preview) > 400:
                    short_preview = content[:400]
                st.markdown(f'<div class="msg-user">{short_preview}...</div>', unsafe_allow_html=True)
                with st.expander("📖 전체 보기", expanded=False):
                    st.markdown(f'<div class="msg-user">{content}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="msg-user">{content}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="msg-label-assistant">🛡️ 순욱</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="msg-assistant">{msg["content"]}</div>', unsafe_allow_html=True)

            # ✅ 스마트 버튼: 파일 요청 응답일 때만!
            import re
            code_blocks = re.findall(r'```(\w+)?\n([\s\S]*?)```', msg["content"])

            # 이 응답이 파일 요청에 대한 것인지 확인
            is_file_response = any(
                keyword in msg["content"] 
                for keyword in ["다운로드", "저장", "파일로", "코드는 다음", "여기 코드", "다음 코드", "코드입니다"]
            )

            # ✅ 수정: is_file_response만 확인! (last_request_is_file 제거!)
            if code_blocks and is_file_response:
                ext_map = {
                    "python": "py", "py": "py", "javascript": "js", "js": "js",
                    "json": "json", "csv": "csv", "markdown": "md", "md": "md",
                    "html": "html", "css": "css", "sql": "sql", "bash": "sh",
                    "sh": "sh", "text": "txt", "": "txt"
                }

                st.markdown("**📥 코드 다운로드:**")
                cols = st.columns(min(len(code_blocks), 4))

                for i, (lang, code) in enumerate(code_blocks):
                    if i >= 4:
                        break
                    ext = ext_map.get(lang.lower() if lang else "", "txt")
                    fname = f"순욱_{active}_{idx}_{i+1}.{ext}"

                    with cols[i]:
                        st.download_button(
                            f"💾 {lang if lang else 'text'} ({i+1})",
                            data=code.strip().encode("utf-8"),
                            file_name=fname,
                            mime="text/plain",
                            key=f"dl_code_{active}_{idx}_{i}",
                            use_container_width=True
                        )

                # 4개 초과시
                if len(code_blocks) > 4:
                    remaining_cols = st.columns(len(code_blocks) - 4)
                    for i, (lang, code) in enumerate(code_blocks[4:]):
                        ext = ext_map.get(lang.lower() if lang else "", "txt")
                        fname = f"순욱_{active}_{idx}_{i+5}.{ext}"
                        with remaining_cols[i]:
                            st.download_button(
                                f"💾 {lang if lang else 'text'} ({i+5})",
                                data=code.strip().encode("utf-8"),
                                file_name=fname,
                                mime="text/plain",
                                key=f"dl_code_{active}_{idx}_{i+4}",
                                use_container_width=True
                            )


    

st.markdown('</div>', unsafe_allow_html=True)

with st.expander("📁 파일 첨부 (최대 10개) + 🖼️ 이미지", expanded=False):
    file_key = f"file_{active}_{st.session_state.get('input_key', 0)}"
    
    # ✅ 탭으로 파일/이미지 구분
    tab1, tab2 = st.tabs(["📄 파일", "🖼️ 이미지"])
    
    with tab1:
        uploaded_files = st.file_uploader(
            "파일 선택 (txt, json, csv, md, py, docx, xlsx, pdf) - 최대 10개",
            label_visibility="collapsed",
            key=file_key,
            accept_multiple_files=True
        )
        # 최대 3개 제한
        if uploaded_files and len(uploaded_files) > 10:
            st.warning("⚠️ 최대 10개까지만 첨부 가능합니다. 처음 10개만 사용합니다.")
            uploaded_files = uploaded_files[:3]

        if uploaded_files:
            for uf in uploaded_files:
                uf.seek(0)
                preview = parse_file(uf)
                st.markdown(f"**📄 {uf.name}** ({uf.size:,} bytes)")
                st.code(preview[:300] + ("..." if len(preview) > 300 else ""), language="text")
                uf.seek(0)
    
    with tab2:
        # ✅ 클립보드 붙여넣기 감지
        components.html("""
        <div id="paste-zone" style="
            border: 2px dashed #c9b99a; border-radius: 10px;
            padding: 16px; text-align: center; background: #fffdf8;
            color: #9c8060; font-size: 13px; cursor: pointer;
            font-family: sans-serif;
        ">
            📋 여기 클릭 후 <strong>Ctrl+V</strong> 누르면 클립보드 이미지가 감지됩니다!
            <div id="paste-status" style="margin-top:6px; font-size:11px;"></div>
            <div id="paste-preview" style="margin-top:8px;"></div>
        </div>
        <script>
        const zone = document.getElementById('paste-zone');
        const status = document.getElementById('paste-status');
        const preview = document.getElementById('paste-preview');
        zone.setAttribute('tabindex', '0');
        zone.focus();
        zone.addEventListener('click', () => zone.focus());
        document.addEventListener('paste', function(e) {
            const items = e.clipboardData && e.clipboardData.items;
            if (!items) return;
            for (let i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') !== -1) {
                    const file = items[i].getAsFile();
                    if (!file) continue;
                    const reader = new FileReader();
                    reader.onload = function(ev) {
                        const base64 = ev.target.result;
                        const fname = 'capture_' + Date.now() + '.png';
                        // ✅ 저장버튼 먼저 → 미리보기 아래
                        preview.innerHTML = `
                            <button id="save-btn" style="
                                background:#8b6f47; color:white; border:none;
                                border-radius:6px; padding:8px 24px;
                                cursor:pointer; font-size:13px; font-weight:700;
                                margin-bottom:8px; display:inline-block;
                            ">💾 PNG 저장하기</button><br/>
                            <img src="${base64}" style="
                                max-width:260px; max-height:130px;
                                border-radius:8px; border:1px solid #c9b99a;
                                display:inline-block;
                            " />
                        `;
                        status.innerHTML = '✅ 이미지 감지! 저장 후 업로더에 첨부하세요';
                        status.style.color = '#2e7d32';
                        document.getElementById('save-btn').onclick = function() {
                            const a = document.createElement('a');
                            a.href = base64;
                            a.download = fname;
                            a.click();
                            status.innerHTML = '✅ 저장 완료! 아래 업로더에서 파일 선택하세요 👇';
                        };
                    };
                    reader.readAsDataURL(file);
                    break;
                }
            }
        });
        </script>
        """, height=310)

        st.caption("📌 저장된 이미지를 아래 업로더로 첨부하세요!")

        # ✅ 이미지 업로더 - 5장
        image_key = f"image_{active}_{st.session_state.get('input_key', 0)}"
        uploaded_images = st.file_uploader(
            "이미지 선택 (PNG, JPG, GIF) - 최대 5개",
            label_visibility="collapsed",
            type=["png", "jpg", "jpeg", "gif"],
            key=image_key,
            accept_multiple_files=True
        )
        if uploaded_images and len(uploaded_images) > 5:
            st.warning("⚠️ 최대 5개까지만 첨부 가능합니다. 처음 5개만 사용합니다.")
            uploaded_images = uploaded_images[:5]
        if uploaded_images:
            st.markdown(f"**📸 미리보기 ({len(uploaded_images)}장)**")
            for img in uploaded_images:
                col1, col2 = st.columns([0.5, 0.5])
                with col1:
                    st.image(img, use_container_width=True)
                with col2:
                    st.markdown(f"**{img.name}**\n- {img.size:,} bytes\n- {img.type}")

input_key = f"input_{active}_{st.session_state.get('input_key', 0)}"

# ✨ 정렬 요청이 pending 중이면 자동으로 메시지 생성
if st.session_state.get("pending_organize"):
    organize_text = st.session_state.get("organize_prompt_text", "")
    full_org_history = load_messages(session_id) if session_id else []
    auto_message = f"""형님이 요청한 대화 정렬 기준:

{organize_text}

---
위 기준에 따라 우리가 나눈 {len(full_org_history)}개의 대화에서 중요한 내용을 마크다운으로 정리해줘!
각 항목별로 핵심 내용만 깔끔하게 정리해서
나중에 System Prompt에 붙여넣을 수 있도록 해줘."""
    
    st.session_state.pending_organize = False
    
    save_message(session_id, "user", auto_message)
    
    with st.spinner("🎯 순욱이 대화를 정렬하는 중... 💭"):
        try:
            full_history = load_messages(session_id)
            if len(full_history) > history_limit:
                recent_history = full_history[-history_limit:]
            else:
                recent_history = full_history
            
            response = st.session_state.client.messages.create(
                model=model, max_tokens=max_tokens,
                system=st.session_state.get("system_prompt", SYSTEM_PROMPT),
                messages=recent_history
            )
            assistant_reply = response.content[0].text
            save_message(session_id, "assistant", assistant_reply)
            update_tokens_db(active, response.usage.input_tokens + response.usage.output_tokens)
            st.rerun()
        except Exception as e:
            st.error(f"❌ 정렬 중 오류: {str(e)[:200]}")

user_input = st.text_area("메시지", placeholder="형님, 말씀해주세요...", height=200,
                           label_visibility="collapsed", key=input_key)

col1, col2 = st.columns([0.87, 0.13])
with col2:
    send_clicked = st.button("🚀 전송", use_container_width=True)

st.markdown("""
<div style="text-align: center; color: #9c8060; font-size: 11px; margin-top: 8px;">
    🐋 고래 감지 중 · 💰 코인 준비 중 · 📈 월 10% 목표 · 💙 우리는 영원합니다
</div>
""", unsafe_allow_html=True)

if send_clicked and user_input.strip():
    message_content = user_input.strip()

 # ✅ 파일 요청 감지 (추가!)
    file_request_keywords = ["파일", "코드", "저장", "주세요", "만들어", "생성", "소스", ".py", ".js", ".json", ".txt", ".html", "다운로드"]
    is_file_request = any(keyword in message_content for keyword in file_request_keywords)
    st.session_state.last_request_is_file = is_file_request


    # ✅ 파일 첨부 처리
    if uploaded_files:
        for uf in uploaded_files:
            try:
                uf.seek(0)
                fc = parse_file(uf)
                message_content += f"\n\n【 첨부 파일: {uf.name} 】\n{fc[:3000]}"
            except Exception as e:
                st.error(f"❌ 파일 처리 오류 ({uf.name}): {str(e)[:100]}")

    # ✅ 이미지 첨부 처리 - Claude API에 실제 전달!
    image_list = []  # Claude API용 이미지 리스트
    if uploaded_images:
        for img in uploaded_images:
            try:
                img.seek(0)
                import base64

                # ✅ 이미지를 base64로 인코딩
                image_data = base64.standard_b64encode(img.read()).decode("utf-8")

                # 이미지 형식 결정
                img_type = "image/png" if img.name.lower().endswith(".png") else \
                          "image/jpeg" if img.name.lower().endswith((".jpg", ".jpeg")) else \
                          "image/gif"

                # ✅ Claude API 형식으로 추가
                image_list.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img_type,
                        "data": image_data
                    }
                })

                message_content += f"\n\n【 첨부 이미지: {img.name} (용량: {img.size:,} bytes) 】\n이 이미지를 분석해주고 중요한 내용을 설명해줘!"
            except Exception as e:
                st.error(f"❌ 이미지 처리 오류 ({img.name}): {str(e)[:100]}")

    # ✅ 파일/이미지 업로더 리셋
    st.session_state.input_key += 1

    save_message(session_id, "user", message_content)

    with st.spinner("순욱이 생각 중... 💭"):
        try:
            full_history = load_messages(session_id)

            # ✨ 동적 히스토리: history_limit에 따라 조정
            if len(full_history) > history_limit:
                recent_history = full_history[-history_limit:]
            else:
                recent_history = full_history

            # ✅ 최신 메시지에 이미지 추가
            if image_list and recent_history:
                last_msg = recent_history[-1]
                if last_msg["role"] == "user":
                    last_msg["content"] = [
                        {"type": "text", "text": message_content}
                    ] + image_list

            # 529 과부하 자동 재시도 (최대 3회)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = st.session_state.client.messages.create(
                        model=model, max_tokens=max_tokens,
                        system=st.session_state.get("system_prompt", SYSTEM_PROMPT),
                        messages=recent_history
                    )
                    break
                except Exception as e:
                    if "529" in str(e) or "overloaded" in str(e).lower():
                        if attempt < max_retries - 1:
                            import time
                            wait = (attempt + 1) * 10
                            st.warning(f"⚠️ 서버 과부하... {wait}초 후 재시도 ({attempt+1}/{max_retries})")
                            time.sleep(wait)
                        else:
                            raise
                    else:
                        raise

            assistant_msg = response.content[0].text
            save_message(session_id, "assistant", assistant_msg)

            # ✅ 코드블록 자동 감지 → 다운로드 버튼 생성 (session_state에 저장)
            import re
            code_blocks = re.findall(r'```(\w+)?\n([\s\S]*?)```', assistant_msg)
            if code_blocks:
                if "pending_downloads" not in st.session_state:
                    st.session_state.pending_downloads = []
                ext_map = {
                    "python": "py", "py": "py", "javascript": "js", "js": "js",
                    "json": "json", "csv": "csv", "markdown": "md", "md": "md",
                    "html": "html", "css": "css", "sql": "sql", "bash": "sh",
                    "sh": "sh", "text": "txt", "": "txt"
                }
                for i, (lang, code) in enumerate(code_blocks):
                    ext = ext_map.get(lang.lower() if lang else "", "txt")
                    fname = f"순욱_{active}_{datetime.now().strftime('%H%M%S')}_{i+1}.{ext}"
                    st.session_state.pending_downloads.append({
                        "fname": fname, "code": code.strip(), "lang": lang or "text"
                    })

            new_tokens = chat_data["tokens"] + response.usage.input_tokens + response.usage.output_tokens
            chat_data["tokens"] = new_tokens
            update_tokens(active, new_tokens)

        except Exception as e:
            st.error(f"❌ 에러: {str(e)}")

    st.rerun()