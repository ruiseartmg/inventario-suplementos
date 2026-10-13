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
# TIPOGRAFÍAS, PALETA Y BOTÓN VERDE SÓLIDO (CSS FORZADO)
# ==========================================
st.markdown("""
    <style>
        /* Importar tipografías Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Open+Sans:wght@400;600&display=swap');

        /* Cuerpo de la aplicación */
        .stApp, html, body, [class*="css"], p, span, label, input, select {
            font-family: 'Open Sans', sans-serif !important;
            background-color: #FAFAFA;
            color: #263238;
        }
        
        /* Títulos principales y subtítulos */
        h1, h2, h3, h4, h5, h6, .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-family: 'Montserrat', sans-serif !important;
            color: #263238 !important;
            font-weight: 600;
        }

        /* Forzar botón principal (Registrar Movimiento) en Verde Sólido con Letras Blancas */
        div.stButton > button[kind="primary"], .stButton>button {
            font-family: 'Montserrat', sans-serif !important;
            background-color: #2E7D32 !important;
            color: #FFFFFF !important;
            border-radius: 8px;
            font-weight: 600;
            border: none !important;
            box-shadow: 0 4px 10px rgba(46, 125, 50, 0.3);
            transition: 0.3s;
        }
        div.stButton > button[kind="primary"]:hover, .stButton>button:hover {
            background-color: #1B5E20 !important;
            color: #FFFFFF !important;
        }

        /* Pestañas seleccionadas */
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-size: 15px;
        }
        
        /* Tarjetas de métricas o totales con diseño natural */
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

# Pestañas en la web
pestana1, pestana2, pestana3, pestana4 = st.tabs(["🛒 Registrar Movimiento", "➕ Nuevo Producto", "📋 Resurtido y Pedidos", "📜 Historial"])

with pestana1:
    st.subheader("Registrar Venta o Entrada")
    
    nombres_productos = [p.get("Nombre del Producto") for p in registros_inv if p.get("Nombre del Producto")]
    
    if nombres_productos:
        prod_seleccionado = st.selectbox("Selecciona Producto", nombres_productos)
        cantidad = st.number_input("Cantidad", min_value=0.1, step=0.25, value=1.0)
        tipo = st.radio("Tipo de Movimiento", ["Venta", "Compra (Entrada)"])
        
        if st.button("Registrar Movimiento", type="primary"):
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
                    if "precio directo" in k.lower() or "precio_directo" in k.lower() or "directo" in k.lower():
                        raw_pd = str(v).replace("$", "").replace(",", "").strip()
                        try:
                            precio_directo = float(raw_pd)
                            break
                        except:
                            pass
                if precio_directo == 0.0:
                    precio_directo = precio_venta
                                
                col_stock_idx = 4
                col_surtir_idx = None
                for idx, h in enumerate(headers):
                    h_limpio = h.strip().lower()
                    if "stock" in h_limpio or "cantidad en stock" in h_limpio:
                        col_stock_idx = idx + 1
                    elif "por surtir" in h_limpio or "por_surtir" in h_limpio:
                        col_surtir_idx = idx + 1

                ahora_mexico = datetime.utcnow() - timedelta(hours=6)

                if tipo == "Venta":
                    nuevo_stock = stock_actual - cantidad
                    total_movimiento = cantidad * precio_venta
                    
                    if nuevo_stock < 0:
                        faltante = cantidad - stock_actual
                        vendible = stock_actual
                        nuevo_stock = 0.0 
                        
                        st.error(f"⚠️ Stock insuficiente. Solo tenías {stock_actual} en existencia.")
                        st.warning(f"Se descontaron {vendible} y se mandaron **{faltante} unidades** a la lista de 'Por surtir'.")
                        
                        if col_surtir_idx:
                            hoja_inv.update_cell(row_idx, col_surtir_idx, por_surtir_actual + faltante)
                        
                        hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                        hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Venta", cantidad, total_movimiento])
                        st.rerun()
                    elif stock_actual == 0:
                        st.warning(f"El producto estaba en stock 0. Se han sumado **{cantidad} unidades** directamente a 'Por surtir'.")
                        if col_surtir_idx:
                            hoja_inv.update_cell(row_idx, col_surtir_idx, por_surtir_actual + cantidad)
                        hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Venta", cantidad, total_movimiento])
                        st.rerun()
                    else:
                        hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                        hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Venta", cantidad, total_movimiento])
                        st.success(f"¡Venta guardada con éxito! {cantidad}x {prod_seleccionado}")
                        st.rerun()
                        
                else:
                    nuevo_stock = stock_actual + cantidad
                    total_movimiento = cantidad * precio_directo
                    
                    if por_surtir_actual > 0:
                        if cantidad >= por_surtir_actual:
                            nuevo_por_surtir = 0.0
                            st.success(f"📦 ¡Entrada registrada! +{cantidad} al stock. Se cubrieron los {por_surtir_actual} pendientes de surtir.")
                        else:
                            nuevo_por_surtir = por_surtir_actual - cantidad
                            st.warning(f"📦 ¡Entrada registrada! +{cantidad} al stock. Aún quedan {nuevo_por_surtir} pendientes por surtir.")
                    else:
                        nuevo_por_surtir = 0.0
                        st.success(f"📦 Entrada registrada con éxito: +{cantidad} al stock de {prod_seleccionado}.")
                    
                    hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                    if col_surtir_idx:
                        hoja_inv.update_cell(row_idx, col_surtir_idx, nuevo_por_surtir)
                        
                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Compra", cantidad, total_movimiento])
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
            
        submitted = st.form_submit_button("Guardar Producto en la Nube", type="primary")
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
        
        # === TARJETA DE INVERSIÓN CON TIPOGRAFÍA Y TONO CORPORATIVO ===
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin: 0; color: #2E7D32 !important; font-weight: 600;">💰 Inversión Total Estimada: ${gran_total_inversion:,.2f}</h3>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        if st.button("🖨️ Imprimir / Guardar Reporte en PDF"):
            html_table = df_resurtido.to_html(classes='table')
            html_content = f"""
            <html>
                <head>
                    <title>Reporte de Resurtido y Pedidos - Nature’s Select</title>
                    <style>
                        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Open+Sans:wght@400;600&display=swap');
                        @page {{ size: letter portrait; margin: 1cm; }}
                        body {{ font-family: 'Open Sans', Arial, sans-serif; margin: 0; padding: 10px; color: #263238; }}
                        h2 {{ font-family: 'Montserrat', sans-serif; color: #2E7D32; font-size: 20px; margin-bottom: 5px; font-weight: 600; }}
                        p {{ font-size: 12px; color: #666; margin-top: 0; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                        th, td {{ border: 1px solid #bdc3c7; padding: 8px 10px; text-align: left; font-size: 13px; }}
                        th {{ background-color: #E8F5E9; color: #2E7D32; font-weight: 600; font-family: 'Montserrat', sans-serif; }}
                        .total {{ font-size: 16px; font-weight: bold; margin-top: 20px; color: #2E7D32; font-family: 'Montserrat', sans-serif; }}
                    </style>
                </head>
                <body>
                    <h2>🌿 Nature’s Select - Reporte de Resurtido y Pedidos</h2>
                    <p>Fecha de emisión: {datetime.utcnow().strftime('%d-%m-%Y %H:%M:%S')} (Hora México)</p>
                    {html_table}
                    <div class="total">Inversión Total Estimada: ${gran_total_inversion:,.2f}</div>
                    <script>window.onload = function() {{ window.print(); }};</script>
                </body>
            </html>
            """
            encoded_html = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
            iframe_code = f'<iframe src="data:text/html;base64,{encoded_html}" width="100%" height="450px" style="border:1px solid #ccc; border-radius:5px;"></iframe>'
            st.markdown(iframe_code, unsafe_allow_html=True)
            st.info("💡 Se ha cargado la vista de impresión. Se abrirá automáticamente la ventana para imprimir o guardar como **PDF en tamaño carta**.")
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
