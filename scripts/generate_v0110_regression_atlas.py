#!/usr/bin/env python3
"""Regenerate the 0.1.10 twelve-scenario review atlas from canonical templates."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "skills" / "vibe-diagram" / "assets" / "templates"
OUTPUT_DIR = ROOT / "docs" / "TASK_20260725_002_全图族制图根因整改回归"
INDEX_PATH = ROOT / "docs" / "TASK_20260725_002_全图族制图根因整改回归.html"
TOKEN_RE = re.compile(r"\{\{([^{}]+)\}\}")
TEXT_TOKEN_RE = re.compile(r"\{\{canvas-text-(\d{3})\}\}")
ATTRIBUTE_TOKEN_RE = re.compile(r"\{\{canvas-attribute-(\d{3})\}\}")
OUTPUT_SUBDIRECTORY = "TASK_20260725_002_全图族制图根因整改回归"
STALE_SAMPLE_FILENAMES = frozenset(
    {
        "01_业务架构_会员积分价值链.html",
        "06_交付验收_SSO接入.html",
        "08_功能迭代_通知链路发布回滚.html",
    }
)


@dataclass(frozen=True)
class Sample:
    filename: str
    family: str
    template: str
    title: str
    summary: str
    short_title: str
    purpose: str
    texts: Dict[int, str]
    facts: List[str]
    attributes: Dict[int, str] = field(default_factory=dict)


def numbered(values: Iterable[str], start: int = 1) -> Dict[int, str]:
    return {index: value for index, value in enumerate(values, start=start)}


def flow_text(
    diagram_title: str,
    description: str,
    nodes: List[tuple[str, str]],
    branch_labels: tuple[str, str, str],
    relations: List[str],
    detail_copy: List[str],
) -> Dict[int, str]:
    values: Dict[int, str] = {1: diagram_title, 2: description}
    cursor = 3
    for title, summary in nodes:
        values[cursor] = title
        values[cursor + 1] = summary
        cursor += 2
    values.update({17: branch_labels[0], 18: branch_labels[1], 19: branch_labels[2]})
    values.update({20 + offset: item for offset, item in enumerate(relations)})
    values[28] = "节点详情"
    values[29] = "业务含义、输入输出与边界"
    for offset, ((title, _), copy) in enumerate(zip(nodes, detail_copy)):
        values[30 + offset * 2] = title
        values[31 + offset * 2] = copy
    values[44] = "窄屏流程关系"
    return values


def matrix_text(
    diagram_title: str,
    description: str,
    context: tuple[str, str],
    candidates: List[tuple[str, str]],
    criteria: List[str],
    cells: List[str],
    recommendation: tuple[str, str],
    details: List[str],
) -> Dict[int, str]:
    values = {
        1: diagram_title,
        2: description,
        3: "决策背景",
        4: "候选 × 条件事实矩阵",
        5: "结论与复评条件",
        6: context[0],
        7: context[1],
        8: candidates[0][0],
        9: candidates[0][1],
        10: candidates[1][0],
        11: candidates[1][1],
        12: candidates[2][0],
        13: candidates[2][1],
        14: recommendation[0],
        15: recommendation[1],
        16: criteria[0],
        17: criteria[1],
        18: criteria[2],
        34: "窄屏矩阵",
        35: "候选与结论详情",
        36: "点击候选或结论查看事实边界",
    }
    values.update({19 + offset: item for offset, item in enumerate(cells)})
    detail_titles = [context[0], candidates[0][0], candidates[1][0], candidates[2][0], recommendation[0]]
    for offset, (title, copy) in enumerate(zip(detail_titles, details)):
        values[37 + offset * 2] = title
        values[38 + offset * 2] = copy
    return values


ARCHITECTURE_MAIN = {
    1: "会员积分能力—业务域架构",
    2: "参与方通过触达、积分与权益经营、分析治理等业务域协作；核心对象和规则约束贯穿各域。",
    3: "参与方",
    4: "会员经营业务边界",
    5: "能力、对象与规则共同形成价值依赖",
    6: "外部协作边界",
    7: "经营规则与治理",
    8: "统一约束会员价值计算",
    9: "核心业务对象",
    10: "贯穿消费、积分、权益与核销",
    11: "👤",
    12: "会员顾客",
    13: "消费、兑换并形成复购",
    14: "业务触点",
    15: "🏪",
    16: "门店收银",
    17: "消费触发",
    18: "📱",
    19: "会员中心",
    20: "积分与权益",
    21: "🎯",
    22: "营销运营",
    23: "规则与活动",
    24: "🧾",
    25: "客服财务",
    26: "退款与调整",
    27: "🧭",
    28: "会员触达与识别域",
    29: "识别会员并承接消费触点",
    30: "会员识别",
    31: "消费归集",
    32: "触点授权",
    33: "身份合并",
    34: "🪙",
    35: "积分与权益经营域",
    36: "从积分计算到优惠券核销",
    37: "积分计算",
    38: "积分入账",
    39: "余额查询",
    40: "积分过期",
    41: "权益兑换",
    42: "优惠券发放",
    43: "核销校验",
    44: "退款扣回",
    45: "📊",
    46: "经营分析与规则域",
    47: "数据反馈作用于下一轮经营",
    48: "复购分析",
    49: "活动归因",
    50: "规则版本",
    51: "倍率配置",
    52: "券门槛",
    53: "客群分层",
    54: "风险监控",
    55: "财务对账",
    56: "审计追踪",
    57: "策略发布",
    58: "🔌",
    59: "外部业务协作",
    60: "连接订单、支付与商品",
    61: "订单服务",
    62: "支付平台",
    63: "商品中心",
    64: "消息通知",
    65: "规则版本",
    66: "有效期",
    67: "幂等键",
    68: "审批流",
    69: "审计日志",
    70: "退款策略",
    71: "🛡️",
    72: "边界与约束",
    73: "限制价值计算与跨域修改",
    74: "tenantId",
    75: "memberId",
    76: "一元一积分",
    77: "365 天有效",
    78: "原单退款扣回",
    79: "会员账户",
    80: "积分流水",
    81: "权益券",
    82: "消费订单",
    83: "核销记录",
    84: "规则版本",
    85: "退款单",
    86: "分析快照",
    252: "⚙️",
    253: "📦",
}


SYSTEM_MAIN = {
    1: "多租户 SaaS 工作负载架构",
    2: "租户入口经边缘解析进入共享业务负载；数据、控制面、外部依赖和基础设施保持清晰边界。",
    3: "租户访问入口",
    4: "共享工作负载与租户隔离",
    5: "每个请求携带租户上下文",
    6: "外部依赖与运维",
    7: "租户控制面",
    8: "管理租户生命周期和运行约束",
    9: "共享基础设施",
    10: "承载计算、数据、消息、密钥与备份",
    11: "👥",
    12: "租户客户端",
    13: "四类入口共享租户身份",
    14: "流量来源",
    15: "🖥️",
    16: "Web 管理台",
    17: "浏览器访问",
    18: "📱",
    19: "员工移动端",
    20: "现场操作",
    21: "🔌",
    22: "伙伴 API",
    23: "系统集成",
    24: "⏱️",
    25: "计划任务",
    26: "定时 Webhook",
    27: "🛡️",
    28: "边缘接入与租户解析",
    29: "认证后建立 tenant context",
    30: "WAF",
    31: "API 网关",
    32: "JWT 校验",
    33: "租户解析器",
    34: "🧩",
    35: "共享业务工作负载",
    36: "无状态服务共享部署，透传租户上下文",
    37: "工单",
    38: "客户",
    39: "员工",
    40: "计费",
    41: "通知",
    42: "文件",
    43: "报表",
    44: "租户配置",
    45: "🔐",
    46: "数据与资源隔离",
    47: "共享存储内按租户命名空间访问",
    48: "PostgreSQL tenant_id",
    49: "RLS 行策略",
    50: "查询拦截器",
    51: "Redis 租户前缀",
    52: "对象存储前缀",
    53: "租户密钥映射",
    54: "备份租户标签",
    55: "独立审计日志",
    56: "毒邻居保护",
    57: "数据导出守卫",
    58: "🔗",
    59: "外部依赖",
    60: "身份、支付与消息通道",
    61: "OIDC 身份平台",
    62: "支付服务商",
    63: "短信网关",
    64: "邮件平台",
    65: "租户开通",
    66: "套餐配额",
    67: "功能开关",
    68: "模式迁移",
    69: "密钥轮换",
    70: "租户停用",
    71: "🔭",
    72: "观测与故障隔离",
    73: "按 tenantId 聚合并可人工隔离",
    74: "租户指标",
    75: "结构化日志",
    76: "分布式追踪",
    77: "告警路由",
    78: "人工租户隔离",
    79: "Kubernetes",
    80: "入口控制 Ingress",
    81: "PostgreSQL",
    82: "Redis",
    83: "对象存储",
    84: "Kafka",
    85: "密钥管理",
    86: "备份服务",
    252: "⚙️",
    253: "☁️",
}


def technical_package_text() -> Dict[int, str]:
    values: Dict[int, str] = {}

    def put(start: int, items: List[str]) -> None:
        values.update(numbered(items, start=start))

    put(
        1,
        [
            "完整技术设计",
            "订单创建与事件投递",
            "六个互补视图连续展开同一设计：边界、时序、契约、一致性、恢复与发布验证。",
        ],
    )
    put(20, ["入口与边界", "事务与事件", "异步消费"])
    put(
        25,
        [
            "创建订单 API",
            "校验租户与幂等键",
            "本地事务",
            "写订单与 Outbox",
            "事件投递",
            "发布 OrderCreated",
            "库存消费者",
            "幂等更新库存",
            "调用",
            "提交",
            "消费",
            "总览节点详情",
            "职责、边界和依赖方向",
            "入口只做协议适配、租户校验与幂等检查。",
            "订单与 Outbox 在同一数据库事务中提交。",
            "投递器只领取可处理事件，收到 broker ack 后推进状态。",
            "消费者按 eventId 去重，再更新库存投影。",
            "窄屏总览关系",
        ],
    )
    put(
        60,
        [
            "02 · 运行时序",
            "订单创建运行时序",
            "以参与方、生命线、消息、返回和超时片段表达一次真实运行。",
        ],
    )
    put(
        70,
        [
            "客户端",
            "提交订单",
            "订单服务",
            "事务协调",
            "事件投递器",
            "发布事件",
            "消息总线 Kafka",
            "消息总线",
            "主事务",
            "写入并提交",
            "客户端 → 订单",
            "同步",
            "提交订单 POST /orders",
            "订单 → 投递器",
            "异步",
            "唤醒待投递事件",
            "事件发布",
            "发布与确认",
            "投递器 → Kafka",
            "异步",
            "订单事件 OrderCreated",
            "Kafka → 投递器",
            "返回",
            "代理确认 broker ack",
            "异常分支 alt",
            "发布超时",
            "投递器 → 订单",
            "异常",
            "记录 FAILED",
            "01",
            "02",
            "03",
            "04",
            "05",
        ],
    )
    put(
        108,
        [
            "参与方与消息详情",
            "点击参与方或消息查看职责、输入输出与失败边界。",
            "客户端生成 orderId 与幂等键，并接收同步受理结果。",
            "订单服务负责本地事务，不直接承担消息重试。",
            "事件投递器领取 NEW/FAILED 事件并执行退避重试。",
            "Kafka 提供 broker ack，不代表下游业务已经完成。",
            "POST /orders 只在幂等校验通过后进入事务。",
            "提交成功后才允许投递器观察到 Outbox 事件。",
            "OrderCreated 使用稳定 eventId 支撑消费端去重。",
            "broker ack 后事件由 NEW 推进到 SENT。",
            "超时写入 FAILED 与 next_retry_at，不覆盖订单事实。",
        ],
    )
    put(
        120,
        [
            "03 · 数据契约",
            "接口、存储与事件契约",
            "以表格明确输入、约束、输出与失败语义，避免把字段关系画成装饰卡片。",
            "关键契约表",
            "契约",
            "输入",
            "约束",
            "输出",
            "失败语义",
            "创建订单 CreateOrder",
            "租户 tenantId，订单 orderId",
            "幂等键唯一",
            "订单编号 orderId",
            "409 重复键",
            "订单表 orders",
            "订单聚合",
            "状态为 CREATED",
            "事务提交",
            "数据库回滚",
            "事件表 outbox_event",
            "事件编号 eventId",
            "事件状态 NEW → SENT",
            "订单事件 OrderCreated",
            "FAILED 可重试",
            "库存消费",
            "事件编号 eventId",
            "幂等去重",
            "库存投影",
            "重放安全",
        ],
    )
    put(
        150,
        [
            "04 · 状态一致性",
            "订单与事件状态一致性",
            "状态变化由真实事件驱动，巡检只负责回补，不改写已提交业务事实。",
            "状态转换与对账反馈",
            "已接收 RECEIVED",
            "请求已校验",
            "已提交 COMMITTED",
            "订单与 Outbox 已提交",
            "提交事务",
            "发布确认",
            "消费幂等",
            "巡检回补",
            "已发布 PUBLISHED",
            "broker 已确认",
            "已投影 PROJECTED",
            "库存投影已更新",
            "状态节点详情",
            "状态、触发事件与可恢复边界",
            "RECEIVED 只表示请求通过基础校验，尚未形成订单事实。",
            "COMMITTED 表示订单与 Outbox 已在同一事务中落库。",
            "PUBLISHED 需要 broker ack，不能由发送调用成功替代。",
            "PROJECTED 表示消费者已幂等更新库存投影。",
            "窄屏一致性关系",
        ],
    )
    put(
        180,
        [
            "05 · 失败恢复",
            "失败恢复与重试流程",
            "自动重试与人工处置在明确汇合点复核，反馈通道有独立语义。",
            "恢复主流程",
            "人工介入通道",
            "发现超时事件",
            "扫描 NEW / FAILED",
            "判断是否可重试",
            "次数、退避与故障类型",
            "自动重试",
            "未超过上限",
            "转人工处置",
            "进入判断",
            "可重试",
            "不可重试",
            "重试结果",
            "人工结果",
            "确认一致",
            "处置后重判",
            "超过上限或毒消息",
            "汇合复核",
            "核对订单与投影",
            "恢复完成",
            "关闭告警",
            "恢复节点详情",
            "点击节点查看判定依据、输入输出与责任边界。",
            "巡检按 next_retry_at 领取超时事件，不扫描全部历史。",
            "判断同时考虑错误类型、次数上限与指数退避。",
            "自动重试沿用原 eventId，避免制造重复业务事件。",
            "人工处置必须记录原因、操作者与修复动作。",
            "汇合复核同时检查订单、Outbox 与库存投影。",
            "确认一致后关闭告警并保留完整审计记录。",
            "窄屏恢复关系",
        ],
    )
    put(
        220,
        [
            "06 · 发布验证",
            "发布门禁与回滚判据",
            "用表格固定每个阶段的变更、验证、门禁与失败动作。",
            "发布与验证清单",
            "阶段",
            "变更",
            "验证",
            "门禁",
            "失败动作",
            "部署前",
            "迁移与兼容检查",
            "契约回归",
            "全部通过",
            "阻断发布",
            "灰度 5%",
            "新旧链路并行",
            "错误率 ≤ 0.5%",
            "观察 15 分钟",
            "切回旧版本",
            "灰度 25%",
            "扩大流量",
            "延迟 P95 ≤ 300ms",
            "库存一致",
            "暂停扩量",
            "全量",
            "100% 流量",
            "巡检无积压",
            "持续观测",
            "保留回滚窗口",
        ],
    )
    return values


SAMPLES = [
    Sample(
        "01_业务架构_会员积分能力域.html",
        "business-architecture",
        "capability-domain-map",
        "业务架构图｜会员积分能力与业务域",
        "从参与方、业务域、能力、对象、规则与外部边界解释会员积分如何形成经营价值；不把执行步骤冒充架构。",
        "会员积分业务架构",
        "能力—业务域架构，而非步骤流程",
        ARCHITECTURE_MAIN,
        [
            "会员消费由门店或会员中心识别并归集到会员账户。",
            "积分计算、入账、权益兑换和核销属于积分与权益经营域。",
            "规则版本、有效期、倍率与退款扣回约束跨域行为。",
            "订单、支付、商品和消息属于外部协作边界。",
            "积分流水、权益券、核销记录和退款单是关键业务对象。",
            "经营分析形成反馈，但不直接改写已发生的积分流水。",
        ],
        {
            3: "会员顾客",
            5: "会员触达与识别域",
            6: "积分与权益经营域",
            7: "经营分析与规则域",
            8: "外部业务协作",
            9: "经营规则与治理",
            10: "边界与约束",
            11: "核心业务对象",
            34: "业务参与方",
            35: "核心业务域",
            36: "外部协作边界",
            37: "规则治理边界",
            38: "业务对象边界",
            39: "参与方",
            40: "触达业务域",
            41: "积分权益业务域",
            42: "经营分析业务域",
            43: "外部协作者",
            44: "规则治理",
            45: "业务约束",
            46: "业务对象",
        },
    ),
    Sample(
        "02_基础流程_订单退款判定.html",
        "business-flow",
        "logic-flowchart",
        "业务流程图｜订单退款资格判定",
        "客服接收退款申请，读取订单事实，完成资格判断，并将通过或拒绝结果统一记录后返回。",
        "订单退款判定",
        "统一自北向南流程内核",
        flow_text(
            "订单退款资格判定",
            "退款申请经过资料读取、资格判断、分支处理、统一记录与结果返回。",
            [
                ("接收退款申请", "客服提交线上订单"),
                ("读取订单资料", "支付、签收与核销状态"),
                ("满足退款条件？", "支付成功、七天内、券未核销"),
                ("创建退款单", "三项条件全部满足"),
                ("返回拒绝原因", "输出首项不满足条件"),
                ("记录判定", "结果与原因统一入库"),
                ("返回处理结果", "通过或拒绝"),
            ],
            ("是", "否", "资料修正后重判"),
            [
                "提交后读取订单资料",
                "资料齐全后进入条件判断",
                "满足条件创建退款单",
                "不满足条件返回拒绝原因",
                "通过结果进入统一记录",
                "拒绝结果进入统一记录",
                "记录完成返回处理结果",
                "资料修正后重新读取",
            ],
            [
                "接收客服提交的退款请求并关联原订单。",
                "读取支付、签收、优惠券核销等不可省略的订单事实。",
                "以三个明确条件形成互斥的是与否分支。",
                "创建退款单并保留原订单、金额和支付渠道。",
                "返回首个不满足条件，便于客服解释。",
                "通过与拒绝都进入同一个判定记录，不在节点顶部挤压箭头。",
                "向客服返回可继续处理的结构化结果。",
            ],
        ),
        ["流程节点按真实文案容量设计。", "分支由判断节点两侧发出。", "通过与拒绝在显式汇合点合并。"],
    ),
    Sample(
        "03_异常流程_退款失败补偿.html",
        "business-flow",
        "logic-flowchart",
        "异常流程图｜退款失败补偿",
        "主流程尝试原路退款；失败分支记录原因、进入财务补偿并在修复后重新汇合，最终统一确认退款结果。",
        "退款失败补偿",
        "异常、补偿与重试共用流程内核",
        flow_text(
            "退款失败补偿流程",
            "原路退款成功直接记录；失败则记录原因并完成财务补偿，再汇合到统一退款结果。",
            [
                ("提交退款", "顾客发起申请"),
                ("校验并确认入库", "订单可退且仓库收货"),
                ("原路退款成功？", "支付平台返回结果"),
                ("记录退款成功", "保存支付退款单号"),
                ("记录失败原因", "保存渠道错误与原始码"),
                ("统一退款结果", "原路或补偿结果入库"),
                ("确认退款并关闭", "完成订单退款状态"),
            ],
            ("成功", "失败", "修复后重试"),
            [
                "申请进入退款校验",
                "校验完成后发起原路退款",
                "渠道成功进入成功记录",
                "渠道失败进入补偿处理",
                "原路成功汇合",
                "财务补偿成功后汇合",
                "统一结果确认并关闭订单",
                "账户修复后重新发起退款",
            ],
            [
                "退款申请保留原订单与申请人信息。",
                "先确认订单可退和仓库已收货，避免错误退款。",
                "只以支付平台的明确结果决定成功或失败分支。",
                "成功分支记录退款单号和完成时间。",
                "失败分支保留原始错误码，供财务核对渠道流水。",
                "原路退款与补偿退款进入同一结果记录。",
                "确认退款成功后再关闭订单，不提前改变终态。",
            ],
        ),
        ["异常分支保持主链可见。", "补偿成功后进入显式汇合点。", "重试走独立反馈通道。"],
    ),
    Sample(
        "04_代码时序_支付异步回调.html",
        "code-sequence",
        "async-callback-sequence",
        "代码时序图｜支付异步回调",
        "订单服务发布支付请求，消息队列异步投递到支付服务；成功回调与三十秒超时在 alt 片段中形成不同结果。",
        "支付异步回调",
        "参与方、生命线、消息与 alt/timeout 片段",
        numbered(
            [
                "订单服务",
                "发布请求并等待异步结果",
                "消息队列",
                "接收、投递并监测超时",
                "支付服务",
                "消费请求并执行扣款",
                "回调网关",
                "接收支付成功回调",
                "阶段一｜发布支付请求",
                "01",
                "订单 → 队列",
                "异步",
                "PaymentRequested",
                "02",
                "队列 → 订单",
                "确认返回",
                "messageId",
                "阶段二｜消费请求并扣款",
                "03",
                "队列 → 支付",
                "异步",
                "PaymentRequested",
                "04",
                "支付 → 队列",
                "消费确认",
                "确认消息已消费",
                "alt｜成功回调或超时",
                "05",
                "支付 → 网关",
                "回调",
                "PaymentSucceeded",
                "06",
                "队列 → 订单",
                "超时 timeout",
                "三十秒无结果，返回 PAYMENT_TIMEOUT",
                "参与方与消息详情",
                "订单服务负责发布请求并保持待支付状态，直到成功回调或超时。",
                "消息队列持久化 PaymentRequested，并向订单服务返回 messageId。",
                "支付服务幂等消费请求，完成扣款后确认消息。",
                "回调网关校验签名并接收 PaymentSucceeded。",
                "发布使用异步消息，订单线程不等待支付服务执行完成。",
                "messageId 用于后续关联消费与超时监测。",
                "支付服务以请求幂等键避免重复扣款。",
                "消费确认只代表消息处理完成，不代表订单已经收到成功回调。",
                "成功回调携带支付单号与签名，进入订单成功路径。",
                "超过三十秒仍无结果时返回超时错误，但不伪造支付失败。",
                "详情",
                "点击参与方或消息查看职责、时序含义与未验证边界。",
            ]
        ),
        ["六条消息按发生顺序排列。", "返回线为虚线，错误线独立着色。", "生命线为 2px 虚线且不遮挡参与方标题。"],
        {1: "支付异步回调时序图", 2: "支付异步回调主画布", 3: "发布支付请求", 4: "返回消息标识", 5: "投递支付请求", 6: "确认消息消费", 7: "成功支付回调", 8: "超时返回错误"},
    ),
    Sample(
        "05_决策沟通_向量检索方案.html",
        "decision-communication",
        "option-matrix-path",
        "决策矩阵图｜向量检索方案选择",
        "平台架构组按同一组事实比较 pgvector、Elasticsearch 与 Milvus；没有用户权重，因此不虚构总分。",
        "向量检索决策矩阵",
        "条件行 × 候选列 × 事实值",
        matrix_text(
            "向量检索方案决策矩阵",
            "三个候选使用相同条件比较；推荐结论绑定现状约束与复评条件。",
            ("向量检索选型", "四周上线，必须私有部署"),
            [("pgvector", "240ms｜0.8 万元/月"), ("Elasticsearch", "180ms｜1.5 万元/月"), ("Milvus 方案", "120ms｜2.8 万元/月")],
            ["P95 延迟", "月增量成本", "团队运维经验"],
            ["240ms", "180ms", "120ms", "0.8 万元", "1.5 万元", "2.8 万元", "已有经验", "已有经验", "暂无经验"],
            ("一期选 pgvector", "满足约束且团队熟悉；数据量或延迟门槛变化时复评"),
            [
                "上线周期、私有部署和预算是本次选择的前提，未提供条件权重。",
                "成本最低且团队已有 PostgreSQL 运维经验，但实测延迟最高。",
                "延迟和经验居中，需承担额外集群与索引运维。",
                "延迟最低但成本最高，团队尚无生产运维经验。",
                "一期偏好实施风险与成本；当 P95 超过 300ms 或月数据量显著增长时重新评估。",
            ],
        ),
        ["事实值来自用户给定场景。", "未提供权重，不生成分数。", "推荐与复评条件同时可见。"],
    ),
    Sample(
        "06_决策沟通_企业SSO验收矩阵.html",
        "decision-communication",
        "option-matrix-path",
        "验收矩阵视图｜企业 SSO 接入",
        "要求、验证证据与验收结论按矩阵逐项对齐；这是一种决策沟通视图，不再包装成虚构的“交付验收图”。",
        "企业 SSO 验收矩阵",
        "要求—证据—结论矩阵",
        matrix_text(
            "企业 SSO 接入验收矩阵",
            "每项要求对应验证证据与结论；生产跨域退出保留为条件验收。",
            ("SSO 上线验收", "逐项检查要求、证据和结论"),
            [("R1 企业 SSO", "OIDC 登录"), ("R2 三类角色", "角色：admin / operator / auditor"), ("R3 联动退出", "生产跨域退出")],
            ["原始要求", "验证证据", "验收结论"],
            [
                "仅保留企业 SSO",
                "三类角色映射",
                "IdP 与本地会话退出",
                "12 条登录用例通过",
                "18 条权限与 8 条退出通过",
                "生产 Cookie 行为待验证",
                "通过",
                "通过",
                "条件验收",
            ],
            ("R1、R2 通过；R3 条件验收", "上线首周监控并补验生产跨域退出"),
            [
                "三项要求必须分别落到证据和结论，不能把未验证项写成完全通过。",
                "OIDC 登录入口、state、nonce 和 PKCE 已由 12 条用例覆盖。",
                "角色映射与本地证据覆盖 admin、operator、auditor。",
                "生产跨域 Cookie 行为尚无真实运行证据。",
                "先上线已验证部分，同时保留补验和回退动作。",
            ],
        ),
        ["逐项要求、证据和结论使用同一矩阵。", "条件验收不得伪装为通过。", "验收矩阵属于决策沟通，不是独立图族。"],
    ),
    Sample(
        "07_故障调试_批处理重复消费.html",
        "fault-debugging",
        "causal-chain",
        "故障因果图｜批处理重复消费",
        "从日志观测与任务行为收敛假设，定位租约失效与幂等缺口的共同根因，并绑定修复与回归验证。",
        "批处理重复消费",
        "观测—假设—根因—修复—验证因果链",
        numbered(
            [
                "批处理重复消费因果链",
                "三个观测收敛到两个假设，再定位共同根因、修复动作与验证结果。",
                "现场观测",
                "候选假设",
                "共同根因",
                "修复动作",
                "回归验证",
                "结果",
                "同批次执行两次",
                "09:00 与 09:03 重复启动",
                "租约提前失效",
                "心跳延迟超过租约窗口",
                "消费幂等表缺失",
                "相同 eventId 写入两次",
                "调度器重启",
                "实例切换触发重复领取",
                "幂等键未落库",
                "业务写入缺少唯一约束",
                "租约与幂等双缺口",
                "重启窗口允许重复处理",
                "延长租约并续约",
                "加入心跳与 fencing token",
                "增加 eventId 唯一键",
                "并发回放无重复写入",
                "重复数 0",
                "回归连续通过",
                "重复启动支持调度器假设",
                "租约日志支持调度器假设",
                "租约日志也支持幂等缺口",
                "重复写入支持幂等缺口",
                "调度器假设指向共同根因",
                "幂等假设指向共同根因",
                "共同根因决定修复",
                "修复后执行并发回放",
                "验证结果形成结论",
                "失败则返回修复",
                "节点详情",
                "点击观测、假设、根因、修复或验证查看证据边界。",
                "同一批次在三分钟内出现两次执行记录。",
                "调度器心跳延迟导致租约在任务完成前失效。",
                "相同 eventId 出现两条业务写入。",
                "实例重启解释重复领取，但不能单独解释重复落库。",
                "没有唯一幂等键使第二次消费能够再次写入。",
                "租约与幂等约束同时缺失才解释全部现象。",
                "续约与 fencing token 阻止过期实例继续提交。",
                "eventId 唯一键拦截重复副作用。",
                "并发回放后重复写入为零。",
                "因果关系",
            ],
        ),
        ["观测只陈述现场事实。", "候选假设必须被多个观测支持。", "回归失败返回修复动作。"],
    ),
    Sample(
        "08_功能迭代_订单通知链路.html",
        "feature-iteration",
        "current-target-flow",
        "当前态—目标态迭代图｜订单通知链路",
        "旧“发布回滚图”入口迁移为当前态—目标态视图：逐项说明保留、替换、新增和淘汰，不再用发布流程卡片冒充迭代图。",
        "订单通知链路迭代",
        "当前态与目标态逐项对齐",
        {
            1: "同步发送通知",
            2: "订单线程直接调用短信",
            3: "失败整单重试",
            4: "通知与订单耦合",
            5: "单通道发送",
            6: "仅短信且无降级",
            7: "无独立观测",
            8: "只能查看订单日志",
            9: "四项能力从当前态演进到目标态",
            10: "Outbox 事件化",
            11: "订单事务只写通知事件",
            12: "通知幂等重试",
            13: "失败按 eventId 重试",
            14: "多通道策略",
            15: "短信、邮件与站内信降级",
            16: "独立可观测性",
            17: "延迟、失败率与积压告警",
            18: "订单通知链路当前态—目标态",
            21: "替换",
            24: "解耦",
            27: "扩展",
            30: "新增",
            40: "同步调用替换为 Outbox 事件",
            41: "整单重试拆分为通知幂等重试",
            42: "单短信扩展为多通道策略",
            43: "新增通知链路观测面",
            47: "窄屏变化摘要",
            48: "同步发送 → Outbox 事件化",
            49: "整单重试 → 通知幂等重试",
            50: "单通道 → 多通道策略",
            51: "无独立观测 → 延迟与积压告警",
            52: "保留订单事务一致性边界",
            53: "淘汰订单线程内外部调用",
            54: "新增 eventId 幂等键",
            55: "新增独立通知运行面",
            56: "当前态",
            57: "目标态",
            58: "迭代节点详情",
            59: "逐项说明当前问题、目标能力与变化边界。",
            60: "同步外部调用放大订单响应时间和故障半径。",
            61: "通知失败会触发整单重试，产生重复副作用风险。",
            62: "只有短信通道，供应商故障时没有降级。",
            63: "订单日志无法独立反映通知延迟和积压。",
            64: "订单事务写 Outbox，通知消费者异步处理。",
            65: "按 eventId 幂等重试，不再重复执行订单。",
            66: "通道策略按可用性降级到邮件或站内信。",
            67: "新增延迟、失败率、积压和死信告警。",
        },
        ["当前态与目标态一一对应。", "每条变化关系为直线。", "发布和回滚流程另行使用业务流程图。"],
    ),
    Sample(
        "09_页面原型_移动库存扫码状态.html",
        "page-mockup",
        "artboard-wireframe",
        "页面原型｜移动库存扫码作业台",
        "中保真响应式页面原型：使用真实搜索、筛选、按钮、表格、状态切换和分页，不使用设备外框或流程箭头冒充页面。",
        "移动库存扫码页面",
        "真实 HTML 控件与状态切换",
        numbered(
            [
                "库存作业台",
                "扫码记录",
                "异常队列",
                "任务设置",
                "搜索条码或库位",
                "状态",
                "全部状态",
                "仅看异常",
                "开始扫码",
                "128",
                "今日扫描",
                "124",
                "识别成功",
                "4",
                "待人工处理",
                "正常列表",
                "空状态",
                "条码",
                "库位",
                "状态",
                "操作",
                "6901234567890",
                "A-01-03",
                "识别成功",
                "查看",
                "6909876543210",
                "B-02-11",
                "重复条码",
                "处理",
                "手工输入",
                "C-04-08",
                "待确认",
                "录入",
                "等待下一次扫描",
                "支持扫码枪、摄像头或手工输入；异常记录进入人工队列。",
                "上一页",
                "第 1 页",
                "下一页",
                "窄屏页面摘要",
                "工具栏在窄屏改为单列。",
                "表格保留横向滚动，不压缩字段。",
                "正常、空状态与异常状态可切换。",
            ]
        ),
        ["页面控件均为真实 HTML。", "空状态由运行时按钮切换。", "窄屏按页面结构重排。"],
        {1: "库存扫码作业页面", 2: "页面应用外壳", 3: "库存作业导航", 4: "筛选工具栏", 5: "搜索库存条码或库位", 6: "筛选扫描状态", 7: "作业指标", 8: "今日扫码指标", 9: "列表模式切换", 10: "库存扫码记录表", 11: "记录表格", 12: "空状态提示", 13: "列表分页", 14: "分页控制"},
    ),
    Sample(
        "10_状态数据_订单取消状态机.html",
        "state-data-model",
        "state-machine",
        "状态机图｜订单取消生命周期",
        "以规范初态、可持续状态、事件与守卫、终态和必要回环描述订单取消；普通处理步骤不冒充状态。",
        "订单取消状态机",
        "初态、状态、守卫、终态与回环",
        numbered(
            [
                "开始",
                "收到取消命令",
                "待取消",
                "订单进入取消处理",
                "取消处理中",
                "检查 warehouseLocked",
                "已取消",
                "仓库未锁定",
                "取消失败",
                "仓库已锁定，等待人工",
                "流程终止",
                "结果已持久化",
                "初态",
                "可取消",
                "守卫判定",
                "持久结果",
                "终态",
                "订单取消状态机",
                "取消命令触发状态转换；守卫决定成功或失败，人工解锁后可重试。",
                "CancelRequested",
                "检查守卫",
                "[未锁定] / cancel",
                "[已锁定] / reject",
                "持久化 persist",
                "人工解锁 / 重试 retry",
                "初态进入待取消",
                "待取消进入守卫判定",
                "未锁定转为已取消",
                "已锁定转为取消失败",
                "持久化后进入终态",
                "人工解锁后重试",
                "窄屏状态关系",
                "状态转换关系",
                "开始",
                "待取消",
                "取消命令",
                "待取消",
                "取消处理中",
                "检查守卫",
                "取消处理中",
                "已取消",
                "仓库未锁定",
                "取消处理中",
                "取消失败",
                "仓库已锁定",
                "已取消",
                "流程终止",
                "持久化结果",
                "取消失败",
                "待取消",
                "人工解锁后重试",
                "状态详情",
                "点击状态查看持续条件、进入事件与离开效果。",
                "命令尚未执行，只表示状态机入口。",
                "订单已接收取消请求，等待执行取消逻辑。",
                "读取 warehouseLocked 并执行守卫判断。",
                "取消成功已经持久化，不再接受重复取消。",
                "取消失败保留原因，等待人工解锁。",
                "订单取消状态机已结束。",
            ]
        ),
        ["状态节点表示可持续事实。", "转换文案包含事件、守卫或效果。", "人工解锁是有语义原因的反馈回环。"],
    ),
    Sample(
        "11_系统架构_多租户SaaS工作负载.html",
        "system-architecture",
        "workload-overview",
        "系统架构图｜多租户 SaaS 工作负载",
        "从多入口租户身份，经边缘解析与共享工作负载进入隔离的数据面、租户控制面、外部依赖和共享基础设施。",
        "多租户 SaaS 系统架构",
        "保留成熟架构语法并清除溢出与无意义折线",
        SYSTEM_MAIN,
        [
            "每个入口在边缘层完成认证并建立 tenant context。",
            "共享业务服务保持无状态并透传 tenantId。",
            "数据与资源按行策略、命名空间和密钥映射隔离。",
            "租户控制面管理开通、配额、迁移与停用。",
            "外部依赖通过适配层接入，故障不直接穿透核心负载。",
            "观测数据按 tenantId 聚合并支持人工隔离。",
            "共享基础设施承载计算、数据、消息、密钥和备份。",
        ],
        {
            3: "租户客户端",
            5: "边缘接入与租户解析",
            6: "共享业务工作负载",
            7: "数据与资源隔离",
            8: "外部依赖",
            9: "租户控制面",
            10: "观测与故障隔离",
            11: "共享基础设施",
            34: "租户访问入口",
            35: "共享工作负载",
            36: "外部依赖与运维",
            37: "租户控制面",
            38: "共享基础设施",
            39: "租户入口",
            40: "边缘接入",
            41: "业务负载",
            42: "数据隔离",
            43: "外部依赖",
            44: "控制面",
            45: "观测隔离",
            46: "基础设施",
        },
    ),
    Sample(
        "12_技术设计_订单创建完整设计.html",
        "technical-design",
        "technical-design-package",
        "完整技术设计｜订单创建与事件投递",
        "总览、运行时序、数据契约、状态一致性、失败恢复与发布验证连续展开，且分别复用成熟图族内核。",
        "订单创建技术设计",
        "六视图完整技术设计",
        technical_package_text(),
        [
            "订单与 Outbox 在同一事务中提交。",
            "投递器在 broker ack 后推进事件状态。",
            "消费者按 eventId 幂等更新库存投影。",
            "失败恢复保留自动重试、人工处置和复核汇合。",
            "发布验证明确灰度门禁与失败动作。",
            "六个视图共享同一组设计事实，不相互重复替代。",
        ],
    ),
]


def default_text(sample: Sample, number: int) -> str:
    fact = sample.facts[(number - 1) % len(sample.facts)]
    if number < 120:
        return fact
    return f"{fact} 该项属于“{sample.short_title}”的结构化节点详情。"


def contains_han(value: str) -> bool:
    return any("\u3400" <= character <= "\u9fff" for character in value)


def infer_primary_labels(template: str, texts: Dict[int, str]) -> Dict[int, str]:
    result: Dict[int, str] = {}
    pattern = re.compile(
        r'data-node-primary-label="\{\{canvas-attribute-(\d{3})\}\}"'
        r'(?:(?!data-node-primary-label=).){0,900}?'
        r'(?:data-node-title[^>]*>|data-slot="layout-slot-\d{3}"[^>]*>)'
        r'\{\{canvas-text-(\d{3})\}\}',
        re.S,
    )
    for attribute_number, text_number in pattern.findall(template):
        label = texts[int(text_number)]
        result[int(attribute_number)] = label if contains_han(label) else f"技术节点：{label}"
    return result


def infer_icon_texts(template: str) -> set[int]:
    return {
        int(number)
        for number in re.findall(
            r'data-node-icon[^>]*>[\s\n]*\{\{canvas-text-(\d{3})\}\}', template
        )
    }


def infer_relation_attributes(template: str) -> Dict[int, str]:
    result: Dict[int, str] = {}
    for match in re.finditer(
        r'<path\b(?P<attrs>[^>]*data-relation-kind="\{\{canvas-attribute-(?P<number>\d{3})\}\}"[^>]*)>',
        template,
    ):
        attrs = match.group("attrs")
        number = int(match.group("number"))
        intent = re.search(r'data-route-intent="([^"]+)"', attrs)
        value = intent.group(1) if intent else "flow"
        if value == "direct":
            value = "flow"
        result.setdefault(number, value)
    return result


def attribute_value(name: str, number: int, sample: Sample, inferred: Dict[int, str]) -> str:
    if number in sample.attributes:
        return sample.attributes[number]
    if number in inferred:
        return inferred[number]
    if name == "aria-label":
        return f"{sample.short_title}主画布"
    if name == "data-reading-guide":
        return "先看主画布，再按需查看节点详情"
    if name == "data-detail-close-label":
        return "关闭详情"
    if name == "data-semantic-role":
        return f"{sample.short_title}语义角色{number}"
    if name == "data-semantic":
        return f"{sample.short_title}关系语义{number}"
    if name == "data-relation-kind":
        return "flow"
    if name == "data-branch-outcome":
        return "是" if number % 2 else "否"
    if name == "placeholder":
        return "输入关键字"
    return f"{sample.short_title}-{number}"


def replace_attributes(payload: str, sample: Sample, inferred: Dict[int, str]) -> str:
    pattern = re.compile(r'(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)="\{\{canvas-attribute-(?P<number>\d{3})\}\}"')

    def replacement(match: re.Match[str]) -> str:
        name = match.group("name")
        number = int(match.group("number"))
        value = html.escape(attribute_value(name, number, sample, inferred), quote=True)
        return f'{name}="{value}"'

    payload = pattern.sub(replacement, payload)
    return ATTRIBUTE_TOKEN_RE.sub(
        lambda match: html.escape(
            sample.attributes.get(int(match.group(1)), f"{sample.short_title}-{int(match.group(1))}"),
            quote=True,
        ),
        payload,
    )


def localize_static_shell(payload: str) -> str:
    markup, separator, scripts = payload.partition("<script")
    replacements = {
        'aria-label="Diagram reading guide"': 'aria-label="图表关系与证据图例"',
        'aria-label="Diagram scale controls"': 'aria-label="图表缩放控制"',
        'aria-label="Diagram zoom controls"': 'aria-label="图表缩放控制"',
        'aria-label="Sequence scale controls"': 'aria-label="时序图缩放控制"',
        ">Reading guide<": ">关系图例<",
        ">Line types<": ">关系类型<",
        ">Evidence states<": ">证据状态<",
        ">Observed implementation<": ">用户提供事实<",
        ">Completed check<": ">已完成检查<",
        ">Not yet verified<": ">尚未验证<",
        ">Interaction<": ">交互方式<",
        ">Auto<": ">自适应<",
        ">Fit width<": ">自适应<",
        'data-diagram-status-fit="Fit width"': 'data-diagram-status-fit="自适应"',
        'data-diagram-status-fits="Fits at 100%"': 'data-diagram-status-fits="当前 100% 已适配"',
        'data-diagram-status-scroll="Scroll"': 'data-diagram-status-scroll="画布内横向滚动"',
        'data-sequence-status-fit="Fit width"': 'data-sequence-status-fit="自适应"',
        'data-sequence-status-fits="Fits at 100%"': 'data-sequence-status-fits="当前 100% 已适配"',
        'data-sequence-status-scroll="Scroll"': 'data-sequence-status-scroll="画布内横向滚动"',
    }
    for source, target in replacements.items():
        markup = markup.replace(source, target)
    return markup + (separator + scripts if separator else "")


def render_sample(sample: Sample) -> str:
    template_path = TEMPLATE_ROOT / sample.family / f"{sample.template}.html"
    payload = template_path.read_text(encoding="utf-8")
    payload = payload.replace('<html lang="en">', '<html lang="zh-CN">', 1)
    payload = re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(sample.title)}</title>",
        payload,
        count=1,
        flags=re.DOTALL,
    )
    texts = {
        number: sample.texts.get(number, default_text(sample, number))
        for number in {int(value) for value in TEXT_TOKEN_RE.findall(payload)}
    }
    for number in infer_icon_texts(payload):
        if not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", texts[number]):
            texts[number] = "🧩"

    inferred = infer_relation_attributes(payload)
    inferred.update(infer_primary_labels(payload, texts))
    payload = replace_attributes(payload, sample, inferred)
    payload = TEXT_TOKEN_RE.sub(
        lambda match: html.escape(texts[int(match.group(1))]), payload
    )

    common = {
        "title": sample.title,
        "summary": sample.summary,
        "reading-guide-line-01": "主关系",
        "reading-guide-line-02": "成功 / 确认",
        "reading-guide-line-03": "异常 / 反馈",
        "reading-guide-line-04": "约束 / 复核",
        "evidence-observed-for": "layout-node-001",
        "evidence-observed-source": "用户场景事实",
        "evidence-check-for": "layout-node-002",
        "evidence-check-source": "0.1.10 静态契约",
        "evidence-unresolved-for": "layout-node-003",
        "evidence-unresolved-source": "真实客户端生命周期未执行",
        "interaction-hint": "点击任一主节点查看对应详情",
        "routing_confidence": "high",
    }
    for token, value in common.items():
        payload = payload.replace("{{" + token + "}}", html.escape(value, quote=True))

    payload = localize_static_shell(payload)
    unresolved = TOKEN_RE.findall(payload)
    if unresolved:
        raise ValueError(f"{sample.filename} has unresolved tokens: {sorted(set(unresolved))}")
    if "如何阅读本图" in payload or "适应宽度" in payload:
        raise ValueError(f"{sample.filename} retained a removed shell phrase")
    return payload


def render_index(samples: List[Sample]) -> str:
    family_count = len({sample.family for sample in samples})
    nav = "".join(
        f'<a href="#sample-{index:02d}">{index:02d} {html.escape(sample.short_title)}</a>'
        for index, sample in enumerate(samples, 1)
    )
    sections = "".join(
        f"""
        <article id="sample-{index:02d}" class="sample">
          <header>
            <div><span>{index:02d} / {html.escape(sample.family.upper())}</span>
              <h2>{html.escape(sample.short_title)}</h2>
              <p>{html.escape(sample.purpose)}</p>
            </div>
            <a class="open" href="{OUTPUT_SUBDIRECTORY}/{html.escape(sample.filename, quote=True)}">打开完整 HTML</a>
          </header>
          <iframe loading="lazy" title="{html.escape(sample.short_title, quote=True)}"
                  src="{OUTPUT_SUBDIRECTORY}/{html.escape(sample.filename, quote=True)}"></iframe>
        </article>"""
        for index, sample in enumerate(samples, 1)
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Vibe Diagram 0.1.10｜十二类真实场景回归</title>
  <style>
    :root {{ color-scheme: light; --ink:#142438; --muted:#617086; --line:#bdd0e2; --blue:#0877ff; }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; color:var(--ink); background:#eef3f8; font:15px/1.55 Inter,"PingFang SC","Microsoft YaHei",sans-serif; }}
    .hero {{ padding:42px max(24px,calc((100vw - 1360px)/2)); background:#fff; border-bottom:1px solid var(--line); }}
    .hero span {{ color:#0d62b7; font-size:12px; font-weight:900; letter-spacing:.16em; }}
    h1 {{ margin:.35rem 0 .45rem; font-size:clamp(30px,4vw,52px); letter-spacing:-.04em; }}
    .hero p {{ max-width:850px; margin:0; color:var(--muted); font-size:17px; }}
    .hero b {{ color:#0c7655; }}
    nav {{ position:sticky; z-index:10; top:0; display:flex; gap:6px; overflow:auto; padding:6px max(24px,calc((100vw - 1360px)/2)); background:rgba(255,255,255,.97); border-bottom:1px solid var(--line); backdrop-filter:blur(14px); }}
    nav a {{ flex:0 0 auto; padding:4px 9px; border:1px solid #c7d7e7; border-radius:6px; color:#29425e; text-decoration:none; font-size:11px; font-weight:800; line-height:1.3; }}
    main {{ width:min(1360px,calc(100% - 32px)); margin:28px auto 80px; display:grid; gap:28px; }}
    .sample {{ scroll-margin-top:70px; overflow:hidden; background:#fff; border:1px solid var(--line); border-radius:14px; box-shadow:0 12px 30px rgba(26,61,94,.08); }}
    .sample > header {{ display:flex; align-items:end; justify-content:space-between; gap:20px; padding:20px 24px; border-bottom:1px solid var(--line); }}
    .sample header span {{ color:#0d62b7; font-size:11px; font-weight:900; letter-spacing:.12em; }}
    h2 {{ margin:.2rem 0 0; font-size:25px; letter-spacing:-.02em; }}
    .sample header p {{ margin:.15rem 0 0; color:var(--muted); }}
    .open {{ flex:0 0 auto; padding:10px 14px; color:#fff; background:#0d6fbd; border-radius:7px; text-decoration:none; font-weight:850; }}
    iframe {{ display:block; width:100%; height:900px; border:0; background:#fff; }}
    @media (max-width:700px) {{
      .hero {{ padding:28px 18px; }}
      nav {{ padding:5px 16px; }}
      main {{ width:100%; margin-block-start:16px; }}
      .sample {{ border-radius:0; border-inline:0; }}
      .sample > header {{ align-items:start; padding:16px; flex-direction:column; }}
      iframe {{ height:844px; }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <span>VIBE DIAGRAM / 0.1.10 / CANONICAL REGENERATION</span>
    <h1>十二类真实场景回归</h1>
    <p>{len(samples)} 个真实场景覆盖 {family_count} 个公开图族，均从 0.1.10 canonical template 重新生成。<b>静态契约、真实浏览器布局、客户端生命周期分开记账</b>；本索引只用于逐图人工审阅。</p>
  </header>
  <nav aria-label="样例导航">{nav}</nav>
  <main>{sections}</main>
</body>
</html>
"""


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename in STALE_SAMPLE_FILENAMES:
        stale_path = OUTPUT_DIR / filename
        if stale_path.is_file() and not stale_path.is_symlink():
            stale_path.unlink()
    for sample in SAMPLES:
        (OUTPUT_DIR / sample.filename).write_text(
            render_sample(sample), encoding="utf-8"
        )
    INDEX_PATH.write_text(render_index(SAMPLES), encoding="utf-8")
    print(f"generated {len(SAMPLES)} samples and {INDEX_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
