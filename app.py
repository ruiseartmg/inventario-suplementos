import io
import base64
import os
from datetime import datetime, timedelta

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

        /* Estilos principales para botones */
        div.stButton > button {
            background-color: #2E7D32 !important;
            color: #FFFFFF !important;
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 600;
            border: none !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 10px rgba(46, 125, 50, 0.3) !important;
            transition: 0.3s !important;
        }
        
        /* Quitar fondo blanco del texto dentro de cualquier botón */
        div.stButton > button * {
            background-color: transparent !important;
            color: #FFFFFF !important;
        }

        div.stButton > button:hover {
            background-color: #1B5E20 !important;
        }

        /* Estilo rojo robusto para botones de Cancelar */
        div[class*="cancelar"] > button {
            background-color: #C62828 !important;
            box-shadow: 0 4px 10px rgba(198, 40, 40, 0.3) !important;
        }
        div[class*="cancelar"] > button:hover {
            background-color: #B71C1C !important;
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

        .stock-badge {
            background-color: #E8F5E9;
            color: #1B5E20;
            padding: 8px 14px;
            border-radius: 8px;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 15px;
            border: 1px solid #C8E6C9;
        }

        .deficit-alert-card {
            background-color: #FFEBEE;
            padding: 15px;
            border-radius: 10px;
            border-left: 6px solid #C62828;
            margin-bottom: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        }

        .surtible-alert-card {
            background-color: #E8F5E9;
            padding: 15px;
            border-radius: 10px;
            border-left: 6px solid #2E7D32;
            margin-bottom: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        }

        .por-pagar-card {
            background-color: #FFF8E1;
            padding: 15px;
            border-radius: 10px;
            border-left: 6px solid #F57F17;
            margin-bottom: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        }
    </style>
""", unsafe_allow_html=True)

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def normalizar_id(val):
    if val is None:
        return ""
    return str(val).split('.')[0].strip()

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

@st.cache_data(ttl=120)
def cargar_inventario_cache():
    return hoja_inv.get_all_records()

@st.cache_data(ttl=120)
def cargar_pedidos_cache():
    return hoja_pedidos.get_all_records()

@st.cache_data(ttl=120)
def cargar_historial_cache():
    return hoja_hist.get_all_records()

def reasignar_deficit_si_hay_stock(prod_nombre):
    """Función para tomar automáticamente stock liberado y asignarlo a pedidos en déficit."""
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
                self.setFillAlpha(0.08)
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

pestana1, pestana2, pestana3, pestana4, pestana5 = st.tabs([
    "🛒 Registrar Pedido", 
    "📦 Pedidos", 
    "📜 Historial", 
    "📋 Resurtido",
    "➕ Nuevo Producto"
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
                        
                        if cant_a_reservar > 0:
                            hoja_inv.update_cell(row_idx, col_stock_idx, stock_actual - cant_a_reservar)
                            id_ped_1 = str(int(datetime.utcnow().timestamp()))
                            hoja_pedidos.append_row([
                                id_ped_1, ahora_mexico.strftime("%d-%m-%Y %H:%M:%S"), cli_con_desc, prod_seleccionado, cant_a_reservar, "Venta", "Por entregar"
                            ])
                        
                        if cant_en_deficit > 0:
                            id_ped_2 = str(int(datetime.utcnow().timestamp()) + 1)
                            hoja_pedidos.append_row([
                                id_ped_2, ahora_mexico.strftime("%d-%m-%Y %H:%M:%S"), cli_con_desc, prod_seleccionado, cant_en_deficit, "Venta", "Déficit"
                            ])
                        
                        if cant_en_deficit > 0 and cant_a_reservar > 0:
                            st.warning(f"⚠️ Pedido Mixto: Se apartaron {cant_a_reservar} unidades (listas) y quedaron {cant_en_deficit} en Déficit.")
                        elif cant_en_deficit > 0 and cant_a_reservar == 0:
                            st.warning(f"⚠️ Sin stock físico: El pedido de {cant_en_deficit} unidades se registró como Déficit.")
                        else:
                            st.success(f"🛒 ¡Pedido apartado con éxito para **{cli_con_desc}**!")
                            
                        st.cache_data.clear()
                        st.rerun()

                    elif tipo_transaccion == "🔄 Devolución de Cliente (Reingreso)":
                        cli_final = nombre_cliente.strip().title()
                        nuevo_stock = stock_actual + cantidad
                        total_devolucion = -(cantidad * precio_vta_selector)
                        
                        hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                        hoja_hist.append_row([
                            ahora_mexico.strftime("%d-%m-%Y"), 
                            ahora_mexico.strftime("%H:%M:%S"), 
                            cli_final, 
                            prod_seleccionado, 
                            "Devolución", 
                            cantidad, 
                            total_devolucion
                        ])
                        reasignar_deficit_si_hay_stock(prod_seleccionado)
                        
                        st.success(f"🔄 Devolución registrada con éxito. Se reingresaron **{cantidad:g} unidades** al inventario para **{cli_final}**.")
                        st.cache_data.clear()
                        st.rerun()
                        
                    elif tipo_transaccion == "Salida Especial (Muestra / Merma / Consumo Propio)":
                        cant_salida = min(cantidad, stock_actual)
                        if cant_salida > 0:
                            hoja_inv.update_cell(row_idx, col_stock_idx, stock_actual - cant_salida)
                            hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), nombre_cliente, prod_seleccionado, "Salida Especial", cant_salida, 0.0])
                            st.success(f"🏷️ Salida registrada por {motivo_salida}. Se descontaron {cant_salida} unidades.")
                        else:
                            st.error("❌ No hay stock físico disponible para registrar esta salida especial.")
                        st.cache_data.clear()
                        st.rerun()
                        
                    else: 
                        nuevo_stock = stock_actual + cantidad
                        hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                        hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), "Proveedor", prod_seleccionado, "Compra", cantidad, 0.0])
                        reasignar_deficit_si_hay_stock(prod_seleccionado)
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
            if p.get("Estado") in ["Por entregar", "Déficit"]:
                prod_p = p.get("Producto")
                cant_p = float(str(p.get("Cantidad", 0)).replace(",", ""))
                suma_por_entregar[prod_p] = suma_por_entregar.get(prod_p, 0.0) + cant_p

        for r in registros_inv:
            n_prod = str(r.get("Nombre del Producto", "")).strip()
            r["Por entregar"] = suma_por_entregar.get(n_prod, 0.0)

        df_inv = pd.DataFrame(registros_inv)
        
        cols_a_quitar = [c for c in df_inv.columns if "precio directo" in c.lower() or "directo" in c.lower() or "por surtir" in c.lower() or "por_surtir" in c.lower() or "presentacion" in c.lower() or "presentación" in c.lower() or "alerta" in c.lower() or "categoria" in c.lower() or "categoría" in c.lower()]
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
        col_stock = next((c for c in columnas_disponibles if "stock" in c.lower() or "cantidad en stock" in c.lower()), None)
        col_precio = next((c for c in columnas_disponibles if "precio de venta" in c.lower()), None)
        
        orden_final = [col_prod]
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
            
        st.table(df_inv)

with pestana2:
    st.subheader("📦 Pedidos Pendientes y Entregas")
    
    subtab1, subtab2 = st.tabs(["📦 Por Entregar", "💳 Cuentas por Cobrar (Por Pagar)"])
    
    pedidos_totales = cargar_pedidos_cache()
    stock_por_producto = {}
    precio_por_producto = {}
    
    for inv_p in registros_inv:
        nombre_p = str(inv_p.get("Nombre del Producto", "")).strip()
        st_val = 0.0
        p_vta = 0.0
        for k, v in inv_p.items():
            if "stock" in k.lower() or "cantidad" in k.lower():
                try: st_val = float(str(v).replace(",", ""))
                except: pass
            if "precio de venta" in k.lower():
                try: p_vta = float(str(v).replace("$", "").replace(",", "").strip())
                except: pass
        stock_por_producto[nombre_p] = st_val
        precio_por_producto[nombre_p] = p_vta

    # SUBTAB 1: POR ENTREGAR
    with subtab1:
        st.markdown("Gestiona las entregas pendientes de tus clientes.")
        pendientes_activos = [p for p in pedidos_totales if p.get("Estado") in ["Por entregar", "Déficit"]]
        
        if pendientes_activos:
            def generar_pdf_pedidos(pendientes):
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=75, bottomMargin=40)
                elements = []
                
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#4A1525'), spaceAfter=15, alignment=1)
                header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=1)
                cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
                cell_left = ParagraphStyle('CellLeft', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
                
                elements.append(Paragraph("Nature’s Select - Reporte de Pedidos Pendientes por Entregar", title_style))
                elements.append(Spacer(1, 10))
                
                data = [[Paragraph("Fecha", header_style), Paragraph("Cliente", header_style), Paragraph("Producto", header_style), Paragraph("Cant.", header_style), Paragraph("Estado", header_style), Paragraph("Precio", header_style), Paragraph("Desc.", header_style), Paragraph("Total", header_style)]]
                gran_total_pedidos = 0.0
                
                for p in pendientes:
                    p_estado = str(p.get("Estado", ""))
                    p_prod = str(p.get("Producto", ""))
                    p_fecha_full = str(p.get("Fecha", ""))
                    p_fecha = p_fecha_full.split(" ")[0] if " " in p_fecha_full else p_fecha_full
                    
                    p_cliente_raw = str(p.get("Cliente", ""))
                    if "(Desc." in p_cliente_raw:
                        p_cliente_limpio = p_cliente_raw.split("(Desc.")[0].strip()
                        try: desc_val = float(p_cliente_raw.split("(Desc.")[1].split("%)")[0].strip())
                        except: desc_val = 0.0
                    else:
                        p_cliente_limpio = p_cliente_raw.strip()
                        desc_val = 0.0
                    
                    desc_txt = f"{desc_val:g}%" if desc_val > 0 else "-"
                    try: p_cant = float(str(p.get("Cantidad", 0)).replace(",", ""))
                    except: p_cant = 0.0
                    
                    if p_estado == "Déficit":
                        st_disp = stock_por_producto.get(p_prod, 0.0)
                        if st_disp > 0:
                            p_estado = "Parcial / Listo"

                    p_unitario = precio_por_producto.get(p_prod, 0.0)
                    precio_final = p_unitario * (1.0 - (desc_val / 100.0))
                    p_total = p_cant * precio_final
                    gran_total_pedidos += p_total
                    cant_fmt = str(int(p_cant)) if p_cant.is_integer() else f"{p_cant:g}"

                    data.append([
                        Paragraph(p_fecha, cell_style),
                        Paragraph(p_cliente_limpio, cell_left),
                        Paragraph(p_prod, cell_left),
                        Paragraph(cant_fmt, cell_style),
                        Paragraph(p_estado, cell_style),
                        Paragraph(f"${p_unitario:,.2f}", cell_style),
                        Paragraph(desc_txt, cell_style),
                        Paragraph(f"${p_total:,.2f}", cell_style)
                    ])
                    
                total_row_style = ParagraphStyle('TotalRow', parent=styles['Normal'], fontSize=8, leading=10, alignment=2)
                total_val_style = ParagraphStyle('TotalVal', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
                
                data.append([
                    Paragraph("Total Pendiente:", total_row_style),
                    "", "", "", "", "", "",
                    Paragraph(f"${gran_total_pedidos:,.2f}", total_val_style)
                ])
                
                t = Table(data, colWidths=[55, 95, 110, 35, 75, 45, 35, 55])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4A1525')),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 6),
                    ('TOPPADDING', (0,0), (-1,0), 6),
                    ('BACKGROUND', (0,1), (-1,-2), colors.HexColor('#FDFBFB')),
                    ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor('#D1C4E9')),
                    ('SPAN', (0, -1), (6, -1)),
                    ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F4ECF7')),
                    ('GRID', (0,-1), (-1,-1), 0.5, colors.HexColor('#D1C4E9')),
                ]))
                elements.append(t)
                doc.build(elements, canvasmaker=NumberedCanvas)
                buffer.seek(0)
                return buffer.getvalue()

            pdf_bytes = generar_pdf_pedidos(pendientes_activos)
            
            gran_total_interfaz = 0.0
            for p in pendientes_activos:
                p_prod = str(p.get("Producto", ""))
                try: p_cant = float(str(p.get("Cantidad", 0)).replace(",", ""))
                except: p_cant = 0.0
                c_raw = str(p.get("Cliente", ""))
                desc_val = float(c_raw.split("(Desc.")[1].split("%)")[0].strip()) if "(Desc." in c_raw else 0.0
                p_unitario = precio_por_producto.get(p_prod, 0.0)
                gran_total_interfaz += p_cant * (p_unitario * (1.0 - (desc_val / 100.0)))

            col_descarga, col_total = st.columns([1, 1])
            with col_descarga:
                st.download_button(
                    label="📄 Descargar Reporte de Pendientes PDF",
                    data=pdf_bytes,
                    file_name=f"reporte_pedidos_{datetime.now().strftime('%d-%m-%Y')}.pdf",
                    mime="application/pdf"
                )
            with col_total:
                st.markdown(f"<h3 style='text-align: right; margin-top: 0; color: #2E7D32;'>Valor Total Pendiente: ${gran_total_interfaz:,.2f}</h3>", unsafe_allow_html=True)
                
            st.markdown("---")

            pedidos_deficit_real = []
            pedidos_deficit_surtible = []
            for ped in pendientes_activos:
                if ped.get("Estado") == "Déficit":
                    p_nom = ped.get("Producto")
                    c_ped = float(str(ped.get("Cantidad", 0)).replace(",", ""))
                    st_disp = stock_por_producto.get(p_nom, 0.0)
                    if st_disp > 0:
                        pedidos_deficit_surtible.append(ped)
                    else:
                        pedidos_deficit_real.append(ped)

            if pedidos_deficit_real:
                st.markdown("### 🚨 Pedidos en Espera por Déficit (Falta Stock)")
                for def_ped in pedidos_deficit_real:
                    c_raw = str(def_ped.get('Cliente', ''))
                    c_clean = c_raw.split("(Desc.")[0].strip() if "(Desc." in c_raw else c_raw.strip()
                    st.markdown(f"""
                        <div class="deficit-alert-card">
                            <b>👤 Cliente:</b> {c_clean} <br>
                            <b>🛍️ Producto:</b> {def_ped.get('Producto')} (Cantidad en espera: <b>{def_ped.get('Cantidad')}</b>) <br>
                            <span style='color: gray; font-size: 11px;'>ID Pedido: {def_ped.get('ID')} | Fecha: {def_ped.get('Fecha')}</span>
                        </div>
                    """, unsafe_allow_html=True)
                st.markdown("---")

            if pedidos_deficit_surtible:
                st.markdown("### 🟢 Déficits con Stock Parcial o Total Disponible")
                for sur_ped in pedidos_deficit_surtible:
                    c_raw = str(sur_ped.get('Cliente', ''))
                    c_clean = c_raw.split("(Desc.")[0].strip() if "(Desc." in c_raw else c_raw.strip()
                    p_nom_s = sur_ped.get('Producto')
                    c_ped_s = float(str(sur_ped.get('Cantidad', 0)).replace(",", ""))
                    st_disp_s = stock_por_producto.get(p_nom_s, 0.0)
                    aviso_txt = f"Cantidad lista: <b>{c_ped_s:g}</b>" if st_disp_s >= c_ped_s else f"Déficit: <b>{c_ped_s:g}</b> (Stock: <b>{st_disp_s:g}</b>)"

                    st.markdown(f"""
                        <div class="surtible-alert-card">
                            <b>👤 Cliente:</b> {c_clean} <br>
                            <b>🛍️ Producto:</b> {p_nom_s} — {aviso_txt} <br>
                        </div>
                    """, unsafe_allow_html=True)
                st.markdown("---")

            clientes_limpios_set = set()
            for p in pendientes_activos:
                c_raw = p.get("Cliente", "")
                c_clean = c_raw.split("(Desc.")[0].strip() if "(Desc." in c_raw else c_raw.strip()
                clientes_limpios_set.add(c_clean)
                
            clientes_disponibles = sorted(list(clientes_limpios_set))
            filtro_cliente = st.selectbox("🔍 Filtrar por Cliente específico:", ["-- Todos los Clientes --"] + clientes_disponibles)
            
            if filtro_cliente != "-- Todos los Clientes --":
                pendientes_activos = [
                    p for p in pendientes_activos 
                    if (p.get("Cliente", "").split("(Desc.")[0].strip() if "(Desc." in p.get("Cliente", "") else p.get("Cliente", "").strip()) == filtro_cliente
                ]
            
            st.markdown("---")
            
            for idx, ped in enumerate(pendientes_activos):
                col_info, col_btn_pagado, col_btn_fiado, col_btn_cancel = st.columns([3.5, 1.5, 1.5, 1.2])
                
                estado_ped = ped.get('Estado')
                prod_ped = str(ped.get("Producto", ""))
                cant_ped = float(str(ped.get("Cantidad", 0)).replace(",", ""))
                stock_disponible = stock_por_producto.get(prod_ped, 0.0)
                
                cli_raw = str(ped.get('Cliente', ''))
                if "(Desc." in cli_raw:
                    cli_clean = cli_raw.split("(Desc.")[0].strip()
                    desc_val_str = cli_raw.split("(Desc.")[1].split("%)")[0].strip()
                    desc_badge = f"<span style='background-color:#E3F2FD; color:#1565C0; padding:2px 6px; border-radius:4px; font-size:12px; margin-left:8px;'>Desc. {desc_val_str}%</span>"
                else:
                    cli_clean = cli_raw.strip()
                    desc_badge = ""
                
                if estado_ped == "Por entregar":
                    estado_lbl = "📦 Reservado (Listo)"
                elif estado_ped == "Déficit":
                    estado_lbl = "🟢 Listo" if stock_disponible >= cant_ped else "🚨 Déficit"
                
                with col_info:
                    st.markdown(f"**👤 {cli_clean}** {desc_badge} \n🛍️ **{prod_ped}** — Cantidad: **{cant_ped:g}** [{estado_lbl}] \n<span style='color: gray; font-size: 11px;'>ID: {ped.get('ID')} | Fecha: {ped.get('Fecha')}</span>", unsafe_allow_html=True)
                
                def procesar_entrega(nuevo_estado):
                    ped_id_str = str(ped.get("ID"))
                    try:
                        cell = hoja_pedidos.find(ped_id_str)
                        fila_real = cell.row
                    except:
                        fila_real = None

                    if not fila_real:
                        todos_p = cargar_pedidos_cache()
                        for i, tp in enumerate(todos_p):
                            if str(tp.get("Cliente")).strip() == str(ped.get("Cliente")).strip() and str(tp.get("Producto")).strip() == str(ped.get("Producto")).strip() and tp.get("Estado") in ["Por entregar", "Déficit"]:
                                fila_real = i + 2
                                break
                    
                    if fila_real:
                        cli_con_desc = str(ped.get("Cliente", ""))
                        precio_vta = 0.0
                        inv_actuales = cargar_inventario_cache()
                        row_inv_idx = None
                        stock_fisc = 0.0
                        for i, inv_item in enumerate(inv_actuales):
                            if str(inv_item.get("Nombre del Producto", "")).strip() == prod_ped:
                                row_inv_idx = i + 2
                                for k, v in inv_item.items():
                                    if "stock" in k.lower() or "cantidad" in k.lower():
                                        try: stock_fisc = float(str(v).replace(",", ""))
                                        except: pass
                                    if "precio de venta" in k.lower():
                                        try: precio_vta = float(str(v).replace("$", "").replace(",", "").strip())
                                        except: pass
                                break
                        
                        desc_val = float(cli_con_desc.split("(Desc.")[1].split("%)")[0].strip()) if "(Desc." in cli_con_desc else 0.0
                        ahora_mexico = datetime.utcnow() - timedelta(hours=6)

                        if estado_ped == "Por entregar":
                            hoja_pedidos.update_cell(fila_real, 7, nuevo_estado)
                            precio_final = precio_vta * (1.0 - (desc_val / 100.0))
                            total_vta = cant_ped * precio_final
                            
                            if nuevo_estado == "Entregado":
                                hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_con_desc, prod_ped, "Venta", cant_ped, total_vta])
                                st.success(f"¡Pedido entregado y pagado por {cli_clean}!")
                            else:
                                hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_con_desc, prod_ped, "Venta (Por Pagar)", cant_ped, f"Pendiente (${total_vta:,.2f})"])
                                st.warning(f"¡Pedido entregado a {cli_clean}! Quedó registrado en Cuentas por Cobrar.")
                        
                        elif estado_ped == "Déficit":
                            cant_a_entregar = min(cant_ped, stock_fisc)
                            cant_remanente = cant_ped - cant_a_entregar
                            
                            if cant_a_entregar > 0 and row_inv_idx:
                                col_st_idx = 2
                                for idx_h, h_name in enumerate(headers):
                                    if "stock" in h_name.lower():
                                        col_st_idx = idx_h + 1
                                        break
                                hoja_inv.update_cell(row_inv_idx, col_st_idx, stock_fisc - cant_a_entregar)
                                precio_final = precio_vta * (1.0 - (desc_val / 100.0))
                                total_vta = cant_a_entregar * precio_final
                                
                                if nuevo_estado == "Entregado":
                                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_con_desc, prod_ped, "Venta", cant_a_entregar, total_vta])
                                else:
                                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_con_desc, prod_ped, "Venta (Por Pagar)", cant_a_entregar, f"Pendiente (${total_vta:,.2f})"])
                                
                                if cant_remanente > 0:
                                    hoja_pedidos.update_cell(fila_real, 5, cant_remanente)
                                    st.warning(f"⚠️ Se entregaron **{cant_a_entregar:g} unidades**. Quedan **{cant_remanente:g}** en déficit.")
                                else:
                                    hoja_pedidos.update_cell(fila_real, 7, nuevo_estado)
                                    st.success(f"¡Pedido surtido y marcado como {nuevo_estado} para {cli_clean}!")

                        st.cache_data.clear()
                        st.rerun()

                with col_btn_pagado:
                    if estado_ped == "Déficit" and stock_disponible <= 0:
                        st.button("⏳ Sin Stock", key=f"entregar_pag_{ped.get('ID')}_{idx}", disabled=True)
                    else:
                        if st.button("💵 Pagado", key=f"entregar_pag_{ped.get('ID')}_{idx}"):
                            procesar_entrega("Entregado")

                with col_btn_fiado:
                    if estado_ped == "Déficit" and stock_disponible <= 0:
                        st.button("⏳ Sin Stock", key=f"entregar_fia_{ped.get('ID')}_{idx}", disabled=True)
                    else:
                        if st.button("💳 Por Pagar", key=f"entregar_fia_{ped.get('ID')}_{idx}"):
                            procesar_entrega("Por pagar")

                with col_btn_cancel:
                    if st.button("❌ Cancelar", key=f"cancelar_ped_{ped.get('ID')}_{idx}"):
                        ped_id_str = str(ped.get("ID"))
                        try:
                            cell = hoja_pedidos.find(ped_id_str)
                            fila_real = cell.row
                        except:
                            fila_real = None

                        if not fila_real:
                            todos_p = cargar_pedidos_cache()
                            for i, tp in enumerate(todos_p):
                                if str(tp.get("Cliente")).strip() == str(ped.get("Cliente")).strip() and str(tp.get("Producto")).strip() == str(ped.get("Producto")).strip() and tp.get("Estado") in ["Por entregar", "Déficit"]:
                                    fila_real = i + 2
                                    break

                        if fila_real:
                            hoja_pedidos.update_cell(fila_real, 7, "Cancelado")
                            if estado_ped == "Por entregar":
                                inv_actuales = cargar_inventario_cache()
                                for i, inv_item in enumerate(inv_actuales):
                                    if str(inv_item.get("Nombre del Producto", "")).strip() == prod_ped:
                                        st_act = float(str(inv_item.get("Cantidad en Stock", 0)).replace(",", ""))
                                        col_st_idx = 2
                                        for idx_h, h_name in enumerate(headers):
                                            if "stock" in h_name.lower():
                                                col_st_idx = idx_h + 1
                                                break
                                        hoja_inv.update_cell(i + 2, col_st_idx, st_act + cant_ped)
                                        break
                                reasignar_deficit_si_hay_stock(prod_ped)
                                st.warning(f"Pedido cancelado. Se devolvieron **{cant_ped:g} unidades** al inventario.")
                            else:
                                st.warning("El pedido en déficit fue cancelado.")
                            st.cache_data.clear()
                            st.rerun()

                # Opción de Cancelación Parcial o Reducción de Piezas sin perder el turno
                with st.expander(f"⚙️ Modificar o reducir cantidad para {cli_clean}"):
                    cant_a_cancelar = st.number_input(
                        "¿Cuántas piezas deseas restar/cancelar de este pedido?", 
                        min_value=1.0, 
                        max_value=cant_ped, 
                        value=1.0, 
                        step=1.0, 
                        key=f"num_cancel_parcial_{ped.get('ID')}_{idx}"
                    )
                    if st.button("✅ Confirmar Reducción de Piezas", key=f"btn_aplicar_red_{ped.get('ID')}_{idx}"):
                        ped_id_str = str(ped.get("ID"))
                        try:
                            cell = hoja_pedidos.find(ped_id_str)
                            fila_real = cell.row
                        except:
                            fila_real = None

                        if not fila_real:
                            todos_p = cargar_pedidos_cache()
                            for i, tp in enumerate(todos_p):
                                if str(tp.get("Cliente")).strip() == str(ped.get("Cliente")).strip() and str(tp.get("Producto")).strip() == str(ped.get("Producto")).strip() and tp.get("Estado") in ["Por entregar", "Déficit"]:
                                    fila_real = i + 2
                                    break

                        if fila_real:
                            nueva_cant = cant_ped - cant_a_cancelar
                            if nueva_cant <= 0:
                                hoja_pedidos.update_cell(fila_real, 7, "Cancelado")
                                if estado_ped == "Por entregar":
                                    inv_actuales = cargar_inventario_cache()
                                    for i, inv_item in enumerate(inv_actuales):
                                        if str(inv_item.get("Nombre del Producto", "")).strip() == prod_ped:
                                            st_act = float(str(inv_item.get("Cantidad en Stock", 0)).replace(",", ""))
                                            col_st_idx = 2
                                            for idx_h, h_name in enumerate(headers):
                                                if "stock" in h_name.lower():
                                                    col_st_idx = idx_h + 1
                                                    break
                                            hoja_inv.update_cell(i + 2, col_st_idx, st_act + cant_ped)
                                            break
                                    reasignar_deficit_si_hay_stock(prod_ped)
                                st.warning(f"Pedido cancelado por completo. Se devolvieron **{cant_ped:g} unidades** al inventario.")
                            else:
                                hoja_pedidos.update_cell(fila_real, 5, nueva_cant)
                                if estado_ped == "Por entregar":
                                    inv_actuales = cargar_inventario_cache()
                                    for i, inv_item in enumerate(inv_actuales):
                                        if str(inv_item.get("Nombre del Producto", "")).strip() == prod_ped:
                                            st_act = float(str(inv_item.get("Cantidad en Stock", 0)).replace(",", ""))
                                            col_st_idx = 2
                                            for idx_h, h_name in enumerate(headers):
                                                if "stock" in h_name.lower():
                                                    col_st_idx = idx_h + 1
                                                    break
                                            hoja_inv.update_cell(i + 2, col_st_idx, st_act + cant_a_cancelar)
                                            break
                                    reasignar_deficit_si_hay_stock(prod_ped)
                                st.success(f"¡Pedido actualizado! Se redujeron **{cant_a_cancelar:g} unidades**. El pedido de **{cli_clean}** ahora es de **{nueva_cant:g} unidades** y conserva su turno.")
                            
                            st.cache_data.clear()
                            st.rerun()

                st.divider()
        else:
            st.info("No hay pedidos pendientes por entregar en este momento.")

    # SUBTAB 2: CUENTAS POR COBRAR (POR PAGAR)
    with subtab2:
        st.markdown("Lista de artículos que ya fueron entregados al cliente pero están **pendientes de cobro**.")
        pedidos_por_pagar = [p for p in pedidos_totales if p.get("Estado") == "Por pagar"]
        
        if pedidos_por_pagar:
            def generar_pdf_cuentas_por_cobrar(lista_por_pagar):
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=75, bottomMargin=40)
                elements = []
                
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#4A1525'), spaceAfter=15, alignment=1)
                header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=1)
                cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
                cell_left = ParagraphStyle('CellLeft', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
                
                elements.append(Paragraph("Nature’s Select - Cuentas por Cobrar (Entregados sin Pago)", title_style))
                elements.append(Spacer(1, 10))
                
                data = [[Paragraph("Fecha", header_style), Paragraph("Cliente", header_style), Paragraph("Producto", header_style), Paragraph("Cant.", header_style), Paragraph("Precio Unit.", header_style), Paragraph("Desc.", header_style), Paragraph("Total a Cobrar", header_style)]]
                gran_total_cobrar = 0.0
                
                for p in lista_por_pagar:
                    p_prod = str(p.get("Producto", ""))
                    p_fecha_full = str(p.get("Fecha", ""))
                    p_fecha = p_fecha_full.split(" ")[0] if " " in p_fecha_full else p_fecha_full
                    p_cliente_raw = str(p.get("Cliente", ""))
                    
                    if "(Desc." in p_cliente_raw:
                        p_cliente_limpio = p_cliente_raw.split("(Desc.")[0].strip()
                        try: desc_val = float(p_cliente_raw.split("(Desc.")[1].split("%)")[0].strip())
                        except: desc_val = 0.0
                    else:
                        p_cliente_limpio = p_cliente_raw.strip()
                        desc_val = 0.0
                    
                    desc_txt = f"{desc_val:g}%" if desc_val > 0 else "-"
                    try: p_cant = float(str(p.get("Cantidad", 0)).replace(",", ""))
                    except: p_cant = 0.0

                    p_unitario = precio_por_producto.get(p_prod, 0.0)
                    precio_final = p_unitario * (1.0 - (desc_val / 100.0))
                    p_total = p_cant * precio_final
                    gran_total_cobrar += p_total
                    cant_fmt = str(int(p_cant)) if p_cant.is_integer() else f"{p_cant:g}"

                    data.append([
                        Paragraph(p_fecha, cell_style),
                        Paragraph(p_cliente_limpio, cell_left),
                        Paragraph(p_prod, cell_left),
                        Paragraph(cant_fmt, cell_style),
                        Paragraph(f"${p_unitario:,.2f}", cell_style),
                        Paragraph(desc_txt, cell_style),
                        Paragraph(f"${p_total:,.2f}", cell_style)
                    ])
                    
                total_row_style = ParagraphStyle('TotalRow', parent=styles['Normal'], fontSize=8, leading=10, alignment=2)
                total_val_style = ParagraphStyle('TotalVal', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
                
                data.append([
                    Paragraph("Total Pendiente por Cobrar:", total_row_style),
                    "", "", "", "", "",
                    Paragraph(f"${gran_total_cobrar:,.2f}", total_val_style)
                ])
                
                t = Table(data, colWidths=[65, 115, 130, 40, 55, 40, 60])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4A1525')),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 6),
                    ('TOPPADDING', (0,0), (-1,0), 6),
                    ('BACKGROUND', (0,1), (-1,-2), colors.HexColor('#FDFBFB')),
                    ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor('#D1C4E9')),
                    ('SPAN', (0, -1), (5, -1)),
                    ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F4ECF7')),
                    ('GRID', (0,-1), (-1,-1), 0.5, colors.HexColor('#D1C4E9')),
                ]))
                elements.append(t)
                doc.build(elements, canvasmaker=NumberedCanvas)
                buffer.seek(0)
                return buffer.getvalue()

            pdf_bytes_cobrar = generar_pdf_cuentas_por_cobrar(pedidos_por_pagar)
            
            gran_total_por_cobrar = 0.0
            for p in pedidos_por_pagar:
                p_prod = str(p.get("Producto", ""))
                try: p_cant = float(str(p.get("Cantidad", 0)).replace(",", ""))
                except: p_cant = 0.0
                c_raw = str(p.get("Cliente", ""))
                desc_val = float(c_raw.split("(Desc.")[1].split("%)")[0].strip()) if "(Desc." in c_raw else 0.0
                p_unitario = precio_por_producto.get(p_prod, 0.0)
                gran_total_por_cobrar += p_cant * (p_unitario * (1.0 - (desc_val / 100.0)))

            col_pdf_c, col_tot_c = st.columns([1, 1])
            with col_pdf_c:
                st.download_button(
                    label="📄 Descargar Cuentas por Cobrar en PDF",
                    data=pdf_bytes_cobrar,
                    file_name=f"cuentas_por_cobrar_{datetime.now().strftime('%d-%m-%Y')}.pdf",
                    mime="application/pdf"
                )
            with col_tot_c:
                st.markdown(f"<h3 style='text-align: right; margin-top: 0; color: #F57F17;'>Total Fiado por Cobrar: ${gran_total_por_cobrar:,.2f}</h3>", unsafe_allow_html=True)

            st.markdown("---")

            for idx, ped in enumerate(pedidos_por_pagar):
                col_info_c, col_btn_cobrar, col_btn_cancel_c = st.columns([4.2, 1.8, 1.5])
                
                prod_ped = str(ped.get("Producto", ""))
                cant_ped = float(str(ped.get("Cantidad", 0)).replace(",", ""))
                
                cli_raw = str(ped.get('Cliente', ''))
                if "(Desc." in cli_raw:
                    cli_clean = cli_raw.split("(Desc.")[0].strip()
                    desc_val = float(cli_raw.split("(Desc.")[1].split("%)")[0].strip())
                    desc_badge = f"<span style='background-color:#E3F2FD; color:#1565C0; padding:2px 6px; border-radius:4px; font-size:12px; margin-left:8px;'>Desc. {desc_val:g}%</span>"
                else:
                    cli_clean = cli_raw.strip()
                    desc_val = 0.0
                    desc_badge = ""
                
                p_unitario = precio_por_producto.get(prod_ped, 0.0)
                precio_final = p_unitario * (1.0 - (desc_val / 100.0))
                total_deuda = cant_ped * precio_final
                
                with col_info_c:
                    st.markdown(f"""
                        <div class="por-pagar-card">
                            <b>👤 Cliente:</b> {cli_clean} {desc_badge} <br>
                            <b>🛍️ Producto:</b> {prod_ped} — Cantidad: <b>{cant_ped:g}</b> <br>
                            <b>💰 Monto Pendiente:</b> <span style="color:#C62828; font-weight:bold;">${total_deuda:,.2f}</span> <br>
                            <span style='color: gray; font-size: 11px;'>ID: {ped.get('ID')} | Fecha de entrega: {ped.get('Fecha')}</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                with col_btn_cobrar:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💰 Marcar como Pagado", key=f"cobrar_{ped.get('ID')}_{idx}"):
                        ped_id_str = str(ped.get("ID"))
                        try:
                            cell = hoja_pedidos.find(ped_id_str)
                            fila_real = cell.row
                        except:
                            fila_real = None

                        if not fila_real:
                            todos_p = cargar_pedidos_cache()
                            for i, tp in enumerate(todos_p):
                                if str(tp.get("Cliente")).strip() == str(ped.get("Cliente")).strip() and str(tp.get("Producto")).strip() == str(ped.get("Producto")).strip() and tp.get("Estado") == "Por pagar":
                                    fila_real = i + 2
                                    break

                        if fila_real:
                            hoja_pedidos.update_cell(fila_real, 7, "Entregado")
                            
                            hist_actuales = cargar_historial_cache()
                            fila_hist_encontrada = None
                            for idx_h_item, h_item in enumerate(hist_actuales):
                                if str(h_item.get("Cliente", "")).strip() == cli_raw and str(h_item.get("Producto", "")).strip() == prod_ped and "Por Pagar" in str(h_item.get("Compra/Venta", "")):
                                    fila_hist_encontrada = idx_h_item + 2
                                    break
                            
                            if fila_hist_encontrada:
                                hoja_hist.update_cell(fila_hist_encontrada, 5, "Venta")
                                hoja_hist.update_cell(fila_hist_encontrada, 7, total_deuda)
                            else:
                                ahora_mexico = datetime.utcnow() - timedelta(hours=6)
                                hoja_hist.append_row([
                                    ahora_mexico.strftime("%d-%m-%Y"), 
                                    ahora_mexico.strftime("%H:%M:%S"), 
                                    cli_raw, 
                                    prod_ped, 
                                    "Venta", 
                                    cant_ped, 
                                    total_deuda
                                ])
                            
                            st.success(f"¡Pago de **${total_deuda:,.2f}** recibido con éxito de **{cli_clean}**!")
                            st.cache_data.clear()
                            st.rerun()

                with col_btn_cancel_c:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("❌ Cancelar", key=f"cancelar_cobro_{ped.get('ID')}_{idx}"):
                        ped_id_str = str(ped.get("ID"))
                        try:
                            cell = hoja_pedidos.find(ped_id_str)
                            fila_real = cell.row
                        except:
                            fila_real = None

                        if not fila_real:
                            todos_p = cargar_pedidos_cache()
                            for i, tp in enumerate(todos_p):
                                if str(tp.get("Cliente")).strip() == str(ped.get("Cliente")).strip() and str(tp.get("Producto")).strip() == str(ped.get("Producto")).strip() and tp.get("Estado") == "Por pagar":
                                    fila_real = i + 2
                                    break

                        if fila_real:
                            hoja_pedidos.update_cell(fila_real, 7, "Cancelado")
                            
                            inv_actuales = cargar_inventario_cache()
                            for i, inv_item in enumerate(inv_actuales):
                                if str(inv_item.get("Nombre del Producto", "")).strip() == prod_ped:
                                    st_act = float(str(inv_item.get("Cantidad en Stock", 0)).replace(",", ""))
                                    col_st_idx = 2
                                    for idx_h, h_name in enumerate(headers):
                                        if "stock" in h_name.lower():
                                            col_st_idx = idx_h + 1
                                            break
                                    hoja_inv.update_cell(i + 2, col_st_idx, st_act + cant_ped)
                                    break
                                    
                            hist_actuales = cargar_historial_cache()
                            for idx_h_item, h_item in enumerate(hist_actuales):
                                if str(h_item.get("Cliente", "")).strip() == cli_raw and str(h_item.get("Producto", "")).strip() == prod_ped and "Por Pagar" in str(h_item.get("Compra/Venta", "")):
                                    hoja_hist.update_cell(idx_h_item + 2, 5, "Cancelado")
                                    hoja_hist.update_cell(idx_h_item + 2, 7, 0.0)
                                    break
                            
                            reasignar_deficit_si_hay_stock(prod_ped)
                            st.warning(f"Pedido cancelado. Se devolvieron **{cant_ped:g} unidades** de **{prod_ped}** al inventario.")
                            st.cache_data.clear()
                            st.rerun()

                st.divider()
        else:
            st.info("🎉 ¡Excelente! No hay cuentas pendientes por cobrar en este momento.")

with pestana3:
    st.subheader("Historial de Transacciones")
    
    registros_h = cargar_historial_cache()
    if registros_h:
        def generar_pdf_historial(historial):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=75, bottomMargin=40)
            elements = []
            
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#4A1525'), spaceAfter=15, alignment=1)
            header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=1)
            cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
            cell_left = ParagraphStyle('CellLeft', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
            
            elements.append(Paragraph("Nature’s Select - Historial de Transacciones", title_style))
            elements.append(Spacer(1, 10))
            
            historial_ordenado = sorted(historial, key=lambda x: str(x.get("Cliente", "")).lower())

            data = [[Paragraph("Fecha", header_style), Paragraph("Producto", header_style), Paragraph("Cliente", header_style), Paragraph("Tipo", header_style), Paragraph("Cant.", header_style), Paragraph("Total", header_style)]]
            for h in historial_ordenado:
                raw_tot = str(h.get("Total", "0")).replace("$", "").replace(",", "").strip()
                if "pendiente" in raw_tot.lower():
                    tot_fmt = raw_tot
                else:
                    try: val_tot = float(raw_tot)
                    except: val_tot = 0.0
                    tot_fmt = f"${val_tot:,.2f}"

                raw_cant = str(h.get("Cantidad", "0")).replace("$", "").replace(",", "").strip()
                try:
                    val_cant = float(raw_cant)
                    cant_fmt = str(int(val_cant)) if val_cant.is_integer() else f"{val_cant:g}"
                except: cant_fmt = raw_cant
                    
                c_raw = str(h.get("Cliente", ""))
                c_clean = c_raw.split("(Desc.")[0].strip() if "(Desc." in c_raw else c_raw.strip()

                data.append([
                    Paragraph(str(h.get("Fecha", "")), cell_style),
                    Paragraph(str(h.get("Producto", "")), cell_left),
                    Paragraph(c_clean, cell_left),
                    Paragraph(str(h.get("Compra/Venta", "")), cell_style),
                    Paragraph(cant_fmt, cell_style),
                    Paragraph(tot_fmt, cell_style)
                ])
                
            t = Table(data, colWidths=[70, 140, 120, 75, 45, 64])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4A1525')),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#FDFBFB')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1C4E9')),
            ]))
            elements.append(t)
            doc.build(elements, canvasmaker=NumberedCanvas)
            buffer.seek(0)
            return buffer.getvalue()

        pdf_bytes_hist = generar_pdf_historial(registros_h)
        st.download_button(
            label="📄 Descargar Historial en PDF",
            data=pdf_bytes_hist,
            file_name=f"reporte_historial_{datetime.now().strftime('%d-%m-%Y')}.pdf",
            mime="application/pdf"
        )
        st.markdown("---")

        df_hist = pd.DataFrame(registros_h)
        if not df_hist.empty:
            if "Total" in df_hist.columns:
                def formatear_total(val):
                    val_str = str(val)
                    if "pendiente" in val_str.lower():
                        return val_str
                    try:
                        num = float(val_str.replace("$", "").replace(",", "").strip())
                        return f"${num:,.2f}"
                    except:
                        return val_str
                df_hist["Total"] = df_hist["Total"].apply(formatear_total)

            if "Cantidad" in df_hist.columns:
                df_hist["Cantidad"] = pd.to_numeric(df_hist["Cantidad"].astype(str).str.replace("$", "").str.replace(",", "").str.strip(), errors="coerce").fillna(0)
                df_hist["Cantidad"] = df_hist["Cantidad"].apply(lambda x: str(int(x)) if x.is_integer() else f"{x:g}")
            
            if "Cliente" in df_hist.columns:
                df_hist["Cliente"] = df_hist["Cliente"].apply(lambda x: str(x).split("(Desc.")[0].strip() if "(Desc." in str(x) else str(x).strip())

            cols_ordenadas = ["Fecha", "Producto", "Cliente", "Compra/Venta", "Cantidad", "Total"]
            df_hist = df_hist[[c for c in cols_ordenadas if c in df_hist.columns]]

            if "Producto" in df_hist.columns:
                df_hist = df_hist.set_index("Producto")
            st.dataframe(df_hist, use_container_width=True)
        else:
            st.info("Aún no hay registros en el historial.")
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
                df_ventas = df_h[df_h["Compra/Venta"].astype(str).str.contains("Venta|Devolución", case=False, na=False)].copy()
            else:
                df_ventas = df_h.copy()
                
            if not df_ventas.empty:
                try:
                    df_ventas["Fecha_str"] = df_ventas["Fecha"].astype(str).str.strip()
                    df_ventas["Mes"] = df_ventas["Fecha_str"].str.slice(3, 10)
                    
                    def procesar_cant_neto(row):
                        tipo = str(row.get("Compra/Venta", ""))
                        cant = float(str(row.get("Cantidad", 0)).replace("$", "").replace(",", "").strip())
                        if "Devolución" in tipo or "Cancelado" in tipo:
                            return -cant
                        return cant

                    df_ventas["Cantidad_num"] = df_ventas.apply(procesar_cant_neto, axis=1)
                    
                    totales_prod_mes = df_ventas.groupby(["Producto", "Mes"])["Cantidad_num"].sum().reset_index()
                    promedios = totales_prod_mes.groupby("Producto")["Cantidad_num"].mean().reset_index()
                    for _, row in promedios.iterrows():
                        promedios_dict[row["Producto"]] = max(0.0, float(row["Cantidad_num"]))
                except:
                    pass

        lista_resurtido = []
        gran_total_inversion = 0.0

        for p in registros_inv:
            nombre = str(p.get("Nombre del Producto", "")).strip()
            
            stock = 0.0
            for k, v in p.items():
                if "stock" in k.lower() or "cantidad" in k.lower():
                    try:
                        stock = float(str(v).replace(",", ""))
                        break
                    except:
                        pass
            
            todos_los_pedidos_res = cargar_pedidos_cache()
            por_entregar_val = 0.0
            for tp in todos_los_pedidos_res:
                if tp.get("Estado") in ["Por entregar", "Déficit"] and tp.get("Producto") == nombre:
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

        def generar_pdf_resurtido(resurtido, total_inv):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=75, bottomMargin=40)
            elements = []
            
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#4A1525'), spaceAfter=15, alignment=1)
            header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=1)
            cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
            cell_left = ParagraphStyle('CellLeft', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
            
            elements.append(Paragraph("Nature’s Select - Sugerencia de Pedido (Resurtido)", title_style))
            elements.append(Spacer(1, 10))
            
            data = [[Paragraph("Producto", header_style), Paragraph("Stock", header_style), Paragraph("Por Entregar", header_style), Paragraph("Prom./Mes", header_style), Paragraph("Sugerido", header_style), Paragraph("Costo Unit.", header_style), Paragraph("Inversión Est.", header_style)]]
            for r in resurtido:
                data.append([
                    Paragraph(str(r.get("Producto", "")), cell_left),
                    Paragraph(str(r.get("Stock Actual", "")), cell_style),
                    Paragraph(str(r.get("Por Entregar (Clientes)", "")), cell_style),
                    Paragraph(str(r.get("Promedio/Mes", "")), cell_style),
                    Paragraph(str(r.get("Sugerido", "")), cell_style),
                    Paragraph(str(r.get("Costo Unit.", "")), cell_style),
                    Paragraph(str(r.get("Inversión Est.", "")), cell_style)
                ])
                
            total_row_style = ParagraphStyle('TotalRow', parent=styles['Normal'], fontSize=8, leading=10, alignment=2)
            total_val_style = ParagraphStyle('TotalVal', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
            
            data.append([
                Paragraph("Inversión Total Estimada:", total_row_style),
                "", "", "", "", "",
                Paragraph(f"${total_inv:,.2f}", total_val_style)
            ])
            
            t = Table(data, colWidths=[140, 50, 70, 60, 60, 65, 95])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4A1525')),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                ('BACKGROUND', (0,1), (-1,-2), colors.HexColor('#FDFBFB')),
                ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor('#D1C4E9')),
                ('SPAN', (0, -1), (5, -1)),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F4ECF7')),
                ('GRID', (0,-1), (-1,-1), 0.5, colors.HexColor('#D1C4E9')),
            ]))
            elements.append(t)
            
            doc.build(elements, canvasmaker=NumberedCanvas)
            buffer.seek(0)
            return buffer.getvalue()

        pdf_bytes_res = generar_pdf_resurtido(lista_resurtido, gran_total_inversion)
        st.download_button(
            label="📄 Descargar Reporte de Resurtido en PDF",
            data=pdf_bytes_res,
            file_name=f"reporte_resurtido_{datetime.now().strftime('%d-%m-%Y')}.pdf",
            mime="application/pdf"
        )
        st.markdown("---")
        
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
        nuevo_nombre = st.text_input("Nombre del Producto con Presentación * (ej. Miel de Abeja 500g)")
        col1, col2 = st.columns(2)
        with col1:
            stock_inicial = st.number_input("Cantidad Inicial en Stock", min_value=0.0, step=1.0, value=0.0)
            precio_dir = st.number_input("Precio Directo", min_value=0.0, step=1.0, value=0.0)
        with col2:
            precio_ven = st.number_input("Precio de Venta", min_value=0.0, step=1.0, value=0.0)
            categoria = st.text_input("Categoría")
            
        submitted = st.form_submit_button("Guardar Producto en la Nube")
        if submitted:
            if not nuevo_nombre.strip():
                st.error("¡El nombre del producto es obligatorio!")
            else:
                try:
                    n_nom_final = nuevo_nombre.strip()  
                    n_cat_final = categoria.strip() if categoria.strip() else "2"

                    nueva_fila = [""] * len(headers)
                    datos_ingresados = {
                        "Nombre del Producto": n_nom_final,
                        "Cantidad en Stock": stock_inicial,
                        "Precio de Venta": precio_ven,
                        "Nivel Mínimo de Alerta": 2,
                        "Precio Directo": precio_dir,
                        "Categoría.": n_cat_final
                    }
                    for idx, header in enumerate(headers):
                        h_limpio = header.strip()
                        if h_limpio in datos_ingresados:
                            nueva_fila[idx] = datos_ingresados[h_limpio]
                    hoja_inv.append_row(nueva_fila)
                    st.success(f"¡El producto '{n_nom_final}' se ha dado de alta correctamente!")
                    
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
