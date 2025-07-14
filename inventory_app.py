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

def get_bom(final_product_id):
    """Get Bill of Materials for a product"""
    conn = sqlite3.connect('inventory.db')
    query = '''SELECT b.*, i.name as ingredient_name, i.unit, i.current_stock
               FROM bom b
               JOIN items i ON b.ingredient_id = i.id
               WHERE b.final_product_id = ?'''
    df = pd.read_sql_query(query, conn, params=[final_product_id])
    conn.close()
    return df

def add_bom_item(final_product_id, ingredient_id, quantity_required):
    """Add item to Bill of Materials"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO bom (final_product_id, ingredient_id, quantity_required)
                 VALUES (?, ?, ?)''', (final_product_id, ingredient_id, quantity_required))
    conn.commit()
    conn.close()

def produce_item(final_product_id, quantity_to_produce):
    """Produce final product and automatically deduct ingredients"""
    bom_df = get_bom(final_product_id)
    
    if bom_df.empty:
        return False, "No Bill of Materials found for this product"
    
    # Check if enough ingredients available
    insufficient_ingredients = []
    for _, row in bom_df.iterrows():
        required_qty = row['quantity_required'] * quantity_to_produce
        if row['current_stock'] < required_qty:
            insufficient_ingredients.append(f"{row['ingredient_name']}: Need {required_qty}, Have {row['current_stock']}")
    
    if insufficient_ingredients:
        return False, f"Insufficient ingredients: {'; '.join(insufficient_ingredients)}"
    
    try:
        # Deduct ingredients
        for _, row in bom_df.iterrows():
            required_qty = row['quantity_required'] * quantity_to_produce
            update_stock(row['ingredient_id'], required_qty, 'OUT', f'Production of {quantity_to_produce} units', 'PRODUCTION', st.session_state.get('username', 'system'))
        
        # Add final product to stock
        update_stock(final_product_id, quantity_to_produce, 'PRODUCTION', f'Production completed', '', st.session_state.get('username', 'system'))
        
        return True, f"Successfully produced {quantity_to_produce} units"
    
    except Exception as e:
        return False, f"Error during production: {str(e)}"

# Login system
def show_login():
    # Hide Streamlit elements on login page
    hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
    .stDecoration {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none;}
    
    /* Mobile responsive login */
    .main .block-container {
        padding-top: 2rem;
        max-width: 500px;
        margin: 0 auto;
    }
    
    .login-header {
        text-align: center;
        margin-bottom: 2rem;
        padding: 1.5rem;
        background: linear-gradient(135deg, #FF4B4B 0%, #FF6B6B 100%);
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .login-form {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
    }
    
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem;
        }
        .login-header {
            padding: 1rem;
        }
        .login-header h1 {
            font-size: 1.8rem !important;
        }
        .login-header h2 {
            font-size: 1.4rem !important;
        }
    }
    </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    # Professional login header
    st.markdown("""
    <div class="login-header">
        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🔥</div>
        <h1 style="margin: 0; font-size: 2rem;">FLAMEBLOCK</h1>
        <h2 style="margin: 0; font-size: 1.6rem; opacity: 0.9;">INVENTORY SYSTEM</h2>
        <p style="margin: 0.5rem 0 0 0; font-size: 1rem; opacity: 0.8;">Professional Stock Control</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-form">', unsafe_allow_html=True)
    
    with st.form("login_form"):
        st.markdown("#### 🔐 Secure Access")
        username = st.text_input("👤 Username", placeholder="Enter your username")
        password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("🚀 Access System", use_container_width=True, type="primary")
        
        if submit:
            if username and password:
                result = authenticate_user(username, password)
                if result:
                    role, full_name = result
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.user_role = role
                    st.session_state.full_name = full_name
                    st.success(f"✅ Welcome {full_name}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials. Please try again.")
            else:
                st.error("❌ Please enter both username and password")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Mobile-friendly navigation
def show_mobile_navigation(user_role):
    """Mobile-friendly navigation system"""
    
    # Define menu items based on user role
    if user_role == "viewer":
        menu_items = [
            ("📊", "Dashboard", "final_products_dashboard"),
            ("📦", "Products", "final_products_view")
        ]
    elif user_role == "boss":
        menu_items = [
            ("📊", "Dashboard", "management_dashboard"),
            ("📦", "Stock View", "complete_stock_view"),
            ("📈", "Movements", "stock_movements"),
            ("📋", "Reports", "management_reports")
        ]
    else:  # warehouse_manager
        menu_items = [
            ("📊", "Dashboard", "dashboard"),
            ("📦", "Stock", "stock_management"),
            ("🏭", "Production", "production_center"),
            ("📈", "Movements", "stock_movements"),
            ("⚙️", "Items", "item_management"),
            ("🧾", "BOM", "bom_management"),
            ("🏪", "Areas", "warehouse_areas"),
            ("📋", "Reports", "reports"),
            ("💾", "Excel", "excel_integration"),
            ("👥", "Users", "user_management")
        ]
    
    # Initialize session state for current page
    if 'current_page' not in st.session_state:
        st.session_state.current_page = menu_items[0][2]
    
    # Mobile navigation style
    nav_style = """
    <style>
    .mobile-nav {
        background: linear-gradient(90deg, #FF4B4B 0%, #FF6B6B 100%);
        padding: 0.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .nav-button {
        display: inline-block;
        margin: 0.2rem;
        padding: 0.5rem 0.8rem;
        background: rgba(255,255,255,0.2);
        border: none;
        border-radius: 6px;
        color: white;
        text-decoration: none;
        font-size: 0.9rem;
        cursor: pointer;
        transition: background 0.3s;
    }
    
    .nav-button:hover {
        background: rgba(255,255,255,0.3);
    }
    
    .nav-button.active {
        background: rgba(255,255,255,0.9);
        color: #FF4B4B;
        font-weight: bold;
    }
    
    @media (max-width: 768px) {
        .nav-button {
            font-size: 0.8rem;
            padding: 0.4rem 0.6rem;
            margin: 0.1rem;
        }
    }
    </style>
    """
    
    st.markdown(nav_style, unsafe_allow_html=True)
    
    # Create navigation buttons
    st.markdown('<div class="mobile-nav">', unsafe_allow_html=True)
    
    cols = st.columns(len(menu_items))
    
    for i, (icon, label, page_key) in enumerate(menu_items):
        with cols[i]:
            # Shorter label for mobile
            mobile_label = label[:8] + "..." if len(label) > 8 else label
            button_text = f"{icon}\n{mobile_label}"
            
            if st.button(button_text, key=f"nav_{page_key}", use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return st.session_state.current_page

# Main application
def main():
    st.set_page_config(
        page_title="🔥 FLAMEBLOCK INVENTORY SYSTEM",  # ← Browser tab name
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )
    
    # Hide Streamlit style elements
    hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
    .stDecoration {visibility: hidden;}
    .stActionButton {visibility: hidden;}
    .stToolbar {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none;}
    
    .stApp > header {
        background-color: transparent;
    }
    
    .main .block-container {
        padding-top: 1rem;
        max-width: 100%;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Hide dataframe toolbars */
    .stDataFrame [data-testid="stElementToolbar"] {
        display: none;
    }
    
    /* Mobile responsive adjustments */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        
        .stSelectbox label, .stTextInput label, .stNumberInput label {
            font-size: 0.9rem;
        }
        
        .element-container {
            margin-bottom: 0.5rem;
        }
    }
    
    /* Professional styling */
    .stSelectbox label, .stTextInput label, .stNumberInput label {
        font-weight: 600;
        color: #262730;
    }
    </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
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
        with st.spinner("Setting up your inventory system..."):
            load_sample_data()
            st.success("✅ Loaded your existing inventory data!")
            st.rerun()
    
    # Header with user info and logout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("""
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <div style="font-size: 2rem; margin-right: 0.5rem;">🔥</div>
            <div>
                <h1 style="margin: 0; color: #262730; font-size: 1.8rem;">FLAMEBLOCK INVENTORY SYSTEM</h1>
                <p style="margin: 0; color: #666; font-size: 0.8rem;">Professional Stock Control</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        user_role = st.session_state.user_role
        role_display = {
            'warehouse_manager': '👨‍💼 Warehouse Manager',
            'boss': '👔 Boss/Owner', 
            'viewer': '👁️ Viewer'
        }
        st.markdown(f"**{role_display.get(user_role, user_role)} - {st.session_state.full_name}**")
    
    with col2:
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Mobile-friendly navigation
    current_page = show_mobile_navigation(user_role)
    
    # Route to appropriate page
    if current_page == "final_products_dashboard":
        show_final_products_dashboard()
    elif current_page == "final_products_view":
        show_final_products_view()
    elif current_page == "management_dashboard":
        show_management_dashboard()
    elif current_page == "complete_stock_view":
        show_complete_stock_view()
    elif current_page == "stock_movements":
        show_stock_movements()
    elif current_page == "management_reports":
        show_management_reports()
    elif current_page == "dashboard":
        show_dashboard()
    elif current_page == "stock_management":
        show_stock_management()
    elif current_page == "production_center":
        show_production_center()
    elif current_page == "item_management":
        show_item_management()
    elif current_page == "bom_management":
        show_bom_management()
    elif current_page == "warehouse_areas":
        show_warehouse_areas()
    elif current_page == "reports":
        show_reports()
    elif current_page == "excel_integration":
        show_excel_integration()
    elif current_page == "user_management":
        show_user_management()

# Page functions
def show_final_products_dashboard():
    """Dashboard for viewers - final products only"""
    st.header("📊 Final Products Dashboard")
    
    items_df = get_all_items("viewer")
    
    if not items_df.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Products", len(items_df))
        
        with col2:
            in_stock = len(items_df[items_df['current_stock'] > 0])
            st.metric("In Stock", in_stock)
        
        with col3:
            low_stock = len(items_df[items_df['current_stock'] <= items_df['min_stock']])
            st.metric("Low Stock", low_stock)
        
        # Product status
        st.subheader("🏭 Product Status")
        
        for _, item in items_df.iterrows():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                status = "✅" if item['current_stock'] > item['min_stock'] else "⚠️" if item['current_stock'] > 0 else "❌"
                st.write(f"{status} **{item['name']}**")
            
            with col2:
                st.write(f"{item['current_stock']} {item['unit']}")
            
            with col3:
                if item['current_stock'] <= item['min_stock']:
                    st.error("LOW")
                else:
                    st.success("OK")
    else:
        st.info("No final products found.")

def show_final_products_view():
    """Detailed view of final products for viewers"""
    st.header("📦 Final Products")
    
    items_df = get_all_items("viewer")
    
    if not items_df.empty:
        # Add status column
        def get_status(row):
            if row['current_stock'] <= 0:
                return "❌ OUT"
            elif row['current_stock'] <= row['min_stock']:
                return "⚠️ LOW"
            else:
                return "✅ OK"
        
        items_df['Status'] = items_df.apply(get_status, axis=1)
        
        # Display table
        display_df = items_df[['name', 'current_stock', 'min_stock', 'unit', 'Status']]
        display_df.columns = ['Product', 'Stock', 'Min', 'Unit', 'Status']
        
        st.dataframe(display_df, use_container_width=True, height=400)

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
            raw_materials = len(items_df[items_df['category'] == 'Raw Material'])
            st.metric("Raw Materials", raw_materials)
        
        with col3:
            final_products = len(items_df[items_df['category'] == 'Final Product'])
            st.metric("Final Products", final_products)
        
        with col4:
            low_stock = len(items_df[items_df['current_stock'] <= items_df['min_stock']])
            st.metric("Need Attention", low_stock)
        
        # Critical alerts
        critical_items = items_df[items_df['current_stock'] <= 0]
        if not critical_items.empty:
            st.error(f"🚨 CRITICAL: {len(critical_items)} items are OUT OF STOCK!")
            st.dataframe(critical_items[['name', 'category', 'current_stock']])

def show_complete_stock_view():
    """Complete stock view for boss"""
    st.header("📦 Complete Stock")
    
    items_df = get_all_items()
    
    # Simple filters for mobile
    category_filter = st.selectbox("Category", ["All"] + list(items_df['category'].unique()))
    
    # Apply filters
    if category_filter != "All":
        items_df = items_df[items_df['category'] == category_filter]
    
    # Display results
    if not items_df.empty:
        display_df = items_df[['name', 'category', 'current_stock', 'min_stock', 'unit']]
        display_df.columns = ['Item', 'Category', 'Stock', 'Min', 'Unit']
        st.dataframe(display_df, use_container_width=True, height=400)

def show_stock_movements():
    """Show stock movement history"""
    st.header("📈 Stock Movements")
    
    # Get movements data
    conn = sqlite3.connect('inventory.db')
    movements_df = pd.read_sql_query('''SELECT sm.*, i.name as item_name, i.unit
                                       FROM stock_movements sm
                                       JOIN items i ON sm.item_id = i.id
                                       ORDER BY sm.date_time DESC LIMIT 100''', conn)
    conn.close()
    
    if not movements_df.empty:
        movements_df['date_time'] = pd.to_datetime(movements_df['date_time']).dt.strftime('%m-%d %H:%M')
        
        display_df = movements_df[['date_time', 'item_name', 'movement_type', 'quantity', 'unit']]
        display_df.columns = ['Date', 'Item', 'Type', 'Qty', 'Unit']
        
        st.dataframe(display_df, use_container_width=True, height=400)
    else:
        st.info("No movements found.")

def show_management_reports():
    """Management reports for boss"""
    st.header("📋 Management Reports")
    
    items_df = get_all_items()
    if items_df.empty:
        st.info("No data available.")
        return
    
    # Category summary
    st.subheader("📊 By Category")
    category_summary = items_df.groupby('category').agg({
        'current_stock': 'sum',
        'name': 'count'
    }).rename(columns={'name': 'items', 'current_stock': 'total_stock'})
    
    st.dataframe(category_summary, use_container_width=True)
    
    # Low stock items
    low_stock = items_df[items_df['current_stock'] <= items_df['min_stock']]
    if not low_stock.empty:
        st.subheader("⚠️ Need Attention")
        display_low = low_stock[['name', 'current_stock', 'min_stock', 'unit']]
        display_low.columns = ['Item', 'Current', 'Min', 'Unit']
        st.dataframe(display_low, use_container_width=True)

def show_dashboard():
    """Main dashboard for warehouse manager"""
    st.header("📊 Dashboard")
    
    items_df = get_all_items()
    
    if not items_df.empty:
        # Main metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Items", len(items_df))
        
        with col2:
            raw_materials = len(items_df[items_df['category'] == 'Raw Material'])
            st.metric("Raw", raw_materials)
        
        with col3:
            pre_final = len(items_df[items_df['category'] == 'Pre-Final'])
            st.metric("Components", pre_final)
        
        with col4:
            final_products = len(items_df[items_df['category'] == 'Final Product'])
            st.metric("Final", final_products)
        
        # Critical alerts
        low_stock_items = items_df[items_df['current_stock'] <= items_df['min_stock']]
        out_of_stock = items_df[items_df['current_stock'] <= 0]
        
        if not out_of_stock.empty:
            st.error("🚨 **OUT OF STOCK**")
            for _, item in out_of_stock.iterrows():
                st.write(f"❌ {item['name']}")
        
        if not low_stock_items.empty and out_of_stock.empty:
            st.warning("⚠️ **LOW STOCK**")
            for _, item in low_stock_items.iterrows():
                if item['current_stock'] > 0:
                    st.write(f"⚠️ {item['name']}: {item['current_stock']}/{item['min_stock']}")
        
        if out_of_stock.empty and low_stock_items.empty:
            st.success("✅ All stock levels OK!")

def show_stock_management():
    """Stock management for warehouse manager"""
    st.header("📦 Stock Management")
    
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    items_df = get_all_items()
    
    if items_df.empty:
        st.info("No items found.")
        return
    
    # Simple category filter
    category_filter = st.selectbox("Category", ["All", "Raw Material", "Pre-Final", "Final Product"])
    
    # Apply filter
    if category_filter != "All":
        items_df = items_df[items_df['category'] == category_filter]
    
    # Display stock table
    if not items_df.empty:
        def get_status(row):
            if row['current_stock'] <= 0:
                return "❌ OUT"
            elif row['current_stock'] <= row['min_stock']:
                return "⚠️ LOW"
            else:
                return "✅ OK"
        
        items_df['Status'] = items_df.apply(get_status, axis=1)
        
        display_df = items_df[['id', 'name', 'current_stock', 'unit', 'Status']]
        display_df.columns = ['ID', 'Name', 'Stock', 'Unit', 'Status']
        
        st.dataframe(display_df, use_container_width=True, height=300)
        
        # Quick stock adjustment
        st.subheader("⚡ Quick Update")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_item = st.selectbox("Item", 
                                       options=items_df['id'].tolist(),
                                       format_func=lambda x: f"{x} - {items_df[items_df['id']==x]['name'].iloc[0]}")
            adjustment_qty = st.number_input("Quantity", value=0.0)
        
        with col2:
            movement_type = st.selectbox("Type", ["IN", "OUT"])
            reference = st.text_input("Reference", placeholder="Reason")
        
        if st.button("💾 Update Stock", type="primary"):
            if selected_item and adjustment_qty != 0:
                update_stock(selected_item, abs(adjustment_qty), movement_type, reference, "", st.session_state.username)
                st.success("Stock updated!")
                st.rerun()

def show_production_center():
    """Production center for warehouse manager"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("🏭 Production")
    
    items_df = get_all_items()
    final_products = items_df[items_df['category'] == 'Final Product']
    
    if final_products.empty:
        st.warning("No final products found.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_product = st.selectbox("Product",
                                      options=final_products['id'].tolist(),
                                      format_func=lambda x: f"{final_products[final_products['id']==x]['name'].iloc[0]}")
        
        quantity_to_produce = st.number_input("Quantity", min_value=1, value=1)
        
        if st.button("🚀 Start Production", type="primary"):
            if selected_product and quantity_to_produce > 0:
                success, message = produce_item(selected_product, quantity_to_produce)
                
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    with col2:
        if selected_product:
            st.subheader("📋 Requirements")
            
            bom = get_bom(selected_product)
            
            if not bom.empty:
                can_produce = True
                
                for _, row in bom.iterrows():
                    required_qty = row['quantity_required'] * quantity_to_produce
                    available_qty = row['current_stock']
                    
                    if available_qty >= required_qty:
                        status = "✅"
                    else:
                        status = "❌"
                        can_produce = False
                    
                    st.write(f"{status} {row['ingredient_name']}: {required_qty} (Have: {available_qty})")
                
                if can_produce:
                    st.success("✅ Can produce")
                else:
                    st.error("❌ Insufficient ingredients")
            else:
                st.warning("No BOM found")

def show_item_management():
    """Item management interface"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("⚙️ Item Management")
    
    tab1, tab2 = st.tabs(["➕ Add Item", "📋 View & Delete Items"])
    
    with tab1:
        st.subheader("Add New Item")
        
        item_id = st.text_input("Item ID", value=str(uuid.uuid4())[:8].upper())
        name = st.text_input("Item Name")
        category = st.selectbox("Category", ["Raw Material", "Pre-Final", "Final Product"])
        unit = st.selectbox("Unit", ["kg", "g", "L", "ml", "pieces", "units"])
        current_stock = st.number_input("Current Stock", min_value=0.0, value=0.0)
        min_stock = st.number_input("Min Stock", min_value=0.0, value=0.0)
        
        if st.button("➕ Add Item", type="primary"):
            if name and item_id:
                add_item(item_id, name, category, unit, current_stock, min_stock, 0, "Main", "General", st.session_state.username)
                st.success(f"✅ Added {name}!")
                st.rerun()
            else:
                st.error("❌ Please fill Item ID and Name")
    
    with tab2:
        st.subheader("📋 All Items")
        items_df = get_all_items()
        
        if not items_df.empty:
            # Filter
            category_filter = st.selectbox("Filter by Category", 
                                         ["All", "Raw Material", "Pre-Final", "Final Product"])
            
            filtered_items = items_df.copy()
            if category_filter != "All":
                filtered_items = filtered_items[filtered_items['category'] == category_filter]
            
            # Add status column
            def get_status(row):
                if row['current_stock'] <= 0:
                    return "❌ OUT"
                elif row['current_stock'] <= row['min_stock']:
                    return "⚠️ LOW"
                else:
                    return "✅ OK"
            
            filtered_items['Status'] = filtered_items.apply(get_status, axis=1)
            
            display_df = filtered_items[['id', 'name', 'category', 'current_stock', 'min_stock', 'unit', 'Status']]
            display_df.columns = ['ID', 'Name', 'Category', 'Stock', 'Min', 'Unit', 'Status']
            
            st.dataframe(display_df, use_container_width=True, height=300)
            
            # DELETE SECTION - Very visible
            st.markdown("---")
            st.subheader("🗑️ DELETE ITEM")
            st.warning("⚠️ **DANGER ZONE** - Item deletion cannot be undone!")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if not filtered_items.empty:
                    item_to_delete = st.selectbox("🗑️ Select Item to DELETE", 
                                                options=[""] + filtered_items['id'].tolist(),
                                                format_func=lambda x: f"SELECT ITEM TO DELETE" if x == "" else f"DELETE: {x} - {filtered_items[filtered_items['id']==x]['name'].iloc[0]}")
                    
                    if item_to_delete and item_to_delete != "":
                        item_info = filtered_items[filtered_items['id'] == item_to_delete].iloc[0]
                        
                        st.error(f"""
                        **⚠️ ITEM TO BE DELETED:**
                        - **ID:** {item_info['id']}
                        - **Name:** {item_info['name']}
                        - **Category:** {item_info['category']}
                        - **Stock:** {item_info['current_stock']} {item_info['unit']}
                        """)
                        
                        # Check BOM usage
                        conn = sqlite3.connect('inventory.db')
                        bom_check = pd.read_sql_query("""
                            SELECT COUNT(*) as count FROM bom 
                            WHERE ingredient_id = ? OR final_product_id = ?
                        """, conn, params=[item_to_delete, item_to_delete])
                        conn.close()
                        
                        if bom_check.iloc[0]['count'] > 0:
                            st.warning("⚠️ This item is used in Bill of Materials!")
            
            with col2:
                if item_to_delete and item_to_delete != "":
                    st.write("**Deletion Controls:**")
                    
                    if st.button("🗑️ DELETE THIS ITEM", type="secondary", use_container_width=True):
                        if st.session_state.get('confirm_delete_item') == item_to_delete:
                            # DELETE THE ITEM
                            conn = sqlite3.connect('inventory.db')
                            c = conn.cursor()
                            
                            # Delete from all tables
                            c.execute('DELETE FROM items WHERE id = ?', (item_to_delete,))
                            c.execute('DELETE FROM bom WHERE final_product_id = ? OR ingredient_id = ?', 
                                     (item_to_delete, item_to_delete))
                            c.execute('DELETE FROM stock_movements WHERE item_id = ?', (item_to_delete,))
                            
                            conn.commit()
                            conn.close()
                            
                            st.success(f"🗑️ DELETED '{item_info['name']}' successfully!")
                            if 'confirm_delete_item' in st.session_state:
                                del st.session_state['confirm_delete_item']
                            st.rerun()
                        else:
                            st.session_state['confirm_delete_item'] = item_to_delete
                            st.error("⚠️ CLICK DELETE AGAIN TO CONFIRM!")
                    
                    if st.button("❌ Cancel Deletion", use_container_width=True):
                        if 'confirm_delete_item' in st.session_state:
                            del st.session_state['confirm_delete_item']
                        st.rerun()
                    
                    if item_info['current_stock'] > 0:
                        if st.button(f"📉 Clear Stock ({item_info['current_stock']} {item_info['unit']})", use_container_width=True):
                            update_stock(item_to_delete, item_info['current_stock'], 'OUT', 
                                       'Stock cleared for deletion', '', st.session_state.username)
                            st.success("Stock cleared to zero!")
                            st.rerun()
        else:
            st.info("No items found.")
        
        # Quick stats
        if not items_df.empty:
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Items", len(items_df))
            
            with col2:
                active_items = len(items_df[items_df['current_stock'] > 0])
                st.metric("Active Items", active_items)
            
            with col3:
                low_stock_items = len(items_df[items_df['current_stock'] <= items_df['min_stock']])
                st.metric("Low Stock", low_stock_items)
            
            with col4:
                zero_stock_items = len(items_df[items_df['current_stock'] <= 0])
                st.metric("Zero Stock", zero_stock_items)

def show_bom_management():
    """Bill of Materials management"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("🧾 Bill of Materials")
    
    items_df = get_all_items()
    if items_df.empty:
        st.warning("Add items first.")
        return
    
    final_products = items_df[items_df['category'] == 'Final Product']
    if final_products.empty:
        st.warning("Add final products first.")
        return
    
    selected_product = st.selectbox("Product",
                                  options=final_products['id'].tolist(),
                                  format_func=lambda x: f"{final_products[final_products['id']==x]['name'].iloc[0]}")
    
    if selected_product:
        # Show existing BOM
        existing_bom = get_bom(selected_product)
        if not existing_bom.empty:
            st.write("**Current BOM:**")
            display_bom = existing_bom[['ingredient_name', 'quantity_required', 'unit']]
            st.dataframe(display_bom, use_container_width=True)
        
        # Add ingredient
        st.subheader("Add Ingredient")
        
        available_ingredients = items_df[items_df['category'].isin(['Raw Material', 'Pre-Final'])]
        ingredient = st.selectbox("Ingredient",
                                options=available_ingredients['id'].tolist(),
                                format_func=lambda x: f"{available_ingredients[available_ingredients['id']==x]['name'].iloc[0]}")
        
        quantity_required = st.number_input("Quantity Required", min_value=0.001, value=1.0)
        
        if st.button("Add to BOM"):
            add_bom_item(selected_product, ingredient, quantity_required)
            st.success("Added to BOM!")
            st.rerun()

def show_warehouse_areas():
    """Warehouse areas management"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("🏪 Warehouse Areas")
    
    areas_df = get_warehouse_areas()
    items_df = get_all_items()
    
    for _, area in areas_df.iterrows():
        area_items = items_df[items_df['warehouse_area'] == area['area_name']]
        
        with st.expander(f"📦 {area['area_name']} ({len(area_items)} items)"):
            if not area_items.empty:
                for _, item in area_items.iterrows():
                    status = "✅" if item['current_stock'] > item['min_stock'] else "⚠️" if item['current_stock'] > 0 else "❌"
                    st.write(f"{status} {item['name']}: {item['current_stock']} {item['unit']}")

def show_reports():
    """Reports and analytics"""
    st.header("📋 Reports")
    
    items_df = get_all_items()
    if items_df.empty:
        st.info("No data available.")
        return
    
    # Stock summary
    summary_stats = items_df.groupby('category').agg({
        'current_stock': 'sum',
        'name': 'count'
    }).rename(columns={'name': 'items'})
    
    st.dataframe(summary_stats, use_container_width=True)
    
    # Low stock
    low_stock = items_df[items_df['current_stock'] <= items_df['min_stock']]
    if not low_stock.empty:
        st.subheader("⚠️ Low Stock")
        display_low = low_stock[['name', 'current_stock', 'min_stock', 'unit']]
        st.dataframe(display_low, use_container_width=True)

def show_excel_integration():
    """Excel import/export functionality"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("💾 Excel")
    
    tab1, tab2 = st.tabs(["Export", "Import"])
    
    with tab1:
        st.subheader("Export Data")
        
        if st.button("🔄 Generate Excel File"):
            items_df = get_all_items()
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                items_df.to_excel(writer, sheet_name='ALL_ITEMS', index=False)
            
            st.download_button(
                label="📥 Download Excel",
                data=output.getvalue(),
                file_name=f"inventory_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with tab2:
        st.subheader("Import Data")
        st.write("Upload Excel file to import items")
        
        uploaded_file = st.file_uploader("Excel file", type=['xlsx', 'xls'])
        
        if uploaded_file is not None:
            if st.button("📤 Import"):
                try:
                    df = pd.read_excel(uploaded_file)
                    
                    for _, row in df.iterrows():
                        item_id = str(uuid.uuid4())[:8].upper()
                        add_item(
                            item_id,
                            row.get('name', ''),
                            row.get('category', 'Raw Material'),
                            row.get('unit', 'pieces'),
                            row.get('current_stock', 0),
                            row.get('min_stock', 0),
                            0, "Main", "General",
                            st.session_state.username
                        )
                    
                    st.success(f"Imported {len(df)} items!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Import failed: {str(e)}")

def show_user_management():
    """User management interface"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("👥 User Management")
    
    # Show current users
    conn = sqlite3.connect('inventory.db')
    users_df = pd.read_sql_query("SELECT username, role, full_name, last_login FROM users ORDER BY role, username", conn)
    conn.close()
    
    st.subheader("👤 Current Users")
    
    if not users_df.empty:
        # Format display
        role_icons = {
            "warehouse_manager": "👨‍💼",
            "boss": "👔", 
            "viewer": "👁️"
        }
        
        users_df['Role'] = users_df['role'].map(lambda x: f"{role_icons.get(x, '👤')} {x.replace('_', ' ').title()}")
        
        display_df = users_df[['username', 'Role', 'full_name', 'last_login']]
        display_df.columns = ['Username', 'Access Level', 'Full Name', 'Last Login']
        
        st.dataframe(display_df, use_container_width=True)
    
    # Tab layout for mobile
    tab1, tab2, tab3 = st.tabs(["➕ Add User", "🗑️ Delete User", "🔒 Reset Password"])
    
    with tab1:
        st.subheader("Add New User")
        
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Username", placeholder="e.g., john_smith")
                new_password = st.text_input("Password", type="password", placeholder="Strong password")
                new_full_name = st.text_input("Full Name", placeholder="e.g., John Smith")
            
            with col2:
                new_role = st.selectbox("Access Level", ["viewer", "boss", "warehouse_manager"])
                
                role_info = {
                    "viewer": "👁️ **Viewer**: Can only see final products. Perfect for sales staff.",
                    "boss": "👔 **Boss**: Can view all inventory but cannot change stock levels.",
                    "warehouse_manager": "👨‍💼 **Manager**: Full access to everything including user management."
                }
                
                st.info(role_info[new_role])
            
            submitted = st.form_submit_button("➕ Create User", type="primary")
            
            if submitted:
                if new_username and new_password and new_full_name:
                    if len(new_password) < 6:
                        st.error("❌ Password must be at least 6 characters!")
                    else:
                        try:
                            conn = sqlite3.connect('inventory.db')
                            c = conn.cursor()
                            
                            # Check if username exists
                            existing = c.execute("SELECT username FROM users WHERE username = ?", (new_username,)).fetchone()
                            if existing:
                                st.error("❌ Username already exists!")
                            else:
                                password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                                c.execute("INSERT INTO users (username, password_hash, role, full_name, created_date) VALUES (?, ?, ?, ?, ?)",
                                         (new_username, password_hash, new_role, new_full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                                
                                conn.commit()
                                st.success(f"✅ User '{new_username}' created successfully!")
                                st.info(f"🔑 **Login Details:**\nUsername: `{new_username}`\nPassword: `{new_password}`")
                                st.rerun()
                            
                            conn.close()
                            
                        except sqlite3.Error as e:
                            st.error(f"❌ Database error: {str(e)}")
                else:
                    st.error("❌ Please fill in all fields!")
    
    with tab2:
        st.subheader("🗑️ Delete User")
        
        if not users_df.empty:
            # Don't allow deleting yourself
            other_users = users_df[users_df['username'] != st.session_state.username]
            
            if not other_users.empty:
                user_to_delete = st.selectbox("Select user to delete", 
                                            options=other_users['username'].tolist(),
                                            format_func=lambda x: f"{x} - {other_users[other_users['username']==x]['full_name'].iloc[0]} ({other_users[other_users['username']==x]['role'].iloc[0]})")
                
                if user_to_delete:
                    user_info = other_users[other_users['username'] == user_to_delete].iloc[0]
                    
                    st.warning(f"⚠️ **Are you sure you want to delete:**\n\n"
                              f"**Username:** {user_info['username']}\n"
                              f"**Name:** {user_info['full_name']}\n"
                              f"**Role:** {user_info['role']}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🗑️ DELETE USER", type="secondary", use_container_width=True):
                            if st.session_state.get('confirm_delete_user') == user_to_delete:
                                # Delete user
                                conn = sqlite3.connect('inventory.db')
                                c = conn.cursor()
                                c.execute('DELETE FROM users WHERE username = ?', (user_to_delete,))
                                conn.commit()
                                conn.close()
                                
                                st.success(f"🗑️ User '{user_to_delete}' deleted successfully!")
                                if 'confirm_delete_user' in st.session_state:
                                    del st.session_state['confirm_delete_user']
                                st.rerun()
                            else:
                                st.session_state['confirm_delete_user'] = user_to_delete
                                st.error("⚠️ Click DELETE USER again to confirm deletion!")
                    
                    with col2:
                        if st.button("❌ Cancel", use_container_width=True):
                            if 'confirm_delete_user' in st.session_state:
                                del st.session_state['confirm_delete_user']
                            st.rerun()
            else:
                st.info("You are the only user in the system.")
        else:
            st.info("No users found.")
    
    with tab3:
        st.subheader("🔒 Reset Password")
        
        if not users_df.empty:
            other_users = users_df[users_df['username'] != st.session_state.username]
            
            if not other_users.empty:
                user_to_reset = st.selectbox("Select user for password reset", 
                                           options=other_users['username'].tolist(),
                                           format_func=lambda x: f"{x} - {other_users[other_users['username']==x]['full_name'].iloc[0]}")
                
                new_temp_password = st.text_input("New password", type="password", placeholder="New password for user")
                
                if st.button("🔒 Reset Password", type="primary"):
                    if new_temp_password and len(new_temp_password) >= 6:
                        conn = sqlite3.connect('inventory.db')
                        c = conn.cursor()
                        
                        password_hash = hashlib.sha256(new_temp_password.encode()).hexdigest()
                        c.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
                                 (password_hash, user_to_reset))
                        conn.commit()
                        conn.close()
                        
                        st.success(f"🔒 Password reset for '{user_to_reset}'!")
                        st.info(f"**New login details:**\nUsername: `{user_to_reset}`\nPassword: `{new_temp_password}`")
                    else:
                        st.error("❌ Password must be at least 6 characters!")
            else:
                st.info("No other users to reset passwords for.")
    
    # Security tips
    with st.expander("🛡️ Security Tips"):
        st.markdown("""
        ### 🔐 User Management Best Practices:
        - ✅ **Use strong passwords** (at least 8 characters)
        - ✅ **Remove users** who no longer need access
        - ✅ **Review user roles** regularly
        - ✅ **Change default passwords** immediately
        
        ### 👥 Role Guidelines:
        - **👁️ Viewer**: Sales staff, drivers, general employees
        - **👔 Boss**: Management, supervisors (view-only access)
        - **👨‍💼 Manager**: Warehouse staff, inventory controllers
        """)

if __name__ == "__main__":
    main()
