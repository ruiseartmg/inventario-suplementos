import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import os

# Configuración de la página
st.set_page_config(page_title="Gestión de Inventario", page_icon="📦", layout="centered")

# ==========================================
# CONEXIÓN A GOOGLE SHEETS (Segura para la Nube)
# ==========================================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

def conectar_sheets():
    # Si estamos en la nube, lee las credenciales seguras de Streamlit. Si estás en tu PC, busca el archivo local.
    if "GOOGLE_CREDS" in st.secrets:
        creds_dict = dict(st.secrets["GOOGLE_CREDS"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    else:
        ruta_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credenciales.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(ruta_json, SCOPE)
        
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

# ==========================================
# PESTAÑA 1: REGISTRAR MOVIMIENTO
# ==========================================
with pestana1:
    st.subheader("Registrar Venta o Entrada")
    
    # Obtener lista de productos
    nombres_productos = [p.get("Nombre del Producto") for p in registros_inv if p.get("Nombre del Producto")]
    
    prod_seleccionado = st.selectbox("Selecciona Producto", nombres_productos)
    cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
    tipo = st.radio("Tipo de Movimiento", ["Venta", "Compra (Entrada)"])
    
    if st.button("Registrar Movimiento", type="primary"):
        # Buscar el producto en los registros
        row_idx = None
        producto_obj = None
        for i, p in enumerate(registros_inv):
            if p.get("Nombre del Producto") == prod_seleccionado:
                row_idx = i + 2 # Fila en Google Sheets
                producto_obj = p
                break
        
        if producto_obj and row_idx:
            try:
                stock_actual = int(producto_obj.get("Cantidad en Stock", 0))
            except:
                stock_actual = 0
                
            # Buscar precio de forma flexible
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
                # Actualizar Google Sheets
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
    
    # Mostrar tabla limpia
    registros_frescos = hoja_inv.get_all_records()
    st.dataframe(registros_frescos, use_container_width=True)

# ==========================================
# PESTAÑA 2: HISTORIAL
# ==========================================
with pestana2:
    st.subheader("Historial de Transacciones")
    if st.button("🔄 Actualizar Historial"):
        st.rerun()
        
    registros_h = hoja_hist.get_all_records()
    if registros_h:
        st.dataframe(list(reversed(registros_h)), use_container_width=True)
    else:
        st.info("Aún no hay registros en el historial.")