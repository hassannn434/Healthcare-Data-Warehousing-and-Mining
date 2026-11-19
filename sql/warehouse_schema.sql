
-- Healthcare Data Warehouse: Star Schema
-- All records are synthetic and intended for academic analysis.

PRAGMA foreign_keys = ON;

-- 1. Patient Dimension
CREATE TABLE IF NOT EXISTS dim_patient (
    patient_key INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL UNIQUE
);

-- 2. Clinical Category Dimension
CREATE TABLE IF NOT EXISTS dim_clinical_category (
    category_key INTEGER PRIMARY KEY AUTOINCREMENT,
    age_group TEXT NOT NULL,
    stay_category TEXT NOT NULL,
    lab_cost_category TEXT NOT NULL,
    medication_category TEXT NOT NULL,
    comorbidity_category TEXT NOT NULL,
    UNIQUE (
        age_group,
        stay_category,
        lab_cost_category,
        medication_category,
        comorbidity_category
    )
);

-- 3. Load Batch Dimension
CREATE TABLE IF NOT EXISTS dim_load_batch (
    batch_key INTEGER PRIMARY KEY AUTOINCREMENT,
    loaded_at TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_checksum TEXT NOT NULL UNIQUE,
    source_record_count INTEGER NOT NULL,
    accepted_record_count INTEGER NOT NULL,
    rejected_record_count INTEGER NOT NULL
);

-- 4. Clinical Records Fact Table
CREATE TABLE IF NOT EXISTS fact_clinical_records (
    fact_key INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_key INTEGER NOT NULL,
    category_key INTEGER NOT NULL,
    batch_key INTEGER NOT NULL,
    age INTEGER NOT NULL,
    length_of_stay INTEGER NOT NULL,
    lab_cost REAL NOT NULL,
    medication_count INTEGER NOT NULL,
    comorbidity_score INTEGER NOT NULL,

    FOREIGN KEY (patient_key)
        REFERENCES dim_patient(patient_key),

    FOREIGN KEY (category_key)
        REFERENCES dim_clinical_category(category_key),

    FOREIGN KEY (batch_key)
        REFERENCES dim_load_batch(batch_key),

    UNIQUE (patient_key, batch_key)
);

-- 5. Indexes for analytical query performance
CREATE INDEX IF NOT EXISTS idx_fact_patient
ON fact_clinical_records(patient_key);

CREATE INDEX IF NOT EXISTS idx_fact_batch
ON fact_clinical_records(batch_key);

CREATE INDEX IF NOT EXISTS idx_fact_category
ON fact_clinical_records(category_key);
