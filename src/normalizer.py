import re
import phonenumbers
from datetime import datetime

COUNTRIES_MAPPING = {
    "united states": "US", "united states of america": "US", "usa": "US", "us": "US",
    "india": "IN", "ind": "IN", "in": "IN",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "gb": "GB",
    "canada": "CA", "ca": "CA",
    "germany": "DE", "de": "DE",
    "france": "FR", "fr": "FR",
    "australia": "AU", "au": "AU",
    "singapore": "SG", "sg": "SG",
}

SKILLS_MAPPING = {
    "js": "JavaScript", "javascript": "JavaScript", "es6": "JavaScript", "ecmascript": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript",
    "py": "Python", "python": "Python", "python3": "Python",
    "golang": "Go", "go": "Go", "go lang": "Go",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "aws": "Amazon Web Services", "amazon web services": "Amazon Web Services",
    "docker": "Docker", "containerization": "Docker",
    "sql": "SQL", "postgresql": "SQL", "mysql": "SQL", "postgres": "SQL",
    "react": "React", "reactjs": "React", "react.js": "React",
}

def normalize_phone(phone_str: str, default_region: str = "US") -> str | None:
    """Normalize a phone number to E.164 format."""
    if not phone_str:
        return None
    phone_clean = phone_str.strip()
    
    # Try parsing directly
    try:
        parsed = phonenumbers.parse(phone_clean, default_region)
        if phonenumbers.is_possible_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
        
    # Try prepending '+' (useful for international codes like '44 ...' without + prefix)
    if not phone_clean.startswith("+"):
        try:
            parsed = phonenumbers.parse("+" + phone_clean, default_region)
            if phonenumbers.is_possible_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass
            
    # Fallback basic regex cleaning
    digits = "".join(c for c in phone_clean if c.isdigit())
    
    # Handle local 7-digit numbers (often fictional 555 numbers) by prepending a standard area code (650)
    if len(digits) == 7:
        digits = "650" + digits
    elif len(digits) == 8 and digits.startswith("1"):
        digits = "650" + digits[1:]
        
    if len(digits) >= 10:
        if phone_clean.startswith("+"):
            return f"+{digits}"
        else:
            return f"+1{digits[-10:]}"  # Default to US prefix +1
    return None

def normalize_date(date_str: str) -> str | None:
    """Normalize written date strings into YYYY-MM format."""
    if not date_str:
        return None
    date_clean = date_str.strip().lower()
    if date_clean in ("present", "current", "now"):
        return datetime.now().strftime("%Y-%m")
    
    # 1. Match YYYY-MM
    match = re.match(r"^(\d{4})[-/](\d{1,2})$", date_clean)
    if match:
        year, month = match.groups()
        return f"{year}-{int(month):02d}"
        
    # 1b. Match MM-YYYY (e.g. 06/2021)
    match_my = re.match(r"^(\d{1,2})[-/](\d{4})$", date_clean)
    if match_my:
        month, year = match_my.groups()
        return f"{year}-{int(month):02d}"
        
    # 2. Match YYYY (e.g. 2017)
    match = re.match(r"^(\d{4})$", date_clean)
    if match:
        return f"{match.group(1)}-01"
        
    # 3. Match written month name and year (e.g. "January 2024")
    months = {
        "jan": "01", "january": "01",
        "feb": "02", "february": "02",
        "mar": "03", "march": "03",
        "apr": "04", "april": "04",
        "may": "05",
        "jun": "06", "june": "06",
        "jul": "07", "july": "07",
        "aug": "08", "august": "08",
        "sep": "09", "september": "09",
        "oct": "10", "october": "10",
        "nov": "11", "november": "11",
        "dec": "12", "december": "12"
    }
    
    for month_name, month_num in months.items():
        if month_name in date_clean:
            year_match = re.search(r"\b(\d{4})\b", date_clean)
            if year_match:
                return f"{year_match.group(1)}-{month_num}"
                
    # Fallback to datetime.strptime
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %Y", "%B %Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_clean, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            pass
            
    return None

def normalize_country(country_str: str) -> str | None:
    """Normalize country names/strings into ISO-3166-1 alpha-2 format."""
    if not country_str:
        return None
    cleaned = country_str.strip().lower()
    return COUNTRIES_MAPPING.get(cleaned, cleaned[:2].upper())

def normalize_skill(skill_str: str) -> str:
    """Standardize a skill name using a predefined synonym mapping."""
    if not skill_str:
        return ""
    cleaned = skill_str.strip().lower()
    return SKILLS_MAPPING.get(cleaned, skill_str.strip())
