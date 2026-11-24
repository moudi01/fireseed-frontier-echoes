"""Standard-library local browser / CLI entry point."""
import argparse
import json
from pathlib import Path
import sys
import time
from engine import BASE, Game
import cases

HELP = '''终战：finale status / moves；finale prepare CONFIRM → finale enter CONFIRM（单向，失败C）
阶段难度：前期与中期普通委任按公开章节定强度，回刷旧关不随队伍成长；difficulty/intel查看冻结数值。
最高险境：第三章D2的L8+G门有一次公开断阵重击；内圈有人没撤会引爆外圈，内圈撤空整招落空。单击实际入血达半数maxHP或被该招实际击倒将重创，本场仍能救治，战后本趟休战至归城；可补预备、战前退离或战中flee CONFIRM。
Boss机制：魔王见证英雄原生主动后强化复制；管理员小怪在场时不点名并获得霸体，清空小怪后才点名；点名、破令或被打断会召唤小怪，8拍后处决原人，对本体实际血伤达到法令公开阈值可提前破令。查看intel与战中Boss提示。
回信：实际完成救助后逐步收到线索，城内 thread status/read 回看，按当前回信提示跟进；只有最后回信可解锁完美结局资格。
战前敌情：intel [已公开节点]；接敌自动显示真实面板、普攻、技能/预警与应对线索。
战前调整：部署/站位/朝向/姿态、已拥有3方案、随行者已学两书槽与技能queue/auto；fight后锁定，采购/学书仍城内。
行军约定：fortune status；现场choose FORTUNE A/B/RISK，支付4铜与2材料领取额度，不领取原材料；新约完整替换旧约。
风险试行：确认前公开50%稀有／30%普通／20%失衡的全部后果，结果出发锁定，回访／读档不重抽。
途中状态：conditions status；EV30 FIT／EV36 CLEANSE／EV39 SHARP／EV54 TREAT／EV55 HAUL／EV59 RUSH
现场选择：choose FIT／SHARP／HAUL／RUSH／TREAT；choose CLEANSE 状态ID（整组处理）
限战准备品：FIT取得CO11护片包，RUSH取得CO12急磨包；战外use CO11／CO12后未来两战生效，可安全带回留到下一趟。
跨区营地：camp恢复生命／侵蚀，或camp CLEANSE 状态ID；共用本次机会，状态处理不附带恢复。
钥匙：finale seal → finale seal CONFIRM；finale carry CONFIRM；B执行者 finale executor 完整ID
身份：finale choice ASK_TERMS / KEEP_SELF / ACCEPT_MERGER；归并另用finale merge CONFIRM，可finale cancel
两战布阵：finale deploy 完整ID on/off；finale place 完整ID q r；finale fight CONFIRM
终战损耗：魔王战后未上场人类承受20%最大生命损耗（至少1点、不致死），再投影管理员；B接入格被敌人占据时可在相邻格连续两拍接入。
失败重试：触发 FIN-C 后 finale retry → finale retry CONFIRM；恢复到进入终战前的城镇整备状态（同一周目/版本），失败结局写入 finale.retry_history。
研究：research status；观测站Lv2后 research analyze CONFIRM
研究后续：前两将报告和观测站Lv3后 research correlate 队员完整ID CONFIRM → research test CONFIRM
研究交付：四将报告齐后 research deliver CONFIRM，同时获得ST-303/校验片，预算20/15
应急载体：agla status/quote；agla craft CONFIRM（四将觉醒、三片、研究完成、工坊Lv3，材料8碎晶4铁＋12铜）
战术回应：learning status/history/cards/preview；城内preview只看下一趟预锁结果，不扣费、不产生证据
公开路账：learning route on/off（ST-104后城内设置）；实际通行或营地使用须关联完成战斗才计观察
回应由过去见证自动筛选，玩家通过改站位/路线/节奏应对；不直接挑选敌方卡，未满足条件使用基础阵容。
设施：facility status；facility quote hospital 1；facility build hospital 1 build-01 CONFIRM
建筑键：hospital医舍 / lamp_store观测站 / rescue_post搜救所 / barracks营房 / armory工坊 / council镇务厅
施工：facility pause/resume/cancel 订单ID CONFIRM；facility branch 建筑 A/B CONFIRM；facility refit 建筑 A/B 请求ID CONFIRM
服务预览：service quote scout - / nursing 队员列表 / rush 工地ID / training 队员ID:经验[,队员ID:经验]
服务付款：service scout - scout-01 CONFIRM；其他服务同样使用 类型 对象 请求ID CONFIRM
探路：出发后 scout reveal 节点；三级用完后可在安全处 scout redirect 节点；scout history 免费查看已走旧路
供给：supply catalog；supply quote buy EF01-Q1；supply buy EF01-Q1 请求ID CONFIRM
拆卖：supply quote sale/dismantle 装备ID；supply sale/dismantle 装备ID 请求ID CONFIRM
材料：supply commission MAT-IRON/MAT-SHARD/MAT-FIBER/MAT-HERB/off；出发后在锁定地点选择原材料选项
技能书：存在手册报价的现场 choose BOOK，替代原事件结果；安全返城入库，失败丢失。
观测站一级后 pack_medical 3；治疗、预备、捕获和补训仍使用同一份真实名册。
对白：dialogue next/skip/close；dialogue history；dialogue replay 已发生ID；dialogue auto on/off。阅读不推进任务或时间。
自然开局：--campaign --cli；quest status 查看进度。试验队入口仍保留。
委任：quest commission CONFIRM；tutorial recommend CONFIRM；tutorial start；D处 tutorial observe；两战后返城。
档案：quest review CONFIRM → quest archive CONFIRM；真实首交1印及基础书自选权益，出征/战斗预算12/8。
原物：quest MG01 record → quest MG01 witness → quest MG01 collect CONFIRM（四委托同格式）。
独立线索册：clue status；clue record/witness/collect MG01（collect追加CONFIRM）。
现场调查：核实后 clue locate MG01 CONFIRM；recover quote MG01；recover start MG01 CONFIRM。
搜救联办：recover quote/start MG01 CAP-0001（start追加CONFIRM）；两点之间 recover continue/return CONFIRM。
搜救所：rescue status；rescue investigate quote CAP批次；rescue investigate start CAP批次 CONFIRM → rescue investigate inspect tracks → rescue investigate inspect marker → rescue investigate return CONFIRM；确认后用原批次rescue，不重置期限。旧missing命令保留兼容。
应召：summon 请求ID CONFIRM；companion register CONFIRM（薇拉实际到场、名额足够）。
讨伐：challenge MG01 → depart；归城town后 quest report MG01 CONFIRM。
追忆：remember MG01；remember evidence MG01-W1；remember retain MG01-W2；remember close 可暂离。
档位：difficulty 查看；城镇 difficulty D0/D1/D2，出发锁定；试验起始底线L1/L2/L4
技能：skill 03 counter/damage/off（雾术师保留反制／伤害优先／关闭）；其他佣兵skill 01 auto/off
连续远征：归城结算后town；route R01；保留实际资产，败战共享携行物资丢失
护送：escort 07 CONFIRM（战外派1名可行动预备带回全部倒地者；原装备随人，共享包留队）
护送后不得重新加入或远程换装，不释放本趟Cost；整趟统一结算1日，无预备可走回入口全队早返
救援：rescue CAP-0001 CONFIRM（现有队伍、1战、基础1补给，搜救所一级后为0、1日；成功救回原人装备）
期限：capture_mode standard/relaxed（仅城内无被俘者可改，将来捕获C+3/C+5）
到期：rest/maintain/depart 若下一日有人到期，需追加CONFIRM；救援当日先救回再清算
城镇：rest（1日休整）；maintain（1日维护）；care 01（1补给，下一行动加速旧伤）；heal 完整ID（按缺口付铜，基础1铜最多4HP）；shelter查看已保全/已交割案件
道德经济：不对等设计——EXPLOIT只兑现当次报酬，不追加物价或机械惩罚；PROTECT每次回信+1随队补给，十案全部保全获得隐藏技能书 SB-Z01（终局对策卡），不给价格折扣；完美结局仍须按真实结果满足全部条件
隐藏书：SB-Z01 缄默回执，book learn/equip 后可在终局选定高威胁敌人，使其下一次攻击无效；冷却20拍按动作循环，不可购买
补员：recruit catalog查看8种佣兵；recruit S01（8铜）/ M01..M08（16铜）；squad 完整ID on/off；level_up 01
整备：buy_supply 2（每份2铜）；pack_medical 2（从仓库移至救护位）；stash/take CO01
建设：build_hospital（20铜4晶、之后2个行动日竣工）
基础：depart；连续探索 walk 方向0..5 [1..12格]、walkto q r（已发现道路）、interact [附近地点ID]、map（列出已发现地点坐标与敌/事件/站点类型）。
案件保底：自然周目按“已遇见案件数”每2趟保底安排1个未遇道德案件；显式定向续办优先，保底不覆盖。
move U仅保留为沿路逐格执行的兼容指令，不能越过待战敌阵；retreat退回接敌边界外。
战斗：fight；step；run 120；flee CONFIRM（1拍追击后全队返城）
狂暴：每场前120拍正常，第121拍怪物伤害×2，此后每10拍再加1倍基础伤害；治疗与护盾主动按冷却循环。
记忆窗口：memory evidence/retain/skip MG01-W1；窗口暂停逻辑钟，需按当前窗口ID回应
编队：deploy 01 off / deploy 07 on；place 07 2 1；部署范围随棋盘变化，接敌时查看可用格；stance 01 hold/advance/flank/evade
事件：choose PRIMARY/SECONDARY/PASS [目标01] [方案PL01]；rub 1 / rub 2
联动：出现后使用 choose LINK 01；原选项保留，须有实际物品或材料，历史不会屏蔽普通卡
避难者：case escort 07 CONFIRM 派遣；case receive CONFIRM 完成交接；case return CONFIRM 全队早返（case 仅用于 EV03；EV07/EV28 用 event EVxx escort/receive）
装备报价：event EV07 quote；到场即显示每件完整报价；Q3可用EF02:strong选择整组强效，EF02默认常规
交易：case trade CONFIRM（搬运工被带回私牢，不可赎回；64铜＋4补给下次城镇结算兑现）
续办：城内 event EVxx followup/visit；case followup EVxx on/off、case visit EVxx CONFIRM（EV03可省略ID；均归城计1日，无普通奖励）
运水：water load CONFIRM 占2材料额度；water trade CONFIRM 出售40铜＋8晶，城镇兑现
运水续办：water followup on/off；water visit CONFIRM 固定续运；每趟只定向一项
药箱：medicine return CONFIRM 全队立即返城送医；medicine trade CONFIRM 出售80铜＋8晶
药箱续办：城内 medicine followup on/off；medicine visit CONFIRM 固定接洽，归城1日
新案件：event 事件ID 操作 [家族列表或护送者] CONFIRM；LOCAL按现场用receive／destroy／release
护送：event EV07 escort 07 CONFIRM → event EV07 receive CONFIRM；EV28同理，也可return全队早返
伤工：event EV05 return CONFIRM；装备交易示例 event EV28 trade EF02,EF05 CONFIRM（固定两件Q2）
现场：event EV25 receive CONFIRM（认领员当面收妥，继续探索）；event EV25 trade CONFIRM
续办：event EV25 followup on/off；event EV25 visit CONFIRM；event EV25 redeem 城内重试凭单
放弃：decline CONFIRM（关闭本趟事件）；PASS仅暂离，可回访
补给：station；camp；medical；use CO01 01；use CO02 01,02,03,04,05,06
物品：discard CO10；城内craft CO01；野外通过制作事件choose PRIMARY
建设：construction status；construction quote 3；construction start 3 build-01 CONFIRM；construction cancel build-01 CONFIRM
整备：outfit status；outfit branch A/B CONFIRM；outfit quote defense/medicine
当趟双防自动生效、归城清除；购买：outfit buy defense 01,02 prep-01 CONFIRM；outfit buy medicine - prep-02 CONFIRM；outfit targets 03,04
改修：outfit refit B refit-01 CONFIRM；8铜2晶、占服务位，下次行动结算完成；第二服务另加4铜1补给，镇务厅三级降为2铜1补给
工坊：workshop status；workshop quote EQ-000001 Q2；workshop upgrade EQ-000001 Q2 work-01 CONFIRM
重铸预览：workshop reforge_quote EQ-000017 none/LEECH；付费：workshop reforge EQ-000017 none/LEECH forge-01 CONFIRM
重铸选择：workshop resolve forge-01 adopt/keep CONFIRM；采用或留旧都耗费，待选择时锁物且不可撤单退款
撤单：workshop cancel work-01 CONFIRM；装备须先卸下入库，同订单ID重试不重复扣款；后续真实行动结算推进
装备：gear list；equip 01 EQ-000001（或当前库存序号0起）；unequip 01 weapon/armor
转移：城内 gear stash/take 实例ID（背包／仓库）；城内穿脱用仓库，野外用背包；战斗中锁定
方案：plan list；plan PL01 PL02；plan clear；plan undo
技能书：book list；book show 01；book buy 01 SB-D02；book learn 01 SB-D02
书槽：book equip 01 SB-D02 SB-M01；book equip 01 clear；book main 01 AUTO/BASIC/SK-SB-D02
书籍来源：book status；book target SB-D02；book task accept SB-T01；book choice ST-104 SB-D02 CONFIRM
战利书：战后原现场 book claim／book drop；事件 choose BOOK。携书安全带回才入库，途中不能学习。
英雄：hero catalog查看12人定位；hero 完整ID info查看人物/技能/短板；hero list查看已取得者
英雄策略：hero 01 recall self/pet；其余使用book queue/auto配置
主动队列：book queue 01 SK-SB-D02 M01-A SK-SB-M01；book auto 01 SK-SB-D02 off/on（城内或远征战前）
出口：next RG06 CONFIRM（单向跨区）；return CONFIRM（安全返城）
调试：debug_win CONFIRM（整个试验标记为作弊，不能用于平衡）
中止：withdraw CONFIRM（保留未完成现场，不冒充撤退结算）
CLI额外：status、help、export、quit。每个成功动作自动保存，保留上一份有效提交的.bak备份。
损坏恢复：save_tools.py inspect 原档路径；save_tools.py recover 原档路径 --output 新文件路径。恢复不会覆盖原件。
'''


def new_path():
    return BASE / 'local' / (time.strftime('%Y%m%d_%H%M%S') + '_' + str(time.time_ns())[-6:]) / 'save.json'


def main():
    parser=argparse.ArgumentParser(description='火种计划灰盒：默认本地浏览器，--cli命令行，--batch自动试验')
    parser.add_argument('--campaign',action='store_true',help='真实初始名册、任务、应召和固定讨伐（使用CLI）')
    parser.add_argument('--cli',action='store_true');parser.add_argument('--batch',action='store_true')
    parser.add_argument('--browser',action='store_true',help='用浏览器操作自然周目或灰盒地图')
    parser.add_argument('--no-browser',action='store_true');parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--load',type=Path);parser.add_argument('--save',type=Path)
    parser.add_argument('--route',default=None);parser.add_argument('--team',default=None);parser.add_argument('--pack',default='P1')
    parser.add_argument('--difficulty',choices=['D0','D1','D2'],default='D0')
    parser.add_argument('--seed',type=int,default=None);parser.add_argument('--birth',choices=['MID','LOW'],default='MID')
    parser.add_argument('--policy',choices=['baseline','rotation','evade','explore'],default='baseline')
    parser.add_argument('--case',choices=['NONE','BOTH','ALL']+list(cases.ALL_IDS),default='EV03',dest='case_mode',help='受控案件试验；未指定route/team/seed时自动采用该案件的已知可达组合')
    args=parser.parse_args()
    try:
        if args.campaign and args.batch:parser.error('自然开局请用 --cli；--batch 仍是独立普通远征试验。')
        route=args.route or 'R01';team=args.team or 'T01';seed=11 if args.seed is None else args.seed
        if args.case_mode in cases.CASE_DEFAULTS and not args.load:
            default_route,default_team,default_seed=cases.CASE_DEFAULTS[args.case_mode]
            route=args.route or default_route;team=args.team or default_team
            seed=default_seed if args.seed is None else args.seed
        if args.campaign:seed=11 if args.seed is None else args.seed
        game=Game.load(args.load) if args.load else Game.new_campaign(seed=seed,save_path=args.save or new_path()) if args.campaign else Game.new(route=route,team=team,pack=args.pack,seed=seed,birth=args.birth,case_mode=args.case_mode,difficulty=args.difficulty,save_path=args.save or new_path())
        if args.batch:
            if game.s.get('campaign'):parser.error('自然开局存档使用 --cli 继续；--batch 是普通远征试验入口。')
            from smoke import play
            play(game,policy=args.policy);path=game.save_path.with_name('report.json');game.export(path)
            print(json.dumps({'phase':game.s['phase'],'summary':game.s['summary'],'report':str(path)},ensure_ascii=False,indent=2));return 0
        if not args.cli and (args.browser or not game.s.get('campaign')):
            from web import serve
            serve(game,args.port,not args.no_browser);return 0
        print(HELP);print(game.describe());print('自动保存：',game.save_path)
        while True:
            try:command=input('\n> ').strip()
            except (EOFError,KeyboardInterrupt):break
            if command=='quit':break
            if command=='help':print(HELP);continue
            if command=='status':print(game.describe());continue
            if command=='export':
                path=game.save_path.with_name('report.json');game.export(path);print(path);continue
            try:print(game.execute(command));print(game.describe())
            except (ValueError,KeyError,IndexError,OSError) as error:print('未执行：',error)
    except KeyboardInterrupt:return 0
    except Exception as error:
        print('无法启动：',error,file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
