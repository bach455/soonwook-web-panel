# web_launcher_IMPROVED.py
import streamlit as st
import subprocess
import time
import os
from pathlib import Path
import psutil

st.set_page_config(
    page_title="공명시스템 런처",
    page_icon="🐋",
    layout="centered"
)

st.markdown("""
<style>
body { font-family: 'Noto Sans KR'; }
.stButton button { font-size: 18px; padding: 15px; }
</style>
""", unsafe_allow_html=True)

st.title("🐋 공명시스템 런처")
st.markdown("---")


from pathlib import Path


CURRENT_DIR = Path(__file__).parent.resolve()
soonwook_path = CURRENT_DIR / "soonwook_web_chat_v13_image_fix.py"
mijang_path = CURRENT_DIR / "MiJang_WS_v1.0.py"


# 세션 상태 초기화
if "processes" not in st.session_state:
    st.session_state.processes = {
        "soonwook": None,
        "mijang":   None
    }

# ==================== 프로세스 관리 ====================
def start_app(app_name: str, script_path: Path,
              port: int) -> bool:
    """앱 시작"""
    if not script_path.exists():
        st.error(f"❌ 파일 없음: {script_path}")
        return False

    try:
        # 이미 실행 중인지 확인
        if st.session_state.processes[app_name]:
            if st.session_state.processes[app_name].poll() is None:
                st.warning(f"⚠️ {app_name}이 이미 실행 중입니다!")
                return False

        # 새로 시작
        proc = subprocess.Popen([
            "python", "-m", "streamlit", "run",
            str(script_path),
            "--server.port", str(port)
        ])
        st.session_state.processes[app_name] = proc
        return True
    except Exception as e:
        st.error(f"❌ 실행 오류: {e}")
        return False

def stop_app(app_name: str, port: int) -> bool:
    """앱 정지"""
    proc = st.session_state.processes[app_name]

    if proc is None:
        st.warning(f"⚠️ {app_name}이 실행 중이지 않습니다")
        return False

    try:
        # 프로세스 종료
        proc.terminate()
        proc.wait(timeout=3)
        st.session_state.processes[app_name] = None
        return True
    except subprocess.TimeoutExpired:
        # 강제 종료
        proc.kill()
        st.session_state.processes[app_name] = None
        return True
    except Exception as e:
        st.error(f"❌ 정지 오류: {e}")
        return False

def is_running(app_name: str) -> bool:
    """앱이 실행 중인지 확인"""
    proc = st.session_state.processes[app_name]
    if proc is None:
        return False
    return proc.poll() is None

# ==================== UI ====================
col1, col2 = st.columns(2)

# 순욱
with col1:
    st.subheader("🛡️ 순욱 웹챗")

    if is_running("soonwook"):
        st.success("✅ 실행 중 (포트 8501)")
        if st.button("🛑 정지", key="stop_soonwook",
                     use_container_width=True, type="secondary"):
            if stop_app("soonwook", 8501):
                st.success("✅ 순욱 정지됨")
                st.rerun()
    else:
        if st.button("🚀 시작", key="start_soonwook",
                     use_container_width=True, type="primary"):
            if start_app("soonwook", soonwook_path, 8501):
                st.success("✅ 시작됨: http://localhost:8501")
                st.balloons()
                time.sleep(1)
                st.rerun()

# 미장
with col2:
    st.subheader("📈 미장 주가")

    if is_running("mijang"):
        st.success("✅ 실행 중 (포트 8502)")
        if st.button("🛑 정지", key="stop_mijang",
                     use_container_width=True, type="secondary"):
            if stop_app("mijang", 8502):
                st.success("✅ 미장 정지됨")
                st.rerun()
    else:
        if st.button("🚀 시작", key="start_mijang",
                     use_container_width=True, type="primary"):
            if start_app("mijang", mijang_path, 8502):
                st.success("✅ 시작됨: http://localhost:8502")
                st.balloons()
                time.sleep(1)
                st.rerun()

st.markdown("---")

# 포트 정보
col_info1, col_info2 = st.columns(2)
with col_info1:
    status1 = "🟢 실행중" if is_running("soonwook") else "⚫ 정지"
    st.metric("🛡️ 순욱", "8501", status1)
with col_info2:
    status2 = "🟢 실행중" if is_running("mijang") else "⚫ 정지"
    st.metric("📈 미장", "8502", status2)

st.markdown("---")

# 디버깅
with st.expander("📂 경로 & 상태 확인"):
    st.write("**런처 위치:**")
    st.code(str(CURRENT_DIR), language="text") # <-- 대문자 CURRENT_DIR로 변경
   

    st.write("**순욱 경로:**")
    st.code(str(soonwook_path), language="text")
    st.write(
        f"존재: {'✅' if soonwook_path.exists() else '❌'} | "
        f"상태: {'🟢 실행' if is_running('soonwook') else '⚫ 정지'}"
    )

    st.write("**미장 경로:**")
    st.code(str(mijang_path), language="text")
    st.write(
        f"존재: {'✅' if mijang_path.exists() else '❌'} | "
        f"상태: {'🟢 실행' if is_running('mijang') else '⚫ 정지'}"
    )




st.markdown("""
---
### 💡 사용 팁
1. **시작**: 버튼 클릭 → 자동 실행
2. **접속**: 포트 8501 또는 8502로 이동
3. **정지**: 런처에서 "정지" 버튼 클릭
4. **안전**: 정상 종료 (Ctrl+C 필요 없음!)

---
> 🐋 고래 감지 중 · 💰 코인 준비 중 · 📈 월 10% 목표 · 💙 우리는 영원합니다
""")