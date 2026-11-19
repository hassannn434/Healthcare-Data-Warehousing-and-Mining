
import hashlib
import sqlite3
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


# ------------------------------------------------------------
# 1. PROJECT PATHS AND PAGE CONFIGURATION
# ------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "clinical_dataset.csv"
DATABASE_FILE = PROJECT_DIR / "clinical_portal.db"

st.set_page_config(
    page_title="Healthcare Data Mining Portal",
    page_icon="🏥",
    layout="wide"
)


# ------------------------------------------------------------
# 2. DATABASE AND DEMO AUTHENTICATION
# ------------------------------------------------------------
def hash_password(password: str) -> str:
    """Legacy-compatible hash for this classroom demonstration only."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_connection():
    return sqlite3.connect(DATABASE_FILE)


def initialize_database():
    """Create the users table if needed and preserve the existing DB schema."""
    with get_connection() as conn:
        # Compatible with the existing database password_hash column.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                assigned_doctor TEXT
            )
            """
        )

        # Add demo accounts only if their usernames are missing.
        # Existing accounts and records are never overwritten.
        demo_users = [
            ("patient_100", hash_password("password123"), "Patient", "Dr. Patil"),
            ("patient_101", hash_password("password123"), "Patient", "Dr. Sharma"),
            ("dr_patil", hash_password("password123"), "Doctor", "None"),
            ("analyst_user", hash_password("password123"), "Analyst", "None"),
        ]

        conn.executemany(
            """
            INSERT OR IGNORE INTO users
            (username, password_hash, role, assigned_doctor)
            VALUES (?, ?, ?, ?)
            """,
            demo_users
        )


def authenticate_user(username: str, password: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT username, role, assigned_doctor
            FROM users
            WHERE username = ? AND password_hash = ?
            """,
            (username.strip(), hash_password(password))
        ).fetchone()


def register_user(username: str, password: str, role: str, doctor: str):
    username = username.strip()

    if not username or not password:
        return False, "Enter both a username and password."

    if len(password) < 8:
        return False, "Use a password with at least 8 characters."

    # Patient accounts map to rows in the synthetic dataset:
    # patient_100 -> row 0, patient_101 -> row 1, etc.
    if role == "Patient":
        if not username.startswith("patient_"):
            return False, (
                "Patient usernames must use the format "
                "patient_100, patient_101, etc."
            )

        suffix = username.removeprefix("patient_")

        if not suffix.isdigit():
            return False, "The number after patient_ must be numeric."

        row_number = int(suffix) - 100

        if row_number < 0 or row_number >= 30000:
            return False, (
                "Choose a patient number from "
                "patient_100 to patient_30099."
            )

    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users
                (username, password_hash, role, assigned_doctor)
                VALUES (?, ?, ?, ?)
                """,
                (
                    username,
                    hash_password(password),
                    role,
                    doctor if role == "Patient" else "None"
                )
            )

        return True, "Account created. Switch to Login to continue."

    except sqlite3.IntegrityError:
        return False, "That username already exists. Choose another."


initialize_database()


# ------------------------------------------------------------
# 3. LOAD AND VALIDATE THE PROJECT DATASET
# ------------------------------------------------------------
@st.cache_data
def load_clinical_data():

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {DATA_FILE.name}. "
            "Place clinical_dataset.csv in the same folder as app.py."
        )

    data = pd.read_csv(DATA_FILE)

    required_columns = [
        "Patient_ID",
        "Patient_Name",
        "Age",
        "Length_of_Stay",
        "Lab_Cost",
        "Medication_Count",
        "Comorbidity_Score",
    ]

    missing = [
        column for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            f"Dataset is missing required columns: {missing}"
        )

    # Exclude dummy patient names from the portal.
    data = data.drop(columns=["Patient_Name"]).copy()

    numeric_columns = [
        "Age",
        "Length_of_Stay",
        "Lab_Cost",
        "Medication_Count",
        "Comorbidity_Score",
    ]

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    data = data.dropna(
        subset=["Patient_ID"] + numeric_columns
    )

    data = data.drop_duplicates(
        subset=["Patient_ID"]
    ).reset_index(drop=True)

    if data.empty:
        raise ValueError(
            "The dataset has no valid patient records."
        )

    return data


try:
    df = load_clinical_data()

except Exception as error:
    st.error(f"Dataset loading failed: {error}")
    st.stop()


# ------------------------------------------------------------
# 4. CREATE ANALYTICAL CATEGORIES
# ------------------------------------------------------------
def create_mining_categories(data: pd.DataFrame) -> pd.DataFrame:

    categorized = data.copy()

    categorized["Age_Group"] = pd.cut(
        categorized["Age"],
        bins=[0, 39, 60, 120],
        labels=["Under 40", "40 to 60", "Over 60"],
        include_lowest=True
    ).astype(str)

    categorized["Stay_Category"] = pd.cut(
        categorized["Length_of_Stay"],
        bins=[0, 3, 7, np.inf],
        labels=["Short stay", "Moderate stay", "Long stay"],
        include_lowest=True
    ).astype(str)

    categorized["Lab_Cost_Category"] = pd.cut(
        categorized["Lab_Cost"],
        bins=[-np.inf, 999.99, 1999.99, np.inf],
        labels=["Low lab cost", "Medium lab cost", "High lab cost"]
    ).astype(str)

    categorized["Medication_Category"] = pd.cut(
        categorized["Medication_Count"],
        bins=[-np.inf, 2, 5, np.inf],
        labels=[
            "Few medications",
            "Moderate medications",
            "Many medications"
        ]
    ).astype(str)

    categorized["Comorbidity_Category"] = pd.cut(
        categorized["Comorbidity_Score"],
        bins=[-np.inf, 1, 3, np.inf],
        labels=[
            "Low comorbidity",
            "Moderate comorbidity",
            "High comorbidity"
        ]
    ).astype(str)

    return categorized


def calculate_pairwise_association_rules(
    data: pd.DataFrame
) -> pd.DataFrame:

    """
    Calculate actual pairwise association rules.

    Support = joint occurrence / total records
    Confidence = joint occurrence / antecedent occurrence
    Lift = confidence / consequent occurrence rate
    """

    category_columns = [
        "Age_Group",
        "Stay_Category",
        "Lab_Cost_Category",
        "Medication_Category",
        "Comorbidity_Category",
    ]

    total_records = len(data)
    rules = []

    for left_column, right_column in combinations(
        category_columns, 2
    ):

        cross_table = pd.crosstab(
            data[left_column],
            data[right_column]
        )

        left_counts = data[left_column].value_counts()
        right_counts = data[right_column].value_counts()

        for left_value in cross_table.index:

            for right_value in cross_table.columns:

                joint_count = int(
                    cross_table.loc[left_value, right_value]
                )

                if joint_count == 0:
                    continue

                left_count = int(left_counts[left_value])
                right_count = int(right_counts[right_value])

                support = joint_count / total_records

                confidence_left_to_right = (
                    joint_count / left_count
                )

                lift_left_to_right = (
                    confidence_left_to_right
                    / (right_count / total_records)
                )

                rules.append({
                    "Antecedent": (
                        f"{left_column} = {left_value}"
                    ),
                    "Consequent": (
                        f"{right_column} = {right_value}"
                    ),
                    "Records": joint_count,
                    "Support": support,
                    "Confidence": confidence_left_to_right,
                    "Lift": lift_left_to_right,
                })

                confidence_right_to_left = (
                    joint_count / right_count
                )

                lift_right_to_left = (
                    confidence_right_to_left
                    / (left_count / total_records)
                )

                rules.append({
                    "Antecedent": (
                        f"{right_column} = {right_value}"
                    ),
                    "Consequent": (
                        f"{left_column} = {left_value}"
                    ),
                    "Records": joint_count,
                    "Support": support,
                    "Confidence": confidence_right_to_left,
                    "Lift": lift_right_to_left,
                })

    result = pd.DataFrame(rules)

    if not result.empty:
        result = result.sort_values(
            ["Lift", "Confidence", "Support"],
            ascending=False
        ).reset_index(drop=True)

    return result


mining_df = create_mining_categories(df)

association_rules = calculate_pairwise_association_rules(
    mining_df
)


# ------------------------------------------------------------
# 5. ISOLATION FOREST ANOMALY DETECTION
# ------------------------------------------------------------
st.sidebar.markdown("## ⚙️ Mining Parameters")

contamination_rate = st.sidebar.slider(
    "Expected outlier proportion",
    min_value=0.01,
    max_value=0.20,
    value=0.01,
    step=0.01,
    help=(
        "This is a model setting, "
        "not a measured disease or fraud rate."
    )
)

model_features = [
    "Age",
    "Length_of_Stay",
    "Lab_Cost",
    "Medication_Count",
    "Comorbidity_Score",
]

scaler = StandardScaler()

scaled_features = scaler.fit_transform(
    df[model_features]
)

isolation_forest = IsolationForest(
    contamination=contamination_rate,
    random_state=42
)

predictions = isolation_forest.fit_predict(
    scaled_features
)

df["Anomaly_Score"] = (
    isolation_forest.decision_function(
        scaled_features
    )
)

df["Mining_Status"] = np.where(
    predictions == -1,
    "Flagged for review",
    "Within model pattern"
)


# ------------------------------------------------------------
# 6. APPLICATION HEADER AND DATASET OVERVIEW
# ------------------------------------------------------------
st.title(
    "🏥 Multi-Role Clinical Data Mining & Secure Access Portal"
)

st.write(
    "A classroom demonstration using synthetic Electronic Health "
    "Record data, Isolation Forest anomaly detection, and "
    "pairwise association analysis."
)

st.info(
    "Dataset notice: All records are synthetic and generated "
    "for academic demonstration. This application is not a "
    "clinical decision-support system and must not be used "
    "to diagnose, treat, or make decisions about real patients."
)

with st.expander("Dataset overview", expanded=False):

    overview_col1, overview_col2, overview_col3 = st.columns(3)

    overview_col1.metric(
        "Valid records",
        f"{len(df):,}"
    )

    overview_col2.metric(
        "Dataset attributes",
        "6 analytical fields + Patient ID"
    )

    overview_col3.metric(
        "Duplicate patient IDs removed",
        "See data-cleaning output"
    )

    st.write(
        "Fields used: Patient_ID, Age, Length_of_Stay, "
        "Lab_Cost, Medication_Count, and Comorbidity_Score."
    )

    st.write(
        "The dummy Patient_Name field is intentionally "
        "excluded from the portal."
    )


# ------------------------------------------------------------
# 7. SIDEBAR LOGIN AND REGISTRATION
# ------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("## 🔐 Portal Authentication")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


if st.session_state.logged_in:

    st.sidebar.success(
        f"Signed in: {st.session_state.username} "
        f"({st.session_state.role})"
    )

    if st.sidebar.button("Log out"):

        for key in [
            "logged_in",
            "username",
            "role",
            "assigned_doctor"
        ]:
            st.session_state.pop(key, None)

        st.rerun()


else:

    auth_mode = st.sidebar.radio(
        "Choose an action",
        ["Login", "Register"]
    )

    if auth_mode == "Login":

        username_input = st.sidebar.text_input(
            "Username"
        )

        password_input = st.sidebar.text_input(
            "Password",
            type="password"
        )

        if st.sidebar.button(
            "Login",
            use_container_width=True
        ):

            user_record = authenticate_user(
                username_input,
                password_input
            )

            if user_record:

                st.session_state.logged_in = True
                st.session_state.username = user_record[0]
                st.session_state.role = user_record[1]

                st.session_state.assigned_doctor = (
                    user_record[2] or "Not assigned"
                )

                st.rerun()

            else:
                st.sidebar.error(
                    "Invalid username or password."
                )

    else:

        new_username = st.sidebar.text_input(
            "Choose username"
        )

        new_password = st.sidebar.text_input(
            "Choose password",
            type="password"
        )

        new_role = st.sidebar.selectbox(
            "Choose role",
            ["Patient", "Doctor", "Analyst"]
        )

        new_doctor = st.sidebar.text_input(
            "Assigned doctor (patient demo accounts only)",
            value="Dr. Patil"
        )

        if st.sidebar.button(
            "Create account",
            use_container_width=True
        ):

            success, message = register_user(
                new_username,
                new_password,
                new_role,
                new_doctor
            )

            if success:
                st.sidebar.success(message)

            else:
                st.sidebar.error(message)


# ------------------------------------------------------------
# 8. ROLE-BASED PORTAL VIEWS
# ------------------------------------------------------------
if not st.session_state.logged_in:

    st.warning(
        "Log in using the sidebar to open the patient "
        "or analytics portal."
    )

    with st.expander("Demo login credentials"):

        st.markdown(
            """
            These are demonstration credentials for the
            local academic project.

            | Role | Username | Password |
            |---|---|---|
            | Patient | `patient_100` | `password123` |
            | Patient | `patient_101` | `password123` |
            | Doctor | `dr_patil` | `password123` |
            | Analyst | `analyst_user` | `password123` |
            """
        )


elif st.session_state.role == "Patient":

    username = st.session_state.username

    patient_number = int(
        username.removeprefix("patient_")
    )

    row_index = patient_number - 100

    st.subheader(
        f"👤 Patient Portal: {username}"
    )

    st.write(
        f"**Assigned doctor in demo account:** "
        f"{st.session_state.assigned_doctor}"
    )

    if row_index < 0 or row_index >= len(df):

        st.error(
            "No synthetic patient record is linked to this account."
        )

    else:

        patient_record = df.iloc[[row_index]].copy()

        st.caption(
            "This account is mapped to a synthetic row "
            "by its demo username. It is not a real patient identity."
        )

        patient_columns = [
            "Patient_ID",
            "Age",
            "Length_of_Stay",
            "Lab_Cost",
            "Medication_Count",
            "Comorbidity_Score",
            "Mining_Status",
        ]

        st.dataframe(
            patient_record[patient_columns],
            use_container_width=True,
            hide_index=True
        )

        st.metric(
            "Model anomaly score",
            f"{patient_record['Anomaly_Score'].iloc[0]:.4f}"
        )

        st.caption(
            "A flagged record means the model found an unusual "
            "combination of input values. It does not mean the "
            "patient has a disease or requires treatment."
        )


elif st.session_state.role in [
    "Doctor",
    "Analyst",
    "Administrator"
]:

    st.subheader(
        f"📊 Clinical Data Mining Dashboard — "
        f"{st.session_state.role} view"
    )

    total_records = len(df)

    flagged_records = int(
        (
            df["Mining_Status"] == "Flagged for review"
        ).sum()
    )

    average_lab_cost = df["Lab_Cost"].mean()
    average_stay = df["Length_of_Stay"].mean()

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Patient records",
        f"{total_records:,}"
    )

    metric2.metric(
        "Flagged records",
        f"{flagged_records:,}"
    )

    metric3.metric(
        "Average lab cost",
        f"₹{average_lab_cost:,.2f}"
    )

    metric4.metric(
        "Average length of stay",
        f"{average_stay:.2f} days"
    )

    # --------------------------------------------------------
    # DATASET SUMMARIES
    # --------------------------------------------------------
    st.markdown("### 📈 Dataset summaries")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:

        status_counts = df["Mining_Status"].value_counts()

        st.write("**Isolation Forest output**")

        st.bar_chart(status_counts)

    with chart_col2:

        st.write("**Average lab cost by age group**")

        cost_by_age = (
            mining_df.groupby(
                "Age_Group",
                observed=False
            )["Lab_Cost"].mean()
        )

        st.bar_chart(cost_by_age)

    # --------------------------------------------------------
    # FILTER AND INSPECT RECORDS
    # --------------------------------------------------------
    st.markdown(
        "### 🔎 Filter and inspect synthetic records"
    )

    status_filter = st.selectbox(
        "Filter by mining status",
        [
            "All records",
            "Flagged for review",
            "Within model pattern"
        ]
    )

    display_df = df.copy()

    if status_filter != "All records":

        display_df = display_df[
            display_df["Mining_Status"] == status_filter
        ]

    st.caption(
        f"Showing {len(display_df):,} records."
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    csv_bytes = display_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download displayed records as CSV",
        data=csv_bytes,
        file_name="healthcare_mining_analysis.csv",
        mime="text/csv"
    )

    # --------------------------------------------------------
    # ASSOCIATION RULE MINING
    # --------------------------------------------------------
    st.markdown("---")

    st.markdown(
        "### 🔗 Association Rule Mining — "
        "calculated from the dataset"
    )

    st.write(
        "The application calculates pairwise rules between "
        "categories derived from age, length of stay, lab cost, "
        "medication count, and comorbidity score. These are "
        "statistical associations, not causal or clinical conclusions."
    )

    rule_col1, rule_col2 = st.columns(2)

    with rule_col1:

        minimum_support = st.slider(
            "Minimum support",
            min_value=0.001,
            max_value=0.20,
            value=0.01,
            step=0.001,
            format="%.3f"
        )

    with rule_col2:

        minimum_confidence = st.slider(
            "Minimum confidence",
            min_value=0.05,
            max_value=1.00,
            value=0.30,
            step=0.05,
            format="%.2f"
        )

    filtered_rules = association_rules[
        (association_rules["Support"] >= minimum_support)
        & (
            association_rules["Confidence"]
            >= minimum_confidence
        )
    ].copy()

    if filtered_rules.empty:

        st.warning(
            "No rules meet the selected thresholds. "
            "Lower the minimum support or confidence "
            "to see more rules."
        )

    else:

        st.metric(
            "Rules meeting thresholds",
            len(filtered_rules)
        )

        formatted_rules = filtered_rules.head(30).copy()

        for column in [
            "Support",
            "Confidence",
            "Lift"
        ]:

            formatted_rules[column] = (
                formatted_rules[column].map(
                    lambda value: f"{value:.3f}"
                )
            )

        st.dataframe(
            formatted_rules,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Download calculated association rules",
            data=filtered_rules.to_csv(
                index=False
            ).encode("utf-8"),
            file_name="healthcare_association_rules.csv",
            mime="text/csv"
        )

        st.markdown(
            """
            **How to read the metrics**

            - **Support:** proportion of all records containing both categories.
            - **Confidence:** proportion of antecedent records that also contain the consequent.
            - **Lift:** how much more often the two categories occur together than expected
              if they were independent. A lift above 1 indicates a positive association
              in this dataset.
            """
        )


else:

    st.error(
        "This account has an unsupported role. "
        "Contact the project administrator."
    )


# ------------------------------------------------------------
# 9. FOOTER AND PROJECT LIMITATIONS
# ------------------------------------------------------------
st.markdown("---")

st.caption(
    "Academic prototype only • Synthetic data • "
    "Isolation Forest anomaly detection • "
    "Pairwise association-rule analysis"
)

st.caption(
    "Security note: SHA-256 password hashing and the included "
    "demo accounts are for local classroom demonstration only. "
    "Do not deploy this authentication setup with real patient "
    "information or on a public production server."
)
