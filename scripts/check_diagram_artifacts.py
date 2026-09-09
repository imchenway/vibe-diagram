#!/usr/bin/env python3
"""直接运行技能的真实生成入口，检查五种图法、原生 HTML 和失败保护；不伪造浏览器结果。"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# 全部行为从当前 canonical 核心取得，示例只提供业务数据。
ROOT = Path(__file__).resolve().parents[1]
# 隔离技能包验证可覆盖此位置，不依赖 docs 中的文件。
CORE = ROOT / 'skills/vibe-diagram'
sys.path.insert(0, str(CORE / 'scripts'))
from vibe_diagram_lint import lint_text
from vibe_diagram_scaffold import render, SHELL_CSS, SHELL_JS
from vibe_diagram_artifact import accept, compare, digest, parse, prepare
from update_skill import _verify_candidate, tree_sha256, UpdateError


def manifest(name, family, title, summary, roles=None):
    """验收设定明确标成拟议示例，不声称生产事实。"""
    return {'$schema':'vibe-diagram/artifact-manifest@1','artifactId':'native-'+name,'language':'zh-CN','title':title,'audience':['product-manager'],'questions':[{'id':'main-question','text':'这张图说明什么业务规则？','priority':'critical','answeredBy':['diagram-summary']}],'criticalFacts':[{'id':'main-rule','statement':summary,'status':'proposed','visibleIn':['diagram-summary'],'evidenceIds':['example']}],'views':[{'id':name,'family':family,'role':'primary','elementId':name+'-view'}],'evidence':[{'id':'example','status':'proposed','sourceKind':'demonstration','source':'本地验收设定，不代表生产规则','supports':['main-rule']}],'extensions':{'nodeRoles':roles or {}}}


def meta(title, summary):
    """固定业务语言及原主题预设，不固定节点或关系模板。"""
    return {'title':title,'subtitle':summary,'locale':'zh-CN','animation':'trace','visual_preset':'signal-flow','quality_profile':'showcase'}


def sources():
    """五类独立事实用于验证入口，没有在生产技能中固化业务节点。"""
    # 架构关系体现分工与信息流向。
    architecture={'schema_version':1,'diagram_type':'architecture','meta':meta('架构关系图｜预约提醒分工','示例设定：预约服务保存预约，消息服务负责向用户发送提醒。'),'components':[{'id':'booking','type':'backend','label':'预约服务','pos':[40,100],'size':[140,64]},{'id':'records','type':'database','label':'预约记录','pos':[340,100],'size':[140,64]},{'id':'notice','type':'messagebus','label':'提醒服务','pos':[640,100],'size':[140,64]}],'connections':[{'id':'save','from':'booking','to':'records','label':'保存预约'},{'id':'remind','from':'records','to':'notice','label':'提供到期预约'}]}
    # 流程包含条件出口；无库存与成功结束不能合并。
    workflow={'schema_version':2,'diagram_type':'workflow','meta':meta('流程图｜预约名额检查','示例设定：有名额才确认预约；没有名额时提示改期，不占用名额。'),'lanes':[{'id':'main','label':'预约办理'},{'id':'exit','label':'未确认'}],'phases':[],'groups':[],'mainPath':['start','available','confirm'],'nodes':[{'id':'start','type':'external','label':'提交预约','lane':'main','col':0,'width':140},{'id':'available','type':'security','label':'还有名额？','lane':'main','col':1,'width':140},{'id':'confirm','type':'backend','label':'确认预约','lane':'main','col':2,'width':140},{'id':'rejected','type':'external','label':'提示改期','lane':'exit','col':2,'width':140}],'edges':[{'id':'request','from':'start','to':'available','label':'检查名额'},{'id':'yes','from':'available','to':'confirm','label':'有名额'},{'id':'no','from':'available','to':'rejected','label':'无名额'}]}
    # 时序保留请求、返回及异步发送的区别。
    sequence={'schema_version':1,'diagram_type':'sequence','meta':meta('时序图｜预约确认与提醒','示例设定：页面收到预约结果后立即展示；提醒另行异步发送。'),'participants':[{'id':'page','type':'frontend','label':'预约页面'},{'id':'service','type':'backend','label':'预约服务'},{'id':'notice','type':'messagebus','label':'提醒服务'}],'messages':[{'id':'submit','from':'page','to':'service','y':175,'label':'提交预约','variant':'default'},{'id':'result','from':'service','to':'page','y':230,'label':'返回预约结果','variant':'return'},{'id':'notify','from':'service','to':'notice','y':310,'label':'异步安排提醒','variant':'dashed'}]}
    sequence['meta']['viewBox']=[680,480]
    # 状态转换使用明确事件，不凭相邻排列补造转换。
    lifecycle={'schema_version':1,'diagram_type':'lifecycle','meta':meta('状态图｜预约状态变化','示例设定：待确认的预约可被确认；已确认后由核销事件进入已完成。'),'lanes':[{'id':'main','label':'预约状态'}],'states':[{'id':'pending','type':'start','label':'待确认','lane':'main','col':0,'width':100},{'id':'confirmed','type':'active','label':'已确认','lane':'main','col':1,'width':100},{'id':'completed','type':'success','label':'已完成','lane':'main','col':2,'width':100}],'transitions':[{'id':'confirm','from':'pending','to':'confirmed','label':'确认预约'},{'id':'finish','from':'confirmed','to':'completed','label':'核销完成'}]}
    lifecycle['meta']['viewBox']=[720,566]
    return [('architecture','architecture',architecture,{}),('workflow','business-flow',workflow,{'start':'start','available':'decision','confirm':'end','rejected':'end'}),('sequence','code-sequence',sequence,{}),('lifecycle','state-machine',lifecycle,{'pending':'initial','completed':'terminal'})]


def entity_svg():
    """实体图直接编写实际 SVG，保留关键字段与可见数量关系。"""
    return '''<svg xmlns="http://www.w3.org/2000/svg" id="entities" viewBox="0 0 760 280">
<style>/* 实体使用既有主题色，字段和连线在离线导出中保持可编辑。 */
text {font-family:system-ui,-apple-system,sans-serif;fill:#10243a;font-size:15px} .entity-box{fill:#e8f3fb;stroke:#176aa6;stroke-width:1.5} .relation{fill:none;stroke:#176aa6;stroke-width:1.5}</style>
<g id="customer" data-vd-node="entity"><rect data-vd-shape="" class="entity-box" x="40" y="80" width="200" height="140" rx="12"/><text x="60" y="112" font-weight="600">客户</text><text x="60" y="150">客户编号 · 唯一</text><text x="60" y="180">姓名</text></g>
<g id="booking" data-vd-node="entity"><rect data-vd-shape="" class="entity-box" x="520" y="80" width="200" height="140" rx="12"/><text x="540" y="112" font-weight="600">预约</text><text x="540" y="150">预约编号 · 唯一</text><text x="540" y="180">所属客户编号</text></g>
<path id="customer-bookings" class="relation" d="M240 150 H520" data-vd-edge="owns" data-from="customer" data-to="booking" data-vd-cardinality="1:0..N"/>
<text id="customer-bookings-label" data-vd-edge-label="customer-bookings" x="380" y="130" text-anchor="middle">一位客户可有零至多份预约</text>
</svg>'''


def run_cli(core, arguments, success=True):
    """调用独立进程；失败输入不得悄悄生成部分文件。"""
    result=subprocess.run([sys.executable,str(core/'scripts/vibe_diagram_build.py'),*map(str,arguments)],capture_output=True,text=True)
    if (result.returncode == 0) != success:
        raise RuntimeError(result.stdout+result.stderr)
    return json.loads(result.stdout or result.stderr)


def check(output, core):
    """生成代表性产物并核对关系数量、语义差异、不可覆盖与失效候选拒绝。"""
    output.mkdir(parents=True,exist_ok=True)
    # 升级器验证直接分发核心；客户端生成包另含适配文件，由包管理器负责完整性。
    _verify_candidate(CORE, json.loads((CORE/'update.json').read_text()))
    with tempfile.TemporaryDirectory() as directory:
        # 即使重新计算摘要，缺少运行入口的包也必须被安装前检查拒绝。
        candidate=Path(directory)/'candidate';shutil.copytree(CORE,candidate,ignore=shutil.ignore_patterns('__pycache__'))
        (candidate/'scripts/vibe_diagram_native.py').unlink()
        candidate_manifest=json.loads((candidate/'update.json').read_text())
        candidate_manifest['tree_sha256']=tree_sha256(candidate)
        (candidate/'update.json').write_text(json.dumps(candidate_manifest))
        try:
            _verify_candidate(candidate,candidate_manifest)
        except UpdateError as error:
            assert 'scripts/vibe_diagram_native.py' in str(error)
        else:
            raise AssertionError('缺少原生入口的包不能通过检查')
    # 独立输出目录防止覆盖上一次人工检查的候选。
    records=[]
    for name,family,source,roles in sources():
        payload=manifest(name,family,source['meta']['title'],source['meta']['subtitle'],roles)
        source_path=output/(name+'.json');manifest_path=output/(name+'.manifest.json')
        source_path.write_text(json.dumps(source,ensure_ascii=False,indent=2));manifest_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
        records.append(run_cli(core,['--input',source_path,'--manifest',manifest_path,'--output',output/(name+'.html')]))
    # 单一生命周期不能凭空出现未定义的中断区或结果区。
    lifecycle_parser,_=parse((output/'lifecycle.html').read_text())
    lifecycle_text=' '.join(element.text for element in lifecycle_parser.elements if element.tag=='text')
    assert '预约状态' in lifecycle_text and 'Interruptions + recovery' not in lifecycle_text and 'Outcomes' not in lifecycle_text
    # 相同查看器承接实体数量关系，数据流引擎不冒充实体关系引擎。
    svg=output/'data.svg';svg.write_text(entity_svg())
    summary='示例设定：一位客户可有零至多份预约；每份预约只属于一位客户。'
    payload=manifest('data','data-model','数据关系图｜客户与预约',summary)
    data_manifest=output/'data.manifest.json';data_manifest.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    records.append(run_cli(core,['--svg',svg,'--summary',summary,'--manifest',data_manifest,'--output',output/'data.html']))
    # 英文标题包含特殊字符，数据流和作者 SVG 必须与页面及覆盖清单逐字一致。
    english_title='Data flow｜Booking & reminder <rules>'
    english_summary='Demonstration: confirmed bookings supply reminder recipients.'
    english={'schema_version':1,'diagram_type':'dataflow','meta':{'title':english_title,'subtitle':english_summary,'locale':'en'},'stages':[{'label':'Booking'},{'label':'Reminder'}],'nodes':[{'id':'bookings','type':'database','label':'Bookings','stage':0,'row':0},{'id':'reminders','type':'backend','label':'Reminders','stage':1,'row':0}],'flows':[{'id':'recipients','from':'bookings','to':'reminders','label':'Supply recipients'}]}
    english_manifest=manifest('dataflow','architecture',english_title,english_summary);english_manifest['language']='en'
    (output/'dataflow.json').write_text(json.dumps(english));(output/'dataflow.manifest.json').write_text(json.dumps(english_manifest))
    records.append(run_cli(core,['--input',output/'dataflow.json','--manifest',output/'dataflow.manifest.json','--output',output/'dataflow.html']))
    english_manifest=manifest('data-english','data-model','Data model｜Customers & bookings <rules>',english_summary);english_manifest['language']='en'
    (output/'data-english.manifest.json').write_text(json.dumps(english_manifest))
    records.append(run_cli(core,['--svg',svg,'--summary',english_summary,'--manifest',output/'data-english.manifest.json','--output',output/'data-english.html']))
    # 原生 HTML 表格仍走轻量外壳，避免给静态表格塞入图形控件。
    title='比较表｜预约结果';text=render(title,'zh-CN',SHELL_CSS.read_text(),SHELL_JS.read_text())
    payload=manifest('matrix','comparison-matrix',title,summary)
    start=text.index('<script id="vibe-diagram-manifest"');end=text.index('</script>',start)
    text=text[:start]+'<script id="vibe-diagram-manifest" type="application/json">'+json.dumps(payload,ensure_ascii=False)+text[end:]
    text=text.replace('<p data-vd-summary data-vd-scaffold-empty></p>','<p data-vd-summary>示例：仅有名额时确认预约。</p>')
    start=text.index('<main data-vd-content');end=text.index('</main>',start)
    text=text[:start]+'''<main data-vd-content><section id="matrix-view" data-vd-view="matrix" data-vd-family="comparison-matrix" data-vd-view-role="primary"><h2 data-vd-view-title>比较表｜预约结果</h2><p id="diagram-summary" data-vd-critical>有名额则确认，没有名额则提示改期。</p><table data-vd-matrix><tr><th>条件</th><th>结果</th></tr><tr data-vd-difference><th>有名额</th><td>确认预约</td></tr><tr><th>无名额</th><td>提示改期</td></tr></table><p data-vd-conclusion>名额检查先于预约确认。</p></section>'''+text[end:]
    assert not lint_text(text),lint_text(text)
    (output/'matrix.html').write_text(text)
    # 几何变化与事实变化必须独立，稳定身份不按近似名称合并。
    flow=(output/'workflow.html').read_text()
    assert any(item['kind']=='changed' for item in compare(flow,flow.replace('提示改期','建议其他时段'))['changes'])
    assert lint_text((output/'data.html').read_text().replace('data-vd-cardinality="1:0..N"',''))
    before=(output/'workflow.html').read_bytes()
    run_cli(core,['--input',output/'workflow.json','--manifest',output/'workflow.manifest.json','--output',output/'workflow.html'],False)
    assert (output/'workflow.html').read_bytes()==before
    # 错误端点不允许产生目标 HTML。
    source=json.loads((output/'workflow.json').read_text());source['edges'][0]['to']='missing'
    bad=output/'bad-source.json';bad.write_text(json.dumps(source,ensure_ascii=False))
    run_cli(core,['--input',bad,'--manifest',output/'workflow.manifest.json','--output',output/'bad.html'],False)
    assert not (output/'bad.html').exists()
    with tempfile.TemporaryDirectory() as directory:
        # 只构造拒绝路径，不生成任何伪造的通过记录。
        folder=Path(directory);candidate=folder/'candidate.html';final=folder/'final.html';final.write_bytes(b'previous output')
        result=prepare(SimpleNamespace(input=str(output/'workflow.html'),output=str(candidate),previous=None,allow_candidates=False))
        candidate.write_text(candidate.read_text()+'<!-- modified -->')
        try:
            accept(SimpleNamespace(input=str(candidate),output=str(final),sha256=result['sha256'],previous_sha256=digest(final.read_bytes()),report='not-read.json',reading_review='不应执行',allow_candidates=False))
            raise AssertionError('失效候选不能替换旧图')
        except ValueError:
            assert final.read_bytes()==b'previous output'
    return {'status':'generation-checks-passed','artifacts':records,'browser_layout':'not-verified','client_runtime':'not-verified'}


def main():
    """输出具名生成证据，浏览器验收另行进行。"""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--core',type=Path,default=CORE)
    args=parser.parse_args()
    print(json.dumps(check(args.output.resolve(),args.core.resolve()),ensure_ascii=False))


if __name__=='__main__':
    main()
