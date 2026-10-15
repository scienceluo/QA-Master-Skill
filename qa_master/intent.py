"""Conservative Chinese/English natural-language intent planner; no side effects."""
from __future__ import annotations
from dataclasses import dataclass, asdict
STAGE_ALIASES={
 'requirements':('需求分析','分析需求','整理需求','逆向需求','requirements analysis'),
 'review':('需求评审','评审需求','review requirements'),
 'design':('测试用例','写用例','生成用例','用例设计','测试设计','test cases','test case'),
 'code_refinement':('分析代码','阅读源码','白盒','code review','代码分析','更新用例'),
 'regression':('回归测试','做回归','回归验证','regression'),
 'report':('测试报告','生成报告','测试总结','test report'),
 'execution':('执行测试','开始测试','运行测试','跑测试','run tests','execute tests')}
NEGATED_EXECUTION=('不执行测试','不要执行测试','暂不执行测试','不开始测试','先不测试','开发还没完成',
 '开发还在进行','等待开发','不跑测试','不要运行测试','严禁执行','禁止执行','无需执行','不得执行','不能执行','do not run tests','without executing','never execute','must not execute')
NEGATED_WRITE=('不导入','不要导入','不创建','不要创建','不要写入','不提交bug','不要提交bug','不修改jira','不操作jira')
REQUESTED_WRITE=('导入jira','导入synapsert','导入用例','创建测试计划','创建测试周期','提交bug','回写结果')
FULL=('从头到尾','全流程','完整测试流程','完整质量闭环','end to end')
LIMITED=('只','仅','先','only','just')
@dataclass(frozen=True)
class IntentPlan:
 stages:tuple[str,...]
 scope:str
 no_execution:bool
 no_external_writes:bool
 questions:tuple[str,...]
 uncertainty:tuple[str,...]
 phase:str
 def to_dict(self):
  r=asdict(self)
  for k in ('stages','questions','uncertainty'):r[k]=list(r[k])
  return r
def plan_task(message:str,known:dict|None=None)->dict:
 if not isinstance(message,str) or not message.strip():raise ValueError('Nonempty task required')
 p=message.casefold().strip();known=known or {}
 no_run=any(s in p for s in NEGATED_EXECUTION)
 no_write=any(s in p for s in NEGATED_WRITE) or not any(s in p for s in REQUESTED_WRITE)
 stages=[s for s,terms in STAGE_ALIASES.items() if any(t in p for t in terms)]
 limited=any(t in p for t in LIMITED)
 if any(t in p for t in FULL) and not limited:
  from .workflow import STEPS
  stages=list(STEPS)
 if no_run:stages=[s for s in stages if s not in ('execution','regression')]
 if not stages:stages=['discovery']
 if not any(s in stages for s in ('execution','regression')):no_run=True
 scope='full' if any(t in p for t in FULL) and not limited else 'limited'
 phase='development' if any(t in p for t in ('开发中','开发还没完成','开发还在进行','正在开发','开发人员正在')) else 'unspecified'
 questions=[];uncertainty=[]
 if not any(known.get(s) for s in ('requirements','gitlab','web_url')):
  questions.append('请提供需求文件/Wiki、GitLab 仓库地址或已部署系统地址（任选一种）。')
 elif known.get('gitlab') and known.get('requirements_status') not in ('PROVIDED','CONFIRMED_NONE') and not known.get('requirements'):
  questions.append('是否有正式需求文档或 Wiki 链接？没有请回答“没有”，再根据代码整理候选需求。')
 if no_run and any(t in p for t in FULL):
  uncertainty.append('请求同时涉及全流程与暂不执行，先只规划/设计，执行需要再次确认。')
 return IntentPlan(tuple(dict.fromkeys(stages)),scope,no_run,no_write,tuple(questions),tuple(uncertainty),phase).to_dict()
