import sys
from pathlib import Path


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_dir))
    from app.services.seed import main as seed_main

    seed_main()


if __name__ == "__main__":
    main()
