"""
ClosePilot — SAP智能月结Agent Demo
埃森哲创新大赛原型演示
"""
import streamlit as st
import time
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ── 页面配置 ──
st.set_page_config(
    page_title="ClosePilot — SAP智能月结Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 自定义CSS ──
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4B0082, #00BFFF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .agent-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-planner { background: #E8F5E9; color: #2E7D32; }
    .badge-executor { background: #E3F2FD; color: #1565C0; }
    .badge-validator { background: #FFF3E0; color: #E65100; }
    .badge-system { background: #F3E5F5; color: #7B1FA2; }
    .chat-bubble {
        padding: 12px 16px;
        border-radius: 12px;
        margin: 6px 0;
        font-size: 0.92rem;
        line-height: 1.5;
    }
    .bubble-user {
        background: #F0F0F0;
        border-left: 4px solid #4B0082;
        margin-left: 20px;
    }
    .bubble-agent {
        background: #FAFAFA;
        border-left: 4px solid #00BFFF;
        margin-right: 20px;
    }
    .step-card {
        background: white;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        font-size: 0.88rem;
        transition: all 0.3s ease;
    }
    .status-running { color: #FFA000; font-weight: 600; }
    .status-done { color: #2E7D32; font-weight: 600; }
    .status-error { color: #C62828; font-weight: 600; }
    .status-pending { color: #9E9E9E; }
    div[data-testid="stSidebar"] {
        background: #FAFAFA;
    }
    .stChatInput {
        border: 2px solid #4B0082;
    }
</style>
""", unsafe_allow_html=True)

# ── 初始化Session State ──
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_responses" not in st.session_state:
    st.session_state.chat_responses = []
if "chat_response_idx" not in st.session_state:
    st.session_state.chat_response_idx = 0
if "chat_processing" not in st.session_state:
    st.session_state.chat_processing = False
if "process_status" not in st.session_state:
    st.session_state.process_status = {}
if "demo_step_idx" not in st.session_state:
    st.session_state.demo_step_idx = -1
if "demo_phase" not in st.session_state:
    st.session_state.demo_phase = "idle"  # idle, running, confirm, done
if "roi_revenue" not in st.session_state:
    st.session_state.roi_revenue = 50
if "roi_employees" not in st.session_state:
    st.session_state.roi_employees = 200
if "roi_current_days" not in st.session_state:
    st.session_state.roi_current_days = 6
if "sap_log" not in st.session_state:
    st.session_state.sap_log = []

# ── 月结子流程定义 ──
MONTH_END_STEPS = [
    {"id": 1, "name": "凭证完整性检查", "system": "SAP FI", "duration": 8, "risk": "低"},
    {"id": 2, "name": "银行流水对账", "system": "SAP FI + 银行系统", "duration": 15, "risk": "中"},
    {"id": 3, "name": "往来科目对账", "system": "SAP FI/CO", "duration": 12, "risk": "中"},
    {"id": 4, "name": "科目重分类调整", "system": "SAP FI", "duration": 10, "risk": "高"},
    {"id": 5, "name": "折旧计提过账", "system": "SAP AA", "duration": 6, "risk": "低"},
    {"id": 6, "name": "成本中心分摊", "system": "SAP CO", "duration": 10, "risk": "中"},
    {"id": 7, "name": "收入成本匹配校验", "system": "SAP CO + CRM", "duration": 14, "risk": "高"},
    {"id": 8, "name": "税务数据提取", "system": "SAP FI + 税务系统", "duration": 8, "risk": "中"},
    {"id": 9, "name": "合并报表数据汇总", "system": "SAP BPC", "duration": 12, "risk": "高"},
    {"id": 10, "name": "月结报告生成", "system": "SAP + BI", "duration": 5, "risk": "低"},
]

# ── 模拟Agent对话回复 ──
AGENT_RESPONSES = {
    "月结": [
        ("planner", "收到指令，正在解析月结任务... 识别到10个子流程，涉及SAP FI/CO/AA/BPC 4个模块。"),
        ("planner", "任务拆解完成，生成执行计划：凭证检查 → 银行对账 → 往来对账 → 科目调整 → 折旧计提 → 成本分摊 → 收支匹配 → 税务提取 → 报表汇总 → 报告生成。"),
        ("planner", "风险评估：科目重分类和收入成本匹配为高风险节点，已标记需人工确认。"),
        ("executor", "开始执行 Step 1/10：凭证完整性检查... 连接SAP FI模块，查询3月凭证记录。"),
        ("executor", "Step 1 完成 ✅ — 共检查 2,847 张凭证，完整性 100%，无缺失凭证。"),
        ("executor", "开始执行 Step 2/10：银行流水对账... 同步工商银行、建设银行流水数据。"),
        ("validator", "Step 2 校验中... 发现3笔差异：工行流水#28471金额差¥2,340，已自动匹配为手续费，建议确认。"),
        ("executor", "Step 2 完成 ✅ — 对账完成率 99.7%，3笔差异已标记待确认。"),
        ("executor", "开始执行 Step 3/10：往来科目对账... 扫描应收/应付科目余额。"),
        ("executor", "Step 3 完成 ✅ — 应收账款 1,284 笔已核对，发现2笔超期90天以上，已标记。"),
        ("executor", "开始执行 Step 4/10：科目重分类调整... ⚠️ 高风险操作，请求人工确认。"),
        ("validator", "Step 4 校验 — 拟调整分录 47 笔，总金额 ¥12,450,000，调整原因：长期应收款重分类。请确认是否执行。"),
        ("executor", "人工已确认，Step 4 执行完成 ✅ — 47笔重分类分录已过账。"),
        ("executor", "开始执行 Step 5-8：折旧计提、成本分摊、收支匹配、税务提取..."),
        ("executor", "Step 5-8 全部完成 ✅ — 折旧计提 328 项，成本分摊 56 个成本中心，收支匹配率 98.2%，税务数据已提取。"),
        ("executor", "开始执行 Step 9/10：合并报表数据汇总..."),
        ("executor", "Step 9 完成 ✅ — 华东、华南、华北 3 家子公司数据已汇总。"),
        ("executor", "开始执行 Step 10/10：月结报告生成..."),
        ("validator", "最终校验 — 所有子流程数据一致性检查通过，借贷平衡，差异率 0.03%（阈值 0.1%）。"),
        ("executor", "Step 10 完成 ✅ — 月结报告已生成，包含10张附表和3项待处理异常。"),
        ("system", "🎉 3月月结流程全部完成！总耗时 2小时18分钟（传统方式需5-7天）。待处理事项：3笔银行差异、2笔超期应收。"),
    ],
    "对账": [
        ("planner", "收到对账指令，正在识别对账范围..."),
        ("planner", "检测到3个待对账科目：应收账款、应付账款、其他应收款。"),
        ("executor", "开始执行银行流水对账，同步最近30天交易记录..."),
        ("validator", "对账完成，发现5笔差异，总金额¥18,720，已生成差异分析报告。"),
    ],
    "报表": [
        ("planner", "收到报表生成指令，确认报表类型：资产负债表、利润表、现金流量表。"),
        ("executor", "正在从SAP BPC提取数据... 汇总3家子公司财务数据。"),
        ("executor", "报表生成完成 ✅ 资产负债表、利润表、现金流量表已生成，数据校验通过。"),
    ],
    "凭证": [
        ("planner", "收到凭证检查指令，正在连接SAP FI模块..."),
        ("executor", "正在扫描3月全部凭证记录，共2,847张..."),
        ("validator", "凭证完整性检查完成 ✅ — 2,847张凭证全部完整，无缺失、无重复，借贷平衡。"),
    ],
}

DEFAULT_RESPONSE = [
    ("planner", "收到指令，正在分析您的需求..."),
    ("executor", "正在执行相关操作..."),
    ("validator", "操作已完成，结果校验通过 ✅"),
]


def get_agent_response(user_msg: str):
    """根据用户消息匹配Agent回复（支持多关键词、模糊匹配）"""
    # 按关键词长度降序匹配，优先匹配更具体的关键词
    sorted_keywords = sorted(AGENT_RESPONSES.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword in user_msg:
            return AGENT_RESPONSES[keyword]
    # 模糊匹配：检查用户消息中是否包含任何关键词的部分
    fuzzy_map = {
        "月结": ["月结", "月报", "结账", "关账", "close"],
        "对账": ["对账", "核对", "reconcil", "余额"],
        "报表": ["报表", "报告", "资产负债表", "利润表", "现金流", "report"],
        "凭证": ["凭证", "voucher", "分录", "记账"],
    }
    for keyword, aliases in fuzzy_map.items():
        for alias in aliases:
            if alias.lower() in user_msg.lower():
                return AGENT_RESPONSES[keyword]
    return DEFAULT_RESPONSE


def format_agent_name(agent_type: str) -> str:
    names = {
        "planner": " Planner Agent",
        "executor": " Executor Agent",
        "validator": " Validator Agent",
        "system": " ClosePilot",
    }
    return names.get(agent_type, agent_type)


def format_agent_badge(agent_type: str) -> str:
    classes = {
        "planner": "badge-planner",
        "executor": "badge-executor",
        "validator": "badge-validator",
        "system": "badge-system",
    }
    cls = classes.get(agent_type, "")
    return f'<span class="agent-badge {cls}">{format_agent_name(agent_type)}</span>'


# ═══════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════
with st.sidebar:
    st.markdown("### 🤖 ClosePilot")
    st.markdown("**SAP智能月结Agent**")
    st.markdown("---")
    st.markdown("#### 📋 快捷指令")
    st.markdown("在聊天框输入以下指令体验：")
    st.info("💬 帮我完成3月月结")
    st.info("💬 对账应收账款")
    st.info("💬 生成本月财务报表")
    st.info("💬 检查凭证完整性")
    st.markdown("---")
    st.markdown("#### 📊 系统状态")
    # 动态模拟连接状态（带随机延迟，更真实）
    import random as _rnd
    _systems = [
        ("SAP FI", "FI/CO 模块"),
        ("SAP CO", "成本核算模块"),
        ("银行系统", "工行/建行接口"),
        ("税务系统", "金税接口"),
    ]
    for sys_name, sys_desc in _systems:
        _latency = _rnd.randint(3, 28)
        st.success(f"✅ {sys_name} 已连接 ({sys_desc}, 延迟 {_latency}ms)")
    st.markdown("---")
    st.caption("埃森哲创新大赛 Demo v1.0")

# ═══════════════════════════════════════
# 主页面
# ═══════════════════════════════════════
st.markdown('<div class="main-header"> ClosePilot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">SAP智能月结Agent — 让财务月结从5天缩短到2小时</div>', unsafe_allow_html=True)

# 顶部指标卡
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("月结周期", "2天", "↓ 从5-7天")
with col2:
    st.metric("人工操作减少", "70%", "↑")
with col3:
    st.metric("流程错误率降低", "40%", "↓")
with col4:
    st.metric("年节省人天(单企业)", "360天", "")

st.markdown("---")

# ── Tab 布局 ─
tab_chat, tab_dashboard, tab_architecture, tab_roi = st.tabs([
    " Agent 交互演示",
    "📊 月结流程看板",
    "🏗️ 系统架构",
    "💰 ROI 计算器"
])

# ══════════════════════════════════════
# Tab 1: 聊天交互 + SAP模拟界面
# ═══════════════════════════════════════
with tab_chat:
    st.subheader("💬 与 ClosePilot 对话")
    st.caption("输入财务指令，观察多Agent协同工作过程 | 右侧实时显示SAP系统操作")

    # SAP操作日志映射
    SAP_ACTION_MAP = {
        "planner": [
            "CALL BAPI: BAPI_DOCUMENT_GETLIST( DOC_TYPE = 'FIAA' )",
            "RFC: RFC_READ_TABLE( QUERY_TABLE = 'BKPF' )",
            "ANALYZE: 识别月结任务依赖图...",
        ],
        "executor": [
            "CALL BAPI: BAPI_ACC_DOCUMENT_POST( DOC_HEADER, DOC_ITEMS )",
            "RFC: RFC_CALL_FUNCTION 'BAPI_AR_ACC_GETOPENITEMS'",
            "EXECUTE: POSTING_RUN( COMPANY_CODE = '1000', FISCAL_PERIOD = '03' )",
            "CALL BAPI: BAPI_GL_ACC_EXISTENCECHECK( GL_ACCOUNT = '11220000' )",
            "DATA_SYNC: 银行流水接口 → 同步 2,847 条记录",
            "CALL BAPI: BAPI_FIXEDASSET_OVRTAKE_CREATE()",
        ],
        "validator": [
            "VALIDATE: CHECK_BALANCE( DEBIT = 12,450,000, CREDIT = 12,450,000 ) → PASS",
            "AUDIT: 操作日志已写入 /LOG/CLOSEPILOT_AUDIT_202603",
            "COMPLIANCE: 敏感数据加密传输 (TLS 1.3, AES-256)",
        ],
        "system": [
            "STATUS: 月结流程 FINISHED, 总耗时 138min",
            "REPORT: 生成月结报告 /REPORT/MONTHLY_CLOSE_202603.pdf",
        ],
    }

    # 左右分栏：聊天 + SAP GUI
    chat_col, sap_col = st.columns([3, 2])

    with chat_col:
        # 聊天历史显示
        chat_container = st.container(height=480, border=True)
        with chat_container:
            if not st.session_state.chat_history:
                st.markdown("""
                <div style="text-align:center; padding: 60px 20px; color: #999;">
                    <p style="font-size: 3rem; margin-bottom: 16px;">🤖</p>
                    <p style="font-size: 1.1rem; margin-bottom: 8px;">你好！我是 ClosePilot，你的SAP智能月结助手。</p>
                    <p>试试输入：<b>"帮我完成3月月结"</b></p>
                </div>
                """, unsafe_allow_html=True)

            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-bubble bubble-user">👤 {msg["content"]}</div>', unsafe_allow_html=True)
                else:
                    badge = format_agent_badge(msg["agent"])
                    st.markdown(f'<div class="chat-bubble bubble-agent">{badge} {msg["content"]}</div>', unsafe_allow_html=True)

            if st.session_state.chat_processing:
                st.markdown('<div class="chat-bubble bubble-agent"><span class="agent-badge badge-planner">🧠 Planner Agent</span> 思考中...</div>', unsafe_allow_html=True)

        # 输入区 + 清空按钮
        input_col, clear_col = st.columns([5, 1])
        with input_col:
            user_input = st.chat_input("输入财务指令，如：帮我完成3月月结", disabled=st.session_state.chat_processing)
        with clear_col:
            if st.button("🗑️ 清空", use_container_width=True, disabled=st.session_state.chat_processing):
                st.session_state.chat_history = []
                st.session_state.chat_responses = []
                st.session_state.chat_response_idx = 0
                st.session_state.chat_processing = False
                st.session_state.sap_log = []
                st.rerun()

        # 聊天处理逻辑
        if user_input and not st.session_state.chat_processing:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            st.session_state.chat_responses = get_agent_response(user_input)
            st.session_state.chat_response_idx = 0
            st.session_state.chat_processing = True
            st.rerun()

        if st.session_state.chat_processing and st.session_state.chat_responses:
            idx = st.session_state.chat_response_idx
            if idx < len(st.session_state.chat_responses):
                agent_type, content = st.session_state.chat_responses[idx]
                st.session_state.chat_history.append({
                    "role": "agent",
                    "agent": agent_type,
                    "content": content
                })
                # 同步添加SAP操作日志
                import random as _sap_rnd
                sap_actions = SAP_ACTION_MAP.get(agent_type, SAP_ACTION_MAP["executor"])
                sap_action = _sap_rnd.choice(sap_actions)
                st.session_state.sap_log.append({
                    "agent": agent_type,
                    "action": sap_action,
                    "time": time.strftime("%H:%M:%S")
                })
                st.session_state.chat_response_idx = idx + 1
                time.sleep(0.6)
                st.rerun()
            else:
                st.session_state.chat_processing = False
                st.rerun()

    # 右侧：SAP GUI 模拟界面
    with sap_col:
        st.markdown("#### 🖥️ SAP 操作终端")
        st.caption("ClosePilot Agent 实时操作记录")

        sap_container = st.container(height=480, border=True)
        with sap_container:
            if not st.session_state.sap_log:
                st.markdown("""
                <div style="text-align:center; padding: 40px 16px; color: #999; font-family: monospace;">
                    <p style="font-size: 1.5rem; margin-bottom: 12px;">🖥️</p>
                    <p>SAP GUI Terminal</p>
                    <p style="font-size: 0.85rem;">等待 Agent 操作指令...</p>
                    <p style="font-size: 0.8rem; color: #bbb;">SAP ERP 6.0 EHP8 | Client 100</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                for log_entry in st.session_state.sap_log:
                    agent = log_entry["agent"]
                    action = log_entry["action"]
                    ts = log_entry["time"]
                    agent_colors = {
                        "planner": "#2E7D32",
                        "executor": "#1565C0",
                        "validator": "#E65100",
                        "system": "#7B1FA2",
                    }
                    color = agent_colors.get(agent, "#666")
                    st.markdown(f"""
                    <div style="font-family: 'Courier New', monospace; font-size: 0.78rem; padding: 6px 10px; margin: 3px 0; background: #1a1a2e; border-radius: 4px; border-left: 3px solid {color};">
                        <span style="color: #888;">[{ts}]</span>
                        <span style="color: {color}; font-weight: 600;"> [{agent.upper()}]</span>
                        <span style="color: #e0e0e0;"> {action}</span>
                    </div>
                    """, unsafe_allow_html=True)

                # 自动滚动到底部的提示
                st.markdown("<div style='text-align: right; font-size: 0.7rem; color: #999; margin-top: 8px;'>🔽 实时滚动中...</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════
# Tab 2: 月结流程看板
# ═══════════════════════════════════════
with tab_dashboard:
    st.subheader("📊 月结流程实时看板")
    st.caption("模拟3月月结执行过程，观察10个子流程的实时状态")

    # 控制按钮
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
    is_running = st.session_state.demo_phase in ("running", "confirm")
    with col_btn1:
        start_demo = st.button(
            "▶ 开始演示" if not is_running else "⏳ 执行中...",
            type="primary",
            use_container_width=True,
            disabled=is_running
        )
    with col_btn2:
        reset_demo = st.button("🔄 重置", use_container_width=True, disabled=is_running)

    if reset_demo:
        st.session_state.process_status = {}
        st.session_state.demo_step_idx = -1
        st.session_state.demo_phase = "idle"
        st.rerun()

    # 流程步骤展示
    total_steps = len(MONTH_END_STEPS)
    completed = sum(1 for s in MONTH_END_STEPS if st.session_state.process_status.get(s["id"]) == "done")
    progress = completed / total_steps

    st.progress(progress, text=f"执行进度：{completed}/{total_steps} 子流程")

    st.markdown("---")

    # 步骤卡片
    for step in MONTH_END_STEPS:
        status = st.session_state.process_status.get(step["id"], "pending")

        if status == "done":
            icon, status_text, status_cls = "✅", "已完成", "status-done"
        elif status == "running":
            icon, status_text, status_cls = "⏳", "执行中...", "status-running"
        elif status == "confirm":
            icon, status_text, status_cls = "⚠️", "需人工确认", "status-error"
        else:
            icon, status_text, status_cls = "⬜", "等待中", "status-pending"

        risk_color = {"低": "#4CAF50", "中": "#FF9800", "高": "#F44336"}.get(step["risk"], "#999")
        border_color = '#2E7D32' if status == 'done' else '#FFA000' if status in ('running', 'confirm') else '#E0E0E0'

        st.markdown(f"""
        <div class="step-card" style="border-left: 4px solid {border_color}; {'opacity: 0.5;' if status == 'pending' else ''}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>{icon} Step {step["id"]}: {step["name"]}</strong>
                    <span style="color: #888; margin-left: 12px;"> {step["system"]}</span>
                    <span style="color: #888; margin-left: 12px;">⏱ {step["duration"]}min</span>
                </div>
                <div>
                    <span style="background: {risk_color}; color: white; padding: 2px 8px; border-radius: 8px; font-size: 0.75rem;">风险: {step["risk"]}</span>
                    <span class="{status_cls}" style="margin-left: 10px;">{status_text}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 演示推进逻辑：每次rerun推进一步
    if start_demo and st.session_state.demo_phase == "idle":
        st.session_state.demo_phase = "running"
        st.session_state.demo_step_idx = 0
        st.rerun()

    if st.session_state.demo_phase == "running":
        idx = st.session_state.demo_step_idx
        if idx < total_steps:
            step = MONTH_END_STEPS[idx]
            # 标记当前步骤为执行中
            st.session_state.process_status[step["id"]] = "running"
            st.rerun()

            # 高风险步骤进入确认状态
            if step["risk"] == "高":
                time.sleep(1.2)
                st.session_state.process_status[step["id"]] = "confirm"
                st.session_state.demo_phase = "confirm"
                st.rerun()

                time.sleep(1.0)
                st.session_state.process_status[step["id"]] = "done"
                st.session_state.demo_phase = "running"
                st.session_state.demo_step_idx = idx + 1
                st.rerun()
            else:
                time.sleep(0.8)
                st.session_state.process_status[step["id"]] = "done"
                st.session_state.demo_step_idx = idx + 1
                st.rerun()
        else:
            st.session_state.demo_phase = "done"

    # 动态统计信息
    st.markdown("---")
    st.subheader("📈 执行统计")

    running_count = sum(1 for s in MONTH_END_STEPS if st.session_state.process_status.get(s["id"]) == "running")
    confirm_count = sum(1 for s in MONTH_END_STEPS if st.session_state.process_status.get(s["id"]) == "confirm")
    auto_done = sum(1 for s in MONTH_END_STEPS if st.session_state.process_status.get(s["id"]) == "done" and s["risk"] != "高")
    manual_done = sum(1 for s in MONTH_END_STEPS if st.session_state.process_status.get(s["id"]) == "done" and s["risk"] == "高")

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        elapsed = sum(s["duration"] for s in MONTH_END_STEPS[:max(0, st.session_state.demo_step_idx + 1)] if st.session_state.process_status.get(s["id"]) in ("done", "confirm"))
        st.metric("已用时间", f"{elapsed} 分钟", "传统方式需数天")
    with stat_col2:
        st.metric("已完成", f"{completed}/{total_steps}", f"自动化 {auto_done} + 人工确认 {manual_done}")
    with stat_col3:
        if completed > 0:
            auto_rate = f"{round(auto_done / max(completed, 1) * 100)}%"
        else:
            auto_rate = "—"
        st.metric("自动化率", auto_rate, "高风险节点需人工确认")
    with stat_col4:
        if running_count > 0:
            st.metric("当前状态", "执行中", f"{running_count} 个流程运行中")
        elif st.session_state.demo_phase == "done":
            st.metric("当前状态", "全部完成", "🎉")
        else:
            st.metric("当前状态", "待启动", "点击开始演示")

    # Before vs After 对比图
    st.markdown("---")
    st.subheader("️ Before vs After：月结流程时间对比")

    step_names = [s["name"] for s in MONTH_END_STEPS]
    traditional_times = [s["duration"] * 6 for s in MONTH_END_STEPS]  # 传统方式耗时（分钟）
    ai_times = [s["duration"] for s in MONTH_END_STEPS]  # AI方式耗时

    fig_compare = go.Figure()
    fig_compare.add_trace(go.Bar(
        name="传统方式（人工）", y=step_names, x=traditional_times,
        orientation='h', marker_color='#EF5350', text=[f"{t}min" for t in traditional_times],
        textposition='outside', textfont=dict(size=10)
    ))
    fig_compare.add_trace(go.Bar(
        name="ClosePilot（AI Agent）", y=step_names, x=ai_times,
        orientation='h', marker_color='#42A5F5', text=[f"{t}min" for t in ai_times],
        textposition='outside', textfont=dict(size=10)
    ))
    fig_compare.update_layout(
        barmode='group', height=420,
        xaxis_title="耗时（分钟）",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=120, r=20, t=20, b=40),
        font=dict(size=11)
    )
    st.plotly_chart(fig_compare, use_container_width=True)

    # 汇总对比
    total_traditional = sum(traditional_times)
    total_ai = sum(ai_times)
    save_pct = round((1 - total_ai / total_traditional) * 100)
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    with summary_col1:
        st.info(f"**传统方式总耗时**：{total_traditional} 分钟（约 {total_traditional//60} 小时）")
    with summary_col2:
        st.success(f"**AI方式总耗时**：{total_ai} 分钟（约 {total_ai//60} 小时）")
    with summary_col3:
        st.warning(f"**效率提升**：{save_pct}%")

# ═══════════════════════════════════════
# Tab 3: 系统架构
# ═══════════════════════════════════════
with tab_architecture:
    st.subheader("🏗️ ClosePilot 系统架构")

    st.markdown("""
### 三层智能架构 + 治理层

```
┌─────────────────────────────────────────────────────────┐
│                   交互层 (Interaction Layer)              │
│         自然语言对话界面 — "帮我完成3月月结"               │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                   决策层 (Decision Layer)                  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 🧠 Planner   │→ │  Executor  │→ │ 🔍 Validator │  │
│  │   Agent      │  │   Agent      │  │   Agent      │  │
│  │ 意图理解     │  │ 跨系统操作   │  │ 结果校验     │  │
│  │ 任务拆解     │  │ API调用执行  │  │ 合规审查     │  │
│  │ 执行计划     │  │ 异常处理     │  │ 自动回滚     │  │
│  └──────────────  └──────────────┘  └──────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                   感知层 (Perception Layer)                │
│      SAP FI/CO/AA/BPC  │  银行系统  │  税务系统  │  CRM   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│               🛡️ 治理层 (Responsible AI)                  │
│        全操作留痕可审计 │ 敏感数据本地化 │ Human-in-the-Loop │
─────────────────────────────────────────────────────────┘
```
    """)

    st.markdown("---")
    st.subheader("🔑 核心差异化能力")

    diff_col1, diff_col2, diff_col3 = st.columns(3)
    with diff_col1:
        st.markdown("""
#### 🎯 深度SAP语义理解
- 原生对接SAP FI/CO模块
- 理解财务业务语义
- 非简单UI模拟
- 流程变更时自适应
        """)
    with diff_col2:
        st.markdown("""
#### 🔄 自主纠错闭环
- Validator实时校验
- 异常自动回滚
- 杜绝"盲执行"风险
- 全程留痕可审计
        """)
    with diff_col3:
        st.markdown("""
#### 🚀 零代码场景扩展
- 对话式配置新流程
- 无需开发介入
- 场景模板即插即用
- 快速复制到新场景
        """)

    st.markdown("---")
    st.subheader("📊 与传统方案对比")

    comparison_df = pd.DataFrame({
        "能力维度": ["语义理解", "跨系统操作", "自主纠错", "零代码扩展", "合规审计", "月结周期"],
        "传统RPA": [" 规则匹配", "⚠️ UI模拟", "❌ 无", "❌ 需开发", "⚠️ 部分", "5-7天"],
        "通用Chatbot": ["⚠️ 浅层", "❌ 仅问答", "❌ 无", " 不支持", "❌ 无", "N/A"],
        "ClosePilot": ["✅ 深度语义", "✅ API原生", "✅ 自动回滚", "✅ 对话配置", "✅ 全留痕", "2天"],
    })
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# Tab 4: ROI 计算器
# ═══════════════════════════════════════
with tab_roi:
    st.subheader("💰 ROI 计算器")
    st.caption("输入企业参数，实时计算 ClosePilot 带来的业务价值")

    st.markdown("---")

    # 输入参数
    input_col1, input_col2, input_col3 = st.columns(3)
    with input_col1:
        revenue = st.slider(
            "年营收（亿元）",
            min_value=5, max_value=500, value=st.session_state.roi_revenue, step=5,
            key="roi_revenue_slider"
        )
    with input_col2:
        employees = st.slider(
            "财务团队人数",
            min_value=5, max_value=500, value=st.session_state.roi_employees, step=5,
            key="roi_employees_slider"
        )
    with input_col3:
        current_days = st.slider(
            "当前月结天数",
            min_value=3, max_value=15, value=st.session_state.roi_current_days, step=1,
            key="roi_days_slider"
        )

    st.session_state.roi_revenue = revenue
    st.session_state.roi_employees = employees
    st.session_state.roi_current_days = current_days

    # ROI 计算逻辑
    # 假设：月结人工占比 = 财务团队 * 60% 时间用于月结相关
    # 传统月结: current_days 天
    # AI月结: 2 天
    # 每次月结节省: (current_days - 2) 天 * 参与人数
    # 参与人数 = 财务团队 * 70% (不是所有人都参与月结)
    monthly_participants = max(int(employees * 0.7), 1)
    days_saved_per_month = max(current_days - 2, 0)
    person_days_saved_per_month = monthly_participants * days_saved_per_month
    person_days_saved_per_year = person_days_saved_per_month * 12

    # 人力成本：假设平均年薪 25 万，日成本 = 250000 / 250 工作日 = 1000 元/天
    cost_per_day = 1000
    annual_cost_savings = person_days_saved_per_year * cost_per_day

    # 错误率降低带来的隐性收益（审计风险、罚款等）
    error_reduction_benefit = annual_cost_savings * 0.15  # 额外 15%

    # 总收益
    total_annual_benefit = annual_cost_savings + error_reduction_benefit

    # 实施成本估算（SaaS模式）
    annual_license_cost = revenue * 10000 * 0.003  # 年营收的 0.3%
    implementation_cost = 500000  # 一次性实施费用

    # ROI
    first_year_roi = (total_annual_benefit - annual_license_cost - implementation_cost) / max(annual_license_cost + implementation_cost, 1) * 100
    ongoing_roi = (total_annual_benefit - annual_license_cost) / max(annual_license_cost, 1) * 100
    payback_months = (implementation_cost) / max((total_annual_benefit - annual_license_cost) / 12, 1)

    st.markdown("---")

    # 核心指标
    roi_col1, roi_col2, roi_col3, roi_col4 = st.columns(4)
    with roi_col1:
        st.metric("年节省人天", f"{person_days_saved_per_year:,} 天", f"每月 {person_days_saved_per_month} 天")
    with roi_col2:
        st.metric("年成本节约", f"¥{annual_cost_savings/10000:.0f} 万", "含隐性收益")
    with roi_col3:
        st.metric("首年 ROI", f"{first_year_roi:.0f}%", f"回收期 {payback_months:.1f} 个月")
    with roi_col4:
        st.metric("持续 ROI", f"{ongoing_roi:.0f}%", "第2年起")

    st.markdown("---")

    # 详细收益分解图
    st.subheader(" 收益分解")
    benefit_labels = ["人力成本节约", "错误率降低收益", "年许可费用", "实施费用(首年)"]
    benefit_values = [annual_cost_savings, error_reduction_benefit, -annual_license_cost, -implementation_cost]
    benefit_colors = ['#4CAF50', '#8BC34A', '#FF9800', '#F44336']

    fig_roi = go.Figure(go.Bar(
        x=benefit_labels, y=benefit_values,
        marker_color=benefit_colors,
        text=[f"¥{abs(v)/10000:.0f}万" for v in benefit_values],
        textposition='outside'
    ))
    fig_roi.update_layout(
        height=350,
        yaxis_title="金额（元）",
        showlegend=False,
        margin=dict(l=60, r=20, t=20, b=60)
    )
    st.plotly_chart(fig_roi, use_container_width=True)

    st.markdown("---")

    # 规模化收益
    st.subheader("📈 规模化收益（埃森哲多客户场景）")
    client_counts = [10, 25, 50, 100]
    total_savings_50clients = person_days_saved_per_year * 50
    total_cost_savings_50clients = annual_cost_savings * 50

    scale_col1, scale_col2, scale_col3 = st.columns(3)
    with scale_col1:
        st.metric("服务 50 家客户年节省人天", f"{total_savings_50clients:,} 天", "")
    with scale_col2:
        st.metric("服务 50 家客户年节约成本", f"¥{total_cost_savings_50clients/100000000:.1f} 亿", "")
    with scale_col3:
        st.metric("服务 100 家客户年节约成本", f"¥{annual_cost_savings * 100 / 100000000:.1f} 亿", "非线性增长")

    st.markdown("---")
    st.caption("* 计算假设：财务人员平均年薪 25 万元，年工作日 250 天，日成本约 1,000 元。许可费用按年营收 0.3% 估算。实际数据因企业规模、行业、现有流程成熟度而异。")
