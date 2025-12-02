import streamlit as st
import pandas as pd
import time
import io
import plotly.express as px
from datetime import datetime, timedelta
import config
import qrcode
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from fpdf import FPDF
import os
import re
import tempfile

# --- SETUP: ATTACHMENTS FOLDER ---
ATTACHMENTS_DIR = "attachments"
if not os.path.exists(ATTACHMENTS_DIR):
    os.makedirs(ATTACHMENTS_DIR)

# --- HELPER: STALE ASSET CHECK ---
def get_asset_health(last_scanned_str):
    if not last_scanned_str or last_scanned_str == "Never":
        return "🔴", "Never Scanned", True
    try:
        scan_date = pd.to_datetime(last_scanned_str)
        if (datetime.now() - scan_date).days > 180:
            return "🔴", f"Stale (>6mo)", True
        return "🟢", "Healthy", False
    except:
        return "⚪", "Unknown", True

# --- HELPER: PDF HANDOVER GENERATOR ---
def generate_handover_pdf(asset, assignee):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="ASSET HANDOVER FORM", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(5)
    
    # Details
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="1. Device Details", ln=True)
    pdf.set_font("Arial", size=12)
    details = [f"Make: {asset['Make']}", f"Model: {asset['Model']}", f"Serial: {asset['Serial']}", f"ID: {asset['ID']}", f"Loc: {asset['Building']} {asset['Room']}"]
    for line in details: pdf.cell(200, 8, txt=line, ln=True)
    pdf.ln(5)
    
    # Assignment
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="2. Employee Assignment", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Issued To: {assignee}", ln=True)
    pdf.ln(20)
    
    # Signatures
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="3. Acceptance", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, txt="I acknowledge receipt of the equipment listed above.")
    pdf.ln(25)
    pdf.cell(90, 10, txt="__________________________", ln=0)
    pdf.cell(90, 10, txt="__________________________", ln=1)
    pdf.cell(90, 5, txt="Employee Signature", ln=0)
    pdf.cell(90, 5, txt="IT Admin Signature", ln=1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- HELPER: BULK QR SHEET GENERATOR (WINDOWS FIX) ---
def generate_qr_sheet(assets_df):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=8)
    
    w, h = 60, 35
    cols = 3
    x_start, y_start = 10, 10
    col_counter, row_counter = 0, 0
    
    for index, row in assets_df.iterrows():
        x = x_start + (col_counter * w)
        y = y_start + (row_counter * h)
        
        if y + h > 280:
            pdf.add_page()
            col_counter, row_counter = 0, 0
            y, x = y_start, x_start

        pdf.rect(x, y, w, h)
        
        # QR Generation
        qr = qrcode.QRCode(box_size=10, border=1)
        qr.add_data(str(row['Serial']))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # WINDOWS FIX: Close file before passing to FPDF
        tmp_name = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                img.save(tmp_file.name)
                tmp_name = tmp_file.name
            
            # Now file is closed, FPDF can open it
            pdf.image(tmp_name, x=x+2, y=y+2, w=20, h=20)
            
        except Exception as e:
            print(f"QR Error: {e}")
        finally:
            # Cleanup
            if tmp_name and os.path.exists(tmp_name):
                try: os.remove(tmp_name)
                except: pass

        # Text
        pdf.set_xy(x + 24, y + 5)
        pdf.set_font("Arial", 'B', 9)
        pdf.multi_cell(34, 4, txt=f"{str(row['Make'])[:15]}\n{str(row['Model'])[:15]}")
        
        pdf.set_xy(x + 24, y + 15)
        pdf.set_font("Arial", size=7)
        pdf.cell(34, 4, txt=f"S/N: {row['Serial']}", ln=1)
        pdf.set_xy(x + 24, y + 19)
        pdf.cell(34, 4, txt=f"ID: {row['ID']}", ln=1)
        
        col_counter += 1
        if col_counter >= cols:
            col_counter = 0
            row_counter += 1
            
    return pdf.output(dest='S').encode('latin-1')

# --- HELPER: SINGLE QR ---
def generate_qr(data):
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

# --- COMPONENT: ASSET DETAILS POPUP ---
@st.dialog("Asset Details")
def show_asset_dialog(asset, user_scope, db):
    emoji, h_text, is_stale = get_asset_health(asset['Last Scanned'])
    
    c_title, c_health = st.columns([3, 1])
    with c_title:
        st.header(f"{asset['Make']} {asset['Model']}") 
        st.caption(f"Serial: {asset['Serial']} | ID: {asset['ID']}")
    with c_health:
        if is_stale: st.error(f"{emoji} {h_text}")
        else: st.success(f"{emoji} {h_text}")

    d_tab1, d_tab2, d_tab3 = st.tabs(["ℹ️ Info & Actions", "📎 Attachments", "🔧 Tools"])

    with d_tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Type:** {asset['Type']}")
            st.write(f"**Location:** {asset['Building']} / Rm {asset['Room']}")
            loc_details = []
            if asset['Rack']: loc_details.append(f"Rack: {asset['Rack']}")
            if asset['Row']: loc_details.append(f"Row: {asset['Row']}")
            if asset['Table']: loc_details.append(f"Table: {asset['Table']}")
            if loc_details: st.caption(" | ".join(loc_details))
            st.write(f"**ITEC:** {asset['ITEC']}")
        with col2:
            status = asset['Assigned To'] if asset['Assigned To'] and asset['Assigned To'] != "Available" else "Available"
            if status == "Available": st.success(f"**Status:** {status}")
            else:
                st.warning(f"**Assigned To:** {status}")
                pdf_bytes = generate_handover_pdf(asset, status)
                st.download_button(label="📄 Handover Form", data=pdf_bytes, file_name=f"Handover_{asset['Serial']}.pdf", mime="application/pdf")
            
            st.write(f"**Price:** ${asset['Price']}")
            st.write(f"**Tags:** {asset['Tags']}")

        st.divider()
        
        # Financial Lifecycle (Fixed Regex)
        if asset['Date Added'] and asset['Price']:
            try:
                # FIX: Regex cleaning for robustness
                raw_p = str(asset['Price'])
                clean_p = re.sub(r'[^\d.]', '', raw_p)
                price = float(clean_p) if clean_p else 0.0
                
                p_date = pd.to_datetime(asset['Date Added'])
                dates = [p_date + pd.DateOffset(years=i) for i in range(6)]
                values = [max(0, price - (price/5 * i)) for i in range(6)]
                dep_df = pd.DataFrame({"Date": dates, "Value": values})
                
                with st.expander("📉 Depreciation Curve"):
                    fig = px.line(dep_df, x="Date", y="Value", markers=True)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.caption("Depreciation unavailable (Invalid Data)")

        if user_scope != config.SCOPE_READ_ONLY:
            st.subheader("Custody")
            if status != "Available":
                if st.button("📥 Check In", key=f"in_{asset['ID']}", type="primary"):
                    db.add_transaction(asset['ID'], st.session_state.username, "CHECKIN")
                    st.rerun()
            else:
                c1, c2 = st.columns([2,1])
                new_assign = c1.text_input("Assign To", key=f"a_{asset['ID']}")
                if c2.button("📤 Check Out", key=f"out_{asset['ID']}", type="primary"):
                    if new_assign:
                        db.add_transaction(asset['ID'], st.session_state.username, "CHECKOUT", assignee=new_assign)
                        st.rerun()

    with d_tab2:
        st.write("**Documents & Photos**")
        if user_scope != config.SCOPE_READ_ONLY:
            uploaded_file = st.file_uploader("Add Attachment", key=f"up_{asset['ID']}")
            if uploaded_file:
                if st.button("Save File", key=f"save_{asset['ID']}"):
                    file_path = os.path.join(ATTACHMENTS_DIR, f"{asset['ID']}_{uploaded_file.name}")
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success("File Saved!")
                    time.sleep(1); st.rerun()
            st.divider()
        
        files = [f for f in os.listdir(ATTACHMENTS_DIR) if f.startswith(f"{asset['ID']}_")]
        if files:
            for f_name in files:
                clean_name = f_name.replace(f"{asset['ID']}_", "")
                f_path = os.path.join(ATTACHMENTS_DIR, f_name)
                with open(f_path, "rb") as f:
                    st.download_button(label=f"⬇️ {clean_name}", data=f, file_name=clean_name, key=f"dl_{f_name}")
        else:
            st.info("No attachments found.")

    with d_tab3:
        c_qr, c_del = st.columns([1, 2])
        with c_qr:
            img = generate_qr(asset['Serial'])
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue(), width=100)
        with c_del:
            st.download_button("⬇ QR Image", data=buf.getvalue(), file_name=f"QR_{asset['Serial']}.png", mime="image/png")
            if user_scope != config.SCOPE_READ_ONLY:
                st.write("")
                if st.button("🗑️ Delete Asset", key=f"del_{asset['ID']}", type="secondary"):
                    db.delete_asset(asset['ID'])
                    st.rerun()

# --- VIEW 1: DASHBOARD ---
def show_dashboard(db, user_scope):
    st.title("📊 Command Center")
    total, value, types, tags_list, _ = db.get_stats()
    assets, total_filtered = db.get_all_assets()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Assets", total)
    c2.metric("Portfolio Value", f"${value:,.2f}")
    c3.metric("Categories", types)
    
    new_this_month = 0
    if assets:
        df_temp = pd.DataFrame(assets)
        if 'Date Added' in df_temp.columns:
            df_temp['Date Added'] = pd.to_datetime(df_temp['Date Added'], errors='coerce')
            now = datetime.now()
            new_this_month = len(df_temp[(df_temp['Date Added'].dt.month == now.month) & (df_temp['Date Added'].dt.year == now.year)])
    
    c4.metric("New (Month)", new_this_month)
    st.markdown("---")

    t1, t2 = st.tabs(["📈 Intelligence", "📋 Operational Data"])
    
    with t1:
        if assets:
            df_analytics = pd.DataFrame(assets)
            c_chart1, c_chart2 = st.columns([2, 1])
            with c_chart1:
                st.subheader("Asset Distribution")
                if 'Type' in df_analytics.columns and 'Make' in df_analytics.columns:
                    fig_tree = px.treemap(df_analytics, path=[px.Constant("All Assets"), 'Type', 'Make'], title="Hierarchy")
                    st.plotly_chart(fig_tree, use_container_width=True)
            with c_chart2:
                st.subheader("Availability")
                if 'Assigned To' in df_analytics.columns:
                    df_analytics['Status_Simple'] = df_analytics['Assigned To'].apply(lambda x: 'Available' if x == 'Available' or not x else 'Assigned')
                    fig_pie = px.pie(df_analytics, names='Status_Simple', hole=0.4, title="Custody")
                    st.plotly_chart(fig_pie, use_container_width=True)
            
            st.divider()
            st.subheader("Financial Overview")
            if 'Price' in df_analytics.columns:
                df_val = df_analytics.groupby('Type')['Price'].sum().reset_index()
                fig_bar = px.bar(df_val, x='Price', y='Type', orientation='h', title="Total Value by Type", text_auto='.2s')
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No data available.")

    with t2:
        c_search, c_filter, c_exp = st.columns([2, 1, 1])
        search = c_search.text_input("🔍 Search", placeholder="Serial, Model...")
        tag_f = c_filter.selectbox("Tag Filter", ["All"] + tags_list)
        
        PAGE_SIZE = 50
        if 'page' not in st.session_state: st.session_state.page = 0
        
        def apply_health(last_scanned):
            emoji, _, _ = get_asset_health(last_scanned)
            return emoji

        filtered_assets, count_filtered = db.get_all_assets(tag_f if tag_f != "All" else None, search if search else None, limit=PAGE_SIZE, offset=st.session_state.page * PAGE_SIZE)
        
        if c_exp.button("⬇ Export CSV"):
            all_assets_export, _ = db.get_all_assets(tag_f if tag_f != "All" else None, search if search else None)
            csv = pd.DataFrame(all_assets_export).to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", data=csv, file_name="full_export.csv", mime="text/csv")

        if filtered_assets:
            df_filt = pd.DataFrame(filtered_assets)
            df_filt['Health'] = df_filt['Last Scanned'].apply(apply_health)
            cols = ['Health'] + [c for c in df_filt.columns if c != 'Health']
            df_filt = df_filt[cols]
            
            event = st.dataframe(df_filt, on_select="rerun", selection_mode="multi-row", use_container_width=True, hide_index=True, column_config={"Price": st.column_config.NumberColumn(format="$%.2f"), "ID": None, "Health": st.column_config.TextColumn(width="small")})
            
            p1, p2, p3 = st.columns([1, 8, 1])
            if st.session_state.page > 0:
                if p1.button("◀ Prev"): st.session_state.page -= 1; st.rerun()
            if (st.session_state.page + 1) * PAGE_SIZE < count_filtered:
                if p3.button("Next ▶"): st.session_state.page += 1; st.rerun()
            p2.caption(f"Showing page {st.session_state.page + 1} of {max(1, (count_filtered // PAGE_SIZE) + 1)}")
            
            rows = event.selection.rows
            if len(rows) == 1:
                idx = rows[0]
                show_asset_dialog(filtered_assets[idx], user_scope, db)
            elif len(rows) > 1:
                subset = df_filt.iloc[rows]
                st.info(f"✅ **{len(rows)} Assets Selected**")
                if st.button("🖨️ Generate QR Label Sheet (PDF)"):
                    pdf_data = generate_qr_sheet(subset)
                    st.download_button(label="⬇ Download Sticker Sheet", data=pdf_data, file_name="qr_stickers.pdf", mime="application/pdf")
        else:
            st.warning("No results.")

# --- VIEW 2: ADD ASSET ---
def show_add_asset(db, user_scope):
    st.title("➕ Add New Asset")
    if user_scope == config.SCOPE_READ_ONLY:
        st.error("🔒 Restricted Access"); return

    tab1, tab2 = st.tabs(["📝 Manual", "📂 CSV Import"])
    
    with tab1:
        st.caption("Fields marked with * are required.")
        st.subheader("Device Details")
        c1, c2, c3 = st.columns(3)
        
        stats = db.get_stats()
        all_types = ["Laptop", "Monitor", "Printer", "Other"] + (stats[4] if len(stats) > 4 else [])
        unique_types = sorted(list(set(all_types)))
        if "Other" in unique_types: unique_types.remove("Other"); unique_types.append("Other")
        
        with c1:
            sel_type = st.selectbox("Device Type *", unique_types)
            if sel_type == "Other":
                specific_type = st.text_input("Specify Device Type *", placeholder="e.g., Tablet")
                final_type = specific_type
            else: final_type = sel_type; specific_type = None

        with c2: make = st.text_input("Make *", placeholder="e.g., Dell")
        with c3: model = st.text_input("Model *", placeholder="e.g., Latitude 7420")

        c4, c5, c6 = st.columns(3)
        with c4: serial = st.text_input("Serial Number *", placeholder="SN-12345")
        with c5: itec = st.text_input("ITEC Account *", placeholder="e.g., 65000")
        with c6: price = st.number_input("AQS Price *", min_value=0.0, step=0.01, format="%.2f")

        st.divider()
        st.subheader("Location Strategy")
        l1, l2 = st.columns(2)
        with l1: build = st.text_input("Building *", placeholder="e.g., Main HQ")
        with l2: room = st.text_input("Room *", placeholder="e.g., 101")
        l3, l4, l5 = st.columns(3)
        with l3: rack = st.text_input("Rack", placeholder="Optional")
        with l4: row = st.text_input("Row", placeholder="Optional")
        with l5: table = st.text_input("Table", placeholder="Optional")

        st.divider()
        st.subheader("Assignment & Tags")
        m1, m2 = st.columns(2)
        with m1: assign = st.text_input("Initial Assignment", placeholder="Employee Name (Optional)")
        with m2:
            existing_tags = stats[3] if len(stats) > 3 else []
            selected_tags = st.multiselect("Tags", existing_tags)
            new_tag = st.text_input("Or create a new tag", placeholder="Type and save to add...")

        st.markdown("")
        if st.button("Save Asset", type="primary", use_container_width=True):
            errors = []
            if sel_type == "Other" and not specific_type: errors.append("Device Type (Other)")
            if not final_type: errors.append("Device Type")
            if not make: errors.append("Make")
            if not model: errors.append("Model")
            if not serial: errors.append("Serial Number")
            if not itec: errors.append("ITEC Account")
            if not build: errors.append("Building")
            if not room: errors.append("Room")
            if price <= 0: errors.append("AQS Price")
            
            if errors: st.error(f"Missing Required Fields: {', '.join(errors)}")
            else:
                final_tags = selected_tags
                if new_tag and new_tag.strip():
                    clean_tag = new_tag.strip()
                    if clean_tag not in final_tags: final_tags.append(clean_tag)
                tag_str = ",".join(final_tags)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                data = (final_type, make, model, serial, "", itec, price, build, room, "", rack, row, table, assign if assign else "Available", tag_str, now, now, "Never")
                
                aid = db.add_asset(data)
                if aid:
                    if assign: db.add_transaction(aid, st.session_state.username, "CREATE_ASSIGN", assign)
                    else: db.add_transaction(aid, st.session_state.username, "CREATE", "Available")
                    st.success("Asset successfully added!"); time.sleep(1); st.rerun()
                else: st.error("Operation Failed: Duplicate Serial Number detected.")

    with tab2:
        up = st.file_uploader("Upload CSV", type="csv")
        st.info("CSV Columns must include: type, make, model, serial, price, building, room")
        if up and st.button("Import"):
            try:
                df = pd.read_csv(up)
                df.columns = [c.lower().strip() for c in df.columns]
                cnt = 0
                for _, r in df.iterrows():
                    if 'serial' in r and not pd.isna(r['serial']):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        data = (r.get('type','Unknown'), r.get('make','Gen'), r.get('model','Gen'), str(r['serial']), "", "", r.get('price',0), r.get('building','Main'), r.get('room','000'), "Imported", "", "", "", r.get('assigned',''), "", now, now, "Never")
                        if db.add_asset(data): cnt += 1
                st.success(f"Imported {cnt} Assets")
            except Exception as e: st.error(f"Error: {e}")

# --- VIEW 3: INVENTORY (UPDATED WITH CAMERA) ---
def show_inventory(db, user_scope):
    st.title("📋 Fast Inventory")
    if 'scanned_session' not in st.session_state: st.session_state.scanned_session = []

    def on_scan(scan_code):
        if scan_code:
            # Check if duplicates in session? Optional.
            # Processing
            asset = db.get_asset_by_serial(scan_code)
            ts = datetime.now().strftime("%H:%M:%S")
            if asset:
                if user_scope != config.SCOPE_READ_ONLY: db.update_scan_time(scan_code)
                st.session_state.scanned_session.insert(0, {"Time": ts, "Serial": scan_code, "Name": f"{asset['Make']} {asset['Model']}", "Status": "✅ Verified"})
                st.toast(f"Verified: {asset['Make']}")
            else:
                st.session_state.scanned_session.insert(0, {"Time": ts, "Serial": scan_code, "Name": "Unknown", "Status": "❌ Not Found"})
                st.toast(f"Unknown: {scan_code}")

    c_input, c_report = st.columns([2, 1])
    with c_input:
        st.write("👉 **Scan Method 1: USB Scanner**")
        
        # Callback wrapper for text input
        def text_callback():
            code = st.session_state.usb_input
            on_scan(code)
            st.session_state.usb_input = "" # Clear input

        st.text_input("Scanner Input", key="usb_input", on_change=text_callback, label_visibility="collapsed")
        
        st.write("👉 **Scan Method 2: Webcam**")
        # FIX: Camera Input Logic
        cam = st.camera_input("Scan QR/Barcode")
        if cam:
            bytes_data = cam.getvalue()
            cv_image = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
            decoded_objects = decode(cv_image)
            if decoded_objects:
                for obj in decoded_objects:
                    d_data = obj.data.decode("utf-8")
                    st.success(f"Detected: {d_data}")
                    if st.button(f"Process {d_data}", key=f"proc_{d_data}"):
                         on_scan(d_data)
                         st.rerun()
            else:
                st.caption("No barcode detected in image.")

        st.write("---")
        st.subheader("Live Session Log")
        if st.session_state.scanned_session:
            st.dataframe(pd.DataFrame(st.session_state.scanned_session), use_container_width=True)
            if st.button("Clear Log"): st.session_state.scanned_session = []; st.rerun()

    with c_report:
        st.info("📊 **Session Report**")
        if st.session_state.scanned_session:
            df_log = pd.DataFrame(st.session_state.scanned_session)
            total_scans = len(df_log)
            unique_assets = df_log['Serial'].nunique()
            verified_count = len(df_log[df_log['Status'] == "✅ Verified"])
            
            r1, r2 = st.columns(2)
            r1.metric("Scans", total_scans)
            r2.metric("Verified", verified_count)
            st.caption(f"Unique Items: {unique_assets}")
            st.divider()
            csv_data = df_log.to_csv(index=False).encode('utf-8')
            st.download_button(label="⬇ Download Report (CSV)", data=csv_data, file_name=f"inventory_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv", type="primary")
        else:
            st.caption("Scan assets to generate a report.")

# --- VIEW 4: ADMIN ---
def show_admin(db, user_scope):
    st.title("🛡️ Admin Panel")
    if user_scope != config.SCOPE_ADMIN: st.error("Denied: Admin Access Required"); return
    
    t1, t2, t3 = st.tabs(["👥 User Management", "📜 Audit Log", "✏️ Bulk Asset Edit"])
    
    with t1:
        u_tab1, u_tab2 = st.tabs(["Create User", "Manage Existing Users"])
        with u_tab1:
            st.subheader("Create New User")
            with st.form("new_u"):
                c1, c2, c3 = st.columns(3)
                u = c1.text_input("Username")
                p = c2.text_input("Password", type="password")
                r = c3.selectbox("Access Scope", [config.SCOPE_READ_ONLY, "Read/Write", config.SCOPE_ADMIN])
                if st.form_submit_button("Create User"): 
                    if u and p:
                        if db.add_user(u, p, "User", r): st.success(f"User '{u}' Created"); time.sleep(1); st.rerun()
                        else: st.error("Username already exists.")

        with u_tab2:
            st.subheader("Manage Existing Users")
            all_users = db.get_all_users()
            user_map = {f"{usr[1]} ({usr[3]})": usr for usr in all_users}
            selected_label = st.selectbox("Select User to Manage", [""] + list(user_map.keys()))
            if selected_label and selected_label != "":
                selected_user = user_map[selected_label]
                uid, uname, urole, uscope = selected_user
                c_scope, c_pass, c_del = st.columns(3)
                with c_scope:
                    new_scope_val = st.selectbox("New Scope", [config.SCOPE_READ_ONLY, "Read/Write", config.SCOPE_ADMIN], key=f"s_{uid}")
                    if st.button("Update Scope", key=f"btn_s_{uid}"): db.update_user_scope(uid, new_scope_val); st.success("Updated!"); st.rerun()
                with c_pass:
                    new_pass_val = st.text_input("New Password", type="password", key=f"p_{uid}")
                    if st.button("Update Password", key=f"btn_p_{uid}"): 
                        if new_pass_val: db.update_user_password(uid, new_pass_val); st.success("Updated!")
                with c_del:
                    st.write("Danger Zone")
                    if st.button("🗑️ Delete User", key=f"del_{uid}", type="primary"):
                        if uname == st.session_state.username: st.error("You cannot delete yourself.")
                        else: db.delete_user(uid); st.success(f"Deleted {uname}"); st.rerun()

    with t2:
        logs = db.get_all_transactions()
        if logs:
            df = pd.DataFrame(logs)
            st.dataframe(df, use_container_width=True)
            c_log1, c_log2 = st.columns(2)
            with c_log1:
                st.caption("Activity by User")
                fig = px.pie(df, names="User", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            with c_log2:
                st.caption("Activity Timeline")
                fig2 = px.scatter(df, x="Timestamp", y="Action", color="User")
                st.plotly_chart(fig2, use_container_width=True)
        else: st.info("No Audit Logs found.")

    with t3:
        with open(config.DB_NAME, "rb") as fp:
            st.download_button("💾 Backup Database", fp, "backup.db", type="primary")

        st.info("⚠️ Admin Mode: Direct Database Edits. Changes are final.")
        assets_data, _ = db.get_all_assets()
        
        if assets_data:
            df_edit = pd.DataFrame(assets_data)
            edited_df = st.data_editor(df_edit, key="edit_bulk", disabled=["ID", "Date Added", "Last Modified"], num_rows="fixed", use_container_width=True)
            
            if st.button("💾 Save Bulk Changes", type="primary"):
                p_bar = st.progress(0)
                total_rows = len(edited_df)
                errors = 0
                try:
                    for i, r in edited_df.iterrows():
                        # FIX: Using new Dict Logic in Database
                        row_dict = r.to_dict()
                        if not db.update_asset_dict(row_dict['ID'], row_dict): errors += 1
                        p_bar.progress((i + 1) / total_rows)
                    if errors == 0: st.success("Database successfully updated!")
                    else: st.warning(f"Updated with {errors} errors.")
                    time.sleep(1); st.rerun()
                except Exception as e: st.error(f"Error updating database: {e}")