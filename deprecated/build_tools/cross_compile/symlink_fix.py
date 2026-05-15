#!/usr/bin/env python3
import os
import sys

def fix_symlinks(root_dir):
    root_dir = os.path.abspath(root_dir)
    for root, dirs, files in os.walk(root_dir):
        for name in dirs + files:
            path = os.path.join(root, name)
            if os.path.islink(path):
                target = os.readlink(path)
                if target.startswith('/'):
                    # Target is absolute, make it relative to the sysroot
                    new_target = os.path.join(root_dir, target.lstrip('/'))
                    # Calculate relative path from symlink location to new target
                    rel_target = os.path.relpath(new_target, root)
                    print(f"Fixing {path}: {target} -> {rel_target}")
                    os.remove(path)
                    os.symlink(rel_target, path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: symlink_fix.py <root_dir>")
        sys.exit(1)
    fix_symlinks(sys.argv[1])
