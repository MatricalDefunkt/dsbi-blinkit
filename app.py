import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import joblib # <-- Import joblib
import numpy as np # <-- Import numpy if not already imported
import os # <-- Import os to check file existence

# ----- CONFIG & CONSTANTS -----
DB_NAME = "sqlite.db"
MODEL_FILENAME = 'random_forest_sales_model.joblib'

# !!! IMPORTANT: Use the exact feature names (with spaces) the model was trained on !!!
# Example list - REPLACE with your actual FEATURES list from the training script
FEATURES = [
    'Item Weight', 'Item Fat Content', 'Item Visibility', 'Item Type',
    'Rating', 'Outlet Size', 'Outlet Location Type', 'Outlet Type', 'Outlet Age'
]
# Identify which features are categorical and numerical based on your training script
# Example lists - REPLACE with your actual lists
CATEGORICAL_FEATURES = [
    'Item Fat Content', 'Item Type', 'Outlet Size',
    'Outlet Location Type', 'Outlet Type'
]
NUMERICAL_FEATURES = [
    'Item Weight', 'Item Visibility', 'Rating', 'Outlet Age'
]
# Feature requiring special handling (input year -> calculate age)
YEAR_FEATURE = 'Outlet Establishment Year' # Original name needed for input
AGE_FEATURE = 'Outlet Age' # Name the model expects


# ----- DB SETUP -----
# (Keep your existing DB setup code)
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

# Create user table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL
)
""")
conn.commit()

# ----- PASSWORD UTILS -----
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed


# ----- AUTH SYSTEM -----
def sign_up(username, password):
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Username already exists

def login(username, password):
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row and verify_password(password, row[0]):
        return True
    return False

# ----- SESSION -----
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None


# ----- MODEL LOADING & UTILS -----

# Load the original data once to get unique values for dropdowns
# In a real app, you might save these unique values separately
@st.cache_data
def load_original_data(file_path='blinkit_grocery_data_orignal.xlsx'):
    try:
        df_orig = pd.read_excel(file_path)
        df_orig.columns = df_orig.columns.str.strip()
        print(df_orig.columns)
        # Apply necessary cleaning like fat content standardization
        df_orig['Item Fat Content'] = df_orig['Item Fat Content'].replace({
            'LF': 'Low Fat', 'low fat': 'Low Fat', 'reg': 'Regular'
        })
        return df_orig
    except FileNotFoundError:
        st.error(f"Original data file '{file_path}' not found for getting dropdown options.")
        return None

original_df = load_original_data()

# Create a dictionary of unique values for categorical features
unique_values = {}
if original_df is not None:
    for col in CATEGORICAL_FEATURES:
        if col in original_df.columns:
            # Handle potential NaN values before getting unique list
             unique_values[col] = sorted([str(x) for x in original_df[col].dropna().unique()])
        else:
             st.warning(f"Categorical feature '{col}' not found in original data for dropdown options.")


@st.cache_resource # Cache the loaded model resource
def load_model(model_path):
    """Loads the saved joblib model pipeline."""
    if not os.path.exists(model_path):
        st.error(f"Model file not found at {model_path}")
        return None
    try:
        model = joblib.load(model_path)
        print("Model loaded successfully.") # Add print statement for debugging
        return model
    except Exception as e:
        st.error(f"Error loading model: {e}")
        return None

# ----- LOGIN / SIGNUP PAGE -----
def login_signup_ui():
    st.title("Login / Sign Up")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    # ... (rest of your login/signup code) ...
    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Welcome back, {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab2:
        new_username = st.text_input("New Username", key="signup_user")
        new_password = st.text_input("New Password", type="password", key="signup_pass")
        if st.button("Sign Up"):
            if sign_up(new_username, new_password):
                st.success("Account created! You can now log in.")
                # Optionally log them in directly after signup
                st.session_state.logged_in = True
                st.session_state.username = new_username
                st.rerun()
            else:
                st.error("Username already taken.")


# ----- MAIN APP -----
def main_app():
    st.title(f"Welcome, {st.session_state.username} 👋")

    # --- Load Model ---
    model_pipeline = load_model(MODEL_FILENAME)

    st.sidebar.header("Navigation")
    app_mode = st.sidebar.radio("Choose Section", ["View Data", "Predict Sales"])

    if app_mode == "View Data":
        st.header("View Database Tables")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        # Filter out internal sqlite tables and the users table
        tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_') and row[0] != 'users']

        if not tables:
            st.warning("No user tables found in the database.")
        else:
            selected_table = st.selectbox("Choose a table to view", tables)
            if selected_table:
                try:
                    df_view = pd.read_sql_query(f"SELECT * FROM {selected_table}", conn)
                    st.dataframe(df_view)
                except Exception as e:
                    st.error(f"Could not read table '{selected_table}': {e}")

    elif app_mode == "Predict Sales":
        st.header("Predict Item Sales")

        if model_pipeline is None:
            st.error("Prediction model could not be loaded. Cannot proceed.")
            return # Stop execution if model isn't loaded

        st.write("Enter the details for the item and outlet:")

        input_data = {}
        form_valid = True # Flag to check if all inputs are provided

        # Create columns for layout if desired (optional)
        # col1, col2 = st.columns(2)

        # --- Input Widgets ---
        # Use a loop or list explicitly like below
        # Need to handle 'Outlet Establishment Year' separately for age calculation

        current_input_year = None

        with st.form("prediction_form"):
            # --- Numerical Inputs ---
            for feature in NUMERICAL_FEATURES:
                 if feature == AGE_FEATURE: # Skip age, we'll calculate it
                     continue
                 # Example: Define reasonable min/max/step, refine as needed
                 min_val = 0.0
                 max_val = None
                 step = 0.01 if feature in ['Item Visibility', 'Rating'] else 1.0 if feature == 'Item Weight' else None # Adjust step
                 default_val = 0.0 # Or use median from training data if available

                 input_data[feature] = st.number_input(
                     label=f"Enter {feature}",
                     min_value=min_val,
                     max_value=max_val,
                     step=step,
                     value=default_val,
                     key=f"input_{feature}"
                 )

            # --- Outlet Establishment Year Input ---
            current_input_year = st.number_input(
                label=f"Enter {YEAR_FEATURE}",
                min_value=1950, # Example range
                max_value=pd.Timestamp.now().year,
                step=1,
                value = 2000, # Example default
                key=f"input_{YEAR_FEATURE}"
             )

            # --- Categorical Inputs ---
            for feature in CATEGORICAL_FEATURES:
                 options = unique_values.get(feature, [])
                 if not options:
                     st.warning(f"No options found for '{feature}'. Using text input.")
                     input_data[feature] = st.text_input(label=f"Enter {feature}", key=f"input_{feature}")
                 else:
                     # Ensure the default index is valid
                     default_index = 0 # Select first option by default
                     input_data[feature] = st.selectbox(
                         label=f"Select {feature}",
                         options=options,
                         index=default_index,
                         key=f"input_{feature}"
                     )
                 # Basic check if input is provided (might need refinement for numerical)
                 if not input_data[feature]:
                     form_valid = False

            # --- Form Submit Button ---
            submitted = st.form_submit_button("Predict Sales")

            if submitted:
                if not form_valid:
                    st.warning("Please fill in all required fields.")
                else:
                    # --- Prepare Data for Prediction ---
                    try:
                         # Calculate Outlet Age
                         current_year = pd.Timestamp.now().year
                         input_data[AGE_FEATURE] = current_year - current_input_year

                         # Create DataFrame with the exact feature order/names model expects
                         input_df = pd.DataFrame([input_data], columns=FEATURES)

                         st.write("Input Data for Model:")
                         st.dataframe(input_df)

                         # --- Make Prediction ---
                         prediction = model_pipeline.predict(input_df)

                         st.success(f"Predicted Sales: ${prediction[0]:,.2f}") # Format prediction

                    except Exception as e:
                        st.error(f"An error occurred during prediction: {e}")
                        # Optionally print input_data or input_df for debugging
                        # st.write("Debug Info - Input Data Dict:", input_data)
                        # if 'input_df' in locals(): st.write("Debug Info - Input DataFrame:", input_df)


    # --- Logout Button common to all modes ---
    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        # Clear relevant session state keys
        for key in ['logged_in', 'username']:
            if key in st.session_state:
                del st.session_state[key]
        # Set logged_in to False explicitly after deletion
        st.session_state.logged_in = False
        st.rerun()

# ----- RENDER -----
if st.session_state.get('logged_in', False): # Use .get for safety
    main_app()
else:
    login_signup_ui()

# Close DB connection when Streamlit script stops (optional, Streamlit manages processes)
# conn.close()