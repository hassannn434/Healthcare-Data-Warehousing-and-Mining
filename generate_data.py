import pandas as pd
import numpy as np

# Set seed for reproducible large-scale data generation
np.random.seed(42)
n_samples = 30000

print(f"Generating synthetic Electronic Health Records (EHR) for {n_samples} patients...")

data = {
    'Patient_ID': [f"PID-{100000+i}" for i in range(n_samples)],
    'Patient_Name': [f"Dummy_Name_{i}" for i in range(n_samples)], # Raw PII to be scrubbed
    'Age': np.random.randint(18, 90, size=n_samples),
    'Length_of_Stay': np.random.exponential(scale=4, size=n_samples).astype(int) + 1,
    'Lab_Cost': np.random.normal(loc=1200, scale=300, size=n_samples).round(2),
    'Medication_Count': np.random.poisson(lam=3, size=n_samples),
    'Comorbidity_Score': np.random.randint(0, 5, size=n_samples)
}
df = pd.DataFrame(data)

# Injecting intentional high-cost/long-stay billing outliers across 300 random rows
outlier_indices = np.random.choice(n_samples, size=300, replace=False)
df.loc[outlier_indices, 'Lab_Cost'] = np.random.uniform(8000, 15000, size=300).round(2)
df.loc[outlier_indices, 'Length_of_Stay'] = np.random.randint(20, 45, size=300)

# Save to CSV
df.to_csv('clinical_dataset.csv', index=False)
print("Success! Updated 'clinical_dataset.csv' with 30,000 rows.")