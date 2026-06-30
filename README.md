<<<<<<< HEAD
# Multi-Source Candidate Data Transformer

A robust Python pipeline designed to ingest candidate profiles from both structured and unstructured sources, normalize data fields (phone, dates, countries, and skill variants), perform entity resolution (deduplication) across profiles, and output unified, schema-valid JSON candidate files. It features a custom runtime projection layer that dynamically reshapes output keys, filters properties, handles missing values, and validates against dynamic schema configurations.

---

## 2. Installation & Setup

Ensure you have **Python 3.10+** installed on your system.

1. Clone or navigate to the project directory:
   ```bash
   cd assignment
   ```

2. Install package dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Installs: `pydantic` for modeling, `phonenumbers` for E.164 formatting, `jsonschema` for dynamic output validation, `pypdf` and `pdfplumber` for PDF text extraction, and `pytesseract` for OCR).*

# Pipeline Flow

```text
Input Sources
      ↓
Data Extraction
      ↓
Normalization
      ↓
Merge & Conflict Resolution
      ↓
Canonical Schema Generation
      ↓
Config-Based Projection
      ↓
Final JSON Output

## 3. Running the Pipeline

You can run the pipeline from the command line using the root-level helper `run.py`.

### A. Run End-to-End on Sample Data (CSV + Resume)
Ingest both the structured CSV and unstructured resume text simultaneously, merge candidates, and write the default profile and custom projected profile:
```bash
python run.py --csv data/sample_csv.csv --resume data/sample_resume.txt --config data/custom_config.json --output-default data/output_default.json --output-custom data/output_custom.json
```

### B. Command Options
```bash
python run.py --help
```
*   `--csv`: Path to the structured Recruiter CSV export.
*   `--resume`: Path to the unstructured Resume (PDF or TXT file).
*   `--config`: Path to the runtime dynamic custom configuration JSON.
*   `--output-default`: Path to write the default canonical JSON (defaults to `data/output_default.json`).
*   `--output-custom`: Path to write the custom projected JSON (defaults to `data/output_custom.json`).

---

## 4. Running the Tests

To verify that the formatters, entity matchers, and custom projectors behave exactly as specified by the constraints:

```bash
python -m unittest tests/test_pipeline.py
```

---

## 5. Architectural Design & Assumptions

### A. Pipeline Stages
1. **Ingestion & Parsing (`src/parser.py`):** Structured CSV data is parsed into simple row structures. Unstructured resume files (PDF or TXT) are read, and name, contact info, experience blocks, and skills are extracted via rule-based regex patterns.
2. **Normalization (`src/normalizer.py`):**
   *   **Phone Numbers:** Formatted to E.164 (e.g. `+16505550199`) using Google `phonenumbers`. For 7-digit local US numbers, it automatically prepends standard area code `650`.
   *   **Dates:** Normalizes prose dates ("January 2024", "Present", "06/2021", "2017") to standard `YYYY-MM`.
   *   **Country Codes:** Converts full country names into ISO-3166-1 alpha-2.
   *   **Skills:** Maps common skill variations (e.g. `JS`, `React.js` $\rightarrow$ `JavaScript`, `React`) to canonical values.
3. **Deduplication & Entity Resolution (`src/merger.py`):** Groups candidates by matching normalized emails or E.164 phone numbers. 
4. **Source Trust Merger (`src/merger.py`):**
   *   Matches properties across conflicting profiles based on trust weights: `ATS JSON (0.95) > Recruiter CSV (0.90) > Resume PDF (0.60)`.
   *   Single values (like name or title) are selected from the highest-ranked source.
   *   Sets (like emails, phone numbers, experience lists) are union-merged.
   *   Maintains a `provenance` block recording the field, source, and selection method.
   *   Computes an `overall_confidence` score based on data completeness and average field confidence.
5. **Configurable Output Projection (`src/projector.py`):** Reshapes the output based on custom config files using JSON paths, custom overrides, toggling metadata, and validating outputs against dynamically generated JSON Schemas.

### B. Handled Edge Cases
*   **Fictional F55-Numbers & 7-Digit US Dialing:** Fallback area code `650` is automatically prepended, allowing fictional numbers to validate as possible US numbers in the `phonenumbers` library.
*   **Prose Date Variations:** Parses formats like "Present", "Jan 2024", "2021" into correct `YYYY-MM` formats.
*   **Missing Fields / Graceful Degradation:** Malformed input files skip processing gracefully. Missing fields default to `null` and are omitted or errored according to the runtime configuration's `on_missing` rule  
