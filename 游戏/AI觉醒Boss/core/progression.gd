extends RefCounted
## Read-only progress classification. Never rewrites already committed outcomes.
static func count(state: Dictionary) -> int:
	var total=0;var completed=true
	for event in state.events:
		match event.get("kind",""):
			"expedition_locked":completed=false
			"battle_finished":completed=event.get("result")=="player_win"
			"journey_returned_early","rescue_withdrawn":completed=false
			"expedition_settled":
				if event.get("valid_for_act",true) and completed:total+=1
	return total
