"""CHOICE-1.0 offline reward allocation; no engine or save transactions."""
import copy
from joint_sampling_model import ReferenceSampler, score, canonical, digest


class EventFirstReference(ReferenceSampler):
    """Ablation: move the old optional goal-material fixture behind events."""
    goal_material_units = 0


class ChoiceSampler(EventFirstReference):
    @staticmethod
    def limited(choice):
        return sum(reason == 'PREVIEWED_BUDGET_LIMIT' for reason in choice['disabled_options'].values())

    def budget_ok(self, assigned):
        if not super().budget_ok(assigned):
            return False
        bounds = getattr(self, 'choice_bounds', None)
        return bounds is None or all(
            sum(self.limited(ch) for (r, _), ch in assigned.items() if r in path) <= bound
            for path, bound in bounds.items())

    def candidates(self, var, assigned, ordinary_only, allow_recent):
        if getattr(self, 'repairing', False):
            # Lock humanity placement and per-site history eligibility. Do not
            # manufacture cheap humanity replacements or break cooldown to fit.
            values = super().candidates(var, assigned, False, self.repair_history[var])
            return [eid for eid in values if self.events[eid]['type'] != 'humanity']
        return super().candidates(var, assigned, ordinary_only, allow_recent)

    def generate(self, request):
        self.repairing = False
        self.choice_bounds = None
        # This reference owns the optimization policy; party, purse and morality
        # are not inputs. Search_limit still governs the feasibility generation.
        req = copy.deepcopy(request)
        req['budget_policy'] = 'explicit_option_limits'
        result = super().generate(req)
        if result['status'] != 'SUCCESS':
            return result
        m = result['manifest']
        initial_nodes = self.nodes
        assigned = {(r, s): copy.deepcopy(v) for r, region in m['regions'].items()
                    for s, v in region['events'].items()}
        initial = copy.deepcopy(assigned)
        locked = {v: ch for v, ch in assigned.items()
                  if self.events[ch['event_id']]['type'] == 'humanity'}
        self.repair_history = {v: m['cold_baseline_failed'] if v[1] != 'D'
                               else v[0] in m['fourth_history_fallback_regions'] for v in assigned}
        self.repairing = True
        # Every already-generated site stays present. A failed improvement never
        # invalidates the feasible plan or silently removes optional events.
        initial_path_limits = {tuple(path): sum(self.limited(ch) for (r, _), ch in assigned.items() if r in path) for path in self.paths}
        attempts = []
        global_nodes = 0
        for bound in range(max(initial_path_limits.values(), default=0)):
            self.req['budget_policy'] = 'full_options' if bound == 0 else 'explicit_option_limits'
            self.choice_bounds = {p: min(bound, n) for p, n in initial_path_limits.items()}
            self.nodes = 0
            self.limit = 1200
            improved = self.solve(list(assigned), locked, ordinary_only=False,
                                  allow_recent=False, budget=True)
            global_nodes += self.nodes
            status = 'FOUND' if isinstance(improved, dict) else ('SEARCH_LIMIT' if improved == 'LIMIT' else 'NO_PLAN_UNDER_LOCKS')
            attempts.append({'per_path_limit': bound, 'status': status, 'nodes': self.nodes})
            if isinstance(improved, dict):
                assigned = improved
                break
        self.choice_bounds = None
        self.req['budget_policy'] = 'full_options'
        search_status = 'ZERO_LIMIT_INCUMBENT' if not any(initial_path_limits.values()) else (
            'IMPROVED' if attempts and attempts[-1]['status'] == 'FOUND' else 'KEPT_FEASIBLE_INCUMBENT')
        # Bounded monotonic local replacement if the complete full-option search
        # is exhausted or disproves a zero-limit solution under these locks.
        swaps = []
        changed = True
        while changed:
            changed = False
            for var in sorted(assigned, key=lambda v: score(self.seed, 'repair/' + str(v))):
                old = assigned[var]
                if not any(reason == 'PREVIEWED_BUDGET_LIMIT' for reason in old['disabled_options'].values()):
                    continue
                rest = {v: ch for v, ch in assigned.items() if v != var}
                candidates = self.candidates(var, rest, False, False)
                if old['event_id'] in candidates:
                    candidates.remove(old['event_id']); candidates.insert(0, old['event_id'])
                for eid in candidates:
                    full = next(self.masks(eid))
                    trial = {**rest, var: full}
                    if self.budget_ok(trial):
                        assigned = trial
                        swaps.append({'site': '/'.join(var), 'from': old['event_id'], 'to': eid})
                        changed = True
                        break
        # A full-choice material-heavy card may be the reason a different card
        # is constrained. Repair pairs as well; otherwise changing only greyed
        # cards misses complementary mixes. No card's reward amount is reduced.
        pair_attempts = 0
        pair_swaps = []
        pair_limit = 2000
        while pair_attempts < pair_limit:
            repaired = False
            limited_vars = sorted((v for v, ch in assigned.items() if self.limited(ch)),
                                  key=lambda v: score(self.seed, 'pair-target/' + str(v)))
            for var in limited_vars:
                partners = sorted((v for v, ch in assigned.items() if v != var and self.events[ch['event_id']]['type'] != 'humanity' and (v[0], var[0]) in self.conflict),
                                  key=lambda v: score(self.seed, 'pair-partner/' + str(v)))
                for partner in partners:
                    rest = {v: ch for v, ch in assigned.items() if v not in [var, partner]}
                    candidates = self.candidates(var, rest, False, False)
                    old_id = assigned[var]['event_id']
                    candidates.sort(key=lambda eid: eid != old_id)
                    for eid in candidates:
                        first = {**rest, var: next(self.masks(eid))}
                        for second_id in self.candidates(partner, first, False, False):
                            if pair_attempts >= pair_limit:
                                break
                            pair_attempts += 1
                            trial = {**first, partner: next(self.masks(second_id))}
                            if self.budget_ok(trial):
                                pair_swaps.append({'sites': ['/'.join(var), '/'.join(partner)],
                                                   'from': [assigned[var]['event_id'], assigned[partner]['event_id']],
                                                   'to': [eid, second_id]})
                                assigned = trial
                                repaired = True
                                break
                        if repaired or pair_attempts >= pair_limit:
                            break
                    if repaired or pair_attempts >= pair_limit:
                        break
                if repaired or pair_attempts >= pair_limit:
                    break
            if not repaired:
                break
        # Optional material bundles use only residual capacity after all choices
        # have been reserved, once before departure, not after player choices.
        topups = []
        for rid in sorted(self.used_regions, key=lambda r: score(self.seed, 'goal-topup/' + r)):
            self.reservations[rid]['material_units'] = self.reservations[rid].get('material_units', 0) + 2
            if self.budget_ok(assigned):
                topups.append(rid)
            else:
                self.reservations[rid]['material_units'] -= 2
        for rid, region in m['regions'].items():
            region['events'] = {s: assigned[rid, s] for s in 'ABCD' if (rid, s) in assigned}
            candidates = self.encounter_choices(rid, [v['event_id'] for v in region['events'].values()])
            chosen = min(candidates, key=lambda x: score(self.seed, 'encounters/' + rid + '/' + canonical(x)))
            chosen['L'] = region['encounters']['L']
            region['encounters'] = chosen
            region['combat_rewards']['G']['bundle_ids'] = ['RB-MAT2'] if rid in topups else []
        m['pre_reserved_by_region'] = copy.deepcopy(self.reservations)
        m['version'] = 'CHOICE-1.0'
        m['choice_policy'] = {
            'goal_materials': 'event_options_first_residual_locked_RB_MAT2',
            'improvement_status': search_status, 'improvement_search_nodes': global_nodes,
            'improvement_search_limit_per_attempt': 1200, 'improvement_attempts': attempts,
            'local_full_choice_swaps': swaps,
            'pair_full_choice_swaps': pair_swaps, 'pair_attempts': pair_attempts,
            'pair_attempt_limit': pair_limit,
            'humanity_placements_locked': {r + '/' + s: v['event_id'] for (r, s), v in locked.items()},
            'initial_site_counts': {r: len(region['events']) for r, region in m['regions'].items()},
            'budget_limits_before_repair': sum(sum(x == 'PREVIEWED_BUDGET_LIMIT' for x in ch['disabled_options'].values()) for ch in initial.values()),
            'budget_limits_after_repair': sum(sum(x == 'PREVIEWED_BUDGET_LIMIT' for x in ch['disabled_options'].values()) for ch in assigned.values()),
            'goal_material_topup_regions': topups,
            'global_optimality_proven': False,
        }
        m['choice_policy']['authoring_gate'] = (
            'CHOICE_BUDGET_REVIEW_REQUIRED' if m['choice_policy']['budget_limits_after_repair']
            else 'BUDGET_CHOICE_OK_NOT_RUNTIME_VERIFIED')
        m.pop('manifest_sha256')
        m['manifest_sha256'] = digest(m)
        result['search_nodes'] = initial_nodes + global_nodes
        self.repairing = False
        return result
