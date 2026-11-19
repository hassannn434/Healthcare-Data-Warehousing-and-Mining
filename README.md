# Healthcare Data Warehousing and Mining

A Python-based healthcare analytics project that demonstrates data extraction, transformation, validation, and loading (ETL), dimensional data warehousing, and clinical data analysis using synthetic healthcare records.

## Project Overview

This project processes a synthetic healthcare dataset containing 30,000 records and stores validated clinical information in a structured SQLite data warehouse.

The system demonstrates how raw healthcare data can be cleaned, validated, transformed into analytical categories, and loaded into a dimensional warehouse for further analysis.

### Key Highlights

- Processed 30,000 synthetic healthcare records.
- Accepted 30,000 records with zero rejected records in the initial ETL run.
- Designed a dimensional data warehouse using a star-schema approach.
- Implemented SHA-256 checksums to identify previously imported source files.
- Created patient, clinical category, and ETL batch dimensions.
- Stored clinical measurements in a central fact table.
- Used SQLite for database storage and Python for ETL processing.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core programming and ETL |
| Pandas | Data extraction, cleaning and transformation |
| SQLite | Relational database and warehouse |
| SQL | Schema design and data storage |
| Streamlit | Application interface |
| NumPy | Numerical operations |
| Scikit-learn | Machine learning and analytical functionality in the application |
| Git and GitHub | Version control |

## Dataset Information

The project uses a synthetic healthcare dataset containing 30,000 records.

### Source Columns

- Patient_ID
- Patient_Name
- Age
- Length_of_Stay
- Lab_Cost
- Medication_Count
- Comorbidity_Score

Patient names are excluded from the warehouse. The warehouse stores patient identifiers and relevant clinical measurements.

**Privacy note:** The dataset contains synthetic records generated for academic and demonstration purposes. It does not contain actual patient medical records.

## Data Warehouse Architecture

The project uses a star-schema-inspired dimensional model.

### Dimension Tables

**1. dim_patient**

Stores unique patient identifiers.

- patient_key
- patient_id

**2. dim_clinical_category**

Stores combinations of analytical categories.

- category_key
- age_group
- stay_category
- lab_cost_category
- medication_category
- comorbidity_category

**3. dim_load_batch**

Maintains ETL execution and source-file metadata.

- batch_key
- loaded_at
- source_file
- source_checksum
- source_record_count
- accepted_record_count
- rejected_record_count

### Fact Table

**fact_clinical_records**

Stores measurable clinical attributes and links to the dimension tables.

- fact_key
- patient_key
- category_key
- batch_key
- age
- length_of_stay
- lab_cost
- medication_count
- comorbidity_score

### Architecture Diagram

```text
             Source CSV Dataset
                     |
                     v
              Extract Process
                     |
                     v
          Transform and Validate
                     |
                     v
                Load Process
                     |
                     v
             SQLite Warehouse
                     |
          +----------+----------+
          |          |          |
          v          v          v
      Patient    Clinical    Load Batch
     Dimension   Category    Dimension
          \          |          /
           \         |         /
            +--------+--------+
                     |
                     v
             Fact Clinical Records
```

## ETL Pipeline

The ETL process is implemented in `etl_pipeline.py`.

### 1. Extract

- Reads the source CSV dataset using Pandas.
- Checks whether all required columns are available.
- Calculates the source record count.

### 2. Transform

- Removes unnecessary source columns.
- Validates patient identifiers.
- Converts numeric fields into appropriate data types.
- Checks missing and invalid numeric values.
- Validates clinical value ranges.
- Detects duplicate patient identifiers within the source file.
- Generates analytical categories.

### 3. Load

- Creates a new ETL batch.
- Inserts unique patients into the patient dimension.
- Inserts unique category combinations into the clinical category dimension.
- Loads clinical measurements into the fact table.
- Maintains foreign-key relationships.
- Uses database transactions to protect the loading process.

### 4. Duplicate Import Prevention

The pipeline calculates a SHA-256 checksum of the source CSV file.

If the same source file has already been loaded, the pipeline identifies the existing batch and skips duplicate ingestion.

## Initial ETL Execution Results

| Metric | Result |
|---|---:|
| Source records | 30,000 |
| Accepted records | 30,000 |
| Rejected records | 0 |
| Unique patients | 30,000 |
| Clinical category combinations | 225 |
| ETL batches | 1 |
| Fact records loaded | 30,000 |

These results represent the initial successful ETL execution.

## Project Structure

```text
healthcare_mining_project/
│
├── app.py
├── database.py
├── generate_data.py
├── warehouse.py
├── etl_pipeline.py
│
├── clinical_dataset.csv
│
├── requirements.txt
├── .gitignore
│
└── sql/
    └── warehouse_schema.sql
```

The local SQLite database and backup directory are excluded from GitHub.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/hassannn434/Healthcare-Data-Warehousing-and-Mining.git
```

### 2. Navigate to the Project Directory

```bash
cd Healthcare-Data-Warehousing-and-Mining
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Initialize the Data Warehouse

```bash
python warehouse.py
```

### 6. Execute the ETL Pipeline

```bash
python etl_pipeline.py
```

The pipeline will extract the CSV data, validate and transform records, and load them into the SQLite warehouse.

### 7. Run the Streamlit Application

```bash
streamlit run app.py
```

## Database and Data Integrity

The warehouse uses SQLite with relational constraints and foreign keys.

Additional implementation features include:

- Unique patient identifiers.
- Unique clinical category combinations.
- Unique source checksums for ETL batches.
- Foreign-key relationships between fact and dimension tables.
- Transaction-based warehouse loading.
- Indexes on frequently referenced fact table keys.

## Future Enhancements

- Integrate warehouse queries directly into the Streamlit dashboards.
- Develop advanced SQL-based healthcare analytics.
- Add interactive clinical trend visualizations.
- Improve anomaly detection and association rule mining.
- Add ETL execution monitoring and detailed rejection reports.
- Expand analytical reporting and data quality checks.

## Limitations

- The dataset is synthetic and is not suitable for real clinical decision-making.
- The current application is an academic prototype, not a production healthcare system.
- Authentication and access controls require further security improvements before production use.

## Author

**Hassan Mahadkar**

B.Tech – Artificial Intelligence and Machine Learning

GitHub: https://github.com/hassannn434

---

*Developed as an academic project to explore healthcare data engineering, dimensional modelling, ETL workflows, and analytical applications using Python and SQL.*
