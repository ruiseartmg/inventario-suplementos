import io
import base64
import os
from datetime import datetime, timedelta
import urllib.parse

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

st.set_page_config(page_title="Nature’s Select - Inventario", page_icon="🌿", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Open+Sans:wght@400;600&display=swap');

        html, body, .stApp {
            font-family: 'Open Sans', sans-serif !important;
            background-color: #FAFAFA !important;
            color: #263238;
        }
        
        h1, h2, h3, h4, h5, h6, .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-family: 'Montserrat', sans-serif !important;
            color: #263238 !important;
            font-weight: 600;
        }

        button[kind="secondary"], button[kind="formSubmit"] {
            background-color: #2E7D32 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-family: 'Montserrat', sans-serif !important;
            box-shadow: 0 4px 6px rgba(46, 125, 50, 0.2) !important;
            min-height: 42px !important;
            height: auto !important;
            width: 100% !important;
            padding: 8px 12px !important;
            transition: 0.2s !important;
        }
        button[kind="secondary"]:hover, button[kind="formSubmit"]:hover {
            background-color: #1B5E20 !important;
        }

        button[kind="primary"] {
            background-color: #C62828 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-family: 'Montserrat', sans-serif !important;
            box-shadow: 0 4px 6px rgba(198, 40, 40, 0.2) !important;
            min-height: 42px !important;
            height: auto !important;
            width: 100% !important;
            padding: 8px 12px !important;
            transition: 0.2s !important;
        }
        button[kind="primary"]:hover {
            background-color: #B71C1C !important;
        }
        
        button[kind="secondary"] *, button[kind="primary"] *, button[kind="formSubmit"] * {
            color: #FFFFFF !important;
        }

        .metric-card { background-color: #E8F5E9; padding: 18px; border-radius: 12px; border-left: 6px solid #2E7D32; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
        .stock-badge { background-color: #E8F5E9; color: #1B5E20; padding: 8px 14px; border-radius: 8px; font-weight: 600; display: inline-block; margin-bottom: 15px; border: 1px solid #C8E6C9; }
        .deficit-alert-card { background-color: #FFEBEE; padding: 15px; border-radius: 10px; border-left: 6px solid #C62828; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }
        .surtible-alert-card { background-color: #E8F5E9; padding: 15px; border-radius: 10px; border-left: 6px solid #2E7D32; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }
        .por-pagar-card { background-color: #FFF8E1; padding: 15px; border-radius: 10px; border-left: 6px solid #F57F17; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }
    </style>
""", unsafe_allow_html=True)

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def obtener_conexion():
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

@st.cache_data(ttl=600)
def cargar_inventario_cache():
    return hoja_inv.get_all_records()

@st.cache_data(ttl=600)
def cargar_pedidos_cache():
    return hoja_pedidos.get_all_records()

@st.cache_data(ttl=600)
def cargar_historial_cache():
    return hoja_hist.get_all_records()

def reasignar_deficit_si_hay_stock(prod_nombre):
    try:
        inv_actuales = hoja_inv.get_all_records()
        row_inv_idx = None
        stock_fisc = 0.0
        col_st_idx = 2
        
        headers_inv = list(inv_actuales[0].keys()) if inv_actuales else []
        for idx_h, h_name in enumerate(headers_inv):
            if "stock" in h_name.lower() or "cantidad" in h_name.lower():
                col_st_idx = idx_h + 1
                break
        
        for i, inv_item in enumerate(inv_actuales):
            if str(inv_item.get("Nombre del Producto", "")).strip() == prod_nombre:
                row_inv_idx = i + 2
                for k, v in inv_item.items():
                    if "stock" in k.lower() or "cantidad" in k.lower():
                        try: stock_fisc = float(str(v).replace(",", ""))
                        except: pass
                break
        
        if not row_inv_idx or stock_fisc <= 0:
            return

        todos_p = hoja_pedidos.get_all_records()
        for idx_p, tp in enumerate(todos_p):
            if str(tp.get("Producto", "")).strip() == str(prod_nombre).strip() and tp.get("Estado") == "Déficit":
                cant_def = float(str(tp.get("Cantidad", 0)).replace(",", ""))
                if stock_fisc >= cant_def:
                    stock_fisc -= cant_def
                    hoja_inv.update_cell(row_inv_idx, col_st_idx, stock_fisc)
                    fila_ped_real = idx_p + 2
                    hoja_pedidos.update_cell(fila_ped_real, 7, "Por entregar")
                    break
    except Exception as e:
        print(f"Error en reasignación: {e}")

try:
    registros_inv = cargar_inventario_cache()
    headers = list(registros_inv[0].keys()) if registros_inv else ["Nombre del Producto", "Cantidad en Stock", "Precio de Venta", "Nivel Mínimo de Alerta", "Precio Directo", "Categoría."]
    if registros_inv:
        registros_inv = sorted(registros_inv, key=lambda x: str(x.get("Nombre del Producto", "")).lower())
except Exception as e:
    st.error(f"Error al leer el inventario: {e}")
    registros_inv = []
    headers = ["Nombre del Producto", "Cantidad en Stock", "Precio de Venta", "Nivel Mínimo de Alerta", "Precio Directo", "Categoría."]

LOGO_PATH = "watermarked_img_3973813175880226978.jpg"

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        if os.path.exists(LOGO_PATH):
            try:
                self.setFillAlpha(0.06)
                self.drawImage(LOGO_PATH, 106, 246, width=400, height=300, preserveAspectRatio=True, mask='auto')
            except:
                pass
                
        if os.path.exists(LOGO_PATH):
            try:
                self.setFillAlpha(1.0)
                self.drawImage(LOGO_PATH, 45, 710, width=95, height=65, preserveAspectRatio=True, mask='auto')
            except:
                pass
        
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#555555'))
        fecha_emision_str = f"Fecha de emisión: {datetime.utcnow().strftime('%d-%m-%Y %H:%M:%S')}"
        self.drawRightString(582, 20, fecha_emision_str)
        self.restoreState()

try:
    with open(LOGO_PATH, "rb") as image_file:
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

pestana1, pestana2, pestana3, pestana4, pestana5, pestana6 = st.tabs([
    "🛒 Registrar Pedido", 
    "📦 Pedidos", 
    "📜 Historial", 
    "📋 Resurtido",
    "➕ Nuevo Producto",
    "🌐 Catálogo Web WhatsApp"
])

with pestana1:
    st.subheader("Registrar Pedido o Movimiento")
    nombres_productos = [str(p.get("Nombre del Producto", "")).strip() for p in registros_inv if p.get("Nombre del Producto")]
    
    if nombres_productos:
        prod_seleccionado = st.selectbox("Selecciona Producto", nombres_productos)
        
        stock_en_selector = 0.0
        precio_vta_selector = 0.0
        for p_item in registros_inv:
            if str(p_item.get("Nombre del Producto", "")).strip() == prod_seleccionado:
                for k, v in p_item.items():
                    if "stock" in k.lower() or "cantidad" in k.lower():
                        try: stock_en_selector = float(str(v).replace(",", ""))
                        except: pass
                    if "precio de venta" in k.lower():
                        try: precio_vta_selector = float(str(v).replace("$", "").replace(",", "").strip())
                        except: pass
                break
        
        stock_str_fmt = str(int(stock_en_selector)) if stock_en_selector.is_integer() else f"{stock_en_selector:g}"
        st.markdown(f'<div class="stock-badge">📦 Existencia Física Actual: <b>{stock_str_fmt} unidades</b></div>', unsafe_allow_html=True)
        
        tipo_transaccion = st.radio("Tipo de Transacción", [
            "Venta / Pedido de Cliente", 
            "🔄 Devolución de Cliente (Reingreso)",
            "Salida Especial (Muestra / Merma / Consumo Propio)", 
            "Compra (Entrada de Proveedor)"
        ])
        
        nombre_cliente = ""
        descuento_porcentaje = 0.0
        
        if tipo_transaccion == "Venta / Pedido de Cliente":
            nombre_cliente = st.text_input("Nombre del Cliente * (Obligatorio):", "")
            descuento_porcentaje = st.number_input("Descuento aplicable (%)", min_value=0.0, max_value=100.0, value=0.0, step=5.0)
        elif tipo_transaccion == "🔄 Devolución de Cliente (Reingreso)":
            nombre_cliente = st.text_input("Nombre del Cliente que devuelve * (Obligatorio):", "")
        elif tipo_transaccion == "Salida Especial (Muestra / Merma / Consumo Propio)":
            motivo_salida = st.selectbox("Motivo de la Salida:", ["Muestra Gratis", "Merma / Dañado", "Consumo Propio"])
            nombre_cliente = motivo_salida
            
        cantidad = st.number_input("Cantidad", min_value=1.0, step=1.0, value=1.0)
        
        if st.button("Registrar en el Sistema") and prod_seleccionado:
            if tipo_transaccion in ["Venta / Pedido de Cliente", "🔄 Devolución de Cliente (Reingreso)"] and not nombre_cliente.strip():
                st.error("❌ El nombre del cliente es obligatorio. Por favor, ingrésalo antes de continuar.")
            else:
                ahora_mexico = datetime.utcnow() - timedelta(hours=6)
                row_idx = None
                producto_obj = None
                inv_actuales = cargar_inventario_cache()
                for i, p in enumerate(inv_actuales):
                    if str(p.get("Nombre del Producto", "")).strip() == prod_seleccionado:
                        row_idx = i + 2 
                        producto_obj = p
                        break
                
                if producto_obj and row_idx:
                    stock_actual = 0.0
                    for k, v in producto_obj.items():
                        if "stock" in k.lower() or "cantidad" in k.lower():
                            try: stock_actual = float(str(v).replace(",", ""))
                            except: pass
                    
                    col_stock_idx = 2  
                    for idx, h in enumerate(headers):
                        h_limpio = h.strip().lower()
                        if "stock" in h_limpio or "cantidad en stock" in h_limpio:
                            col_stock_idx = idx + 1
                            break

                    if tipo_transaccion == "Venta / Pedido de Cliente":
                        cli_final = nombre_cliente.strip().title()
                        desc_txt = f" (Desc. {descuento_porcentaje:g}%)" if descuento_porcentaje > 0 else ""
                        cli_con_desc = cli_final + desc_txt
                        
                        cant_a_reservar = min(cantidad, stock_actual)
                        cant_en_deficit = cantidad - cant_a_reservar
                        
                        if cant_a_reserv
