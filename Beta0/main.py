from memory import MemoryStore


def show_subject(memory: MemoryStore, subject: str) -> None:
    print(f"\n=== {subject} ===")
    experiences = memory.experiences_for(subject)
    if not experiences:
        print("No experiences yet.")
        return

    print("Experience history:")
    for exp in experiences:
        print(f"  [{exp.id}] {exp.observation}  ({exp.source}, {exp.created_at})")

    belief = memory.latest_belief(subject)
    if belief:
        print("Current interpretation:")
        print(
            f"  {belief.statement} | status={belief.status} | confidence={belief.confidence:.0%}"
        )
    else:
        print("Current interpretation: UNKNOWN")


def teach(memory: MemoryStore) -> None:
    subject = input("Subject/name: ").strip()
    observation = input("What happened / what did Beta observe? ").strip()
    if not subject or not observation:
        print("Subject and observation are required.")
        return

    experience_id = memory.add_experience(subject, observation)
    print(f"Stored experience #{experience_id}. Original history is preserved.")

    statement = input("Current interpretation (leave blank for UNKNOWN): ").strip()
    if statement:
        raw_conf = input("Confidence 0-100 (example 70): ").strip() or "50"
        confidence = max(0.0, min(100.0, float(raw_conf))) / 100.0
        status = "known" if confidence >= 0.95 else "believed" if confidence >= 0.60 else "uncertain"
        memory.add_belief(subject, statement, confidence, experience_id, status)
        print("Stored a new interpretation without deleting older experience.")

    show_subject(memory, subject)


def main() -> None:
    print("Beta-0 Brain v0.1")
    print("Persistent Experience -> Interpretation -> Recall")

    with MemoryStore() as memory:
        while True:
            print("\n1) Teach / add experience")
            print("2) Recall a subject")
            print("3) List known subjects")
            print("4) Exit")
            choice = input("> ").strip()

            if choice == "1":
                teach(memory)
            elif choice == "2":
                subject = input("Subject/name: ").strip()
                show_subject(memory, subject)
            elif choice == "3":
                subjects = list(memory.subjects())
                print("Subjects:", ", ".join(subjects) if subjects else "none")
            elif choice == "4":
                print("Beta-0 shutdown. Memory remains on disk.")
                return
            else:
                print("Choose 1, 2, 3, or 4.")


if __name__ == "__main__":
    main()
