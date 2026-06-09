# Canonical Recipe Backlog

Use this file to track generator-ready canonical recipes assembled from
validated research artifacts. Check an item only after the canonical JSON
validates with `load_recipe` and a sample PDF generation succeeds.

Do not check items merely because research folders exist.

## Ready Candidates

- [x] `singapore_history_1900_2020s_v1.json`
  - scope: Singapore from colonial port governance through wartime occupation, self-government, state-building, housing, and advanced services
  - output: `data/recipes/canonical/singapore_history_1900_2020s_v1.json`
  - research folders:
    - `data/recipes/research/singapore_colonial_port_governance_1900_1941`
    - `data/recipes/research/singapore_japanese_occupation_1942_1945`
    - `data/recipes/research/singapore_labor_self_government_1950s`
    - `data/recipes/research/singapore_merger_malaysia_separation_1963_1965`
    - `data/recipes/research/singapore_lee_kuan_yew_state_building`
    - `data/recipes/research/singapore_housing_urban_planning_after_independence`
    - `data/recipes/research/singapore_changi_shipping_finance_advanced_services`

- [x] `malaysia_history_1900_post_2018_v1.json`
  - scope: Malaysia from British Malaya through occupation, Emergency, independence, federation, redistribution, and post-2018 politics
  - output: `data/recipes/canonical/malaysia_history_1900_post_2018_v1.json`
  - research folders:
    - `data/recipes/research/malaysia_british_malaya_colonial_structure_1900_1941`
    - `data/recipes/research/malaysia_japanese_occupation_postwar_consequences`
    - `data/recipes/research/malaysia_emergency_security_policy_anti_communist_conflict`
    - `data/recipes/research/malaysia_tunku_abdul_rahman_independence_1957`
    - `data/recipes/research/malaysia_formation_1963_federal_state_building`
    - `data/recipes/research/malaysia_new_economic_policy_redistribution_development`
    - `data/recipes/research/malaysia_coalition_politics_post_2018_electoral_change`

- [x] `indonesia_colonial_nationalist_origins_v1.json`
  - scope: Indonesia from Dutch colonial rule through nationalist movements before 1945
  - output: `data/recipes/canonical/indonesia_colonial_nationalist_origins_v1.json`
  - research folders:
    - `data/recipes/research/indonesia_dutch_colonial_rule_early_twentieth_century`
    - `data/recipes/research/indonesia_nationalist_youth_anti_colonial_before_1945`

- [x] `malaya_malaysia_state_formation_v1.json`
  - scope: British Malaya, Japanese occupation, independence in 1957, Malaysia formation in 1963, and federal state-building
  - output: `data/recipes/canonical/malaya_malaysia_state_formation_v1.json`
  - research folders:
    - `data/recipes/research/malaysia_british_malaya_colonial_structure_1900_1941`
    - `data/recipes/research/malaysia_japanese_occupation_postwar_consequences`
    - `data/recipes/research/malaysia_tunku_abdul_rahman_independence_1957`
    - `data/recipes/research/malaysia_formation_1963_federal_state_building`

- [x] `singapore_malaysia_1963_1965_v1.json`
  - scope: merger, federal conflict, separation, and immediate state-building links across Singapore and Malaysia
  - output: `data/recipes/canonical/singapore_malaysia_1963_1965_v1.json`
  - research folders:
    - `data/recipes/research/singapore_merger_malaysia_separation_1963_1965`
    - `data/recipes/research/singapore_lee_kuan_yew_state_building`
    - `data/recipes/research/malaysia_formation_1963_federal_state_building`

## Later Candidates

Add more canonical targets here as additional research folders are completed.
Good future targets include:

- Indonesia independence, Guided Democracy, New Order, and Reformasi
- Thailand constitutional change, military politics, and economic growth
- Vietnam colonial rule, war, reunification, and Doi Moi
- regional decolonization across British, Dutch, French, Portuguese, and American legacies
- ASEAN founding and regional diplomatic architecture

## Completion Checklist For Each Canonical Recipe

- [ ] selected research folders pass `scripts/validate_research_recipe.py`
- [ ] canonical JSON is written under `data/recipes/canonical/`
- [ ] canonical JSON validates with `load_recipe`
- [ ] sample PDF generation succeeds
- [ ] `metadata.source_notes` preserves source metadata
- [ ] tables and figures from research artifacts are represented
- [ ] checklist item above is marked complete only after validation and sample generation
