"""
ClosePilot — SAP智能月结Agent Demo
埃森哲创新大赛原型演示
"""
import streamlit as st
import time
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dashscope
from dashscope import Generation

# ── 通义千问 API 配置 ──
dashscope.api_key = st.secrets.get("QWEN_API_KEY", "")

SYSTEM_PROMPT = """你是ClosePilot，一个专业的SAP智能月结Agent。你帮助财务人员通过自然语言完成月结相关操作。

你的能力范围：
1. 月结流程：凭证检查、银行对账、往来对账、科目重分类、折旧计提、成本分摊、收支匹配、税务提取、报表汇总、报告生成
2. 对账操作：银行流水对账、往来科目对账
3. 报表生成：资产负债表、利润表、现金流量表
4. 凭证管理：凭证完整性检查、凭证查询

你必须严格按照以下JSON格式回复，不要输出其他内容：
[
  {"agent": "planner", "content": "简短的分析内容，1-2句话"},
  {"agent": "executor", "content": "简短的执行内容，1-2句话"},
  {"agent": "validator", "content": "简短的校验内容，1-2句话"}
]

规则：
- 至少5条，最多10条，逐步展示流程
- agent按顺序循环：planner → executor → validator → executor → validator → ...
- 每条content控制在30-80字，简洁专业
- 包含具体的SAP T-Code、数据量、金额等细节
- 最后一条用system agent做总结"""

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
    st.session_state.demo_phase = "idle"  # idle, running, confirm, revise, reconfirm, done
if "demo_sub" not in st.session_state:
    st.session_state.demo_sub = "start"  # start → wait → advance
if "demo_reject_reason" not in st.session_state:
    st.session_state.demo_reject_reason = ""
if "roi_revenue" not in st.session_state:
    st.session_state.roi_revenue = 50
if "roi_employees" not in st.session_state:
    st.session_state.roi_employees = 200
if "roi_current_days" not in st.session_state:
    st.session_state.roi_current_days = 6
if "sap_log" not in st.session_state:
    st.session_state.sap_log = []
if "knowledge_base" not in st.session_state:
    st.session_state.knowledge_base = []
if "contact_log" not in st.session_state:
    st.session_state.contact_log = []
if "client_template" not in st.session_state:
    st.session_state.client_template = "manufacturing"

# ── 月结子流程定义（多客户模板）──
CLIENT_TEMPLATES = {
    "manufacturing": {
        "name": "制造集团A",
        "steps": 10,
        "modules": "FI/CO/AA/BPC",
        "features": "含成本核算、折旧计提、合并报表",
        "data": [
            {"id": 1, "name": "凭证完整性检查", "system": "SAP FI", "duration": 8, "risk": "低"},
            {"id": 2, "name": "银行流水对账", "system": "SAP FI + 银行系统", "duration": 15, "risk": "中"},
            {"id": 3, "name": "往来科目对账", "system": "SAP FI/CO", "duration": 12, "risk": "中"},
            {"id": 4, "name": "科目重分类调整", "system": "SAP FI", "duration": 10, "risk": "高",
             "confirm_detail": "拟调整分录 47 笔，总金额 ¥12,450,000\n调整原因：长期应收款重分类至非流动资产\n影响科目：1221010000 → 1501010000\nT-Code: FAGL_FC_VAL"},
            {"id": 5, "name": "折旧计提过账", "system": "SAP AA", "duration": 6, "risk": "低"},
            {"id": 6, "name": "成本中心分摊", "system": "SAP CO", "duration": 10, "risk": "中"},
            {"id": 7, "name": "收入成本匹配校验", "system": "SAP CO + CRM", "duration": 14, "risk": "高",
             "confirm_detail": "发现3笔收入成本不匹配，差异金额 ¥284,500\n订单#SO-20240315 收入已确认但成本未归集\n订单#SO-20240322 成本多计 ¥156,000\n建议：暂估入账或冲回调整"},
            {"id": 8, "name": "税务数据提取", "system": "SAP FI + 税务系统", "duration": 8, "risk": "中"},
            {"id": 9, "name": "合并报表数据汇总", "system": "SAP BPC", "duration": 12, "risk": "高",
             "confirm_detail": "3家子公司数据已提取，发现2项合并调整\n华东公司内部交易抵消 ¥3,200,000\n华南公司汇率差异调整 ¥187,000\n合并后净利润：¥45,680,000"},
            {"id": 10, "name": "月结报告生成", "system": "SAP + BI", "duration": 5, "risk": "低"},
        ],
    },
    "retail": {
        "name": "零售集团B",
        "steps": 12,
        "modules": "FI/CO/MM/SD",
        "features": "含库存估值、促销分摊、多门店合并",
        "data": [
            {"id": 1, "name": "凭证完整性检查", "system": "SAP FI", "duration": 8, "risk": "低"},
            {"id": 2, "name": "银行流水对账", "system": "SAP FI + 银行系统", "duration": 15, "risk": "中"},
            {"id": 3, "name": "往来科目对账", "system": "SAP FI/CO", "duration": 12, "risk": "中"},
            {"id": 4, "name": "库存估值调整", "system": "SAP MM", "duration": 18, "risk": "高",
             "confirm_detail": "发现5个SKU库存估值差异，总金额 ¥892,000\nSKU-A001: 先进先出法 vs 加权平均法差异 ¥340,000\nSKU-B015: 过期商品未计提跌价准备 ¥210,000\n建议：按加权平均法重估，计提跌价准备"},
            {"id": 5, "name": "促销费用分摊", "system": "SAP CO + CRM", "duration": 10, "risk": "中"},
            {"id": 6, "name": "门店收入确认", "system": "SAP SD + FI", "duration": 14, "risk": "高",
             "confirm_detail": "3家门店收入确认时点差异\n门店#SH-001: 已发货未开票 ¥560,000\n门店#BJ-003: 预收款未发货 ¥230,000\n建议：按发货时点确认收入"},
            {"id": 7, "name": "科目重分类调整", "system": "SAP FI", "duration": 10, "risk": "高",
             "confirm_detail": "拟调整分录 32 笔，总金额 ¥8,750,000\n调整原因：预付账款重分类至其他流动资产"},
            {"id": 8, "name": "折旧计提过账", "system": "SAP AA", "duration": 6, "risk": "低"},
            {"id": 9, "name": "成本中心分摊", "system": "SAP CO", "duration": 10, "risk": "中"},
            {"id": 10, "name": "税务数据提取", "system": "SAP FI + 税务系统", "duration": 8, "risk": "中"},
            {"id": 11, "name": "多门店合并报表", "system": "SAP BPC", "duration": 15, "risk": "高",
             "confirm_detail": "12家门店数据已提取，发现3项合并调整\n内部调拨抵消 ¥1,800,000\n跨区域汇率差异 ¥95,000"},
            {"id": 12, "name": "月结报告生成", "system": "SAP + BI", "duration": 5, "risk": "低"},
        ],
    },
    "service": {
        "name": "服务集团C",
        "steps": 8,
        "modules": "FI/CO/PS",
        "features": "含项目结算、人力成本分摊",
        "data": [
            {"id": 1, "name": "凭证完整性检查", "system": "SAP FI", "duration": 8, "risk": "低"},
            {"id": 2, "name": "银行流水对账", "system": "SAP FI + 银行系统", "duration": 12, "risk": "中"},
            {"id": 3, "name": "项目成本结算", "system": "SAP PS + CO", "duration": 16, "risk": "高",
             "confirm_detail": "8个在建项目成本结算\n项目#P-2026-003: 已发生成本 ¥2,400,000，完工进度 65%\n项目#P-2026-007: 预算超支 12%，需项目经理确认\n建议：按完工百分比法确认收入"},
            {"id": 4, "name": "人力成本分摊", "system": "SAP CO + HR", "duration": 14, "risk": "中"},
            {"id": 5, "name": "往来科目对账", "system": "SAP FI/CO", "duration": 10, "risk": "中"},
            {"id": 6, "name": "税务数据提取", "system": "SAP FI + 税务系统", "duration": 8, "risk": "中"},
            {"id": 7, "name": "管理报表汇总", "system": "SAP + BI", "duration": 10, "risk": "低"},
            {"id": 8, "name": "月结报告生成", "system": "SAP + BI", "duration": 5, "risk": "低"},
        ],
    },
}

# 默认使用制造集团模板
MONTH_END_STEPS = CLIENT_TEMPLATES["manufacturing"]["data"]

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

# ── 异常历史记录（过去12个月月结执行统计，按企业区分）──
# anomalies/total = 异常率，由系统自动计算
ANOMALY_HISTORY = {
    "manufacturing": {
        "凭证完整性检查": {"total": 12, "anomalies": 1, "avg_time": 15, "issue": "凭证缺失、摘要不规范"},
        "银行流水对账": {"total": 12, "anomalies": 4, "avg_time": 45, "issue": "流水延迟、手续费未入账"},
        "往来科目对账": {"total": 12, "anomalies": 3, "avg_time": 30, "issue": "时间性差异、汇率波动"},
        "科目重分类调整": {"total": 12, "anomalies": 2, "avg_time": 20, "issue": "科目分类错误"},
        "折旧计提过账": {"total": 12, "anomalies": 0, "avg_time": 10, "issue": "资产新增/处置未同步"},
        "成本中心分摊": {"total": 12, "anomalies": 2, "avg_time": 15, "issue": "分摊基数争议"},
        "收入成本匹配校验": {"total": 12, "anomalies": 3, "avg_time": 25, "issue": "发票延迟、暂估调整"},
        "税务数据提取": {"total": 12, "anomalies": 1, "avg_time": 12, "issue": "税率变更、跨境税务"},
        "合并报表数据汇总": {"total": 12, "anomalies": 3, "avg_time": 40, "issue": "内部交易抵消、汇率调整"},
        "月结报告生成": {"total": 12, "anomalies": 0, "avg_time": 8, "issue": "格式调整、数据核对"},
    },
    "retail": {
        "凭证完整性检查": {"total": 12, "anomalies": 2, "avg_time": 12, "issue": "跨门店摘要不一致、凭证缺失"},
        "银行流水对账": {"total": 12, "anomalies": 3, "avg_time": 40, "issue": "多账户流水延迟、手续费未入账"},
        "往来科目对账": {"total": 12, "anomalies": 2, "avg_time": 25, "issue": "供应商对账延迟、时间性差异"},
        "库存估值调整": {"total": 12, "anomalies": 5, "avg_time": 35, "issue": "估值方法差异、跌价准备未计提"},
        "促销费用分摊": {"total": 12, "anomalies": 3, "avg_time": 20, "issue": "促销分摊规则争议、活动确认延迟"},
        "门店收入确认": {"total": 12, "anomalies": 4, "avg_time": 28, "issue": "收入确认时点争议、预收款处理"},
        "科目重分类调整": {"total": 12, "anomalies": 1, "avg_time": 18, "issue": "预付账款重分类遗漏"},
        "折旧计提过账": {"total": 12, "anomalies": 0, "avg_time": 8, "issue": "资产新增/处置未同步"},
        "成本中心分摊": {"total": 12, "anomalies": 1, "avg_time": 12, "issue": "门店分摊基数争议"},
        "税务数据提取": {"total": 12, "anomalies": 2, "avg_time": 15, "issue": "多门店税率差异、跨境税务"},
        "多门店合并报表": {"total": 12, "anomalies": 4, "avg_time": 45, "issue": "内部调拨抵消、跨区域汇率"},
        "月结报告生成": {"total": 12, "anomalies": 0, "avg_time": 10, "issue": "多门店数据核对"},
    },
    "service": {
        "凭证完整性检查": {"total": 12, "anomalies": 1, "avg_time": 10, "issue": "凭证缺失、项目编号遗漏"},
        "银行流水对账": {"total": 12, "anomalies": 2, "avg_time": 35, "issue": "项目回款流水延迟、手续费未入账"},
        "项目成本结算": {"total": 12, "anomalies": 4, "avg_time": 50, "issue": "完工进度估算偏差、预算超支"},
        "人力成本分摊": {"total": 12, "anomalies": 3, "avg_time": 30, "issue": "工时归集不准确、项目分摊争议"},
        "往来科目对账": {"total": 12, "anomalies": 1, "avg_time": 20, "issue": "时间性差异、预收款项处理"},
        "税务数据提取": {"total": 12, "anomalies": 1, "avg_time": 10, "issue": "跨境项目税务处理"},
        "管理报表汇总": {"total": 12, "anomalies": 1, "avg_time": 15, "issue": "报表口径不一致、项目维度差异"},
        "月结报告生成": {"total": 12, "anomalies": 0, "avg_time": 5, "issue": "格式调整、数据核对"},
    },
}

# ── 知识沉淀库（历史处理记录）──
KNOWLEDGE_BASE = [
    {
        "scenario": "银行流水差异-手续费",
        "pattern": "工行流水.*金额差.*手续费",
        "suggestion": "根据历史记录，该差异出现过3次，均为银行手续费未入账。建议直接计入“财务费用-手续费”科目。",
        "history": "张会计于2026-02-15做了相同处理，审计通过",
        "confidence": 92,
    },
    {
        "scenario": "应收账款超期90天",
        "pattern": "超期90天",
        "suggestion": "超期90天以上的应收账款，建议先联系业务员确认客户付款计划，同时计提坏账准备。",
        "history": "上月类似情况：客户A因资金周转延迟，已制定分期还款计划",
        "confidence": 85,
    },
    {
        "scenario": "收入成本不匹配",
        "pattern": "收入成本不匹配|成本未归集",
        "suggestion": "收入已确认但成本未归集，通常为供应商发票延迟。建议暂估入账，待发票到达后冲回调整。",
        "history": "2026-01月结中3笔类似情况均采用暂估方式，审计无异议",
        "confidence": 88,
    },
    {
        "scenario": "外币汇率差异",
        "pattern": "汇率差异|外币评估",
        "suggestion": "汇率差异在阈值0.5%以内可自动调整，超过阈值需财务经理审批。建议使用月末中间价重估。",
        "history": "近6个月汇率差异均在0.3%以内，全部自动调整通过",
        "confidence": 95,
    },
]

# ── 智能联络人映射 ─
CONTACT_MAP = {
    "银行流水差异": {
        "person": "王明（出纳）",
        "email": "wangming@company.com",
        "department": "财务部-资金组",
        "message_template": "3月月结中发现银行流水差异，工行流水#{流水号}金额差¥{金额}，SAP无对应凭证。请确认该笔款项的性质和归属。",
    },
    "应收账款差异": {
        "person": "李华（销售专员）",
        "email": "lihua@company.com",
        "department": "销售部",
        "message_template": "客户{客户名}应收账款对账发现差异¥{金额}，对应订单#{订单号}。请确认客户是否已付款及付款凭证。",
    },
    "应付账款差异": {
        "person": "赵强（采购专员）",
        "email": "zhaoqiang@company.com",
        "department": "采购部",
        "message_template": "供应商{供应商名}应付账款对账发现差异¥{金额}，对应采购订单#{订单号}。请确认是价格变动还是数量问题。",
    },
    "费用归属不清": {
        "person": "各部门负责人",
        "email": "dept-head@company.com",
        "department": "相关业务部门",
        "message_template": "3月月结中发现一笔费用¥{金额}归属不清，凭证摘要：{摘要}。请确认该费用应归入哪个成本中心。",
    },
    "凭证摘要不规范": {
        "person": "做凭证的会计",
        "email": "accounting@company.com",
        "department": "财务部-核算组",
        "message_template": "凭证#{凭证号}的摘要填写不规范（当前摘要：“{摘要}”），请补充具体业务说明以便审计查阅。",
    },
}


def call_qwen_api(user_msg: str) -> list:
    """调用通义千问API，返回多Agent格式的回复列表"""
    import json as _json
    try:
        response = Generation.call(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            result_format="message"
        )
        if response.status_code == 200 and response.output.choices:
            ai_text = response.output.choices[0].message.content.strip()
            # 尝试解析JSON数组
            if ai_text.startswith("["):
                steps = _json.loads(ai_text)
                return [(s["agent"], s["content"]) for s in steps if "agent" in s and "content" in s]
            # 如果不是JSON，尝试从代码块中提取
            if "```" in ai_text:
                json_str = ai_text.split("```")[1].strip()
                if json_str.startswith("json"):
                    json_str = json_str[4:].strip()
                steps = _json.loads(json_str)
                return [(s["agent"], s["content"]) for s in steps if "agent" in s and "content" in s]
            # 兜底：将整段文本作为planner回复
            return [("planner", ai_text[:300])]
        return None
    except Exception:
        return None


def get_agent_response(user_msg: str, use_ai=False):
    """根据用户消息匹配Agent回复（支持多关键词、模糊匹配、AI生成）"""
    # AI模式：调用通义千问
    if use_ai:
        ai_result = call_qwen_api(user_msg)
        if ai_result:
            return ai_result
    # 规则模式：关键词匹配（保证Demo稳定性）
    sorted_keywords = sorted(AGENT_RESPONSES.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword in user_msg:
            return AGENT_RESPONSES[keyword]
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
    st.markdown("#### 🤖 AI 引擎")
    use_ai = st.toggle("通义千问 AI", value=True, help="开启后使用通义千问大模型生成回复，关闭则使用预设规则引擎")
    if use_ai:
        st.success("✅ 通义千问 qwen-plus 已连接")
    else:
        st.info("ℹ️ 规则引擎模式（预设回复）")
    st.markdown("---")
    st.caption("埃森哲创新大赛 Demo v2.0 — 决赛版")

# ═══════════════════════════════════════
# 主页面
# ═══════════════════════════════════════
st.markdown('<div class="main-header"> ClosePilot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">SAP智能月结Agent — 让财务月结从5天缩短到2小时</div>', unsafe_allow_html=True)

# 痛点故事
st.markdown(
    "<div style='background:linear-gradient(135deg, #FFF3E0 0%, #FFECB3 100%);"
    "border-radius:12px; padding:18px 22px; margin:16px 0; border-left:4px solid #FF9800;'>"
    "<div style='font-weight:700; font-size:1.05rem; color:#E65100; margin-bottom:8px;'>"
    " 每个月末，财务经理 Lisa 都要经历这样的场景：</div>"
    "<div style='font-size:0.92rem; color:#333; line-height:1.7;'>"
    "带着团队 <b>连续加班5-7天</b>，在SAP里手动查凭证、对银行流水、做重分类调整。"
    "Excel和SAP之间反复切换，一笔差异就要追溯半天。"
    "好不容易做完，审计师来了又说<b>凭证缺失、分录不规范</b>。"
    "她想：这些重复操作，为什么不能让系统自己干？"
    "</div></div>",
    unsafe_allow_html=True
)

# 顶部指标卡
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("月结周期", "2天", "↓ 从5-7天")
with col2:
    st.metric("人工操作减少", "70%", "↑")
with col3:
    st.metric("流程错误率降低", "40%", "↓")
with col4:
    st.metric("年节省人天(单企业)", "~360天", "按20人团队估算")

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
            st.session_state.chat_responses = get_agent_response(user_input, use_ai=use_ai)
            st.session_state.chat_response_idx = 0
            st.session_state.chat_processing = True
            st.rerun()

        if st.session_state.chat_processing and st.session_state.chat_responses is not None:
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

    # ── 知识沉淀 + 智能联络面板（全宽显示）──
    # 当聊天历史中包含差异/异常信息时，展示知识建议和联络选项
    has_discrepancy = any(
        "差异" in msg.get("content", "") or "异常" in msg.get("content", "") or "不匹配" in msg.get("content", "")
        for msg in st.session_state.chat_history
    )

    if has_discrepancy and not st.session_state.chat_processing:
        st.markdown("---")

        # 知识沉淀建议
        st.subheader("💡 智能建议（知识沉淀）")
        st.caption("AI根据历史处理记录，自动匹配相似场景的解决方案")

        for kb in KNOWLEDGE_BASE[:2]:  # 展示最相关的2条
            confidence_color = "#4CAF50" if kb["confidence"] >= 90 else "#FF9800"
            st.markdown(
                f"<div style='background:#F1F8E9; border:1px solid #AED581; border-radius:8px; "
                f"padding:12px 16px; margin:8px 0;'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>"
                f"<span style='font-weight:700; color:#33691E;'>📚 {kb['scenario']}</span>"
                f"<span style='background:{confidence_color}; color:white; padding:2px 8px; "
                f"border-radius:10px; font-size:0.75rem;'>匹配度 {kb['confidence']}%</span>"
                f"</div>"
                f"<div style='font-size:0.88rem; color:#333; line-height:1.6;'>{kb['suggestion']}</div>"
                f"<div style='font-size:0.8rem; color:#666; margin-top:6px; font-style:italic;'>"
                f"📝 历史记录：{kb['history']}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        # 智能联络
        st.markdown("---")
        st.subheader("📧 智能联络（一键协调）")
        st.caption("AI自动识别责任人并生成邮件草稿，可直接编辑后发送")

        # 模拟第一个联络场景
        contact_scenario = "银行流水差异"
        contact = CONTACT_MAP[contact_scenario]

        # 联系人信息
        st.info(f"**📧 收件人**：{contact['person']}（{contact['department']}）\n"
                f"**收件地址**：{contact['email']}")

        # 可编辑的邮件主题和正文
        default_subject = "【月结确认】工行流水差异 ¥2,340 需确认"
        default_body = (
            "王明你好，\n\n"
            "3月月结中发现以下差异需要确认：\n"
            "• 工行2月15日流水 #28471，金额差异 ¥2,340，SAP无对应凭证\n"
            "• 根据历史记录，该差异通常为银行手续费未入账\n\n"
            "请确认：\n"
            "1. 该笔款项是否为银行手续费？\n"
            "2. 如确认，我将直接计入“财务费用-手续费”科目\n\n"
            "请在3月31日前回复，谢谢！\n\n"
            "— ClosePilot 自动发送"
        )

        email_subject = st.text_input("邮件主题", value=default_subject, key="email_subject")
        email_body = st.text_area("邮件正文", value=default_body, height=220, key="email_body")

        st.caption("💡 可直接在上方编辑邮件内容，确认无误后点击发送")
        send_clicked = st.button("📧 发送邮件", type="primary", use_container_width=True, key="send_contact")

        if send_clicked:
            st.session_state.contact_log.append({
                "to": contact["email"],
                "to_name": contact["person"],
                "subject": email_subject,
                "scenario": contact_scenario,
                "time": time.strftime("%H:%M:%S"),
                "status": "已发送"
            })
            st.success(f"✅ 邮件已发送至 {contact['person']} <{contact['email']}>")
            st.rerun()

        # 显示已发送记录
        if st.session_state.contact_log:
            st.markdown("---")
            st.subheader("📨 联络记录")
            for log in st.session_state.contact_log:
                st.markdown(
                    f"<div style='font-size:0.85rem; padding:8px 12px; margin:4px 0; "
                    f"background:#F5F5F5; border-radius:6px;'>"
                    f"<span style='color:#888;'>[{log['time']}]</span> "
                    f"<span style='color:#1565C0; font-weight:600;'>→ {log.get('to_name', log['to'])}</span> "
                    f"<span style='color:#333;'>{log.get('subject', log['scenario'])}</span> "
                    f"<span style='color:#4CAF50; font-weight:600;'>{log['status']}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

# ═══════════════════════════════════════
# Tab 2: 月结流程看板
# ═══════════════════════════════════════
with tab_dashboard:
    st.subheader("📊 月结流程实时看板")
    st.caption("模拟3月月结执行过程，观察10个子流程的实时状态")

    # ── 客户模板切换（展示拓展性）──
    st.markdown("---")
    st.subheader("🏢 客户流程配置")
    st.caption("不同客户的月结流程不同，通过配置切换，无需改代码")

    template_col1, template_col2, template_col3 = st.columns(3)
    with template_col1:
        select_manufacturing = st.button(
            "🏭 制造集团A（10步）",
            use_container_width=True,
            type="primary" if st.session_state.client_template == "manufacturing" else "secondary",
            key="tpl_mfg"
        )
    with template_col2:
        select_retail = st.button(
            " 零售集团B（12步）",
            use_container_width=True,
            type="primary" if st.session_state.client_template == "retail" else "secondary",
            key="tpl_retail"
        )
    with template_col3:
        select_service = st.button(
            "💼 服务集团C（8步）",
            use_container_width=True,
            type="primary" if st.session_state.client_template == "service" else "secondary",
            key="tpl_service"
        )

    if select_manufacturing:
        st.session_state.client_template = "manufacturing"
        st.session_state.process_status = {}
        st.session_state.demo_step_idx = -1
        st.session_state.demo_phase = "idle"
        st.session_state.demo_sub = "start"
        st.rerun()
    if select_retail:
        st.session_state.client_template = "retail"
        st.session_state.process_status = {}
        st.session_state.demo_step_idx = -1
        st.session_state.demo_phase = "idle"
        st.session_state.demo_sub = "start"
        st.rerun()
    if select_service:
        st.session_state.client_template = "service"
        st.session_state.process_status = {}
        st.session_state.demo_step_idx = -1
        st.session_state.demo_phase = "idle"
        st.session_state.demo_sub = "start"
        st.rerun()

    # 根据模板显示不同的流程说明
    current_tpl = CLIENT_TEMPLATES[st.session_state.client_template]
    current_steps = current_tpl["data"]
    st.info(
        f"**{current_tpl['name']}** — {current_tpl['steps']}个子流程 | "
        f"涉及模块：{current_tpl['modules']} | "
        f"特色：{current_tpl['features']}"
    )

    # 配置查看器
    with st.expander("📝 查看当前配置（YAML格式）", expanded=False):
        config_yaml = f"""# {current_tpl['name']} 月结流程配置
# 业务顾问维护此文件，定义月结流程的步骤、系统和风险等级
# 系统根据 risk 自动判断是否需要人工确认，无需额外配置

client: {current_tpl['name']}
modules: {current_tpl['modules']}
features: {current_tpl['features']}

steps:"""
        for s in current_steps:
            comment = "  # 高风险，需人工确认" if s["risk"] == "高" else ""
            config_yaml += f"""
  - name: {s['name']}
    system: {s['system']}
    risk: {s['risk']}{comment}"""
        st.code(config_yaml, language="yaml")
        st.caption("💡 实际项目中，业务顾问修改此配置即可适配不同客户，无需改代码")

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
        st.session_state.demo_sub = "start"
        st.session_state.demo_reject_reason = ""
        st.rerun()

    # 流程步骤展示
    total_steps = len(current_steps)
    completed = sum(1 for s in current_steps if st.session_state.process_status.get(s["id"]) == "done")
    progress = completed / total_steps

    st.progress(progress, text=f"执行进度：{completed}/{total_steps} 子流程")

    st.markdown("---")

    # 步骤卡片
    for step in current_steps:
        status = st.session_state.process_status.get(step["id"], "pending")

        if status == "done":
            icon, status_text, status_cls = "✅", "已完成", "status-done"
        elif status == "rejected":
            icon, status_text, status_cls = "❌", "已驳回", "status-error"
        elif status == "running":
            icon, status_text, status_cls = "⏳", "执行中...", "status-running"
        elif status == "confirm":
            icon, status_text, status_cls = "⚠️", "需人工确认", "status-error"
        else:
            icon, status_text, status_cls = "⬜", "等待中", "status-pending"

        risk_color = {"低": "#4CAF50", "中": "#FF9800", "高": "#F44336"}.get(step["risk"], "#999")
        border_color = '#2E7D32' if status == 'done' else '#C62828' if status == 'rejected' else '#FFA000' if status in ('running', 'confirm') else '#E0E0E0'

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

    # 演示推进逻辑：状态机，每次rerun推进一步
    if start_demo and st.session_state.demo_phase == "idle":
        st.session_state.demo_phase = "running"
        st.session_state.demo_step_idx = 0
        st.session_state.demo_sub = "start"
        st.rerun()

    if st.session_state.demo_phase == "running":
        idx = st.session_state.demo_step_idx
        sub = st.session_state.demo_sub

        if idx >= total_steps:
            st.session_state.demo_phase = "done"
            st.rerun()

        step = current_steps[idx]

        if sub == "start":
            # 标记当前步骤为执行中
            st.session_state.process_status[step["id"]] = "running"
            st.session_state.demo_sub = "wait"
            st.rerun()

        elif sub == "wait":
            # 等待后更新状态
            if step["risk"] == "高":
                time.sleep(1.2)
                st.session_state.process_status[step["id"]] = "confirm"
                st.session_state.demo_phase = "confirm"
                st.session_state.demo_sub = "start"
            else:
                time.sleep(0.8)
                st.session_state.process_status[step["id"]] = "done"
                st.session_state.demo_step_idx = idx + 1
                st.session_state.demo_sub = "start"
            st.rerun()

    if st.session_state.demo_phase == "confirm":
        idx = st.session_state.demo_step_idx
        step = current_steps[idx]
        detail = step.get("confirm_detail", "高风险操作，请确认后执行。")

        # 显示Human-in-the-Loop确认对话框
        st.markdown("---")
        st.warning(
            f" **Human-in-the-Loop** — Step {step['id']}「{step['name']}」为高风险操作，"
            f"Agent已暂停执行，等待财务人员确认。"
        )

        # 确认详情面板
        st.markdown(
            f"<div style='background:#FFF8E1; border:1px solid #FFB300; border-radius:8px; padding:14px 18px; margin:8px 0;'>"
            f"<div style='font-weight:700; color:#E65100; margin-bottom:8px;'> Agent 拟执行操作：</div>"
            f"<pre style='background:white; padding:10px; border-radius:6px; font-size:0.85rem; white-space:pre-wrap; margin:0;'>{detail}</pre>"
            f"</div>",
            unsafe_allow_html=True
        )

        confirm_col1, confirm_col2, confirm_col3 = st.columns([1, 1, 2])
        with confirm_col1:
            confirm_clicked = st.button(
                "✅ 确认执行",
                type="primary",
                use_container_width=True,
                key="confirm_approve"
            )
        with confirm_col2:
            reject_clicked = st.button(
                "❌ 驳回修改",
                use_container_width=True,
                key="confirm_reject"
            )
        with confirm_col3:
            st.caption("这是ClosePilot的安全机制：AI自主决策 + 人工把关高风险节点")

        if confirm_clicked:
            st.session_state.process_status[step["id"]] = "done"
            st.session_state.demo_phase = "running"
            st.session_state.demo_step_idx = idx + 1
            st.session_state.demo_sub = "start"
            st.rerun()

        if reject_clicked:
            st.session_state.demo_phase = "revise"
            st.rerun()

    # ─ 驳回修改阶段：输入修改意见 ──
    if st.session_state.demo_phase == "revise":
        idx = st.session_state.demo_step_idx
        step = current_steps[idx]

        st.markdown("---")
        st.error(f" **Step {step['id']}「{step['name']}」已被驳回**，请说明修改要求，Agent将调整方案后重新提交确认。")

        reject_reason = st.text_area(
            "驳回原因 / 修改要求",
            value=st.session_state.demo_reject_reason,
            placeholder="例如：金额有误，请重新核对；或：暂不执行，待下月处理",
            height=80,
            key="reject_reason_input"
        )

        submit_col1, submit_col2 = st.columns([1, 3])
        with submit_col1:
            submit_clicked = st.button(
                "📤 提交修改意见",
                type="primary",
                use_container_width=True,
                key="submit_reject"
            )
        with submit_col2:
            st.caption("Agent将根据您的意见调整方案，再次提交确认")

        if submit_clicked and reject_reason.strip():
            st.session_state.demo_reject_reason = reject_reason.strip()
            st.session_state.demo_phase = "reconfirm"
            st.rerun()

    # ── 重新确认阶段：Agent调整后的方案 ──
    if st.session_state.demo_phase == "reconfirm":
        idx = st.session_state.demo_step_idx
        step = current_steps[idx]
        detail = step.get("confirm_detail", "高风险操作，请确认后执行。")
        reason = st.session_state.demo_reject_reason

        st.markdown("---")
        st.info(f" **Agent 已根据您的意见调整方案** — Step {step['id']}「{step['name']}」")

        # 显示驳回意见
        st.markdown(
            f"<div style='background:#FFEBEE; border:1px solid #EF5350; border-radius:8px; padding:10px 14px; margin:6px 0;'>"
            f"<div style='font-weight:600; color:#C62828; font-size:0.85rem;'> 您的修改意见：</div>"
            f"<div style='font-size:0.85rem; color:#333; margin-top:4px;'>{reason}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

        # 显示调整后的方案
        st.markdown(
            f"<div style='background:#E8F5E9; border:1px solid #66BB6A; border-radius:8px; padding:14px 18px; margin:8px 0;'>"
            f"<div style='font-weight:700; color:#2E7D32; margin-bottom:8px;'> Agent 调整后的方案：</div>"
            f"<pre style='background:white; padding:10px; border-radius:6px; font-size:0.85rem; white-space:pre-wrap; margin:0;'>{detail}\n\n[已根据您的意见调整]</pre>"
            f"</div>",
            unsafe_allow_html=True
        )

        reconfirm_col1, reconfirm_col2 = st.columns([1, 3])
        with reconfirm_col1:
            reconfirm_clicked = st.button(
                "✅ 确认执行",
                type="primary",
                use_container_width=True,
                key="reconfirm_approve"
            )
        with reconfirm_col2:
            st.caption("此次为最终确认，Agent将按调整后的方案执行")

        if reconfirm_clicked:
            st.session_state.process_status[step["id"]] = "done"
            st.session_state.demo_phase = "running"
            st.session_state.demo_step_idx = idx + 1
            st.session_state.demo_sub = "start"
            st.session_state.demo_reject_reason = ""
            st.rerun()

    # 动态统计信息
    st.markdown("---")
    st.subheader("📈 执行统计")

    running_count = sum(1 for s in current_steps if st.session_state.process_status.get(s["id"]) == "running")
    confirm_count = sum(1 for s in current_steps if st.session_state.process_status.get(s["id"]) == "confirm")
    auto_done = sum(1 for s in current_steps if st.session_state.process_status.get(s["id"]) == "done" and s["risk"] != "高")
    manual_done = sum(1 for s in current_steps if st.session_state.process_status.get(s["id"]) == "done" and s["risk"] == "高")

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        elapsed = sum(s["duration"] for s in current_steps[:max(0, st.session_state.demo_step_idx + 1)] if st.session_state.process_status.get(s["id"]) in ("done", "confirm"))
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

    # ── 异常热力图 ──
    st.markdown("---")
    st.subheader("月结异常热力图（历史数据）")
    st.caption("过去12个月月结执行统计，异常率 = 异常次数 / 执行总次数 × 100%")

    # 异常数据（从当前企业的历史记录计算）
    _history = ANOMALY_HISTORY.get(st.session_state.client_template, {})
    anomaly_data = {
        "步骤": [s["name"] for s in current_steps],
        "异常次数": [f"{_history.get(s['name'], {}).get('anomalies', 0)}/{_history.get(s['name'], {}).get('total', 12)}" for s in current_steps],
        "异常率(%)": [round(_history.get(s['name'], {}).get('anomalies', 0) / _history.get(s['name'], {}).get('total', 12) * 100) for s in current_steps],
        "平均处理时间(min)": [_history.get(s['name'], {}).get('avg_time', 10) for s in current_steps],
        "常见问题": [_history.get(s['name'], {}).get('issue', '—') for s in current_steps],
    }
    anomaly_df = pd.DataFrame(anomaly_data)

    # 用Plotly画热力图风格的条形图
    fig_anomaly = go.Figure(go.Bar(
        x=anomaly_data["步骤"], y=anomaly_data["异常率(%)"],
        marker_color=[
            '#EF5350' if v >= 25 else '#FF9800' if v >= 10 else '#4CAF50'
            for v in anomaly_data["异常率(%)"]
        ],
        text=[f"{v}%" for v in anomaly_data["异常率(%)"]],
        textposition='outside',
    ))
    fig_anomaly.update_layout(
        height=300,
        xaxis_title="月结步骤",
        yaxis_title="异常率 (%)",
        margin=dict(l=60, r=20, t=20, b=80),
        font=dict(size=11),
    )
    st.plotly_chart(fig_anomaly, use_container_width=True)

    # 异常详情表
    st.markdown("**异常详情：**")
    anomaly_display_df = anomaly_df[["步骤", "异常次数", "异常率(%)", "平均处理时间(min)", "常见问题"]].copy()
    anomaly_display_df.columns = ["步骤", "异常次数(近12月)", "异常率", "平均处理时间", "常见问题"]
    st.dataframe(anomaly_display_df, use_container_width=True, hide_index=True)

    # Before vs After 对比图
    st.markdown("---")
    st.subheader("Before vs After：月结流程时间对比")

    step_names = [s["name"] for s in current_steps]
    traditional_times = [s["duration"] * 6 for s in current_steps]  # 传统方式耗时（分钟）
    ai_times = [s["duration"] for s in current_steps]  # AI方式耗时

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
    st.subheader("️ ClosePilot 系统架构")
    st.caption("四层架构设计：配置化流程 + 通用Agent + 动作注册表 + SAP对接层")

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

    # ── SAP Financial Closing Assistant 对比 ─
    st.markdown("---")
    st.subheader("SAP Financial Closing Assistant 对比")
    st.caption("与SAP原生月结自动化能力的差异化对比")
    
    st.info(
        "💡 SAP FCA 是「月结的项目经理」——告诉你该做什么、做到哪了；"
        "ClosePilot 是「月结的数字员工」——听懂你要什么，然后自己去干。"
    )

    sap_compare_df = pd.DataFrame({
        "对比维度": ["产品定位", "核心能力", "操作方式", "系统范围", "智能程度", "扩展方式", "月结周期"],
        "SAP Financial Closing Assistant": [
            "月结任务管理工具",
            "列清单、分配任务、跟踪进度、发提醒",
            "人在SAP里手动操作，FCA只负责跟踪",
            "仅SAP内部",
            "规则驱动，无AI决策",
            "需ABAP开发",
            "5-7天（人操作）"
        ],
        "ClosePilot": [
            "月结自主执行Agent",
            "理解指令→拆解任务→跨系统自动执行→校验结果",
            "自然语言下达指令，Agent代替人操作",
            "SAP + 银行 + 税务 + CRM 跨系统编排",
            "多Agent协同，自主纠错，Human-in-the-Loop",
            "对话式配置，零代码",
            "2天（Agent执行）"
        ],
    })
    st.dataframe(sap_compare_df, use_container_width=True, hide_index=True)

    st.markdown("**关键提升点：**")
    st.markdown("- SAP FCA 解决了「管理可见性」问题（知道谁在做什么、进度如何），但操作仍靠人工")
    st.markdown("- ClosePilot 进一步解决了「执行自动化」问题——Agent理解财务语义，跨系统自主完成操作")
    st.markdown("- 两者互补而非替代：ClosePilot可对接FCA的任务管理，在其基础上叠加AI执行层")

    # ─ 落地架构说明 ─
    st.markdown("---")
    st.subheader("🔧 落地架构设计原则")

    arch_col1, arch_col2 = st.columns(2)
    with arch_col1:
        st.markdown("""
####  配置化流程引擎
- 流程步骤通过 YAML 配置定义
- 客户有10步还是15步，改配置不改代码
- 预置行业模板（制造/零售/服务）
- 新增步骤 = 加一段配置
        """)
    with arch_col2:
        st.markdown("""
####  动作注册表（插件化）
- 每个SAP操作注册为一个“插件”
- Agent不关心具体是哪一步，只读配置
- 新增BAPI = 加一个插件条目
- 核心引擎永远不用改
        """)

    arch_col3, arch_col4 = st.columns(2)
    with arch_col3:
        st.markdown("""
####  意图映射层（防幻觉）
- AI只输出“意图”，不直接生成T-Code
- 规则引擎把意图翻译成具体BAPI调用
- 避免大模型编造不存在的接口
- 可审计、可追溯
        """)
    with arch_col4:
        st.markdown("""
#### 📚 知识沉淀闭环
- 记录每次人工干预的处理方式
- 下次遇到相似场景自动给出建议
- AI越用越聪明，经验不随人流失
- 形成企业月结知识资产
        """)

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
    # 假设：月结核心人员 = 财务团队 * 30%（不是所有人都参与月结）
    # 传统月结: current_days 天
    # AI月结: 2 天
    # 每次月结节省: (current_days - 2) 天 * 核心参与人数
    monthly_participants = max(int(employees * 0.3), 1)
    days_saved_per_month = max(current_days - 2, 0)
    person_days_saved_per_month = monthly_participants * days_saved_per_month
    person_days_saved_per_year = person_days_saved_per_month * 12

    # 人力成本：假设平均年薪 25 万，日成本 = 250000 / 250 工作日 = 1000 元/天
    cost_per_day = 1000
    annual_cost_savings = person_days_saved_per_year * cost_per_day

    # 错误率降低带来的隐性收益（审计风险、罚款等）
    error_reduction_benefit = annual_cost_savings * 0.1  # 额外 10%

    # 总收益
    total_annual_benefit = annual_cost_savings + error_reduction_benefit

    # 实施成本估算（SaaS模式）
    # 许可费 = 基础费 + 按人头计费（更合理的定价模型）
    annual_license_cost = 80000 + employees * 3000  # 基础8万 + 每人3000/年
    implementation_cost = 800000  # 一次性实施费用（含配置、培训、测试）

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
    st.subheader("收益分解")
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

    # 客户价值故事
    st.subheader("对财务人员意味着什么？")
    st.markdown(
        "<div style='background:#E3F2FD; border-radius:12px; padding:18px 22px; "
        "border-left:4px solid #1976D2;'>"
        "<div style='font-size:0.92rem; color:#333; line-height:1.8;'>"
        "对 Lisa 来说，ClosePilot 改变的不仅是数字——"
        "<br><br>"
        " <b>月末不用再加班了。</b> 以前5-7天的月结，现在2天完成，团队可以准时下班。"
        "<br>"
        "🎯 <b>审计不再头疼。</b> 每步操作自动留痕，凭证完整、分录规范，审计师来了直接看报告。"
        "<br>"
        " <b>团队做更有价值的事。</b> 从重复的\"对账工\"变成真正的\"财务分析师\"，把时间花在预算规划、经营分析上。"
        "<br>"
        "🛡️ <b>风险可控。</b> 高风险操作必须人工确认，AI不会盲目执行，合规有保障。"
        "</div></div>",
        unsafe_allow_html=True
    )

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
        st.metric("服务 100 家客户年节约成本", f"¥{annual_cost_savings * 100 / 100000000:.1f} 亿", "规模效应")

    st.markdown("---")

    # 商业价值故事
    st.subheader("💼 商业机会")
    st.markdown(
        "<div style='background:#F3E5F5; border-radius:12px; padding:18px 22px; "
        "border-left:4px solid #7B1FA2;'>"
        "<div style='font-size:0.92rem; color:#333; line-height:1.8;'>"
        "<b>市场有多大？</b> 中国有超过 <b>300万家</b> 使用SAP的中大型企业，"
        "每家都需要月结。即使只覆盖1%，也是3万家客户。"
        "<br><br>"
        "<b>怎么赚钱？</b> SaaS订阅制——按企业规模分级定价，"
        "中小企业 ¥5万/年，大型企业 ¥30万/年。"
        "<br><br>"
        "<b>为什么是现在？</b> 通义千问等大模型已经成熟，"
        "AI理解财务语义的能力首次达到可用水平。"
        "SAP FCA解决了\"看得见\"的问题，ClosePilot解决\"做得快\"的问题——"
        "这是SAP生态里一个 <b>尚未被填补的空白</b>。"
        "</div></div>",
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.caption("* 计算假设：财务人员平均年薪 25 万元，年工作日 250 天，日成本约 1,000 元。月结核心人员按财务团队 30% 估算。许可费用按基础8万元 + 每人3,000元/年估算。实际数据因企业规模、行业、现有流程成熟度而异。")
