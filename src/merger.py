import uuid
from src.normalizer import normalize_phone, normalize_date, normalize_country, normalize_skill

SOURCE_TRUST_WEIGHTS = {
    "ats_json": 0.95,
    "recruiter_csv": 0.90,
    "github": 0.80,
    "linkedin": 0.80,
    "resume": 0.70,
    "recruiter_notes": 0.50
}

def resolve_entities(raw_candidates: list[dict]) -> list[list[dict]]:
    """Group candidate records that belong to the same physical person."""
    # Step 1: Normalize emails & phones for each raw record to build match index
    normalized_records = []
    for rc in raw_candidates:
        source = rc.get("source", "unknown")
        emails = [email.strip().lower() for email in rc.get("emails", []) if email]
        phones = []
        for p in rc.get("phones", []):
            np = normalize_phone(p)
            if np:
                phones.append(np)
        
        # Track and normalize github usernames
        githubs = set()
        links = rc.get("links")
        if links and isinstance(links, dict):
            gh = links.get("github")
            if gh and isinstance(gh, str):
                gh_clean = gh.strip().lower()
                username = gh_clean
                if "github.com/" in username:
                    parts = [p for p in username.split("/") if p]
                    if parts:
                        username = parts[-1]
                username_clean = username.split("?")[0].split("#")[0].strip()
                if username_clean:
                    githubs.add(username_clean)
        
        normalized_records.append({
            "raw": rc,
            "emails": set(emails),
            "phones": set(phones),
            "githubs": githubs,
            "source": source
        })

    # Step 2: Disjoint-set / Union-Find or simple grouping based on shared emails/phones/githubs
    groups = []
    for rec in normalized_records:
        matched_group_indices = []
        for idx, g in enumerate(groups):
            # Check if there is any overlap in emails, phones, or github profiles
            shares_email = not rec["emails"].isdisjoint(g["emails"])
            shares_phone = not rec["phones"].isdisjoint(g["phones"])
            shares_github = not rec["githubs"].isdisjoint(g["githubs"])
            if shares_email or shares_phone or shares_github:
                matched_group_indices.append(idx)
        
        if not matched_group_indices:
            # Create new group
            groups.append({
                "records": [rec],
                "emails": set(rec["emails"]),
                "phones": set(rec["phones"]),
                "githubs": set(rec["githubs"])
            })
        elif len(matched_group_indices) == 1:
            # Add to the single matched group
            g_idx = matched_group_indices[0]
            groups[g_idx]["records"].append(rec)
            groups[g_idx]["emails"].update(rec["emails"])
            groups[g_idx]["phones"].update(rec["phones"])
            groups[g_idx]["githubs"].update(rec["githubs"])
        else:
            # Merge multiple groups that are now connected by this record
            new_records = [rec]
            new_emails = set(rec["emails"])
            new_phones = set(rec["phones"])
            new_githubs = set(rec["githubs"])
            
            # Extract records from old groups
            remaining_groups = []
            for idx, g in enumerate(groups):
                if idx in matched_group_indices:
                    new_records.extend(g["records"])
                    new_emails.update(g["emails"])
                    new_phones.update(g["phones"])
                    new_githubs.update(g["githubs"])
                else:
                    remaining_groups.append(g)
            
            groups = remaining_groups
            groups.append({
                "records": new_records,
                "emails": new_emails,
                "phones": new_phones,
                "githubs": new_githubs
            })

    return [[rec["raw"] for rec in g["records"]] for g in groups]

def merge_candidate_group(records: list[dict]) -> dict:
    """Merge grouped candidate records into a single canonical candidate profile."""
    # Sort records by source trust weight (descending)
    sorted_records = sorted(
        records,
        key=lambda r: SOURCE_TRUST_WEIGHTS.get(r.get("source", ""), 0.50),
        reverse=True
    )
    
    primary_source = sorted_records[0].get("source", "unknown")
    
    # 1. candidate_id (deterministic UUID based on primary email, or random)
    all_emails = set()
    for r in sorted_records:
        for email in r.get("emails", []):
            if email:
                all_emails.add(email.strip().lower())
    
    if all_emails:
        # Use first email alphabetically to create a deterministic ID
        first_email = sorted(list(all_emails))[0]
        candidate_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, first_email))
    else:
        candidate_id = str(uuid.uuid4())
        
    provenance = []
    
    # helper to select field based on trust weight
    def select_field(field_name: str, fallback_val=None):
        for r in sorted_records:
            val = r.get(field_name)
            if val is not None and val != "" and val != []:
                provenance.append({
                    "field": field_name,
                    "source": r.get("source", "unknown"),
                    "method": "source_trust_hierarchy"
                })
                return val
        return fallback_val

    # 2. full_name
    full_name = select_field("full_name", "")
    
    # 3. emails (union of all unique emails)
    emails = sorted(list(all_emails))
    if emails:
        provenance.append({
            "field": "emails",
            "source": primary_source,
            "method": "union_all_sources"
        })
        
    # 4. phones (union of unique normalized phones)
    all_phones = set()
    for r in sorted_records:
        for p in r.get("phones", []):
            np = normalize_phone(p)
            if np:
                all_phones.add(np)
    phones = sorted(list(all_phones))
    if phones:
        provenance.append({
            "field": "phones",
            "source": primary_source,
            "method": "union_all_sources"
        })
        
    # 5. location (resolve field by field or object-level)
    # Let's resolve location by merging details
    location = {"city": "", "region": "", "country": ""}
    location_resolved = False
    for r in sorted_records:
        loc = r.get("location")
        if loc and isinstance(loc, dict):
            city = loc.get("city", "").strip()
            region = loc.get("region", "").strip()
            country = normalize_country(loc.get("country", ""))
            
            if not location["city"] and city:
                location["city"] = city
                location_resolved = True
            if not location["region"] and region:
                location["region"] = region
                location_resolved = True
            if not location["country"] and country:
                location["country"] = country
                location_resolved = True
                
    if location_resolved:
        provenance.append({
            "field": "location",
            "source": primary_source,
            "method": "merge_properties"
        })
        
    # 6. links
    links = {"linkedin": "", "github": "", "portfolio": "", "other": []}
    links_resolved = False
    for r in sorted_records:
        src_links = r.get("links")
        if src_links and isinstance(src_links, dict):
            li = src_links.get("linkedin", "").strip()
            gh = src_links.get("github", "").strip()
            port = src_links.get("portfolio", "").strip()
            other = src_links.get("other", [])
            
            if not links["linkedin"] and li:
                links["linkedin"] = li
                links_resolved = True
            if not links["github"] and gh:
                links["github"] = gh
                links_resolved = True
            if not links["portfolio"] and port:
                links["portfolio"] = port
                links_resolved = True
            for o in other:
                if o and o not in links["other"]:
                    links["other"].append(o)
                    links_resolved = True
                    
    if links_resolved:
        provenance.append({
            "field": "links",
            "source": primary_source,
            "method": "merge_properties"
        })
        
    # 7. headline
    headline = select_field("headline", None)
    
    # 8. years_experience (We'll calculate experience from start/end dates if missing)
    years_experience = select_field("years_experience", None)
    
    # 8b. repository_count
    repository_count = select_field("repository_count", None)
    
    # 9. experience
    experience_list = []
    # Deduplicate experience by company + title
    seen_jobs = set()
    for r in sorted_records:
        for job in r.get("experience", []):
            company = job.get("company", "").strip().lower()
            title = job.get("title", "").strip().lower()
            if not company:
                continue
                
            job_key = (company, title)
            if job_key not in seen_jobs:
                seen_jobs.add(job_key)
                # Normalize experience dates
                start = normalize_date(job.get("start", ""))
                end = normalize_date(job.get("end", ""))
                
                experience_list.append({
                    "company": job.get("company", "").strip(),
                    "title": job.get("title", "").strip(),
                    "start": start,
                    "end": end,
                    "summary": job.get("summary", "").strip()
                })
                
    if experience_list:
        provenance.append({
            "field": "experience",
            "source": primary_source,
            "method": "union_all_sources"
        })
        
        # Calculate years of experience if not explicitly provided
        if not years_experience:
            total_months = 0
            for job in experience_list:
                start = job["start"]
                end = job["end"]
                if start:
                    try:
                        sy, sm = map(int, start.split("-"))
                        ey, em = map(int, (end or datetime.now().strftime("%Y-%m")).split("-"))
                        months = (ey - sy) * 12 + (em - sm)
                        if months > 0:
                            total_months += months
                    except Exception:
                        pass
            if total_months > 0:
                years_experience = round(total_months / 12.0, 1)
                provenance.append({
                    "field": "years_experience",
                    "source": "calculated",
                    "method": "date_diff_sum"
                })
                
    # 10. education
    education_list = []
    seen_edu = set()
    for r in sorted_records:
        for edu in r.get("education", []):
            inst = edu.get("institution", "").strip().lower()
            deg = edu.get("degree", "").strip().lower()
            if not inst:
                continue
            edu_key = (inst, deg)
            if edu_key not in seen_edu:
                seen_edu.add(edu_key)
                education_list.append({
                    "institution": edu.get("institution", "").strip(),
                    "degree": edu.get("degree", "").strip(),
                    "field": edu.get("field", "").strip(),
                    "end_year": edu.get("end_year")
                })
                
    if education_list:
        provenance.append({
            "field": "education",
            "source": primary_source,
            "method": "union_all_sources"
        })
        
    # 11. skills (canonical skill names + confidence + sources list)
    skills_map = {}
    for r in sorted_records:
        src = r.get("source", "unknown")
        src_weight = SOURCE_TRUST_WEIGHTS.get(src, 0.50)
        for skill in r.get("skills", []):
            if isinstance(skill, str):
                name = normalize_skill(skill)
                conf = src_weight
            elif isinstance(skill, dict):
                name = normalize_skill(skill.get("name", ""))
                conf = skill.get("confidence", src_weight)
            else:
                continue
                
            if not name:
                continue
                
            if name not in skills_map:
                skills_map[name] = {
                    "name": name,
                    "confidence": conf,
                    "sources": {src}
                }
            else:
                skills_map[name]["sources"].add(src)
                # Combine confidence: take max or weighted combo
                skills_map[name]["confidence"] = max(skills_map[name]["confidence"], conf)
                
    skills = []
    for k, v in skills_map.items():
        v["sources"] = sorted(list(v["sources"]))
        skills.append(v)
        
    if skills:
        provenance.append({
            "field": "skills",
            "source": primary_source,
            "method": "merge_properties"
        })
        
    # 12. overall_confidence calculation
    # Base overall score is average of field confidence weights, weighted by completeness
    completeness_fields = [
        bool(full_name),
        bool(emails),
        bool(phones),
        location_resolved,
        links_resolved,
        bool(headline),
        bool(skills),
        bool(experience_list),
        bool(education_list)
    ]
    completeness = sum(completeness_fields) / len(completeness_fields)
    
    # Calculate average confidence weight of present fields
    field_weights = []
    for p in provenance:
        weight = SOURCE_TRUST_WEIGHTS.get(p["source"], 0.50)
        field_weights.append(weight)
    
    avg_confidence = sum(field_weights) / len(field_weights) if field_weights else 0.50
    overall_confidence = round(completeness * avg_confidence, 2)
    
    return {
        "candidate_id": candidate_id,
        "full_name": full_name,
        "emails": emails,
        "phones": phones,
        "location": location if location_resolved else {"city": "", "region": "", "country": ""},
        "links": links if links_resolved else {"linkedin": "", "github": "", "portfolio": "", "other": []},
        "headline": headline,
        "years_experience": years_experience,
        "skills": skills,
        "experience": experience_list,
        "education": education_list,
        "repository_count": repository_count,
        "provenance": provenance,
        "overall_confidence": overall_confidence
    }

def merge_candidates(raw_candidates: list[dict]) -> list[dict]:
    """Process a list of raw candidate inputs, resolving entities and merging duplicates."""
    resolved_groups = resolve_entities(raw_candidates)
    merged_profiles = []
    for group in resolved_groups:
        merged_profiles.append(merge_candidate_group(group))
    return merged_profiles
