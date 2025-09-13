import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from gspread_dataframe import set_with_dataframe


CASHIERS = sorted(["Misrak", "Emush", "Adanu", "Yemisrach", "Ejigayehu", "Tigist"])
BANKS = sorted([
    "Abay", "Amhara", "Awash", "Bank of Abyssinia", "Bunna",
    "CBE", "Dashen", "Enat", "Hibret", "Lion", "Nib", "Telebirr", "Wegagen", "Zemen"
])
HEADERS = ["ID", "Timestamp", "Cashier", "Bank", "Credit"]

GOOGLE_SHEET_NAME = "Cred_entry"


def connect_to_gsheet():
    try:
        
        sa = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
       
        sh = sa.open(GOOGLE_SHEET_NAME)
        
        ws = sh.get_worksheet(0)
        return ws
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        st.stop()


def load_data_from_gsheet(ws):
    """Loads all data from the worksheet into a pandas DataFrame."""
    try:
        df = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return pd.DataFrame(columns=HEADERS)
       
        if 'ID' in df.columns:
            df['ID'] = df['ID'].astype(str)
        return df
    except Exception as e:
        st.error(f"Failed to load data from Google Sheet: {e}")
        return pd.DataFrame(columns=HEADERS)

def get_next_id(df):
   
    if df.empty or 'ID' not in df.columns:
        return 1
    
    max_id = pd.to_numeric(df['ID'], errors='coerce').max()
    return int(max_id) + 1 if pd.notna(max_id) else 1

def save_entry(ws, df, entry):
    
    try:
        entry_id = get_next_id(df)
        entry["ID"] = entry_id
        
        
        data_row = [entry.get(h, "") for h in HEADERS]
        
       
        ws.append_row(data_row, value_input_option='USER_ENTERED')
        
        st.success(f"Saved: ID {entry_id} | {entry['Bank']} - {entry['Credit']:,.2f}")
        return True
    except Exception as e:
        st.error(f"Failed to save entry: {e}")
        return False

def remove_entry_from_gsheet(ws, entry_id):
    
    try:
       
        cell = ws.find(str(entry_id), in_column=1) 
        if cell:
            
            ws.delete_rows(cell.row)
            return True, f"Entry ID {entry_id} deleted successfully."
        else:
            return False, f"Could not find entry ID {entry_id}."
    except Exception as e:
        return False, f"An error occurred while deleting: {e}"

# --- UI PAGES ---
def cashier_selection_page():
    
    st.header("Select Cashier to Continue")
    cols = st.columns(2)
    for i, cashier in enumerate(CASHIERS):
        with cols[i % 2]:
            if st.button(cashier, key=f"cashier_{cashier}", use_container_width=True):
                st.session_state.selected_cashier = cashier
                st.rerun()

def main_app_page(ws):
    
    st.markdown("""
        <style>
            .main .block-container { padding-top: 2rem; }
            .bank-buttons .stButton button { font-size: 1.2rem; font-weight: bold; height: 50px; }
        </style>
    """, unsafe_allow_html=True)

    cashier = st.session_state.selected_cashier

    
    top_col1, top_col2 = st.columns([1, 4])
    with top_col1:
        if st.button("⬅️ Change Cashier"):
            del st.session_state.selected_cashier
            if 'selected_bank' in st.session_state:
                del st.session_state.selected_bank
            st.rerun()
    with top_col2:
        st.markdown(f"## Welcome, **{cashier}**!")

    if 'selected_bank' not in st.session_state:
        st.session_state.selected_bank = None

    
    col1, col2 = st.columns([1.5, 2])

    with col1:
        
        st.subheader("1. Select a Bank")
        st.markdown('<div class="bank-buttons">', unsafe_allow_html=True)
        bank_cols = st.columns(3)
        for i, bank in enumerate(BANKS):
            col = bank_cols[i % 3]
            is_selected = (bank == st.session_state.selected_bank)
            button_type = "primary" if is_selected else "secondary"
            if col.button(bank, key=f"bank_{bank}", use_container_width=True, type=button_type):
                st.session_state.selected_bank = bank
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        
        st.subheader("2. Enter Amount & Submit")
        with st.form("entry_form", clear_on_submit=True):
            credit = st.number_input("Enter Credit Amount", min_value=0.01, format="%.2f", value=None)
            submitted = st.form_submit_button("Submit Entry", use_container_width=True)
            if submitted:
                bank = st.session_state.get("selected_bank")
                if not bank:
                    st.warning("Please select a bank.")
                elif credit is None:
                    st.warning("Please enter a credit amount.")
                else:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    entry_data = {"Timestamp": timestamp, "Bank": bank, "Credit": credit, "Cashier": cashier}
                    
                    df_for_id = load_data_from_gsheet(ws)
                    if save_entry(ws, df_for_id, entry_data):
                       
                        pass

    with col2:
        st.subheader("Entries Log")
        
        
        df = load_data_from_gsheet(ws)

       
        search_query = st.text_input("Search Entries", placeholder="Search by any column...")
        if search_query:
            mask = df.apply(lambda row: search_query.lower() in ' '.join(row.astype(str)).lower(), axis=1)
            filtered_df = df[mask]
        else:
            filtered_df = df
        
        display_df = filtered_df.sort_values(by="ID", ascending=False).reset_index(drop=True)

        st.dataframe(
            display_df, use_container_width=True, hide_index=True,
            key="entries_df", on_select="rerun", selection_mode="single-row"
        )
        
        
        st.markdown("---")
        st.subheader("Delete an Entry")
        st.write("Click a row in the table above to select it.")
        
        try:
            selection = st.session_state.entries_df["selection"]["rows"]
            if selection:
                selected_row_index = selection[0]
                selected_id = display_df.iloc[selected_row_index]["ID"]
                
                st.warning(f"You have selected Entry ID **{selected_id}** for deletion.")
                if st.button(f"Confirm Deletion of ID {selected_id}", type="primary", use_container_width=True):
                    success, message = remove_entry_from_gsheet(ws, selected_id)
                    if success:
                        st.success(message)
                        st.rerun() 
                    else:
                        st.error(message)
            else:
                st.info("No entry selected.")
        except (KeyError, IndexError):
             st.info("No entry selected.")

    
    st.markdown("---")
    _, end_session_col = st.columns([4, 1])
    with end_session_col:
        if st.button("🚪 Log Out"):
            st.session_state.clear()
            st.success("You have been logged out. Select a cashier to begin a new session.")
            st.rerun()



if __name__ == "__main__":
    st.set_page_config(page_title="Credit Entry", layout="wide")

   
    worksheet = connect_to_gsheet()

    if 'selected_cashier' not in st.session_state:
        cashier_selection_page()
    else:
        main_app_page(worksheet)