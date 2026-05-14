# Board Editor Frontend Contract

Admin users can create and edit board configurations.

Required fields:

- board_id
- name
- roles
- sheriff_enabled
- speech_rule
- vote_rule
- win_condition
- enabled

Validation:

- At least one werewolf role.
- At least one villager faction role.
- Total role count must match game player count.
