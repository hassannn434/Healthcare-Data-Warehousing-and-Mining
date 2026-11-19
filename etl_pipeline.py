
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from warehouse import (
    DATABASE_FILE,
    get_warehouse_connection,
    initialize_warehouse,
)


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "clinical_dataset.csv"

REQUIRED_COLUMNS = [
    "Patient_ID",
    "Age",
    "Length_of_Stay",
    "Lab_Cost",
    "Medication_Count",
    "Comorbidity_Score",
]

NUMERIC_COLUMNS = [
    "Age",
    "Length_of_Stay",
    "Lab_Cost",
    "Medication_Count",
    "Comorbidity_Score",
]


# --------------------------------------------------
# EXTRACT
# --------------------------------------------------

def extract_data():
    """Read the source CSV dataset."""

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_FILE}"
        )

    dataframe = pd.read_csv(DATA_FILE)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    return dataframe


def calculate_file_checksum():
    """Generate SHA-256 checksum to identify duplicate imports."""

    sha256 = hashlib.sha256()

    with open(DATA_FILE, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


# --------------------------------------------------
# TRANSFORM
# --------------------------------------------------

def classify_clinical_records(dataframe):
    """Generate analytical categories for each clinical record."""

    dataframe = dataframe.copy()

    dataframe["Age_Group"] = pd.cut(
        dataframe["Age"],
        bins=[-float("inf"), 39, 60, float("inf")],
        labels=["Under 40", "40 to 60", "Over 60"],
    ).astype(str)

    dataframe["Stay_Category"] = pd.cut(
        dataframe["Length_of_Stay"],
        bins=[-float("inf"), 3, 7, float("inf")],
        labels=["Short stay", "Moderate stay", "Long stay"],
    ).astype(str)

    dataframe["Lab_Cost_Category"] = pd.cut(
        dataframe["Lab_Cost"],
        bins=[-float("inf"), 1000, 2000, float("inf")],
        labels=["Low lab cost", "Medium lab cost", "High lab cost"],
    ).astype(str)

    dataframe["Medication_Category"] = pd.cut(
        dataframe["Medication_Count"],
        bins=[-float("inf"), 2, 5, float("inf")],
        labels=[
            "Few medications",
            "Moderate medications",
            "Many medications",
        ],
    ).astype(str)

    dataframe["Comorbidity_Category"] = pd.cut(
        dataframe["Comorbidity_Score"],
        bins=[-float("inf"), 1, 3, float("inf")],
        labels=[
            "Low comorbidity",
            "Moderate comorbidity",
            "High comorbidity",
        ],
    ).astype(str)

    return dataframe


def transform_data(dataframe):
    """
    Clean and validate source records.

    Returns:
        cleaned_data: Valid records ready for loading.
        rejected_count: Number of rejected source records.
    """

    dataframe = dataframe[REQUIRED_COLUMNS].copy()

    original_count = len(dataframe)

    # Remove rows without a patient identifier.
    dataframe["Patient_ID"] = (
        dataframe["Patient_ID"].astype("string").str.strip()
    )

    valid_id = (
        dataframe["Patient_ID"].notna()
        & dataframe["Patient_ID"].ne("")
    )

    # Convert numeric columns safely.
    for column in NUMERIC_COLUMNS:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    # Check for missing or invalid numeric values.
    valid_numeric = dataframe[NUMERIC_COLUMNS].notna().all(axis=1)

    # Check that numeric values are finite.
    valid_finite = pd.Series(True, index=dataframe.index)

    for column in NUMERIC_COLUMNS:
        valid_finite &= dataframe[column].map(
            lambda value: pd.notna(value)
            and float("-inf") < value < float("inf")
        )

    # Clinical value validation.
    valid_ranges = (
        dataframe["Age"].between(18, 120)
        & dataframe["Length_of_Stay"].ge(1)
        & dataframe["Lab_Cost"].ge(0)
        & dataframe["Medication_Count"].ge(0)
        & dataframe["Comorbidity_Score"].between(0, 4)
    )

    # Check whole-number fields.
    integer_columns = [
        "Age",
        "Length_of_Stay",
        "Medication_Count",
        "Comorbidity_Score",
    ]

    valid_integers = pd.Series(True, index=dataframe.index)

    for column in integer_columns:
        valid_integers &= (
            dataframe[column].mod(1).eq(0)
        )

    valid_rows = (
        valid_id
        & valid_numeric
        & valid_finite
        & valid_ranges
        & valid_integers
    )

    # Reject duplicate patient IDs within this source file.
    duplicate_ids = dataframe["Patient_ID"].duplicated(
        keep="first"
    )

    valid_rows &= ~duplicate_ids

    cleaned_data = dataframe.loc[valid_rows].copy()

    rejected_count = original_count - len(cleaned_data)

    # Convert validated integer fields to integer type.
    for column in integer_columns:
        cleaned_data[column] = cleaned_data[column].astype(int)

    # Add analytical categories.
    cleaned_data = classify_clinical_records(cleaned_data)

    return cleaned_data, rejected_count


# --------------------------------------------------
# LOAD
# --------------------------------------------------

def load_data(cleaned_data, source_count, rejected_count, checksum):
    """Load transformed data into the SQLite warehouse."""

    connection = get_warehouse_connection()

    try:
        connection.execute("BEGIN")

        # Prevent the same source file from being imported twice.
        existing_batch = connection.execute(
            """
            SELECT batch_key
            FROM dim_load_batch
            WHERE source_checksum = ?
            """,
            (checksum,),
        ).fetchone()

        if existing_batch:
            connection.rollback()

            return {
                "status": "already_loaded",
                "batch_key": existing_batch[0],
                "accepted_records": 0,
                "rejected_records": 0,
            }

        # Register a new load batch.
        cursor = connection.execute(
            """
            INSERT INTO dim_load_batch (
                loaded_at,
                source_file,
                source_checksum,
                source_record_count,
                accepted_record_count,
                rejected_record_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                DATA_FILE.name,
                checksum,
                source_count,
                len(cleaned_data),
                rejected_count,
            ),
        )

        batch_key = cursor.lastrowid

        # Insert unique patients.
        patient_ids = [
            (patient_id,)
            for patient_id in cleaned_data["Patient_ID"].unique()
        ]

        connection.executemany(
            """
            INSERT OR IGNORE INTO dim_patient (patient_id)
            VALUES (?)
            """,
            patient_ids,
        )

        # Insert unique clinical category combinations.
        category_columns = [
            "Age_Group",
            "Stay_Category",
            "Lab_Cost_Category",
            "Medication_Category",
            "Comorbidity_Category",
        ]

        unique_categories = cleaned_data[
            category_columns
        ].drop_duplicates()

        connection.executemany(
            """
            INSERT OR IGNORE INTO dim_clinical_category (
                age_group,
                stay_category,
                lab_cost_category,
                medication_category,
                comorbidity_category
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            list(
                unique_categories.itertuples(
                    index=False,
                    name=None,
                )
            ),
        )

        # Retrieve patient dimension keys.
        patient_map = dict(
            connection.execute(
                "SELECT patient_id, patient_key FROM dim_patient"
            ).fetchall()
        )

        # Retrieve clinical category dimension keys.
        category_map = {}

        category_rows = connection.execute(
            """
            SELECT
                age_group,
                stay_category,
                lab_cost_category,
                medication_category,
                comorbidity_category,
                category_key
            FROM dim_clinical_category
            """
        ).fetchall()

        for row in category_rows:
            category_map[tuple(row[:5])] = row[5]

        # Prepare fact table records.
        fact_records = []

        for row in cleaned_data.itertuples(index=False):
            patient_key = patient_map[row.Patient_ID]

            category_tuple = (
                row.Age_Group,
                row.Stay_Category,
                row.Lab_Cost_Category,
                row.Medication_Category,
                row.Comorbidity_Category,
            )

            category_key = category_map[category_tuple]

            fact_records.append(
                (
                    patient_key,
                    category_key,
                    batch_key,
                    row.Age,
                    row.Length_of_Stay,
                    row.Lab_Cost,
                    row.Medication_Count,
                    row.Comorbidity_Score,
                )
            )

        # Load measurable clinical attributes.
        connection.executemany(
            """
            INSERT INTO fact_clinical_records (
                patient_key,
                category_key,
                batch_key,
                age,
                length_of_stay,
                lab_cost,
                medication_count,
                comorbidity_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            fact_records,
        )

        connection.commit()

        return {
            "status": "success",
            "batch_key": batch_key,
            "accepted_records": len(cleaned_data),
            "rejected_records": rejected_count,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# --------------------------------------------------
# ETL EXECUTION
# --------------------------------------------------

def run_etl_pipeline():
    """Execute the complete extract, transform and load process."""

    print("=" * 55)
    print("HEALTHCARE DATA WAREHOUSE - ETL PIPELINE")
    print("=" * 55)

    print("\nSTEP 1: Initializing warehouse...")
    initialize_warehouse()

    print("\nSTEP 2: Extracting source data...")
    source_data = extract_data()

    source_count = len(source_data)

    print(f"Source records: {source_count}")

    print("\nSTEP 3: Transforming and validating data...")
    cleaned_data, rejected_count = transform_data(source_data)

    print(f"Accepted records: {len(cleaned_data)}")
    print(f"Rejected records: {rejected_count}")

    print("\nSTEP 4: Calculating source checksum...")
    checksum = calculate_file_checksum()

    print(f"SHA-256: {checksum}")

    print("\nSTEP 5: Loading warehouse...")
    result = load_data(
        cleaned_data,
        source_count,
        rejected_count,
        checksum,
    )

    print("\n" + "=" * 55)

    if result["status"] == "already_loaded":
        print("ETL SKIPPED: This source file was already loaded.")
        print(f"Existing batch key: {result['batch_key']}")

    else:
        print("ETL COMPLETED SUCCESSFULLY!")
        print(f"Batch key: {result['batch_key']}")
        print(f"Loaded records: {result['accepted_records']}")
        print(f"Rejected records: {result['rejected_records']}")

    print("=" * 55)

    return result


if __name__ == "__main__":
    run_etl_pipeline()
