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

registros_inv = hoja_inv.get_all_records()
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

pestana1, pestana2, pestana3, pestana4, pestana5 = st.tabs([
    "🛒 Pedidos y Ventas", 
    "➕ Nuevo Producto", 
    "📋 Resurtido y Pedidos", 
    "📜 Historial",
    "📦 Control de Pedidos"
])

with pestana1:
    st.subheader("Registrar Pedido o Entrada")
    
    nombres_productos = [p.get("Nombre del Producto") for p in registros_inv if p.get("Nombre del Producto")]
    
    if nombres_productos:
        # Buscador rápido
        busqueda = st.text_input("🔍 Buscar producto por nombre (escribe para filtrar):", "")
        productos_filtrados = [p for p in nombres_productos if busqueda.lower() in p.lower()]
        
        if not productos_filtrados:
            st.warning("No se encontraron productos con ese nombre.")
            prod_seleccionado = None
        else:
            prod_seleccionado = st.selectbox("Selecciona Producto de la lista", productos_filtrados)
        
        nombre_cliente = st.text_input("Nombre del Cliente (Opcional si es compra directa de proveedor):", "")
        cantidad = st.number_input("Cantidad", min_value=0.1, step=0.25, value=1.0)
        tipo = st.radio("Tipo de Transacción", ["Venta / Pedido de Cliente", "Compra (Entrada de Proveedor)"])
        
        if st.button("Registrar en el Sistema") and prod_seleccionado:
            ahora_mexico = datetime.utcnow() - timedelta(hours=6)
            
            # Ubicar índices y datos del producto en Inventario
            row_idx = None
            producto_obj = None
            for i, p in enumerate(hoja_inv.get_all_records()):
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
                
                por_surtir_actual = 0.0
                for k, v in producto_obj.items():
                    if "por surtir" in k.lower() or "por_surtir" in k.lower():
                        try:
                            por_surtir_actual = float(str(v or 0).replace(",", ""))
                        except:
                            pass
                
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

                precio_directo = 0.0
                for k, v in producto_obj.items():
                    if "precio directo" in k.lower() or "directo" in k.lower():
                        raw_pd = str(v).replace("$", "").replace(",", "").strip()
                        try:
                            precio_directo = float(raw_pd)
                            break
                        except:
                            pass
                if precio_directo == 0.0:
                    precio_directo = precio_venta or 1.0

                col_stock_idx = 4
                col_surtir_idx = None
                for idx, h in enumerate(headers):
                    h_limpio = h.strip().lower()
                    if "stock" in h_limpio or "cantidad en stock" in h_limpio:
                        col_stock_idx = idx + 1
                    elif "por surtir" in h_limpio or "por_surtir" in h_limpio:
                        col_surtir_idx = idx + 1

                if tipo == "Venta / Pedido de Cliente":
                    # 1. Registrar el pedido en la hoja de Pedidos
                    id_pedido = str(int(datetime.utcnow().timestamp()))
                    hoja_pedidos.append_row([
                        id_pedido, 
                        ahora_mexico.strftime("%d-%m-%Y %H:%M:%S"), 
                        nombre_cliente if nombre_cliente.strip() else "Mostrador / General", 
                        prod_seleccionado, 
                        cantidad, 
                        "Venta", 
                        "Pendiente de Entrega"
                    ])
                    
                    # 2. Afectar inventario de inmediato (Apartado / Descuento)
                    nuevo_stock = stock_actual - cantidad
                    total_movimiento = cantidad * precio_venta
                    
                    if nuevo_stock < 0:
                        faltante = cantidad - stock_actual
                        vendible = stock_actual
                        nuevo_stock = 0.0 
                        st.warning(f"⚠️ Stock insuficiente. Se descontaron {vendible} y se mandaron **{faltante} unidades** a 'Por surtir'.")
                        if col_surtir_idx:
                            hoja_inv.update_cell(row_idx, col_surtir_idx, por_surtir_actual + faltante)
                    else:
                        st.success(f"🛒 ¡Pedido registrado y stock descontado para **{nombre_cliente or 'General'}**!")
                    
                    hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Venta", cantidad, total_movimiento])
                    st.rerun()
                else:
                    # Compra de proveedor
                    nuevo_stock = stock_actual + cantidad
                    total_movimiento = cantidad * precio_directo
                    nuevo_por_surtir = max(0.0, por_surtir_actual - cantidad) if por_surtir_actual > 0 else 0.0
                    
                    hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                    if col_surtir_idx:
                        hoja_inv.update_cell(row_idx, col_surtir_idx, nuevo_por_surtir)
                        
                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Compra", cantidad, total_movimiento])
                    st.success(f"📦 ¡Entrada de proveedor registrada con éxito! +{cantidad} al stock de {prod_seleccionado}.")
                    st.rerun()
    else:
        st.info("No hay productos registrados todavía.")

    st.divider()
    st.subheader("Estado Actual del Inventario")
    if registros_inv:
        df_inv = pd.DataFrame(registros_inv)
        for col in df_inv.columns:
            if "precio" in col.lower():
                df_inv[col] = pd.to_numeric(df_inv[col].astype(str).str.replace("$", "").str.replace(",", "").str.strip(), errors="coerce").fillna(0)
                df_inv[col] = df_inv[col].apply(lambda x: f"${x:,.2f}")
            elif "stock" in col.lower() or "cantidad" in col.lower() or "surtir" in col.lower():
                df_inv[col] = pd.to_numeric(df_inv[col], errors="coerce").fillna(0)
                df_inv[col] = df_inv[col].apply(lambda x: str(int(x)) if x.is_integer() else f"{x:g}")
        
        if "Nombre del Producto" in df_inv.columns:
            df_inv = df_inv.set_index("Nombre del Producto")
            
        st.dataframe(df_inv, use_container_width=True)

with pestana2:
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
                        "Categoria": categoria,
                        "Por surtir": 0
                    }
                    for idx, header in enumerate(headers):
                        if header in datos_ingresados:
                            nueva_fila[idx] = datos_ingresados[header]
                    hoja_inv.append_row(nueva_fila)
                    st.success(f"¡El producto '{nuevo_nombre}' se ha dado de alta correctamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

with pestana3:
    st.subheader("📋 Sugerencia de Pedido, Costos y Resurtido")
    st.markdown("Consulta el pedido sugerido, el costo estimado por artículo y el total a invertir.")
    
    if st.button("🔄 Actualizar Datos de Pedidos"):
        st.rerun()
        
    reg_hist_actuales = hoja_hist.get_all_records()
    
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
            
            por_surtir = 0.0
            for k, v in p.items():
                if "por surtir" in k.lower() or "por_surtir" in k.lower():
                    try:
                        por_surtir = float(str(v or 0).replace(",", ""))
                    except:
                        pass
            
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
            sugerido_pedido = por_surtir + promedio_mes_val
            costo_total_producto = sugerido_pedido * p_directo
            gran_total_inversion += costo_total_producto
            
            stock_str = str(int(stock)) if stock.is_integer() else f"{stock:g}"
            surtir_str = str(int(por_surtir)) if por_surtir.is_integer() else f"{por_surtir:g}"
            prom_str = str(int(promedio_mes_val)) if promedio_mes_val.is_integer() else f"{promedio_mes_val:g}"
            sugerido_str = str(int(sugerido_pedido)) if sugerido_pedido.is_integer() else f"{sugerido_pedido:g}"
            
            lista_resurtido.append({
                "Producto": nombre,
                "Stock Actual": stock_str,
                "Por Surtir": surtir_str,
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

with pestana4:
    st.subheader("Historial de Transacciones")
    if st.button("🔄 Actualizar Historial"):
        st.rerun()
        
    registros_h = hoja_hist.get_all_records()
    if registros_h:
        df_hist = pd.DataFrame(list(reversed(registros_h)))
        if "Producto" in df_hist.columns:
            df_hist = df_hist.set_index("Producto")
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Aún no hay registros en el historial.")

with pestana5:
    st.subheader("📦 Control de Pedidos y Entregas")
    st.markdown("Aquí gestionas los pedidos activos. Si un pedido se **Entrega**, se marca como completado; si se **Cancela**, el producto regresa en automático al inventario.")
    
    if st.button("🔄 Actualizar Lista de Pedidos"):
        st.rerun()
        
    pedidos_pendientes = hoja_pedidos.get_all_records()
    pendientes_activos = [p for p in pedidos_pendientes if p.get("Estado") == "Pendiente de Entrega"]
    
    if pendientes_activos:
        for idx, ped in enumerate(pendientes_activos):
            col1, col2, col3, col4, col5 = st.columns([2, 3, 2, 2, 2])
            with col1:
                st.write(f"**Cliente:** {ped.get('Cliente')}")
                st.caption(f"Fecha: {ped.get('Fecha')}")
            with col2:
                st.write(f"**Producto:** {ped.get('Producto')}")
                st.write(f"**Cantidad:** {ped.get('Cantidad')}")
            with col3:
                st.write(f"**Estado:** 🕒 Pendiente")
            with col4:
                if st.button(f"✅ Entregar #{ped.get('ID')}", key=f"entregar_{ped.get('ID')}_{idx}"):
                    todos_p = hoja_pedidos.get_all_records()
                    fila_real = None
                    for i, tp in enumerate(todos_p):
                        if str(tp.get("ID")) == str(ped.get("ID")):
                            fila_real = i + 2
                            break
                    if fila_real:
                        hoja_pedidos.update_cell(fila_real, 7, "Entregado")
                        st.success(f"¡Pedido de {ped.get('Cliente')} marcado como Entregado!")
                        st.rerun()
            with col5:
                if st.button(f"❌ Cancelar #{ped.get('ID')}", key=f"cancelar_{ped.get('ID')}_{idx}"):
                    todos_p = hoja_pedidos.get_all_records()
                    fila_real = None
                    for i, tp in enumerate(todos_p):
                        if str(tp.get("ID")) == str(ped.get("ID")):
                            fila_real = i + 2
                            break
                    if fila_real:
                        # 1. Marcar como Cancelado en la hoja Pedidos
                        hoja_pedidos.update_cell(fila_real, 7, "Cancelado")
                        
                        # 2. Devolver la mercancía al inventario en automático
                        prod_ped = ped.get("Producto")
                        cant_ped = float(ped.get("Cantidad"))
                        
                        row_inv_idx = None
                        prod_obj = None
                        for i, inv_item in enumerate(hoja_inv.get_all_records()):
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
                            
                        st.warning(f"Pedido cancelado. Se han devuelto **{cant_ped} unidades** de {prod_ped} al inventario.")
                        st.rerun()
            st.divider()
    else:
        st.info("No hay pedidos pendientes de entrega en este momento.")
