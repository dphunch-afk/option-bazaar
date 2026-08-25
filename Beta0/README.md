# Beta-0

Beta-0 is the functional software-development prototype for the Beta home learning robot project.

## First milestone

Prove a minimal persistent-learning loop:

1. Accept an experience.
2. Store it permanently in SQLite.
3. Recall prior experiences after restart.
4. Add new evidence without deleting the original experience.
5. Show the current interpretation separately from the immutable experience history.

## Run

```bash
cd Beta0
python main.py
```

## Test

```bash
python -m unittest discover -s tests -v
```

This prototype intentionally does not implement the later security architecture or physical robot control.
