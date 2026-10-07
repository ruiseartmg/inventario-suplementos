import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import base64
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Gestión de Inventario", page_icon="📦", layout="centered")

# ==========================================
# CONEXIÓN A GOOGLE SHEETS (Método Base64 + Limpieza Extrema)
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

# Cargar datos actuales y encabezados
registros_inv = hoja_inv.get_all_records()
headers = hoja_inv.row_values(1)

st.title("📦 Productos Naturales - Inventario")

# Pestañas en la web
pestana1, pestana2, pestana3, pestana4 = st.tabs(["🛒 Registrar Movimiento", "➕ Nuevo Producto", "📋 Resurtido y Pedidos", "📜 Historial"])

with pestana1:
    st.subheader("Registrar Venta o Entrada")
    
    nombres_productos = [p.get("Nombre del Producto") for p in registros_inv if p.get("Nombre del Producto")]
    
    if nombres_productos:
        prod_seleccionado = st.selectbox("Selecciona Producto", nombres_productos)
        cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
        tipo = st.radio("Tipo de Movimiento", ["Venta", "Compra (Entrada)"])
        
        if st.button("Registrar Movimiento", type="primary"):
            row_idx = None
            producto_obj = None
            for i, p in enumerate(registros_inv):
                if p.get("Nombre del Producto") == prod_seleccionado:
                    row_idx = i + 2 
                    producto_obj = p
                    break
            
            if producto_obj and row_idx:
                # Stock actual
                stock_actual = 0
                for k, v in producto_obj.items():
                    if "stock" in k.lower() or "cantidad" in k.lower():
                        try:
                            stock_actual = int(v)
                            break
                        except:
                            continue
                
                # Por surtir actual
                por_surtir_actual = 0
                for k, v in producto_obj.items():
                    if "por surtir" in k.lower() or "por_surtir" in k.lower():
                        try:
                            por_surtir_actual = int(v or 0)
                        except:
                            pass
                
                # Precio de venta
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
                        if "precio" in k.lower():
                            raw_p = str(v).replace("$", "").replace(",", "").strip()
                            try:
                                val_p = float(raw_p)
                                if val_p > 0:
                                    precio_venta = val_p
                                    break
                            except:
                                continue
                                
                # Ubicar índices exactos de columnas en Google Sheets
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
                    
                    if nuevo_stock < 0:
                        faltante = cantidad - stock_actual
                        vendible = stock_actual
                        nuevo_stock = 0 
                        
                        st.error(f"⚠️ Stock insuficiente. Solo tenías {stock_actual} en existencia.")
                        st.warning(f"Se descontaron {vendible} y se mandaron **{faltante} piezas** a la lista de 'Por surtir'.")
                        
                        if col_surtir_idx:
                            hoja_inv.update_cell(row_idx, col_surtir_idx, por_surtir_actual + faltante)
                        
                        hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                        hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Venta", cantidad, cantidad * precio_venta])
                        st.rerun()
                    elif stock_actual == 0:
                        st.warning(f"El producto estaba en stock 0. Se han sumado **{cantidad} piezas** directamente a 'Por surtir'.")
                        if col_surtir_idx:
                            hoja_inv.update_cell(row_idx, col_surtir_idx, por_surtir_actual + cantidad)
                        hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Venta", cantidad, cantidad * precio_venta])
                        st.rerun()
                    else:
                        hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                        hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Venta", cantidad, cantidad * precio_venta])
                        st.success(f"¡Venta guardada con éxito! {cantidad}x {prod_seleccionado}")
                        st.rerun()
                        
                else:  # === COMPRA / ENTRADA DE MATERIAL ===
                    nuevo_stock = stock_actual + cantidad
                    
                    if por_surtir_actual > 0:
                        if cantidad >= por_surtir_actual:
                            nuevo_por_surtir = 0
                            st.success(f"📦 ¡Entrada registrada! +{cantidad} piezas al stock. Se cubrieron los {por_surtir_actual} pendientes de surtir.")
                        else:
                            nuevo_por_surtir = por_surtir_actual - cantidad
                            st.warning(f"📦 ¡Entrada registrada! +{cantidad} piezas al stock. Aún quedan {nuevo_por_surtir} pendientes por surtir.")
                    else:
                        nuevo_por_surtir = 0
                        st.success(f"📦 Entrada registrada con éxito: +{cantidad} piezas al stock de {prod_seleccionado}.")
                    
                    hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                    if col_surtir_idx:
                        hoja_inv.update_cell(row_idx, col_surtir_idx, nuevo_por_surtir)
                        
                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), prod_seleccionado, "Compra", cantidad, 0])
                    st.rerun()
    else:
        st.info("No hay productos registrados todavía.")

    st.divider()
    st.subheader("Estado Actual del Inventario")
    registros_frescos = hoja_inv.get_all_records()
    if registros_frescos:
        df_inv = pd.DataFrame(registros_frescos)
        # Formatear columnas de precios y cantidades numéricas limpias
        for col in df_inv.columns:
            if "precio" in col.lower():
                df_inv[col] = pd.to_numeric(df_inv[col].astype(str).str.replace("$", "").str.replace(",", "").str.strip(), errors="coerce").fillna(0)
                df_inv[col] = df_inv[col].apply(lambda x: f"${x:,.2f}")
            elif "stock" in col.lower() or "cantidad" in col.lower() or "surtir" in col.lower():
                df_inv[col] = pd.to_numeric(df_inv[col], errors="coerce").fillna(0).astype(int)
        st.dataframe(df_inv, use_container_width=True)

with pestana2:
    st.subheader("Agregar un Producto Nuevo al Inventario")
    with st.form("form_nuevo_producto"):
        nuevo_nombre = st.text_input("Nombre del Producto *")
        col1, col2 = st.columns(2)
        with col1:
            nueva_presentacion = st.text_input("Presentación (ej. 500 g, 60 cápsulas)")
            stock_inicial = st.number_input("Cantidad Inicial en Stock", min_value=0, step=1, value=0)
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
    st.subheader("📋 Sugerencia de Pedido y Resurtido")
    st.markdown("Aquí puedes ver lo que tienes pendiente de surtir a clientes más el promedio de venta mensual para calcular tu pedido ideal.")
    
    if st.button("🔄 Actualizar Datos de Pedidos"):
        st.rerun()
        
    reg_inv_actuales = hoja_inv.get_all_records()
    reg_hist_actuales = hoja_hist.get_all_records()
    
    if reg_inv_actuales:
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
                    totales_prod_mes = df_ventas.groupby(["Producto", "Mes"])["Cantidad"].sum().reset_index()
                    promedios = totales_prod_mes.groupby("Producto")["Cantidad"].mean().reset_index()
                    for _, row in promedios.iterrows():
                        promedios_dict[row["Producto"]] = round(row["Cantidad"], 1)
                except:
                    pass

        lista_resurtido = []
        for p in reg_inv_actuales:
            nombre = p.get("Nombre del Producto", "")
            stock = int(p.get("Cantidad en Stock", 0) or 0)
            
            por_surtir = 0
            for k, v in p.items():
                if "por surtir" in k.lower() or "por_surtir" in k.lower():
                    try:
                        por_surtir = int(v or 0)
                    except:
                        pass
            
            promedio_mes = promedios_dict.get(nombre, 0.0)
            sugerido_pedido = por_surtir + int(promedio_mes)
            
            lista_resurtido.append({
                "Producto": nombre,
                "Stock Actual": stock,
                "Por Surtir (Pendiente)": por_surtir,
                "Promedio Venta / Mes": promedio_mes,
                "Sugerido a Pedir": sugerido_pedido
            })
            
        df_resurtido = pd.DataFrame(lista_resurtido)
        st.dataframe(df_resurtido, use_container_width=True)
    else:
        st.info("No hay productos en el inventario.")

with pestana4:
    st.subheader("Historial de Transacciones")
    if st.button("🔄 Actualizar Historial"):
        st.rerun()
        
    registros_h = hoja_hist.get_all_records()
    if registros_h:
        st.dataframe(list(reversed(registros_h)), use_container_width=True)
    else:
        st.info("Aún no hay registros en el historial.")
