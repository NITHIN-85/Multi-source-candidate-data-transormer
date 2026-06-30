import argparse
import json
import sys
import os
from src.pipeline import run_transformer_pipeline

def main():
    parser = argparse.ArgumentParser(description="Multi-Source Candidate Data Transformer")
    parser.add_argument("--csv", help="Path to structured recruiter CSV export")
    parser.add_argument("--resume", help="Path to unstructured resume PDF or TXT")
    parser.add_argument("--github", help="Path to GitHub profile URL, username, or mock JSON path")
    parser.add_argument("--github-token", help="Optional GitHub Personal Access Token for authenticated requests")
    parser.add_argument("--config", help="Path to runtime custom projection configuration JSON")
    parser.add_argument("--output-default", default="data/output_default.json", help="Path to output default schema JSON")
    parser.add_argument("--output-custom", default="data/output_custom.json", help="Path to output custom schema JSON")
    
    args = parser.parse_args()
    
    if not args.csv and not args.resume and not args.github:
        print("Error: You must provide at least one input source using --csv, --resume, or --github.")
        parser.print_help()
        sys.exit(1)
        
    # Read custom configuration if provided
    config = None
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error: Failed to read custom config file {args.config}: {e}")
            sys.exit(1)
            
    # Create output directories if they do not exist
    os.makedirs(os.path.dirname(os.path.abspath(args.output_default)), exist_ok=True)
    if args.output_custom:
        os.makedirs(os.path.dirname(os.path.abspath(args.output_custom)), exist_ok=True)
        
    # Execute pipeline
    print("Running Candidate Data Transformer pipeline...")
    result = run_transformer_pipeline(
        csv_path=args.csv,
        resume_path=args.resume,
        github_path=args.github,
        github_token=args.github_token,
        config=config
    )
    
    # Write default canonical profiles
    try:
        with open(args.output_default, "w", encoding="utf-8") as f:
            json.dump(result["default"], f, indent=2, default=str)
        print(f"Success: Default schema profile(s) written to {args.output_default}")
    except Exception as e:
        print(f"Error: Failed to write default profiles: {e}")
        
    # Write custom projected profiles
    if config and result["custom"] is not None:
        try:
            with open(args.output_custom, "w", encoding="utf-8") as f:
                json.dump(result["custom"], f, indent=2, default=str)
            print(f"Success: Custom schema profile(s) written to {args.output_custom}")
        except Exception as e:
            print(f"Error: Failed to write custom profiles: {e}")

if __name__ == "__main__":
    main()
