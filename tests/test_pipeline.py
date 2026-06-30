import unittest
from src.normalizer import normalize_phone, normalize_date, normalize_country, normalize_skill
from src.merger import resolve_entities, merge_candidate_group
from src.projector import get_by_path, project_candidate

class TestNormalizer(unittest.TestCase):
    
    def test_phone_normalization(self):
        self.assertEqual(normalize_phone("+1 555-0199"), "+15550199")
        self.assertEqual(normalize_phone("(555) 0199"), "+15550199") # Default US region
        self.assertEqual(normalize_phone("+44 7911 123456"), "+447911123456")
        self.assertIsNone(normalize_phone("not-a-number"))

    def test_date_normalization(self):
        self.assertEqual(normalize_date("January 2024"), "2024-01")
        self.assertEqual(normalize_date("06/2021"), "2021-06")
        self.assertEqual(normalize_date("2017"), "2017-01")
        self.assertIsNotNone(normalize_date("Present"))

    def test_country_normalization(self):
        self.assertEqual(normalize_country("United States"), "US")
        self.assertEqual(normalize_country("India"), "IN")
        self.assertEqual(normalize_country("United Kingdom"), "GB")
        self.assertEqual(normalize_country("Canada"), "CA")

    def test_skill_normalization(self):
        self.assertEqual(normalize_skill("js"), "JavaScript")
        self.assertEqual(normalize_skill("ReactJS"), "React")
        self.assertEqual(normalize_skill("Python3"), "Python")
        self.assertEqual(normalize_skill("Custom Skill"), "Custom Skill")

class TestMerger(unittest.TestCase):
    
    def setUp(self):
        self.record_csv = {
            "full_name": "Alice Smith",
            "emails": ["alice.smith@example.com"],
            "phones": ["+1 555-0199"],
            "experience": [{"company": "Google", "title": "Software Engineer"}],
            "source": "recruiter_csv"
        }
        self.record_resume = {
            "full_name": "Alice S. Smith",
            "emails": ["alice.smith@example.com"],
            "phones": ["5550199"],
            "skills": ["Python", "JS", "Go"],
            "experience": [
                {"company": "Google", "title": "Senior Software Engineer", "start": "Jan 2024", "end": "Present"},
                {"company": "Microsoft", "title": "Software Engineer II", "start": "June 2021", "end": "Dec 2023"}
            ],
            "source": "resume"
        }

    def test_entity_resolution(self):
        raw = [self.record_csv, self.record_resume]
        groups = resolve_entities(raw)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)

    def test_candidate_merging(self):
        raw = [self.record_csv, self.record_resume]
        merged = merge_candidate_group(raw)
        
        # Trust weight CSV (0.90) > Resume (0.60) -> CSV name wins
        self.assertEqual(merged["full_name"], "Alice Smith")
        self.assertIn("alice.smith@example.com", merged["emails"])
        
        # Skills standardizations
        skills_names = [s["name"] for s in merged["skills"]]
        self.assertIn("JavaScript", skills_names)
        self.assertIn("Python", skills_names)
        
        # Provenance mapping exists
        self.assertTrue(len(merged["provenance"]) > 0)
        
        # Overall confidence calculated
        self.assertTrue(merged["overall_confidence"] > 0)

class TestProjector(unittest.TestCase):
    
    def setUp(self):
        self.candidate = {
            "full_name": "Alice Smith",
            "emails": ["alice.smith@example.com", "alice.personal@example.com"],
            "phones": ["+15550199"],
            "skills": [{"name": "Python", "confidence": 0.60, "sources": ["resume"]}],
            "overall_confidence": 0.85,
            "provenance": [{"field": "full_name", "source": "recruiter_csv", "method": "exact_copy"}]
        }
        self.config = {
            "fields": [
                { "path": "full_name", "type": "string", "required": true },
                { "path": "primary_email", "from": "emails[0]", "type": "string", "required": true },
                { "path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164" }
            ],
            "include_confidence": True,
            "on_missing": "null"
        }
        
    def test_path_extraction(self):
        self.assertEqual(get_by_path(self.candidate, "emails[0]"), "alice.smith@example.com")
        self.assertEqual(get_by_path(self.candidate, "emails[1]"), "alice.personal@example.com")
        self.assertIsNone(get_by_path(self.candidate, "emails[2]"))
        self.assertEqual(get_by_path(self.candidate, "skills[].name"), ["Python"])

    def test_projection(self):
        projected = project_candidate(self.candidate, self.config)
        self.assertEqual(projected["full_name"], "Alice Smith")
        self.assertEqual(projected["primary_email"], "alice.smith@example.com")
        self.assertEqual(projected["phone"], "+15550199")
        self.assertEqual(projected["overall_confidence"], 0.85)

    def test_missing_values_omit(self):
        # Set phone missing
        self.candidate["phones"] = []
        config_omit = self.config.copy()
        config_omit["on_missing"] = "omit"
        
        projected = project_candidate(self.candidate, config_omit)
        self.assertNotIn("phone", projected)

    def test_missing_values_error(self):
        self.candidate["phones"] = []
        config_err = self.config.copy()
        config_err["fields"] = [
            { "path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164", "required": True }
        ]
        config_err["on_missing"] = "error"
        
        with self.assertRaises(ValueError):
            project_candidate(self.candidate, config_err)

class TestGitHubIngestion(unittest.TestCase):
    
    def test_github_parser(self):
        from src.parser import parse_github
        # Ingest the mock file
        candidate = parse_github("data/github_mock.json")
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["full_name"], "Alice Smith")
        self.assertIn("alice.smith@example.com", candidate["emails"])
        self.assertEqual(candidate["links"]["github"], "https://github.com/alicesmith")
        self.assertEqual(candidate["links"]["portfolio"], "https://alicesmith.dev")
        self.assertEqual(candidate["location"]["city"], "San Francisco")
        self.assertEqual(candidate["location"]["country"], "USA")
        self.assertEqual(candidate["headline"], "Senior Backend & Infrastructure Engineer. Building scalable services.")
        self.assertEqual(candidate["repository_count"], 3)
        
        # Verify skills extracted from repo languages
        skills = candidate["skills"]
        self.assertIn("Python", skills)
        self.assertIn("Go", skills)
        self.assertIn("JavaScript", skills)
        
        # Verify experience items (repositories are no longer mapped to experience)
        self.assertEqual(len(candidate["experience"]), 0)
        
    def test_github_merging_integration(self):
        from src.pipeline import run_transformer_pipeline
        # We run the pipeline combining CSV and GitHub
        # Alice is in the CSV with email alice.smith@example.com
        # Alice is also in the github mock file with email alice.smith@example.com
        # They should merge into one profile.
        result = run_transformer_pipeline(
            csv_path="data/sample_csv.csv",
            github_path="data/github_mock.json"
        )
        profiles = result["default"]
        
        # Find Alice
        alice = next((p for p in profiles if "alice.smith@example.com" in p["emails"]), None)
        self.assertIsNotNone(alice)
        
        # Name: CSV trust (0.90) > GitHub (0.80), but both are "Alice Smith"
        self.assertEqual(alice["full_name"], "Alice Smith")
        self.assertEqual(alice["repository_count"], 3)
        
        # Experience: should only contain the CSV experience
        self.assertEqual(len(alice["experience"]), 1)
        
        # Skills: should come from GitHub languages
        skills_names = [s["name"] for s in alice["skills"]]
        self.assertIn("Python", skills_names)
        self.assertIn("Go", skills_names)
        
        # Links: GitHub profile url and blog should be merged
        self.assertEqual(alice["links"]["github"], "https://github.com/alicesmith")
        self.assertEqual(alice["links"]["portfolio"], "https://alicesmith.dev")
        
        # Provenance check: should contain github records
        prov_sources = {p["source"] for p in alice["provenance"]}
        self.assertIn("github", prov_sources)

# Pydantic JSON compatible boolean variables
true = True
false = False

if __name__ == "__main__":
    unittest.main()
