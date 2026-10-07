import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
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
            
            # Limpieza extrema: arreglar saltos de línea literales y quitar comillas
            llave_limpia = llave_sucia.replace("\\n", "\n").replace('"', '').replace("'", "").strip()
            
            # Si por error se coló una barra invertida (\) al inicio, la quitamos
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

# Cargar datos actuales
registros_inv = hoja_inv.get_all_records()

st.title("📦 Productos Naturales - Inventario")

# Pestañas en la web
pestana1, pestana2, pestana3 = st.tabs(["🛒 Registrar Movimiento", "➕ Nuevo Producto", "📜 Historial de Movimientos"])

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
                # Buscamos el stock real sin importar la posición de la columna
                stock_actual = 0
                for k, v in producto_obj.items():
                    if "stock" in k.lower() or "cantidad" in k.lower():
                        try:
                            # Evitamos tomar celdas que sean otra cosa
                            val_temp = int(v)
                            stock_actual = val_temp
                            break
                        except:
                            continue
                
                # Buscamos el precio de venta de forma segura
                precio_venta = 0.0
                for k, v in producto_obj.items():
                    if "precio de venta" in k.lower() or (k.lower().strip() == "precio de venta"):
                        raw_precio = str(v).replace("$", "").replace(",", "").strip()
                        try:
                            precio_venta = float(raw_precio)
                            break
                        except:
                            pass
                
                # Si falló el específico, buscamos cualquiera que tenga la palabra precio y no sea cero
                if precio_venta == 0.0:
                    for k, v in producto_obj.items():
                        if "precio" in k.lower():
                            raw_precio = str(v).replace("$", "").replace(",", "").strip()
                            try:
                                val_p = float(raw_precio)
                                if val_p > 0:
                                    precio_venta = val_p
                                    break
                            except:
                                continue
                    
                if tipo == "Venta":
                    nuevo_stock = stock_actual - cantidad
                    mov_texto = "Venta"
                else:
                    nuevo_stock = stock_actual + cantidad
                    mov_texto = "Compra"
                    
                if nuevo_stock < 0:
                    st.error("¡No hay suficiente stock en existencia!")
                else:
                    # Encontramos el número exacto de la columna de stock para actualizarla bien
                    headers = hoja_inv.row_values(1)
                    col_stock_idx = 4 # Valor por defecto por si acaso
                    for idx, h in enumerate(headers):
                        if "stock" in h.lower() or "cantidad en stock" in h.lower():
                            col_stock_idx = idx + 1
                            break
                            
                    hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                    
                    ahora = datetime.now()
                    fecha_str = ahora.strftime("%Y-%m-%d")
                    hora_str = ahora.strftime("%H:%M:%S")
                    total = cantidad * precio_venta
                    
                    hoja_hist.append_row([fecha_str, hora_str, prod_seleccionado, mov_texto, cantidad, total])
                    
                    st.success(f"¡Movimiento guardado con éxito! {mov_texto} de {cantidad}x {prod_seleccionado}")
                    st.rerun()
    else:
        st.info("No hay productos registrados todavía. Agrega uno en la pestaña de 'Nuevo Producto'.")

    st.divider()
    st.subheader("Estado Actual del Inventario")
    
    registros_frescos = hoja_inv.get_all_records()
    if registros_frescos:
        df_inventario = pd.DataFrame(registros_frescos)
        st.dataframe(df_inventario, use_container_width=True)

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
                    headers = hoja_inv.row_values(1)
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
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar el producto: {e}")

with pestana3:
    st.subheader("Historial de Transacciones")
    if st.button("🔄 Actualizar Historial"):
        st.rerun()
        
    registros_h = hoja_hist.get_all_records()
    if registros_h:
        st.dataframe(list(reversed(registros_h)), use_container_width=True)
    else:
        st.info("Aún no hay registros en el historial.")
