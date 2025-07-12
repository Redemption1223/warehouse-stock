import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime
import io
import uuid
import hashlib

# User Management
def init_user_database():
    """Initialize user management system"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT,
        created_date TEXT,
        last_login TEXT
    )''')
    
    # Create default users if not exist
    users_exist = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if users_exist == 0:
        # Default warehouse manager
        manager_hash = hashlib.sha256("manager123".encode()).hexdigest()
        boss_hash = hashlib.sha256("boss123".encode()).hexdigest()
        viewer_hash = hashlib.sha256("viewer123".encode()).hexdigest()
        
        default_users = [
            ("warehouse_manager", manager_hash, "warehouse_manager", "Warehouse Manager", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("boss", boss_hash, "boss", "Boss/Owner", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("viewer", viewer_hash, "viewer", "Staff Viewer", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ]
        
        c.executemany("INSERT INTO users (username, password_hash, role, full_name, created_date) VALUES (?, ?, ?, ?, ?)", 
                     default_users)
    
    conn.commit()
    conn.close()

def authenticate_user(username, password):
    """Authenticate user and return role"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    result = c.execute("SELECT role, full_name FROM users WHERE username = ? AND password_hash = ?", 
                      (username, password_hash)).fetchone()
    
    if result:
        # Update last login
        c.execute("UPDATE users SET last_login = ? WHERE username = ?", 
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
        conn.commit()
    
    conn.close()
    return result

def check_permission(required_role):
    """Check if current user has required permission"""
    if 'user_role' not in st.session_state:
        return False
    
    user_role = st.session_state.user_role
    
    # Permission hierarchy
    roles_hierarchy = {
        'warehouse_manager': 3,  # Full access
        'boss': 2,              # Read all, limited write
        'viewer': 1             # Final products only
    }
    
    required_level = roles_hierarchy.get(required_role, 0)
    user_level = roles_hierarchy.get(user_role, 0)
    
    return user_level >= required_level

# Database setup
def init_database():
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Items table
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit TEXT NOT NULL,
        current_stock REAL DEFAULT 0,
        min_stock REAL DEFAULT 0,
        cost_per_unit REAL DEFAULT 0,
        location TEXT DEFAULT 'Main',
        warehouse_area TEXT DEFAULT 'General',
        created_date TEXT,
        created_by TEXT
    )''')
    
    # Bill of Materials table
    c.execute('''CREATE TABLE IF NOT EXISTS bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        final_product_id TEXT NOT NULL,
        ingredient_id TEXT NOT NULL,
        quantity_required REAL NOT NULL,
        FOREIGN KEY (final_product_id) REFERENCES items (id),
        FOREIGN KEY (ingredient_id) REFERENCES items (id)
    )''')
    
    # Stock movements table
    c.execute('''CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT NOT NULL,
        movement_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        reference TEXT,
        batch_nr TEXT,
        date_time TEXT,
        user_id TEXT,
        FOREIGN KEY (item_id) REFERENCES items (id)
    )''')
    
    # Warehouse areas table
    c.execute('''CREATE TABLE IF NOT EXISTS warehouse_areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_name TEXT UNIQUE NOT NULL,
        description TEXT,
        capacity REAL,
        created_date TEXT
    )''')
    
    # Create default warehouse areas
    default_areas = [
        ("Raw Materials Storage", "Storage area for chemical compounds and powders"),
        ("Components Storage", "Buckets, stickers, nozzles, and extinguisher bodies"),
        ("Final Products", "Completed fire extinguishers ready for dispatch"),
        ("Quality Control", "Items pending quality inspection"),
        ("Dispatch Area", "Items ready for shipping")
    ]
    
    for area_name, description in default_areas:
        c.execute("INSERT OR IGNORE INTO warehouse_areas (area_name, description, created_date) VALUES (?, ?, ?)",
                 (area_name, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

def load_sample_data():
    """Load your existing data into the new system"""
    
    # Check if data already exists
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM items")
    if c.fetchone()[0] > 0:
        conn.close()
        return  # Data already loaded
    conn.close()
    
    # Raw Materials from your Excel
    raw_materials = [
        ("LIG001", "LIGNO", "Raw Material", "kg", 300, 1000, "Raw Materials Storage"),
        ("KOH001", "KOH", "Raw Material", "kg", 40, 100, "Raw Materials Storage"),
        ("ETH001", "ETHYLENE GLYCOL", "Raw Material", "kg", 64, 20, "Raw Materials Storage"),
        ("ACE001", "ACETIC ACID", "Raw Material", "kg", 0, 300, "Raw Materials Storage"),
        ("FOR001", "FORMIC ACID", "Raw Material", "kg", 678.5, 250, "Raw Materials Storage"),
        ("BEN001", "BENTONITE CLAY", "Raw Material", "kg", 40, 100, "Raw Materials Storage"),
        ("XGU001", "X GUM", "Raw Material", "kg", 17.8, 25, "Raw Materials Storage"),
        ("PRO001", "PROPYLENE GLYCOL", "Raw Material", "kg", 30.7, 2, "Raw Materials Storage"),
        ("COR001", "CORNSTARCH", "Raw Material", "kg", 10.1, 25, "Raw Materials Storage"),
    ]
    
    # Pre-Final Components
    prefinal_components = [
        ("LIB001", "LITHIUM BLACK POWDER", "Pre-Final", "kg", 2000, 5, "Components Storage"),
        ("2LB001", "2L BOXES", "Pre-Final", "pieces", 325, 50, "Components Storage"),
        ("6LB001", "6L BOXES", "Pre-Final", "pieces", 146, 50, "Components Storage"),
        ("9LB001", "9L BOXES", "Pre-Final", "pieces", 2, 50, "Components Storage"),
        ("20B001", "20KG BUCKETS", "Pre-Final", "pieces", 65, 10, "Components Storage"),
        ("2LE001", "2L EMPTY EXTINGUISHERS", "Pre-Final", "pieces", 9, 10, "Components Storage"),
        ("6LE001", "6L EMPTY EXTINGUISHERS", "Pre-Final", "pieces", 26, 1, "Components Storage"),
        ("2LS001", "2L STICKERS", "Pre-Final", "pieces", 144, 50, "Components Storage"),
        ("6LS001", "6L STICKERS", "Pre-Final", "pieces", 516, 50, "Components Storage"),
        ("9LS001", "9L STICKERS", "Pre-Final", "pieces", 522, 50, "Components Storage"),
    ]
    
    # Final Products
    final_products = [
        ("LB9L001", "LITHIUM BLACK 9L", "Final Product", "pieces", 3, 100, "Final Products"),
        ("LB6L001", "LITHIUM BLACK 6L", "Final Product", "pieces", 23, 100, "Final Products"),
        ("LB2L001", "LITHIUM BLACK 2L", "Final Product", "pieces", 0, 50, "Final Products"),
        ("SH20001", "SHIELD 20KG", "Final Product", "pieces", 9, 10, "Final Products"),
        ("CT9L001", "CAPE TOWN 9L", "Final Product", "pieces", 7, 10, "Final Products"),
        ("PT9L001", "PINE TOWN 9L", "Final Product", "pieces", 14, 10, "Final Products"),
    ]
    
    # Insert all data
    all_items = raw_materials + prefinal_components + final_products
    
    for item_data in all_items:
        item_id, name, category, unit, current_stock, min_stock, warehouse_area = item_data
        add_item(item_id, name, category, unit, current_stock, min_stock, 0, "Main", warehouse_area, "system")

def add_item(item_id, name, category, unit, current_stock=0, min_stock=0, cost_per_unit=0, location="Main", warehouse_area="General", created_by="system"):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO items 
                 (id, name, category, unit, current_stock, min_stock, cost_per_unit, location, warehouse_area, created_date, created_by)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (item_id, name, category, unit, current_stock, min_stock, cost_per_unit, location, warehouse_area,
               datetime.now().strftime("%Y-%m-%d %H:%M:%S"), created_by))
    conn.commit()
    conn.close()

def get_all_items(user_role=None):
    conn = sqlite3.connect('inventory.db')
    
    # Filter based on user role
    if user_role == "viewer":
        query = "SELECT * FROM items WHERE category = 'Final Product' ORDER BY category, name"
    else:
        query = "SELECT * FROM items ORDER BY category, name"
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_warehouse_areas():
    conn = sqlite3.connect('inventory.db')
    df = pd.read_sql_query("SELECT * FROM warehouse_areas ORDER BY area_name", conn)
    conn.close()
    return df

def update_stock(item_id, quantity, movement_type, reference="", batch_nr="", user_id="system"):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Update current stock
    if movement_type in ['IN', 'ADJUSTMENT_IN', 'PRODUCTION']:
        c.execute("UPDATE items SET current_stock = current_stock + ? WHERE id = ?", (quantity, item_id))
    else:
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id = ?", (quantity, item_id))
    
    # Record movement
    c.execute('''INSERT INTO stock_movements (item_id, movement_type, quantity, reference, batch_nr, date_time, user_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (item_id, movement_type, quantity, reference, batch_nr, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    
    conn.commit()
    conn.close()

def import_from_excel_with_areas(uploaded_file):
    """Import items from Excel and assign to warehouse areas"""
    try:
        # Read different sheets
        raw_df = pd.read_excel(uploaded_file, sheet_name='RAW STOCK')
        raw_df['category'] = 'Raw Material'
        raw_df['unit'] = 'kg'
        raw_df['warehouse_area'] = 'Raw Materials Storage'
        raw_df = raw_df.rename(columns={'PRODUCTS': 'name', 'QTY KG': 'current_stock'})
        
        prefinal_df = pd.read_excel(uploaded_file, sheet_name='PREFINAL STOCK')
        prefinal_df['category'] = 'Pre-Final'
        prefinal_df['unit'] = 'pieces'
        prefinal_df['warehouse_area'] = 'Components Storage'
        prefinal_df = prefinal_df.rename(columns={'PRODUCTS': 'name', 'QUANTITY': 'current_stock'})
        
        final_df = pd.read_excel(uploaded_file, sheet_name='FINAL STOCK')
        final_df['category'] = 'Final Product'
        final_df['unit'] = 'pieces'
        final_df['warehouse_area'] = 'Final Products'
        final_df = final_df.rename(columns={'PRODUCTS': 'name', 'QTY': 'current_stock', 'AMOUNT NEEDED IN STOCK': 'min_stock'})
        
        # Combine all dataframes
        items_df = pd.concat([raw_df, prefinal_df, final_df], ignore_index=True)
        
        # Add items to database
        for _, row in items_df.iterrows():
            item_id = str(uuid.uuid4())[:8].upper()
            add_item(
                item_id,
                row['name'],
                row['category'],
                row['unit'],
                row.get('current_stock', 0),
                row.get('min_stock', 0),
                row.get('cost_per_unit', 0),
                "Main",
                row['warehouse_area'],
                st.session_state.get('username', 'import')
            )
        
        return True, f"Successfully imported {len(items_df)} items to designated warehouse areas"
    except Exception as e:
        return False, f"Error importing Excel file: {str(e)}"

# Login system
def show_login():
    st.title("🔐 Fire Extinguisher Inventory System")
    st.markdown("### Please Login to Continue")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            st.markdown("#### User Login")
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("🔓 Login", use_container_width=True)
            
            if submit:
                if username and password:
                    result = authenticate_user(username, password)
                    if result:
                        role, full_name = result
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.user_role = role
                        st.session_state.full_name = full_name
                        st.success(f"Welcome {full_name}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
                else:
                    st.error("❌ Please enter both username and password")
        
        # Default credentials info
        with st.expander("🔑 Default Login Credentials"):
            st.markdown("""
            **Warehouse Manager:** (Full Access)
            - Username: `warehouse_manager`
            - Password: `manager123`
            
            **Boss/Owner:** (View All, Limited Edit)
            - Username: `boss` 
            - Password: `boss123`
            
            **Staff Viewer:** (Final Products Only)
            - Username: `viewer`
            - Password: `viewer123`
            """)

# Main application
def main():
    st.set_page_config(page_title="🔥 Fire Extinguisher Stock Control", layout="wide")
    
    # Initialize databases
    init_database()
    init_user_database()
    
    # Check authentication
    if not st.session_state.get('authenticated', False):
        show_login()
        return
    
    # Check if database is empty and load sample data
    items_df = get_all_items()
    if items_df.empty:
        with st.spinner("Setting up your inventory system with existing data..."):
            load_sample_data()
            st.success("✅ Loaded your existing inventory data!")
            st.rerun()
    
    # Header with user info and logout
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.title("🔥 Fire Extinguisher Stock Control System")
        user_role = st.session_state.user_role
        role_display = {
            'warehouse_manager': '👨‍💼 Warehouse Manager',
            'boss': '👔 Boss/Owner', 
            'viewer': '👁️ Viewer'
        }
        st.markdown(f"**{role_display.get(user_role, user_role)} - {st.session_state.full_name}**")
    
    with col3:
        if st.button("🚪 Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    st.markdown("---")
    
    # Navigation based on user role
    if user_role == "viewer":
        # Viewers only see final products
        menu = st.sidebar.selectbox("Select Module", [
            "📊 Final Products Dashboard",
            "📦 Final Products View"
        ])
        
        if menu == "📊 Final Products Dashboard":
            show_final_products_dashboard()
        elif menu == "📦 Final Products View":
            show_final_products_view()
            
    elif user_role == "boss":
        # Boss sees everything but limited editing
        menu = st.sidebar.selectbox("Select Module", [
            "📊 Management Dashboard",
            "📦 Complete Stock View", 
            "📈 Stock Movements",
            "📋 Management Reports",
            "👥 User Management"
        ])
        
        if menu == "📊 Management Dashboard":
            show_management_dashboard()
        elif menu == "📦 Complete Stock View":
            show_complete_stock_view()
        elif menu == "📈 Stock Movements":
            show_stock_movements()
        elif menu == "📋 Management Reports":
            show_management_reports()
        elif menu == "👥 User Management":
            show_user_management()
            
    else:  # warehouse_manager
        # Full access
        menu = st.sidebar.selectbox("Select Module", [
            "📊 Dashboard",
            "📦 Stock Management", 
            "🏭 Production Center",
            "📈 Stock Movements",
            "⚙️ Item Management",
            "🧾 Bill of Materials",
            "🏪 Warehouse Areas",
            "📋 Reports",
            "💾 Excel Import/Export",
            "👥 User Management"
        ])
        
        if menu == "📊 Dashboard":
            show_dashboard()
        elif menu == "📦 Stock Management":
            show_stock_management()
        elif menu == "🏭 Production Center":
            show_production_center()
        elif menu == "📈 Stock Movements":
            show_stock_movements()
        elif menu == "⚙️ Item Management":
            show_item_management()
        elif menu == "🧾 Bill of Materials":
            show_bom_management()
        elif menu == "🏪 Warehouse Areas":
            show_warehouse_areas()
        elif menu == "📋 Reports":
            show_reports()
        elif menu == "💾 Excel Import/Export":
            show_excel_integration()
        elif menu == "👥 User Management":
            show_user_management()

def show_final_products_dashboard():
    """Dashboard for viewers - final products only"""
    st.header("📊 Final Products Dashboard")
    
    items_df = get_all_items("viewer")
    
    if not items_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Final Products", len(items_df))
        
        with col2:
            in_stock = len(items_df[items_df['current_stock'] > 0])
            st.metric("In Stock", in_stock)
        
        with col3:
            low_stock = len(items_df[items_df['current_stock'] <= items_df['min_stock']])
            st.metric("Low Stock", low_stock, delta=f"-{low_stock}" if low_stock > 0 else None)
        
        with col4:
            total_value = (items_df['current_stock'] * items_df['cost_per_unit']).sum()
            st.metric("Total Value", f"R{total_value:,.2f}")
        
        # Product status
        st.subheader("🏭 Final Products Status")
        
        for _, item in items_df.iterrows():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                status = "✅" if item['current_stock'] > item['min_stock'] else "⚠️" if item['current_stock'] > 0 else "❌"
                st.write(f"{status} **{item['name']}**")
            
            with col2:
                st.write(f"{item['current_stock']} {item['unit']}")
            
            with col3:
                if item['current_stock'] <= item['min_stock']:
                    st.error("LOW STOCK")
                else:
                    st.success("IN STOCK")

def show_final_products_view():
    """Detailed view of final products for viewers"""
    st.header("📦 Final Products Inventory")
    
    items_df = get_all_items("viewer")
    
    if not items_df.empty:
        # Add status column
        def get_status(row):
            if row['current_stock'] <= 0:
                return "❌ OUT OF STOCK"
            elif row['current_stock'] <= row['min_stock']:
                return "⚠️ LOW STOCK"
            else:
                return "✅ IN STOCK"
        
        items_df['Status'] = items_df.apply(get_status, axis=1)
        
        # Display table
        display_df = items_df[['name', 'current_stock', 'min_stock', 'unit', 'warehouse_area', 'Status']]
        display_df.columns = ['Product Name', 'Current Stock', 'Min Stock', 'Unit', 'Location', 'Status']
        
        st.dataframe(display_df, use_container_width=True, height=600)

def show_management_dashboard():
    """Dashboard for boss - complete overview"""
    st.header("📊 Management Dashboard")
    
    items_df = get_all_items()
    
    if not items_df.empty:
        # High-level metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Items", len(items_df))
        
        with col2:
            total_value = (items_df['current_stock'] * items_df['cost_per_unit']).sum()
            st.metric("Inventory Value", f"R{total_value:,.2f}")
        
        with col3:
            low_stock = len(items_df[items_df['current_stock'] <= items_df['min_stock']])
            st.metric("Items Needing Attention", low_stock)
        
        with col4:
            final_products = len(items_df[items_df['category'] == 'Final Product'])
            st.metric("Final Products", final_products)
        
        # Category breakdown
        st.subheader("📊 Inventory by Category")
        
        category_summary = items_df.groupby('category').agg({
            'current_stock': 'sum',
            'cost_per_unit': lambda x: (items_df[items_df['category'] == x.name]['current_stock'] * items_df[items_df['category'] == x.name]['cost_per_unit']).sum(),
            'name': 'count'
        }).round(2)
        
        category_summary.columns = ['Total Stock', 'Total Value', 'Item Count']
        st.dataframe(category_summary, use_container_width=True)
        
        # Critical alerts
        critical_items = items_df[items_df['current_stock'] <= 0]
        if not critical_items.empty:
            st.error(f"🚨 CRITICAL: {len(critical_items)} items are OUT OF STOCK!")
            st.dataframe(critical_items[['name', 'category', 'current_stock', 'min_stock']])

def show_complete_stock_view():
    """Complete stock view for boss"""
    st.header("📦 Complete Stock Overview")
    
    items_df = get_all_items()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        category_filter = st.selectbox("Category", ["All"] + list(items_df['category'].unique()))
    
    with col2:
        area_filter = st.selectbox("Warehouse Area", ["All"] + list(items_df['warehouse_area'].unique()))
    
    with col3:
        status_filter = st.selectbox("Status", ["All", "In Stock", "Low Stock", "Out of Stock"])
    
    # Apply filters
    filtered_df = items_df.copy()
    
    if category_filter != "All":
        filtered_df = filtered_df[filtered_df['category'] == category_filter]
    
    if area_filter != "All":
        filtered_df = filtered_df[filtered_df['warehouse_area'] == area_filter]
    
    if status_filter == "In Stock":
        filtered_df = filtered_df[filtered_df['current_stock'] > filtered_df['min_stock']]
    elif status_filter == "Low Stock":
        filtered_df = filtered_df[(filtered_df['current_stock'] <= filtered_df['min_stock']) & (filtered_df['current_stock'] > 0)]
    elif status_filter == "Out of Stock":
        filtered_df = filtered_df[filtered_df['current_stock'] <= 0]
    
    # Display results
    if not filtered_df.empty:
        display_df = filtered_df[['name', 'category', 'current_stock', 'min_stock', 'unit', 'warehouse_area']]
        display_df.columns = ['Item', 'Category', 'Current', 'Minimum', 'Unit', 'Location']
        st.dataframe(display_df, use_container_width=True, height=600)
    else:
        st.info("No items match the selected filters.")

def show_stock_management():
    """Stock management for warehouse manager"""
    st.header("📦 Stock Management")
    
    tab1, tab2 = st.tabs(["Quick Stock Updates", "Warehouse Organization"])
    
    with tab1:
        show_quick_stock_updates()
    
    with tab2:
        show_warehouse_organization()

def show_quick_stock_updates():
    """Quick stock update interface"""
    items_df = get_all_items()
    
    if items_df.empty:
        st.info("No items found.")
        return
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        category_filter = st.selectbox("Filter by Category", 
                                     ["All", "Raw Material", "Pre-Final", "Final Product"])
    
    with col2:
        area_filter = st.selectbox("Filter by Area", 
                                 ["All"] + list(items_df['warehouse_area'].unique()))
    
    with col3:
        search_term = st.text_input("Search Items", placeholder="Type item name...")
    
    # Apply filters
    filtered_df = items_df.copy()
    
    if category_filter != "All":
        filtered_df = filtered_df[filtered_df['category'] == category_filter]
    
    if area_filter != "All":
        filtered_df = filtered_df[filtered_df['warehouse_area'] == area_filter]
    
    if search_term:
        filtered_df = filtered_df[filtered_df['name'].str.contains(search_term, case=False)]
    
    # Display stock table
    if not filtered_df.empty:
        def get_status(row):
            if row['current_stock'] <= 0:
                return "❌ OUT OF STOCK"
            elif row['current_stock'] <= row['min_stock']:
                return "⚠️ LOW STOCK"
            else:
                return "✅ IN STOCK"
        
        filtered_df['Status'] = filtered_df.apply(get_status, axis=1)
        
        display_df = filtered_df[['id', 'name', 'category', 'current_stock', 'min_stock', 'unit', 'warehouse_area', 'Status']]
        display_df.columns = ['ID', 'Name', 'Category', 'Current', 'Min', 'Unit', 'Area', 'Status']
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Quick stock adjustment
        st.subheader("⚡ Quick Stock Adjustment")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            selected_item = st.selectbox("Select Item", 
                                       options=filtered_df['id'].tolist(),
                                       format_func=lambda x: f"{x} - {filtered_df[filtered_df['id']==x]['name'].iloc[0] if not filtered_df[filtered_df['id']==x].empty else x}")
        
        with col2:
            adjustment_qty = st.number_input("Quantity", value=0.0)
        
        with col3:
            movement_type = st.selectbox("Type", ["IN", "OUT"])
        
        with col4:
            batch_nr = st.text_input("Batch #", placeholder="Optional")
        
        with col5:
            reference = st.text_input("Reference", placeholder="Reason/Note")
        
        if st.button("💾 Update Stock", type="primary"):
            if selected_item and adjustment_qty != 0:
                update_stock(selected_item, abs(adjustment_qty), movement_type, reference, batch_nr, st.session_state.username)
                st.success("Stock updated successfully!")
                st.rerun()

def show_warehouse_organization():
    """Warehouse area organization"""
    st.subheader("🏪 Warehouse Areas Organization")
    
    areas_df = get_warehouse_areas()
    items_df = get_all_items()
    
    # Show items by warehouse area
    for _, area in areas_df.iterrows():
        area_items = items_df[items_df['warehouse_area'] == area['area_name']]
        
        with st.expander(f"📦 {area['area_name']} ({len(area_items)} items)"):
            st.write(f"**Description:** {area['description']}")
            
            if not area_items.empty:
                area_summary = area_items.groupby('category').agg({
                    'current_stock': 'sum',
                    'name': 'count'
                })
                
                st.write("**Items in this area:**")
                for _, item in area_items.iterrows():
                    status = "✅" if item['current_stock'] > item['min_stock'] else "⚠️" if item['current_stock'] > 0 else "❌"
                    st.write(f"{status} {item['name']}: {item['current_stock']} {item['unit']}")

# Additional functions would continue here...
# (Due to length constraints, I'm showing the key user management and multi-device structure)

def show_dashboard():
    """Main dashboard for warehouse manager"""
    st.header("📊 Warehouse Manager Dashboard")
    
    items_df = get_all_items()
    
    if not items_df.empty:
        # Main metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Items", len(items_df))
        
        with col2:
            raw_materials = len(items_df[items_df['category'] == 'Raw Material'])
            st.metric("Raw Materials", raw_materials)
        
        with col3:
            pre_final = len(items_df[items_df['category'] == 'Pre-Final'])
            st.metric("Pre-Final Items", pre_final)
        
        with col4:
            final_products = len(items_df[items_df['category'] == 'Final Product'])
            st.metric("Final Products", final_products)
        
        # Critical alerts
        low_stock_items = items_df[items_df['current_stock'] <= items_df['min_stock']]
        out_of_stock = items_df[items_df['current_stock'] <= 0]
        
        if not out_of_stock.empty or not low_stock_items.empty:
            st.error("🚨 **URGENT ATTENTION NEEDED!**")
            
            if not out_of_stock.empty:
                st.write("**OUT OF STOCK:**")
                for _, item in out_of_stock.iterrows():
                    st.write(f"❌ {item['name']} - {item['current_stock']} {item['unit']} (Area: {item['warehouse_area']})")
            
            if not low_stock_items.empty:
                st.write("**LOW STOCK ALERTS:**")
                for _, item in low_stock_items.iterrows():
                    if item['current_stock'] > 0:
                        st.write(f"⚠️ {item['name']} - {item['current_stock']}/{item['min_stock']} {item['unit']} (Area: {item['warehouse_area']})")
        else:
            st.success("✅ All items are above minimum stock levels!")

def show_user_management():
    """User management interface"""
    if not check_permission('boss'):
        st.error("❌ Access denied. Boss or Warehouse Manager access required.")
        return
    
    st.header("👥 User Management")
    
    # Show current users
    conn = sqlite3.connect('inventory.db')
    users_df = pd.read_sql_query("SELECT username, role, full_name, created_date, last_login FROM users", conn)
    conn.close()
    
    st.subheader("Current Users")
    st.dataframe(users_df, use_container_width=True)
    
    # Add new user (only warehouse manager)
    if check_permission('warehouse_manager'):
        st.subheader("➕ Add New User")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            new_full_name = st.text_input("Full Name")
        
        with col2:
            new_role = st.selectbox("Role", ["viewer", "boss", "warehouse_manager"])
            
            role_descriptions = {
                "viewer": "Can only view final products",
                "boss": "Can view everything, limited editing",
                "warehouse_manager": "Full access to everything"
            }
            
            st.info(f"**{new_role}:** {role_descriptions[new_role]}")
        
        if st.button("➕ Add User"):
            if new_username and new_password and new_full_name:
                try:
                    conn = sqlite3.connect('inventory.db')
                    c = conn.cursor()
                    
                    password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                    c.execute("INSERT INTO users (username, password_hash, role, full_name, created_date) VALUES (?, ?, ?, ?, ?)",
                             (new_username, password_hash, new_role, new_full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ User {new_username} added successfully!")
                    st.rerun()
                    
                except sqlite3.IntegrityError:
                    st.error("❌ Username already exists!")
            else:
                st.error("❌ Please fill in all fields!")

# Deployment instructions
def show_deployment_info():
    """Show deployment instructions for multi-device access"""
    st.subheader("🌐 Deploy for Multi-Device Access")
    
    st.markdown("""
    ### 🚀 **To access from multiple devices when your laptop is OFF:**
    
    #### **Option 1: Streamlit Cloud (Recommended - FREE)**
    1. Upload your code to GitHub
    2. Go to [share.streamlit.io](https://share.streamlit.io)
    3. Connect your GitHub repo
    4. Deploy instantly!
    5. **Result**: Get a URL like `https://yourapp.streamlit.app`
    
    #### **Option 2: Heroku (Professional)**
    1. Create Heroku account
    2. Install Heroku CLI
    3. Deploy with database
    4. **Result**: 24/7 access from any device
    
    #### **Option 3: Local Network Server**
    1. Keep one computer running 24/7
    2. Run: `streamlit run inventory_app.py --server.address 0.0.0.0`
    3. Access from other devices: `http://[computer-ip]:8501`
    
    ### 📱 **Benefits of Cloud Deployment:**
    - ✅ Access from phones, tablets, computers
    - ✅ Works when your laptop is off
    - ✅ Automatic backups
    - ✅ Multiple users simultaneously
    - ✅ Professional business solution
    """)

# Include all other necessary functions (show_item_management, show_bom_management, etc.)
# They would follow the same pattern with permission checks

if __name__ == "__main__":
    main()
