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
# CSS PERSONALIZADO PARA FORZAR EL CENTRADO DE COLUMNAS
# ==========================================
st.markdown("""
    <style>
    /* Centra el texto de las celdas numéricas o específicas en las tablas */
    [data-testid="stTable"] td:nth-child(5), 
    [data-testid="stTable"] th:nth-child(5),
    [data-testid="stDataFrame"] td:nth-child(5), 
    [data-testid="stDataFrame"] th:nth-child(5) {
        text-align: center !important;
    }
    </style>
""", unsafe_allow_html=True)

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
pestana1, pestana2 = st.tabs(["🛒 Registrar Movimiento", "📜 Historial de Movimientos"])

with pestana1:
    st.subheader("Registrar Venta o Entrada")
    
    nombres_productos = [p.get("Nombre del Producto") for p in registros_inv if p.get("Nombre del Producto")]
    
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
            try:
                stock_actual = int(producto_obj.get("Cantidad en Stock", 0))
            except:
                stock_actual = 0
                
            raw_precio = "0"
            for k, v in producto_obj.items():
                if "precio" in k.lower():
                    raw_precio = str(v).replace("$", "").replace(",", "").strip()
                    break
            try:
                precio_venta = float(raw_precio)
            except:
                precio_venta = 0.0
                
            if tipo == "Venta":
                nuevo_stock = stock_actual - cantidad
                mov_texto = "Venta"
            else:
                nuevo_stock = stock_actual + cantidad
                mov_texto = "Compra"
                
            if nuevo_stock < 0:
                st.error("¡No hay suficiente stock en existencia!")
            else:
                hoja_inv.update_cell(row_idx, 4, nuevo_stock)
                
                ahora = datetime.now()
                fecha_str = ahora.strftime("%Y-%m-%d")
                hora_str = ahora.strftime("%H:%M:%S")
                total = cantidad * precio_venta
                
                hoja_hist.append_row([fecha_str, hora_str, prod_seleccionado, mov_texto, cantidad, total])
                
                st.success(f"¡Movimiento guardado con éxito! {mov_texto} de {cantidad}x {prod_seleccionado}")
                st.rerun()

    st.divider()
    st.subheader("Estado Actual del Inventario")
    
    registros_frescos = hoja_inv.get_all_records()
    
    if registros_frescos:
        df_inventario = pd.DataFrame(registros_frescos)
        st.dataframe(df_inventario, use_container_width=True)

with pestana2:
    st.subheader("Historial de Transacciones")
    if st.button("🔄 Actualizar Historial"):
        st.rerun()
        
    registros_h = hoja_hist.get_all_records()
    if registros_h:
        st.dataframe(list(reversed(registros_h)), use_container_width=True)
    else:
        st.info("Aún no hay registros en el historial.")
