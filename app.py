import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import base64
import pandas as pd

# Configuración de la página en modo ancho
st.set_page_config(page_title="Nature’s Select - Inventario", page_icon="🌿", layout="wide")

# ==========================================
# TIPOGRAFÍAS Y ESTILO CSS
# ==========================================
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Open+Sans:wght@400;600&display=swap');

        .stApp, html, body, [class*="css"], p, span, label, input, select {
            font-family: 'Open Sans', sans-serif !important;
            background-color: #FAFAFA;
            color: #263238;
        }
        
        h1, h2, h3, h4, h5, h6, .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-family: 'Montserrat', sans-serif !important;
            color: #263238 !important;
            font-weight: 600;
        }

        div.stButton > button, div.stButton > button * {
            background-color: #2E7D32 !important;
            color: #FFFFFF !important;
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 600;
            border: none !important;
        }
        div.stButton > button {
            border-radius: 8px !important;
            box-shadow: 0 4px 10px rgba(46, 125, 50, 0.3) !important;
            transition: 0.3s !important;
        }
        div.stButton > button:hover, div.stButton > button:hover * {
            background-color: #1B5E20 !important;
            color: #FFFFFF !important;
        }

        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-size: 15px;
        }
        
        .metric-card {
            background-color: #E8F5E9;
            padding: 18px;
            border-radius: 12px;
            border-left: 6px solid #2E7D32;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONEXIÓN A GOOGLE SHEETS
# ==========================================
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def conectar_sheets():
    if "GOOGLE_CREDS" in st.secrets:
        creds_dict = dict(st.secrets["GOOGLE_CREDS"])
        if "private_key_base64" in creds_dict:
            pk_bytes = base64.b64decode(creds_dict["private_key_base64"])
            llave_sucia = pk_bytes.decode("utf-8")
            llave_limpia = llave_sucia.replace("\\n", "\n").replace('"', '').replace("'", "").strip()
            while llave_limpia.startswith("\\"):
                llave_limpia = llave_limpia[1:].strip()
            creds_dict["private_key"] = llave_limpia
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    else:
        ruta_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credenciales.json")
        creds = Credentials.from_service_account_file(ruta_json, scopes=SCOPE)
        
    client = gspread.authorize(creds)
    sheet = client.open("Inventario Suplementos")
    return sheet

@st.cache_resource
def obtener_conexion():
    return conectar_sheets()

try:
    spreadsheet = obtener_conexion()
    hoja_inv = spreadsheet.worksheet("Hoja 1")
    hoja_hist = spreadsheet.worksheet("Historial")
    
    try:
        hoja_pedidos = spreadsheet.worksheet("Pedidos")
    except:
        hoja_pedidos = spreadsheet.add_worksheet(title="Pedidos", rows=100, cols=10)
        hoja_pedidos.append_row(["ID", "Fecha", "Cliente", "Producto", "Cantidad", "Tipo", "Estado"])
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# Funciones de lectura con caché para blindar la app contra el error 429
@st.cache_data(ttl=60)
def cargar_inventario_cache():
    return hoja_inv.get_all_records()

@st.cache_data(ttl=60)
def cargar_pedidos_cache():
    return hoja_pedidos.get_all_records()

@st.cache_data(ttl=60)
def cargar_historial_cache():
    return hoja_hist.get_all_records()

# Botón general para limpiar caché si el usuario quiere forzar datos nuevos
col_master1, col_master2 = st.columns([6, 1])
with col_master2:
    if st.button("🔄 Recargar Nube"):
        st.cache_data.clear()
        st.rerun()

registros_inv = cargar_inventario_cache()
headers = hoja_inv.row_values(1)

if registros_inv:
    registros_inv = sorted(registros_inv, key=lambda x: str(x.get("Nombre del Producto", "")).lower())

# Cabecera con Logotipo
try:
    with open("watermarked_img_3973813175880226978.jpg", "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode()
    st.markdown(
        f"""
        <div style="text-align: center; margin-bottom: 20px; width: 100%;">
            <img src="data:image/jpeg;base64,{encoded_image}" style="width: 100%; max-width: 700px; border-radius: 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.1);">
        </div>
        """,
        unsafe_allow_html=True
    )
except:
    st.title("🌿 Nature’s Select")

st.markdown("---")

# ORDEN DE PESTAÑAS
pestana1, pestana2, pestana3, pestana4, pestana5 = st.tabs([
    "🛒 Pedidos", 
    "📦 Control de Pedidos", 
    "📜 Historial", 
    "📋 Resurtido",
    "➕ Nuevo Producto"
])

with pestana1:
    st.subheader("Registrar Pedido o Entrada")
    
    nombres_productos = [p.get("Nombre del Producto") for p in registros_inv if p.get("Nombre del Producto")]
    
    if nombres_productos:
        prod_seleccionado = st.selectbox("Selecciona Producto", nombres_productos)
        
        nombre_cliente = st.text_input("Nombre del Cliente (Opcional si es compra directa de proveedor):", "")
        cantidad = st.number_input("Cantidad", min_value=0.1, step=0.25, value=1.0)
        tipo = st.radio("Tipo de Transacción", ["Venta / Pedido de Cliente", "Compra (Entrada de Proveedor)"])
        
        if st.button("Registrar en el Sistema") and prod_seleccionado:
            ahora_mexico = datetime.utcnow() - timedelta(hours=6)
            cli_final = nombre_cliente.strip() if nombre_cliente.strip() else "Mostrador / General"
            
            row_idx = None
            producto_obj = None
            inv_actuales = hoja_inv.get_all_records() # Lectura directa para actualización
            for i, p in enumerate(inv_actuales):
                if p.get("Nombre del Producto") == prod_seleccionado:
                    row_idx = i + 2 
                    producto_obj = p
                    break
            
            if producto_obj and row_idx:
                stock_actual = 0.0
                for k, v in producto_obj.items():
                    if "stock" in k.lower() or "cantidad" in k.lower():
                        try:
                            stock_actual = float(str(v).replace(",", ""))
                            break
                        except:
                            continue
                
                precio_venta = 0.0
                for k, v in producto_obj.items():
                    if "precio de venta" in k.lower() or (k.lower().strip() == "precio de venta"):
                        raw_p = str(v).replace("$", "").replace(",", "").strip()
                        try:
                            precio_venta = float(raw_p)
                            break
                        except:
                            pass
                if precio_venta == 0.0:
                    for k, v in producto_obj.items():
                        if "precio" in k.lower() and "directo" not in k.lower():
                            raw_p = str(v).replace("$", "").replace(",", "").strip()
                            try:
                                val_p = float(raw_p)
                                if val_p > 0:
                                    precio_venta = val_p
                                    break
                            except:
                                continue

                col_stock_idx = 4
                for idx, h in enumerate(headers):
                    h_limpio = h.strip().lower()
                    if "stock" in h_limpio or "cantidad en stock" in h_limpio:
                        col_stock_idx = idx + 1
                        break

                if tipo == "Venta / Pedido de Cliente":
                    id_pedido = str(int(datetime.utcnow().timestamp()))
                    hoja_pedidos.append_row([
                        id_pedido, 
                        ahora_mexico.strftime("%d-%m-%Y %H:%M:%S"), 
                        cli_final, 
                        prod_seleccionado, 
                        cantidad, 
                        "Venta", 
                        "Por entregar"
                    ])
                    
                    nuevo_stock = stock_actual - cantidad
                    total_movimiento = cantidad * precio_venta
                    
                    if nuevo_stock < 0:
                        nuevo_stock = 0.0 
                        st.warning(f"⚠️ Stock insuficiente. Se ajustó el stock a 0 y se registró el pedido 'Por entregar'.")
                    else:
                        st.success(f"🛒 ¡Pedido registrado y stock descontado para **{cli_final}**!")
                    
                    hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_final, prod_seleccionado, "Venta", cantidad, total_movimiento])
                    st.cache_data.clear() # Limpiar caché para reflejar cambios
                    st.rerun()
                else:
                    nuevo_stock = stock_actual + cantidad
                    total_movimiento = 0.0
                    
                    hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_final, prod_seleccionado, "Compra", cantidad, total_movimiento])
                    st.success(f"📦 ¡Entrada de proveedor registrada con éxito! +{cantidad} al stock de {prod_seleccionado}.")
                    st.cache_data.clear()
                    st.rerun()
    else:
        st.info("No hay productos registrados todavía.")

    st.divider()
    st.subheader("Estado Actual del Inventario")
    if registros_inv:
        todos_los_pedidos = cargar_pedidos_cache()
        suma_por_entregar = {}
        for p in todos_los_pedidos:
            if p.get("Estado") == "Por entregar":
                prod_p = p.get("Producto")
                cant_p = float(str(p.get("Cantidad", 0)).replace(",", ""))
                suma_por_entregar[prod_p] = suma_por_entregar.get(prod_p, 0.0) + cant_p

        for r in registros_inv:
            n_prod = r.get("Nombre del Producto")
            r["Por entregar"] = suma_por_entregar.get(n_prod, 0.0)

        df_inv = pd.DataFrame(registros_inv)
        
        cols_a_quitar = [c for c in df_inv.columns if "precio directo" in c.lower() or "directo" in c.lower() or "por surtir" in c.lower() or "por_surtir" in c.lower()]
        df_inv = df_inv.drop(columns=cols_a_quitar, errors="ignore")

        for col in df_inv.columns:
            if "precio" in col.lower():
                df_inv[col] = pd.to_numeric(df_inv[col].astype(str).str.replace("$", "").str.replace(",", "").str.strip(), errors="coerce").fillna(0)
                df_inv[col] = df_inv[col].apply(lambda x: f"${x:,.2f}")
            elif "stock" in col.lower() or "cantidad" in col.lower() or "por entregar" in col.lower():
                df_inv[col] = pd.to_numeric(df_inv[col], errors="coerce").fillna(0)
                df_inv[col] = df_inv[col].apply(lambda x: str(int(x)) if x.is_integer() else f"{x:g}")

        columnas_disponibles = list(df_inv.columns)
        col_prod = next((c for c in columnas_disponibles if "nombre" in c.lower()), columnas_disponibles[0])
        col_pres = next((c for c in columnas_disponibles if "presentacion" in c.lower() or "presentación" in c.lower()), None)
        col_stock = next((c for c in columnas_disponibles if "stock" in c.lower() or "cantidad en stock" in c.lower()), None)
        col_precio = next((c for c in columnas_disponibles if "precio de venta" in c.lower()), None)
        
        orden_final = [col_prod]
        if col_pres and col_pres in columnas_disponibles:
            orden_final.append(col_pres)
        if col_stock and col_stock in columnas_disponibles:
            orden_final.append(col_stock)
        
        orden_final.append("Por entregar")
        
        if col_precio and col_precio in columnas_disponibles:
            orden_final.append(col_precio)
            
        for c in columnas_disponibles:
            if c not in orden_final:
                orden_final.append(c)
                
        df_inv = df_inv[[c for c in orden_final if c in df_inv.columns]]

        if "Nombre del Producto" in df_inv.columns:
            df_inv = df_inv.set_index("Nombre del Producto")
            
        st.dataframe(df_inv, use_container_width=True)

with pestana2:
    st.subheader("📦 Control de Pedidos y Entregas")
    st.markdown("Filtra por cliente para ver sus artículos pendientes y gestiona cada entrega de forma rápida.")
    
    pedidos_pendientes = cargar_pedidos_cache()
    pendientes_activos = [p for p in pedidos_pendientes if p.get("Estado") == "Por entregar"]
    
    if pendientes_activos:
        clientes_disponibles = sorted(list(set([p.get("Cliente") for p in pendientes_activos])))
        filtro_cliente = st.selectbox("🔍 Filtrar por Cliente específico:", ["-- Todos los Clientes --"] + clientes_disponibles)
        
        if filtro_cliente != "-- Todos los Clientes --":
            pendientes_activos = [p for p in pendientes_activos if p.get("Cliente") == filtro_cliente]
        
        st.markdown("---")
        
        for idx, ped in enumerate(pendientes_activos):
            col_info, col_btn1, col_btn2 = st.columns([4.5, 1.75, 1.75])
            with col_info:
                st.markdown(f"**👤 {ped.get('Cliente')}**  \n🛍️ **{ped.get('Producto')}** — Cantidad: **{ped.get('Cantidad')}**  \n<span style='color: gray; font-size: 11px;'>ID: {ped.get('ID')} | Fecha: {ped.get('Fecha')}</span>", unsafe_allow_html=True)
            with col_btn1:
                if st.button("✅ Entregar", key=f"entregar_{ped.get('ID')}_{idx}"):
                    todos_p = hoja_pedidos.get_all_records()
                    fila_real = None
                    for i, tp in enumerate(todos_p):
                        if str(tp.get("ID")) == str(ped.get("ID")):
                            fila_real = i + 2
                            break
                    if fila_real:
                        hoja_pedidos.update_cell(fila_real, 7, "Entregado")
                        st.success(f"¡Pedido entregado a {ped.get('Cliente')}!")
                        st.cache_data.clear()
                        st.rerun()
            with col_btn2:
                cancelar_key = f"cancelar_{ped.get('ID')}_{idx}"
                st.markdown("""
                    <style>
                        div[data-testid="column"]:nth-child(3) button {
                            background-color: #C62828 !important;
                        }
                        div[data-testid="column"]:nth-child(3) button:hover {
                            background-color: #B71C1C !important;
                        }
                    </style>
                """, unsafe_allow_html=True)
                
                if st.button("❌ Cancelar", key=cancelar_key):
                    todos_p = hoja_pedidos.get_all_records()
                    fila_real = None
                    for i, tp in enumerate(todos_p):
                        if str(tp.get("ID")) == str(ped.get("ID")):
                            fila_real = i + 2
                            break
                    if fila_real:
                        hoja_pedidos.update_cell(fila_real, 7, "Cancelado")
                        
                        prod_ped = ped.get("Producto")
                        cant_ped = float(ped.get("Cantidad"))
                        
                        row_inv_idx = None
                        prod_obj = None
                        inv_actuales = hoja_inv.get_all_records()
                        for i, inv_item in enumerate(inv_actuales):
                            if inv_item.get("Nombre del Producto") == prod_ped:
                                row_inv_idx = i + 2
                                prod_obj = inv_item
                                break
                        
                        if prod_obj and row_inv_idx:
                            st_act = float(str(prod_obj.get("Cantidad en Stock", 0)).replace(",", ""))
                            col_st_idx = 4
                            for idx_h, h_name in enumerate(headers):
                                if "stock" in h_name.lower():
                                    col_st_idx = idx_h + 1
                                    break
                            
                            nuevo_st = st_act + cant_ped
                            hoja_inv.update_cell(row_inv_idx, col_st_idx, nuevo_st)
                            
                        st.warning(f"Pedido cancelado. Se devolvieron **{cant_ped} unidades** de {prod_ped} al inventario.")
                        st.cache_data.clear()
                        st.rerun()
            st.divider()
    else:
        st.info("No hay productos 'Por entregar' a clientes en este momento.")

with pestana3:
    st.subheader("Historial de Transacciones")
    
    registros_h = cargar_historial_cache()
    if registros_h:
        df_hist = pd.DataFrame(list(reversed(registros_h)))
        
        if "Cliente" not in df_hist.columns:
            df_hist.insert(2, "Cliente", "General / Mostrador")
            
        if "Producto" in df_hist.columns:
            df_hist = df_hist.set_index("Producto")
            
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Aún no hay registros en el historial.")

with pestana4:
    st.subheader("📋 Sugerencia de Pedido (Por Surtir con Proveedor) y Costos")
    st.markdown("Consulta el pedido sugerido al proveedor, el costo estimado por artículo y el total a invertir.")
    
    reg_hist_actuales = cargar_historial_cache()
    
    if registros_inv:
        df_h = pd.DataFrame(reg_hist_actuales) if reg_hist_actuales else pd.DataFrame()
        promedios_dict = {}
        
        if not df_h.empty and "Producto" in df_h.columns and "Cantidad" in df_h.columns and "Fecha" in df_h.columns:
            if "Compra/Venta" in df_h.columns:
                df_ventas = df_h[df_h["Compra/Venta"] == "Venta"].copy()
            else:
                df_ventas = df_h.copy()
                
            if not df_ventas.empty:
                try:
                    df_ventas["Mes"] = df_ventas["Fecha"].str.slice(3, 10)
                    df_ventas["Cantidad"] = pd.to_numeric(df_ventas["Cantidad"], errors="coerce").fillna(0)
                    totales_prod_mes = df_ventas.groupby(["Producto", "Mes"])["Cantidad"].sum().reset_index()
                    promedios = totales_prod_mes.groupby("Producto")["Cantidad"].mean().reset_index()
                    for _, row in promedios.iterrows():
                        promedios_dict[row["Producto"]] = float(row["Cantidad"])
                except:
                    pass

        lista_resurtido = []
        gran_total_inversion = 0.0

        for p in registros_inv:
            nombre = p.get("Nombre del Producto", "")
            stock = float(str(p.get("Cantidad en Stock", 0) or 0).replace(",", ""))
            
            todos_los_pedidos_res = cargar_pedidos_cache()
            por_entregar_val = 0.0
            for tp in todos_los_pedidos_res:
                if tp.get("Estado") == "Por entregar" and tp.get("Producto") == nombre:
                    por_entregar_val += float(str(tp.get("Cantidad", 0)).replace(",", ""))
            
            p_directo = 0.0
            for k, v in p.items():
                if "precio directo" in k.lower() or "directo" in k.lower():
                    raw_pd = str(v).replace("$", "").replace(",", "").strip()
                    try:
                        p_directo = float(raw_pd)
                        break
                    except:
                        pass
            if p_directo == 0.0:
                for k, v in p.items():
                    if "precio" in k.lower():
                        raw_pd = str(v).replace("$", "").replace(",", "").strip()
                        try:
                            val_p = float(raw_pd)
                            if val_p > 0:
                                p_directo = val_p
                                break
                        except:
                            continue

            promedio_mes_val = promedios_dict.get(nombre, 0.0)
            sugerido_pedido = por_entregar_val + promedio_mes_val
            costo_total_producto = sugerido_pedido * p_directo
            gran_total_inversion += costo_total_producto
            
            stock_str = str(int(stock)) if stock.is_integer() else f"{stock:g}"
            surtir_str = str(int(por_entregar_val)) if por_entregar_val.is_integer() else f"{por_entregar_val:g}"
            prom_str = str(int(promedio_mes_val)) if promedio_mes_val.is_integer() else f"{promedio_mes_val:g}"
            sugerido_str = str(int(sugerido_pedido)) if sugerido_pedido.is_integer() else f"{sugerido_pedido:g}"
            
            lista_resurtido.append({
                "Producto": nombre,
                "Stock Actual": stock_str,
                "Por Entregar (Clientes)": surtir_str,
                "Promedio/Mes": prom_str,
                "Sugerido": sugerido_str,
                "Costo Unit.": f"${p_directo:,.2f}",
                "Inversión Est.": f"${costo_total_producto:,.2f}"
            })
            
        df_resurtido = pd.DataFrame(lista_resurtido)
        
        if "Producto" in df_resurtido.columns:
            df_resurtido = df_resurtido.set_index("Producto")
            
        st.dataframe(df_resurtido, use_container_width=True)
        
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin: 0; color: #2E7D32 !important; font-weight: 600;">💰 Inversión Total Estimada: ${gran_total_inversion:,.2f}</h3>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No hay productos en el inventario.")

with pestana5:
    st.subheader("Agregar un Producto Nuevo al Inventario")
    with st.form("form_nuevo_producto"):
        nuevo_nombre = st.text_input("Nombre del Producto * (ej. Miel 500 g, Granola 1 kg)")
        col1, col2 = st.columns(2)
        with col1:
            nueva_presentacion = st.text_input("Presentación (ej. 500 g, 1 kg, frasco)")
            stock_inicial = st.number_input("Cantidad Inicial en Stock", min_value=0.0, step=0.25, value=0.0)
            precio_dir = st.number_input("Precio Directo", min_value=0.0, step=1.0, value=0.0)
        with col2:
            nueva_marca = st.text_input("Marca")
            precio_ven = st.number_input("Precio de Venta", min_value=0.0, step=1.0, value=0.0)
            categoria = st.text_input("Categoría")
            
        submitted = st.form_submit_button("Guardar Producto en la Nube")
        if submitted:
            if not nuevo_nombre.strip():
                st.error("¡El nombre del producto es obligatorio!")
            else:
                try:
                    nueva_fila = [""] * len(headers)
                    datos_ingresados = {
                        "Nombre del Producto": nuevo_nombre,
                        "Presentacion": nueva_presentacion,
                        "Marca": nueva_marca,
                        "Cantidad en Stock": stock_inicial,
                        "Precio Directo": precio_dir,
                        "Precio de Venta": precio_ven,
                        "Categoría": categoria,
                        "Categoria": categoria
                    }
                    for idx, header in enumerate(headers):
                        if header in datos_ingresados:
                            nueva_fila[idx] = datos_ingresados[header]
                    hoja_inv.append_row(nueva_fila)
                    st.success(f"¡El producto '{nuevo_nombre}' se ha dado de alta correctamente!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
