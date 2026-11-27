extends RefCounted

# IDs match the cloud copy sheet. Command and save identifiers are independent.
const STRINGS := {
	"UI.S01.BTN.NEW_GAME": "开始新远征",
	"UI.S01.BTN.CONTINUE": "继续所选存档",
	"UI.S01.EMPTY.SAVE_SLOT": "暂无可读存档。",
	"UI.S01.HUD.RESUME_OK": "已恢复至最近保存点",
	"UI.S01.TIP.KEYBIND_BAR": "方向键选择 · 回车确认 · Esc 返回",
	"UI.S01.HUD.SAVE_SLOT_META": "%s · %s",
	"UI.S02.HUD.GOAL_ST101": "当前目标：在暮汀接受灰栎边道侦路委任",
	"UI.S02.HUD.GOAL_ST101_READY": "当前目标：整备队伍，出发侦察灰栎边道",
	"UI.S02.HUD.GOAL_ST102": "灰栎侦路：两战%d/2｜远眺%s｜安全归城",
	"UI.S02.HUD.GOAL_ST103": "当前目标：通过「旧档案」与许苇核对旧日志",
	"UI.S02.HUD.GOAL_ST104": "当前目标：通过「旧档案」交存首章调查与旧名册",
	"UI.S02.HUD.GOAL_ST104_DONE": "首章已交档：可建工坊、整备并开启首批讨伐",
	"UI.S02.HUD.RES_BAR": "铜币%d｜公共结晶%d｜补给%d｜第%d日",
	"UI.S02.BTN.ACCEPT_COMMISSION": "接受委任",
	"UI.S02.TIP.ACCEPT_COMMISSION": "登记3名盾兵、3名近战兵和2名弓兵。配发60铜、12公共结晶和6补给。",
	"UI.S02.ERR.FACILITY_LOCKED": "%s尚未开放。%s",
	"UI.S02.ERR.RES_SHORTAGE": "%s不足（需%d，当前%d）",
	"UI.S02.TIP.ROSTER_HEADER": "查看留城队员、伤势和随队资格。",
	"UI.S03.HUD.COST_SUMMARY": "出征Cost %d/%d｜战斗Cost %d/%d",
	"UI.S03.BTN.AUTO_DEPLOY": "采用建议部署",
	"UI.S03.ERR.UNIT_UNAVAILABLE": "当前无法出战（%s）。",
	"UI.S03.ERR.DEPLOY_EMPTY": "请至少部署一名可上阵的队员。",
	"UI.S03.ERR.SUPPLY_SHORT": "出发补给不足（需%d，仓库余%d）。",
	"UI.S03.DLG.DEPART_LOCK": "前往灰栎边道需消耗1份补给，并锁定本趟队伍与携行。确认出发？",
	"UI.S03.EMPTY.BAG_SLOT": "当前未携带战外消耗品或准备品。",
	"UI.S03.TIP.TUT01_ROUTE": "赢下林道与根口两战，在远眺点观察并记录，再安全归城。",
	"UI.S04.HUD.TUT01_GUIDE": "目标：赢下两战，在远眺点记录后安全归城。",
	"UI.S04.BTN.EARLY_RETURN": "从入口提前返城",
	"UI.S04.BTN.NODE_INTERACT": "领取材料",
	"UI.S04.BTN.OBSERVE_D": "观察并记录",
	"UI.S04.TIP.OVERLOOK_VIEW_ONLY": "仅到达远眺点或查看远眺图不会留下记录。",
	"UI.S04.DLG.EXIT_X_READY": "林道与根口两战已胜，远眺点已记录。确认安全归城？",
	"UI.S04.DLG.EXIT_X_MISSING_D": "尚未在远眺点「观察并记录」，现在归城无法交付侦路。请点「取消」，再点「经根口返回远眺点」补记；直接归城下次须重做两战与观察。",
	"UI.S05.HUD.DEPLOY_HINT": "点高亮格部署，「旋转朝向」转向（战斗Cost%d/%d）",
	"UI.S05.BTN.PRE_RETREAT": "返回道路",
	"UI.S05.BTN.START_BATTLE": "确认开战",
	"UI.S05.HUD.BATTLE_CTRL": "空格暂停/继续｜第%d拍",
	"UI.S05.DLG.MID_RETREAT": "撤退后先结算一拍追击。仍有上阵者站立即可带回物资，否则判为败战。",
	"UI.S06.TTL.RETURN_SAFE": "安全归城 · 第%d日结算",
	"UI.S06.HUD.ST102_COMPLETE": "灰栎侦路完成，请通过「旧档案」与许苇核对旧日志。",
	"UI.S06.HUD.ST102_INCOMPLETE": "侦路未完成。下趟须重做两战与观察。",
	"UI.S06.HUD.ST102_MISS_OBS": "两战已胜但漏远眺记录，调查未完，下次须重做两战与观察。",
	"UI.S06.HUD.ST102_EARLY_RETURN": "已提前返城，补给不退，侦路未完成。",
	"UI.S06.HUD.ST102_MID_RETREAT": "战中撤退成功，生还者与物资返城，本次侦路未完成。",
	"UI.S06.TTL.RETURN_DEFEAT": "远征败战 · 独自归城",
	"UI.S07.BTN.CHECK_LOG": "请许苇核对调查",
	"UI.S07.TIP.ST103_REPLAY": "旧日志已核对。可在「旧档案」交存首章调查。",
	"UI.S07.BTN.SUBMIT_ARCHIVE": "交存调查与旧名册",
	"UI.S07.DLG.ST104_REWARD": "首章交档完成：获应召印×%d、基础技能书自选权益×1、%s；出征/战斗Cost升至%d/%d，开放工坊与首批讨伐。",
	"UI.S07.TIP.REPLAY_NO_DUP": "首章档案已交存，当前仅作回看，不再发放奖励。",
}

# UI.S07.TIP.WHISTLE_NEXT follows the actual steps exposed by the sidecar.
const WHISTLE_TIPS := {
	"record": "先查阅铜哨寄存登记，再向秦姨核对证词。",
	"witness": "寄存登记已查阅。下一步：向秦姨核对证词。",
	"collect": "证词已核实。可付%d铜修缮取回，或在断誓堡垒现场自取。",
	"field": "已登记现场自取。请按线索前往断誓堡垒。",
	"done": "裂口铜哨已持有，可带它前往断誓堡垒。",
}

const CLOCKMAKER_NO_TESTIMONY := "修钟匠把泛黄的寄存单按在柜台上：「阿铎把哨口吹裂了也舍不得换。要见着他，替我问问那半斤修表油。」"
const CLOCKMAKER_VERIFIED := "修钟匠朝你抬了抬下巴：「阿铎那枚裂口铜哨，你已经问过来历了。动身前记得把哨子带上。」"
const CLOCKMAKER_ACQUIRED := "修钟匠瞥见你腰袋边的旧哨绳：「哨子在你这儿就好。见着阿铎，替我问他还欠不欠半斤修表油。」"


static func text(id: String, values: Array = []) -> String:
	var template: String = STRINGS[id]
	return template if values.is_empty() else template % values


static func whistle_tip(stage: String, price: int) -> String:
	var template: String = WHISTLE_TIPS.get(stage, "")
	return template % price if stage == "collect" else template


static func clockmaker_line(stage: String) -> String:
	match stage:
		"record", "witness": return CLOCKMAKER_NO_TESTIMONY
		"collect", "field": return CLOCKMAKER_VERIFIED
		"done": return CLOCKMAKER_ACQUIRED
	return ""
