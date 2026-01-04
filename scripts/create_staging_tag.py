#!/usr/bin/env python3
import subprocess
import sys
import os

def run_command(cmd, capture=True):
    try:
        if capture:
            return subprocess.check_output(cmd, shell=True).decode().strip()
        else:
            return subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        sys.exit(e.returncode)

def main():
    print("Finding next Staging (RC) tag...")
    
    # Use the existing helper script to get the tag
    script_path = os.path.join(os.path.dirname(__file__), 'get_next_version.py')
    try:
        cmd = f"python3 {script_path} --type rc"
        raw_tag = run_command(cmd)
        
        # Ensure it starts with v
        if not raw_tag.startswith('v'):
            tag = f"v{raw_tag}"
        else:
            tag = raw_tag
            
    except Exception as e:
        print(f"Failed to calculate next version: {e}")
        sys.exit(1)

    print(f"\nProposing new tag: \033[1;32m{tag}\033[0m")
    
    confirm = input("Do you want to create and push this tag? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        sys.exit(0)

    print(f"Creating tag {tag}...")
    run_command(f"git tag {tag}", capture=False)
    
    print(f"Pushing tag {tag} to origin...")
    run_command(f"git push origin {tag}", capture=False)
    
    print(f"\n\033[1;32mSuccess! Staging build triggered for {tag}.\033[0m")
    print(f"View build status at: https://console.cloud.google.com/cloud-build/builds?project=datcom-ci")

if __name__ == "__main__":
    main()
