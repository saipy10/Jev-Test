import os
import shutil
from pathlib import Path


def undo_organization(target_dir: Path) -> None:
    """
    Move all files from subdirectories within target_dir back to target_dir root,
    and delete the empty subdirectories.
    """
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: Target directory '{target_dir}' does not exist.")
        return

    # Find all top-level subdirectories in target_dir
    subdirs = [item for item in target_dir.iterdir() if item.is_dir()]
    if not subdirs:
        print(f"No subdirectories found in '{target_dir.name}' to undo.")
        return

    total_moved = 0
    print(f"Found {len(subdirs)} subfolder(s) to unpack...\n")

    for subdir in subdirs:
        print(f"Processing folder: '{subdir.name}'")
        # Find all files inside this subdirectory (including any nested ones)
        files = [f for f in subdir.rglob("*") if f.is_file()]

        for file_path in files:
            dest_path = target_dir / file_path.name

            # Avoid name collisions if a file with the same name already exists in root
            if dest_path.exists() and dest_path != file_path:
                stem = file_path.stem
                suffix = file_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(file_path), str(dest_path))
            print(f"  <- Moved back: '{subdir.name}/{file_path.name}' -> '{dest_path.name}'")
            total_moved += 1

        # Remove the empty subfolder tree
        shutil.rmtree(subdir)
        print(f"  Removed folder: '{subdir.name}'\n")

    print("=================== UNDO SUMMARY ===================")
    print(f"Successfully restored {total_moved} file(s) to '{target_dir.name}'.")
    print("All category subdirectories have been removed.")
    print("====================================================")


def main():
    base_dir = Path(__file__).resolve().parent
    unorganised_folder = base_dir / "Unorganised Folder"
    print(f"Starting undo operation for: {unorganised_folder}\n")
    undo_organization(unorganised_folder)


if __name__ == "__main__":
    main()
