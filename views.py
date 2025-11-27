import streamlit as st
import pandas as pd
import time
import io
import plotly.express as px
from datetime import datetime
import config
import qrcode
import cv2
import numpy as np
from pyzbar.pyzbar import decode

# --- HELPER: QR CODE GENERATOR ---
def generate_qr(data):
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

# --- COMPONENT: ASSET DETAILS POPUP ---
@st.dialog("Asset Details")
def show_asset_dialog(asset, user_scope, db):
    """
    Displays asset details, lifecycle actions, history, and financial data.
    """
    # Asset Tuple Mapping based on database.py:
    # 0:ID, 1:Type, 2:Make, 3:Model, 4:Serial, 5:Stock, 6:ITEC, 7:Price, 
    # 8:Build, 9:Room, 10:Class, 11:Rack, 12:Row, 13:Table, 14:Assigned, 
    # 15:Tags, 16:Added, 17:Mod, 18:Scanned
    
    # Header
    st.header(f"{asset[2]} {asset[3]}") 
    st.caption(f"Serial: {asset[4]} | ID: {asset[0]}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Type:** {asset[1]}")
        st.write(f"**Location:** {asset[8]} / Rm {asset[9]}")
        st.write(f"**Stock #:** {asset[5]}")
        st.write(f"**ITEC:** {asset[6]}")
    with col2:
        # Highlight Status
        status = asset[14] if asset[14] and asset[14] != "Available" else "Available"
        if status == "Available":
            st.success(f"**Status:** {status}")
        else:
            st.warning(f"**Assigned To:** {status}")
            
        st.write(f"**Price:** ${asset[7]}")
        st.write(f"**Classification:** {asset[10]}")
        st.write(f"**Tags:** {asset[15]}")

    st.divider()

    # --- 1. FINANCIAL LIFECYCLE (ROBUST VERSION) ---
    st.subheader("Financial Lifecycle")
    
    # Sanitize Price (Remove '$' and ',') to handle imported string data
    raw_price = str(asset[7]) if asset[7] is not None else "0"
    clean_price_str = raw_price.replace('$', '').replace(',', '').strip()
    
    try:
        purchase_price = float(clean_price_str)
    except ValueError:
        purchase_price = 0.0

    # Check Data Validity
    has_price = purchase_price > 0
    has_date = asset[16] is not None and asset[16] != ""
    
    if has_price and has_date:
        try:
            # Parse Date
            purchase_date = pd.to_datetime(asset[16])
            if pd.isna(purchase_date):
                raise ValueError("Invalid Date")

            useful_life_years = 5
            
            # Generate Depreciation Curve
            dates = [purchase_date + pd.DateOffset(years=i) for i in range(useful_life_years + 1)]
            values = [max(0, purchase_price - (purchase_price/useful_life_years * i)) for i in range(useful_life_years + 1)]
            
            dep_df = pd.DataFrame({"Date": dates, "Value": values})
            
            # Draw Chart
            with st.expander("📉 View Depreciation Curve", expanded=True):
                fig_dep = px.line(dep_df, x="Date", y="Value", markers=True, title=f"5-Year Depreciation")
                fig_dep.update_traces(line_color='#3498db', line_width=3)
                fig_dep.add_vline(x=datetime.now(), line_dash="dash", line_color="red", annotation_text="Today")
                st.plotly_chart(fig_dep, use_container_width=True)
                
                # Current Value Calculation
                months_passed = (datetime.now() - purchase_date).days / 30
                current_value = max(0, purchase_price * (1 - (months_passed / 60)))
                st.caption(f"Original: **${purchase_price:,.2f}** → Current: **${current_value:,.2f}**")

        except Exception as e:
            st.error(f"Chart Error: {e}")
    else:
        # FEEDBACK: Tell the user EXACTLY what is missing
        if not has_price:
            st.warning(f"⚠️ Price is detected as ${purchase_price}. Please Edit and enter a valid number (e.g. 1000).")
        elif not has_date:
            st.warning("⚠️ 'Date Added' is missing. Edit the asset and click Save to fix timestamp.")

    # --- 2. CUSTODY ACTIONS (CHECK IN/OUT) ---
    if user_scope != config.SCOPE_READ_ONLY:
        st.subheader("Custody Actions")
        
        current_assignee = asset[14]
        is_assigned = current_assignee and current_assignee != "Available"

        if is_assigned:
            if st.button("📥 Check In Asset", type="primary", use_container_width=True, key=f"in_{asset[0]}"):
                db.add_transaction(asset[0], st.session_state.username, "CHECKIN")
                st.success("Asset Checked In!")
                time.sleep(1)
                st.rerun()
        else:
            c_input, c_btn = st.columns([3, 1])
            new_assignee = c_input.text_input("Assign to (Name/ID)", placeholder="e.g. John Doe", key=f"assign_input_{asset[0]}")
            if c_btn.button("📤 Check Out", type="primary", key=f"out_{asset[0]}"):
                if new_assignee:
                    db.add_transaction(asset[0], st.session_state.username, "CHECKOUT", assignee=new_assignee)
                    st.success(f"Checked out to {new_assignee}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Enter a name.")
    
    st.divider()

    # --- 3. ASSET HISTORY ---
    with st.expander("📜 Asset History"):
        history = db.get_asset_history(asset[0])
        if history:
            st.dataframe(pd.DataFrame(history), hide_index=True, use_container_width=True)
        else:
            st.info("No transaction history found.")

    st.markdown("---")

    # --- 4. QR CODE & ADMIN ACTIONS ---
    # QR Code
    img = generate_qr(asset[4])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    byte_im = buf.getvalue()
    
    c_qr1, c_qr2 = st.columns([1, 3])
    c_qr1.image(byte_im, width=100)
    c_qr2.download_button(
        label="⬇ Download QR Code", 
        data=byte_im, 
        file_name=f"QR_{asset[4]}.png", 
        mime="image/png"
    )

    # Edit / Delete
    if user_scope != config.SCOPE_READ_ONLY:
        st.subheader("Admin Actions")
        
        c_edit, c_del = st.columns(2)
        
        # DELETE BUTTON
        if c_del.button("🗑️ Delete Asset", key=f"del_{asset[0]}", type="primary"):
            db.delete_asset(asset[0])
            st.rerun()

        # EDIT BUTTON (Popover)
        with c_edit.popover("✏️ Edit Details", use_container_width=True):
            st.write("**Edit Asset Information**")
            with st.form(f"edit_form_{asset[0]}"):
                
                ec1, ec2 = st.columns(2)
                e_build = ec1.text_input("Building", value=asset[8])
                e_room = ec2.text_input("Room", value=asset[9])
                
                # --- NEW EDIT FIELD: CLASSIFICATION ---
                levels = ["Unclassified", "Internal", "Confidential", "Secret", "Top Secret"]
                # Safe fallback if current class is not in list
                current_class = asset[10] if asset[10] in levels else levels[0]
                e_class = st.selectbox("Classification Level", levels, index=levels.index(current_class))
                
                ec3, ec4, ec5 = st.columns(3)
                e_rack = ec3.text_input("Rack", value=asset[11])
                e_row = ec4.text_input("Row", value=asset[12])
                e_table = ec5.text_input("Table", value=asset[13])

                e_price = st.number_input("Price", value=float(clean_price_str))
                e_tags = st.text_input("Tags", value=asset[15])
                
                if st.form_submit_button("Save Changes"):
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # UPDATE THE TUPLE
                    update_data = (
                        asset[1], asset[2], asset[3], asset[4], asset[5], 
                        asset[6], e_price, e_build, e_room, e_class,    # <--- e_class updated here
                        e_rack, e_row, e_table, asset[14], e_tags,        
                        now                                               
                    )
                    
                    if db.update_asset(asset[0], update_data):
                        st.success("Updated!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Update failed.")


# --- VIEW 1: DASHBOARD (Command Center) ---
def show_dashboard(db, user_scope):
    st.title("📊 Command Center")

    # 1. High-Level Metrics
    total, value, types = db.get_stats()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Assets", total, delta="Active Units")
    c2.metric("Portfolio Value", f"${value:,.2f}", delta="USD")
    c3.metric("Categories", types, delta="Device Types")
    
    # Calculate "Assets Added This Month"
    assets = db.get_all_assets() 
    if assets:
        df = pd.DataFrame(assets, columns=config.ASSET_COLUMNS)
        # Ensure date column is datetime
        df['Date Added'] = pd.to_datetime(df['Date Added'], errors='coerce')
        
        current_month = datetime.now().month
        current_year = datetime.now().year
        # Filter logic
        new_this_month = len(df[(df['Date Added'].dt.month == current_month) & (df['Date Added'].dt.year == current_year)])
        c4.metric("New (This Month)", new_this_month, delta="Velocity")
    else:
        c4.metric("New (This Month)", 0)

    st.markdown("---")

    # 2. Advanced Analytics Layer
    if assets and not df.empty:
        t1, t2 = st.tabs(["📈 Intelligence", "📋 Operational Data"])
        
        with t1:
            row1_1, row1_2 = st.columns([2, 1])
            
            with row1_1:
                st.subheader("Asset Distribution Map")
                # Sunburst: Hierarchical view of Building -> Room -> Type
                # Handle missing/empty values for cleaner charts
                df_chart = df.fillna("Unknown")
                fig_sun = px.sunburst(
                    df_chart, 
                    path=['Building', 'Room', 'Type'], 
                    values='Price',
                    color='Price',
                    color_continuous_scale='Blues',
                    title="Value Concentration by Location"
                )
                fig_sun.update_layout(height=500)
                st.plotly_chart(fig_sun, use_container_width=True)

            with row1_2:
                st.subheader("Recent Activity")
                fig_hist = px.histogram(
                    df, 
                    x="Date Added", 
                    y="Price",
                    title="Acquisition Timeline",
                    template="simple_white"
                )
                st.plotly_chart(fig_hist, use_container_width=True)
                st.info("💡 **Insight:** Larger segments in the Sunburst chart represent high-value locations.")

        with t2:
            # 3. Search & Filter
            col_search, col_filter = st.columns([3, 1])
            search_term = col_search.text_input("🔍 Search Database", placeholder="Serial, Model, User...")
            unique_tags = ["All"] + db.get_unique_tags()
            tag_filter = col_filter.selectbox("Tag Filter", unique_tags)

            # Re-fetch filtered data
            filtered_assets = db.get_all_assets(
                tag_filter if tag_filter != "All" else None, 
                search_term if search_term else None
            )
            
            if filtered_assets:
                df_filtered = pd.DataFrame(filtered_assets, columns=config.ASSET_COLUMNS)
                
                event = st.dataframe(
                    df_filtered,
                    on_select="rerun",
                    selection_mode="single-row",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Price": st.column_config.NumberColumn(format="$%.2f"),
                        "ID": None,
                        "Last Modified": None,
                        "Tags": st.column_config.TextColumn(width="small"),
                        "Serial": st.column_config.TextColumn(width="medium"),
                    }
                )

                # Handle Click Event
                if len(event.selection.rows) > 0:
                    selected_index = event.selection.rows[0]
                    selected_asset_id = df_filtered.iloc[selected_index]["ID"]
                    selected_asset = next((a for a in filtered_assets if a[0] == selected_asset_id), None)
                    if selected_asset:
                        show_asset_dialog(selected_asset, user_scope, db)
            else:
                st.warning("No assets match your search.")
    else:
        st.info("No assets in database.")


# --- VIEW 2: ADD ASSET ---
def show_add_asset(db, user_scope):
    st.title("➕ Add New Asset")

    if user_scope == config.SCOPE_READ_ONLY:
        st.error("You have Read Only access. You cannot add assets.")
        return

    # Tabs for Manual vs CSV
    tab1, tab2 = st.tabs(["📝 Manual Entry", "📂 Bulk Import (CSV)"])

    # --- TAB 1: MANUAL ENTRY ---
    with tab1:
        st.subheader("Device Identity")
        c1, c2 = st.columns(2)
        
        # Dynamic Device Type
        default_types = ["Laptop", "Monitor", "Server", "Printer", "Other"]
        db_types = [t for t in db.get_existing_types() if t not in default_types]
        all_options = default_types[:-1] + db_types + ["Other"]
        
        selected_type = c1.selectbox("Device Type", all_options)
        
        is_other = (selected_type == "Other")
        custom_type_name = c1.text_input(
            "Device Type Name (Required if 'Other')", 
            disabled=not is_other,
            placeholder="e.g. Drone, VR Headset..." if is_other else "Select 'Other' to enable"
        )

        make = c2.text_input("Make *")
        model = c1.text_input("Model *")
        serial = c2.text_input("Serial Number *")
        stock_num = c1.text_input("Stock Number")
        itec = c2.text_input("ITEC Account")
        
        st.subheader("Location & Details")
        c3, c4 = st.columns(2)
        building = c3.text_input("Building *")
        room = c4.text_input("Room *")
        
        # --- NEW CLASSIFICATION FIELD ---
        c_class, c_assign = st.columns(2)
        classification = c_class.selectbox("Classification Level", ["Unclassified", "Internal", "Confidential", "Secret", "Top Secret"])
        assigned = c_assign.text_input("Initial Assignment")
        
        c_rack, c_row, c_table = st.columns(3)
        rack = c_rack.text_input("Rack")
        row_loc = c_row.text_input("Row")
        table_num = c_table.text_input("Table #")
        
        price = st.number_input("AQS Price", min_value=0.0, step=10.0)
        
        st.write("Tags")
        existing_tags = db.get_unique_tags()
        selected_tags = st.multiselect("Select existing tags", existing_tags)
        new_tag = st.text_input("Or create a new tag")
        
        if st.button("Save Asset", type="primary"):
            # Determine Type
            final_type = selected_type
            if is_other:
                if not custom_type_name.strip():
                    st.error("Please specify the Device Type Name.")
                    return 
                final_type = custom_type_name

            # Validate
            if not (make and model and serial and building and room):
                st.error("Please fill in all Required (*) fields.")
            else:
                # Process Tags
                final_tags = selected_tags
                if new_tag: final_tags.append(new_tag)
                tag_string = ", ".join(final_tags)

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Create Asset
                data = (
                    final_type, make, model, serial, stock_num, 
                    itec, price, building, room, classification, # <--- Added Classification
                    rack, row_loc, table_num, assigned, tag_string, 
                    now, now, "Never"
                )
                
                asset_id = db.add_asset(data)
                if asset_id:
                    # If initially assigned, log the transaction automatically
                    if assigned:
                        db.add_transaction(asset_id, st.session_state.username, "CREATE_ASSIGN", assignee=assigned)
                    
                    st.success(f"Asset '{make} {model}' saved!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Error: Serial Number likely already exists.")

    # --- TAB 2: CSV IMPORT ---
    with tab2:
        st.subheader("Upload CSV File")
        st.info("CSV Columns needed: 'Make', 'Model', 'Serial', 'Building', 'Room'. Optional: 'Type', 'Price', 'Assigned'.")
        
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        
        if uploaded_file:
            if st.button("Start Import"):
                try:
                    df_import = pd.read_csv(uploaded_file)
                    df_import.columns = [c.strip().lower() for c in df_import.columns]
                    
                    success_count = 0
                    errors = []

                    for _, row in df_import.iterrows():
                        if 'serial' not in row or pd.isna(row['serial']):
                            continue
                        
                        r_type = row.get('type', 'Unknown')
                        r_make = row.get('make', 'Generic')
                        r_model = row.get('model', 'Generic')
                        r_serial = str(row['serial'])
                        r_build = row.get('building', 'Main')
                        r_room = row.get('room', '000')
                        r_price = row.get('price', 0.0)
                        r_assign = row.get('assigned', '')
                        
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        data = (
                            r_type, r_make, r_model, r_serial, "", 
                            "", r_price, r_build, r_room, "Imported", 
                            "", "", "", r_assign, "Imported", 
                            now, now, "Never"
                        )
                        
                        if db.add_asset(data):
                            success_count += 1
                        else:
                            errors.append(r_serial)
                    
                    st.success(f"Successfully imported {success_count} assets.")
                    if errors:
                        st.warning(f"Skipped {len(errors)} duplicates.")
                
                except Exception as e:
                    st.error(f"Error processing CSV: {e}")


# --- VIEW 3: INVENTORY (Hybrid Scanner) ---
def show_inventory(db, user_scope):
    st.title("📋 Inventory Scanner")
    
    if user_scope == config.SCOPE_READ_ONLY:
        st.warning("Read Only mode. Scans will not be saved to database history (Session only).")

    if 'scanned_serials' not in st.session_state:
        st.session_state.scanned_serials = [] 

    # --- INPUT SELECTION ---
    tab_gun, tab_cam = st.tabs(["🔫 Handheld Scanner (Primary)", "📷 Mobile Camera"])
    
    serial_to_process = None

    # --- OPTION A: USB HANDHELD SCANNER ---
    with tab_gun:
        st.caption("Keep this tab open for high-speed USB scanning.")
        usb_input = st.text_input(
            "Scan Barcode / Serial Number", 
            key="usb_scan_input",
            placeholder="Click here and scan...",
            help="Ensure this input box is focused before using the gun."
        )
        
        if usb_input:
            serial_to_process = usb_input

    # --- OPTION B: DEVICE CAMERA ---
    with tab_cam:
        st.caption("Use your device camera to scan QR Codes or Barcodes.")
        img_buffer = st.camera_input("Take a picture of the asset tag")
        
        if img_buffer:
            try:
                # Convert the buffer to an OpenCV image
                bytes_data = img_buffer.getvalue()
                cv_image = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
                
                # Decode
                decoded_objects = decode(cv_image)
                
                if decoded_objects:
                    # Take the first code found
                    detected_serial = decoded_objects[0].data.decode("utf-8")
                    st.success(f"Detected: {detected_serial}")
                    serial_to_process = detected_serial
                else:
                    st.error("Could not read barcode. Please try moving closer or steadying the camera.")
            except Exception as e:
                st.error(f"Error processing image: {e}")

    st.divider()

    # --- UNIFIED PROCESSING LOGIC ---
    if serial_to_process:
        asset = db.get_asset_by_serial(serial_to_process)
        
        if asset:
            # Update 'Last Scanned' if not Read Only
            if user_scope != config.SCOPE_READ_ONLY:
                db.update_scan_time(serial_to_process)
            
            # Add to Session Log
            if serial_to_process not in [x[0] for x in st.session_state.scanned_serials]:
                st.session_state.scanned_serials.insert(0, (serial_to_process, f"{asset[2]} {asset[3]}", "Verified"))
            
            st.success(f"✅ VERIFIED: {asset[2]} {asset[3]} (ID: {asset[0]})")
            
        else:
            if serial_to_process not in [x[0] for x in st.session_state.scanned_serials]:
                st.session_state.scanned_serials.insert(0, (serial_to_process, "Unknown Asset", "Missing in DB"))
            
            st.error(f"❌ UNKNOWN: {serial_to_process}")

    # Reports
    st.subheader("Inventory Session Report")
    
    r_tab1, r_tab2, r_tab3 = st.tabs(["Session Log", "Compliance Report", "Actions"])
    
    with r_tab1:
        if st.session_state.scanned_serials:
            log_df = pd.DataFrame(st.session_state.scanned_serials, columns=["Serial", "Description", "Status"])
            st.dataframe(log_df, use_container_width=True)
        else:
            st.info("No items scanned yet.")

    with r_tab2:
        if st.button("Generate Compliance Report"):
            all_assets = db.get_all_assets()
            total_db = len(all_assets)
            
            scanned_set = {x[0] for x in st.session_state.scanned_serials if x[2] == "Verified"}
            missing_assets = [a for a in all_assets if a[4] not in scanned_set]
            
            c_a, c_b = st.columns(2)
            c_a.metric("Total DB Assets", total_db)
            c_b.metric("Verified Scanned", len(scanned_set))
            
            st.progress(len(scanned_set) / total_db if total_db > 0 else 0)
            
            if missing_assets:
                st.error(f"⚠️ {len(missing_assets)} Assets Not Scanned")
                
                missing_df = pd.DataFrame(missing_assets, columns=config.ASSET_COLUMNS)
                st.dataframe(missing_df[["Make", "Model", "Serial", "Building", "Room", "Assigned To"]], use_container_width=True)
                
                # Download CSV
                csv = missing_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇ Download Missing Assets Report (CSV)",
                    data=csv,
                    file_name="missing_assets_report.csv",
                    mime="text/csv",
                )
            else:
                st.success("🎉 100% Inventory Accuracy!")

    with r_tab3:
        if st.button("Clear Session Log", type="primary"):
            st.session_state.scanned_serials = []
            st.rerun()


# --- VIEW 4: ADMIN ---
def show_admin(db, user_scope):
    st.title("🛡️ Admin Panel")
    
    if user_scope != config.SCOPE_ADMIN:
        st.error("Access Denied.")
        return

    st.subheader("Create New User")
    with st.form("add_user"):
        c1, c2, c3, c4 = st.columns(4)
        u_name = c1.text_input("Username")
        u_pass = c2.text_input("Password", type="password")
        u_role = c3.selectbox("Role", ["User", "Manager", "Admin"]) 
        u_scope = c4.selectbox("Scope", [config.SCOPE_READ_ONLY, config.SCOPE_READ_WRITE, config.SCOPE_ADMIN])
        
        if st.form_submit_button("Create User"):
            if db.add_user(u_name, u_pass, u_role, u_scope):
                st.success(f"User {u_name} created.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Username exists.")

    st.divider()
    st.subheader("Manage Users")
    
    users = db.get_all_users()
    for u in users:
        with st.expander(f"{u[1]} ({u[3]})"):
            c1, c2 = st.columns(2)
            
            new_pass = c1.text_input("New Password", key=f"pass_{u[0]}", type="password")
            if c1.button("Reset Password", key=f"btn_reset_{u[0]}"):
                if new_pass:
                    db.update_user_password(u[0], new_pass)
                    st.success(f"Password reset for {u[1]}")
                else:
                    st.warning("Enter a password first.")

            if u[1] != "admin": 
                if c2.button("Delete User", key=f"del_{u[0]}", type="primary"):
                    db.delete_user(u[0])
                    st.rerun()