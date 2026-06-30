import os
from src.parser import parse_csv, parse_resume, parse_github
from src.merger import merge_candidates
from src.projector import project_candidate

def run_transformer_pipeline(
    csv_path: str = None,
    resume_path: str = None,
    github_path: str = None,
    github_token: str = None,
    config: dict = None
) -> dict:
    """Run the candidate transformer pipeline end-to-end.
    
    Ingests, parses, normalizes, deduplicates, and projects/validates candidates.
    Returns a dictionary with 'default' profiles and 'custom' projected profiles if config is provided.
    """
    raw_candidates = []
    
    # 1. Ingest Structured Source
    if csv_path:
        csv_candidates = parse_csv(csv_path)
        raw_candidates.extend(csv_candidates)
        
    # 2. Ingest Unstructured Sources
    if resume_path:
        if os.path.isdir(resume_path):
            for file_name in os.listdir(resume_path):
                if file_name.lower().endswith((".pdf", ".txt")):
                    full_path = os.path.join(resume_path, file_name)
                    resume_cand = parse_resume(full_path)
                    if resume_cand:
                        raw_candidates.append(resume_cand)
        else:
            resume_cand = parse_resume(resume_path)
            if resume_cand:
                raw_candidates.append(resume_cand)
            
    if github_path:
        github_cand = parse_github(github_path, token=github_token)
        if github_cand:
            raw_candidates.append(github_cand)
            
    # 2b. Automatically enrich candidates if a GitHub link is present in their parsed profiles
    enriched_github_cands = []
    seen_github_urls = set()
    
    # Track any explicitly passed github path to avoid duplicate fetching
    if github_path and not os.path.exists(github_path):
        gh_clean = github_path.strip().lower().rstrip("/")
        if "github.com/" in gh_clean:
            parts = [p for p in gh_clean.split("/") if p]
            if parts:
                seen_github_urls.add(parts[-1])
        else:
            seen_github_urls.add(gh_clean.split("?")[0].split("#")[0].strip())

    for cand in raw_candidates:
        links = cand.get("links")
        if links and isinstance(links, dict):
            gh_url = links.get("github")
            if gh_url and isinstance(gh_url, str):
                gh_url_clean = gh_url.strip()
                # Parse username
                username = gh_url_clean
                if "github.com/" in username.lower():
                    parts = [p for p in username.split("/") if p]
                    if parts:
                        username = parts[-1]
                username_clean = username.split("?")[0].split("#")[0].strip().lower()
                
                if username_clean and username_clean not in seen_github_urls:
                    seen_github_urls.add(username_clean)
                    print(f"Auto-enriching candidate from GitHub URL: {gh_url_clean}...")
                    github_cand = parse_github(gh_url_clean, token=github_token)
                    if github_cand:
                        enriched_github_cands.append(github_cand)
                        
    raw_candidates.extend(enriched_github_cands)
            
    # 3. Deduplicate and Merge candidates into Canonical Profiles
    canonical_profiles = merge_candidates(raw_candidates)
    
    # 4. Project using config if provided
    projected_profiles = []
    if config:
        for profile in canonical_profiles:
            try:
                projected = project_candidate(profile, config)
                projected_profiles.append(projected)
            except Exception as e:
                print(f"Warning: Failed to project candidate {profile.get('full_name')}: {e}")
                
    return {
        "default": canonical_profiles,
        "custom": projected_profiles if config else None
    }
