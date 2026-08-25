# Beta-00

Beta-00 is the generation-0 system with brain-generation-0 for the Beta home learning robot project.

Naming convention:
- First digit = Beta system/robot generation.
- Second digit = brain architecture generation.
- Normal software improvements use separate software revision numbers and do not change Beta-00 unless the brain architecture changes.

## First milestone

Prove a minimal persistent-learning loop:

1. Accept an experience.
2. Store it permanently in SQLite.
3. Recall prior experiences after restart.
4. Add new evidence without deleting the original experience.
5. Show the current interpretation separately from the immutable experience history.

This prototype intentionally does not implement the later security architecture or physical robot control.
