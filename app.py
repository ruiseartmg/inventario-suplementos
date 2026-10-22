import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import base64
import pandas as pd
import time
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import io

st.set_page_config(page_title="Nature’s Select - Inventario", page_icon="🌿", layout="wide")

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
        headers_hist = hoja_hist.row_values(1)
        if not headers_hist or "Cliente" not in [h.strip() for h in headers_hist]:
            hoja_hist.clear()
            hoja_hist.append_row(["Fecha", "Hora", "Cliente", "Producto", "Compra/Venta", "Cantidad", "Total"])
    except:
        pass
    
    try:
        hoja_pedidos = spreadsheet.worksheet("Pedidos")
    except:
        hoja_pedidos = spreadsheet.add_worksheet(title="Pedidos", rows=100, cols=10)
        hoja_pedidos.append_row(["ID", "Fecha", "Cliente", "Producto", "Cantidad", "Tipo", "Estado"])
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

@st.cache_data(ttl=3600)
def cargar_inventario_cache():
    time.sleep(0.3)
    return hoja_inv.get_all_records()

@st.cache_data(ttl=3600)
def cargar_pedidos_cache():
    time.sleep(0.3)
    return hoja_pedidos.get_all_records()

@st.cache_data(ttl=3600)
def cargar_historial_cache():
    time.sleep(0.3)
    return hoja_hist.get_all_records()

try:
    registros_inv = cargar_inventario_cache()
    headers = hoja_inv.row_values(1)
    if registros_inv:
        registros_inv = sorted(registros_inv, key=lambda x: str(x.get("Nombre del Producto", "")).lower())
except Exception as e:
    st.error(f"Error al leer el inventario: {e}")
    registros_inv = []
    headers = []

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
        
        # 1. Marca de agua central tenue
        if os.path.exists(LOGO_PATH):
            try:
                self.setFillAlpha(0.08)
                self.drawImage(LOGO_PATH, 106, 246, width=400, height=300, preserveAspectRatio=True, mask='auto')
            except:
                pass
                
        # 2. Logo corporativo en la esquina superior izquierda dentro del margen (X=30, Y=730)
        if os.path.exists(LOGO_PATH):
            try:
                self.setFillAlpha(1.0)
                self.drawImage(LOGO_PATH, 30, 725, width=65, height=45, preserveAspectRatio=True, mask='auto')
            except:
                pass
        
        # 3. Fecha de emisión abajo a la derecha
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
    st.subheader("Registrar Pedido o Entrada")
    
    nombres_productos = [str(p.get("Nombre del Producto", "")).strip() for p in registros_inv if p.get("Nombre del Producto")]
    
    if nombres_productos:
        prod_seleccionado = st.selectbox("Selecciona Producto", nombres_productos)
        
        stock_en_selector = 0.0
        for p_item in registros_inv:
            if str(p_item.get("Nombre del Producto", "")).strip() == prod_seleccionado:
                for k, v in p_item.items():
                    if "stock" in k.lower() or "cantidad" in k.lower():
                        try:
                            stock_en_selector = float(str(v).replace(",", ""))
                            break
                        except:
                            continue
        
        stock_str_fmt = str(int(stock_en_selector)) if stock_en_selector.is_integer() else f"{stock_en_selector:g}"
        st.markdown(f'<div class="stock-badge">📦 Existencia Física Actual: <b>{stock_str_fmt} unidades</b></div>', unsafe_allow_html=True)
        
        tipo_transaccion = st.radio("Tipo de Transacción", ["Venta / Pedido de Cliente", "Salida Especial (Muestra / Merma / Consumo Propio)", "Compra (Entrada de Proveedor)"])
        
        nombre_cliente = ""
        descuento_porcentaje = 0.0
        
        if tipo_transaccion == "Venta / Pedido de Cliente":
            nombre_cliente = st.text_input("Nombre del Cliente * (Obligatorio):", "")
            descuento_porcentaje = st.number_input("Descuento aplicable (%)", min_value=0.0, max_value=100.0, value=0.0, step=5.0)
        elif tipo_transaccion == "Salida Especial (Muestra / Merma / Consumo Propio)":
            motivo_salida = st.selectbox("Motivo de la Salida:", ["Muestra Gratis", "Merma / Dañado", "Consumo Propio"])
            nombre_cliente = motivo_salida
            
        cantidad = st.number_input("Cantidad", min_value=1.0, step=1.0, value=1.0)
        
        if st.button("Registrar en el Sistema") and prod_seleccionado:
            if tipo_transaccion == "Venta / Pedido de Cliente" and not nombre_cliente.strip():
                st.error("❌ El nombre del cliente es obligatorio para registrar una venta o pedido. Por favor, ingrésalo antes de continuar.")
            else:
                ahora_mexico = datetime.utcnow() - timedelta(hours=6)
                
                row_idx = None
                producto_obj = None
                inv_actuales = hoja_inv.get_all_records()
                for i, p in enumerate(inv_actuales):
                    if str(p.get("Nombre del Producto", "")).strip() == prod_seleccionado:
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
                            time.sleep(1) 
                        
                        if cant_en_deficit > 0:
                            id_ped_2 = str(int(datetime.utcnow().timestamp()) + 1)
                            hoja_pedidos.append_row([
                                id_ped_2, ahora_mexico.strftime("%d-%m-%Y %H:%M:%S"), cli_con_desc, prod_seleccionado, cant_en_deficit, "Venta", "Déficit"
                            ])
                        
                        if cant_en_deficit > 0 and cant_a_reservar > 0:
                            st.warning(f"⚠️ Pedido Mixto: Se apartaron {cant_a_reservar} unidades (listas) y quedaron {cant_en_deficit} en Déficit (esperando proveedor).")
                        elif cant_en_deficit > 0 and cant_a_reservar == 0:
                            st.warning(f"⚠️ Sin stock físico: El pedido de {cant_en_deficit} unidades se registró completamente como Déficit.")
                        else:
                            st.success(f"🛒 ¡Pedido apartado con éxito para **{cli_con_desc}** (Listo para entrega)!")
                            
                        st.cache_data.clear()
                        st.rerun()
                        
                    elif tipo_transaccion == "Salida Especial (Muestra / Merma / Consumo Propio)":
                        cant_salida = min(cantidad, stock_actual)
                        if cant_salida > 0:
                            hoja_inv.update_cell(row_idx, col_stock_idx, stock_actual - cant_salida)
                            hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), nombre_cliente, prod_seleccionado, "Salida Especial", cant_salida, 0.0])
                            st.success(f"🏷️ Salida registrada por {motivo_salida}. Se descontaron {cant_salida} unidades sin afectar las ventas financieras.")
                        else:
                            st.error("❌ No hay stock físico disponible para registrar esta salida especial.")
                        st.cache_data.clear()
                        st.rerun()
                        
                    else: 
                        nuevo_stock = stock_actual + cantidad
                        total_movimiento = 0.0
                        hoja_inv.update_cell(row_idx, col_stock_idx, nuevo_stock)
                        hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), "Proveedor", prod_seleccionado, "Compra", cantidad, total_movimiento])
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
    st.markdown("Filtra por cliente para ver sus artículos pendientes y gestiona cada entrega de forma rápida.")
    
    pedidos_pendientes = cargar_pedidos_cache()
    pendientes_activos = [p for p in pedidos_pendientes if p.get("Estado") in ["Por entregar", "Déficit"]]
    
    stock_por_producto = {}
    for inv_p in registros_inv:
        nombre_p = str(inv_p.get("Nombre del Producto", "")).strip()
        st_val = 0.0
        for k, v in inv_p.items():
            if "stock" in k.lower() or "cantidad" in k.lower():
                try:
                    st_val = float(str(v).replace(",", ""))
                    break
                except:
                    continue
        stock_por_producto[nombre_p] = st_val

    if pendientes_activos:
        def generar_pdf_pedidos(pendientes):
            buffer = io.BytesIO()
            # Margen superior incrementado a 55 para dejar espacio libre al logo superior izquierdo
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=55, bottomMargin=40)
            elements = []
            
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#4A1525'), spaceAfter=15, alignment=1)
            header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=1)
            cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
            cell_left = ParagraphStyle('CellLeft', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
            
            elements.append(Paragraph("Nature’s Select - Reporte de Pedidos Pendientes", title_style))
            elements.append(Spacer(1, 10))
            
            data = [[Paragraph("Cliente", header_style), Paragraph("Producto", header_style), Paragraph("Cantidad", header_style), Paragraph("Estado", header_style), Paragraph("Fecha", header_style)]]
            for p in pendientes:
                p_estado = str(p.get("Estado", ""))
                p_prod = str(p.get("Producto", ""))
                
                if p_estado == "Déficit":
                    st_disp = stock_por_producto.get(p_prod, 0.0)
                    if st_disp > 0:
                        p_estado = "Parcialmente Surtible / Listo"

                data.append([
                    Paragraph(str(p.get("Cliente", "")), cell_left),
                    Paragraph(p_prod, cell_left),
                    Paragraph(str(p.get("Cantidad", "")), cell_style),
                    Paragraph(p_estado, cell_style),
                    Paragraph(str(p.get("Fecha", "")), cell_style)
                ])
                
            t = Table(data, colWidths=[130, 140, 55, 85, 90])
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

        pdf_bytes = generar_pdf_pedidos(pendientes_activos)
        st.download_button(
            label="📄 Descargar Reporte de Pedidos en PDF",
            data=pdf_bytes,
            file_name=f"reporte_pedidos_{datetime.now().strftime('%d-%m-%Y')}.pdf",
            mime="application/pdf"
        )
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
                st.markdown(f"""
                    <div class="deficit-alert-card">
                        <b>👤 Cliente:</b> {def_ped.get('Cliente')} <br>
                        <b>🛍️ Producto:</b> {def_ped.get('Producto')} (Cantidad en espera de proveedor: <b>{def_ped.get('Cantidad')}</b>) <br>
                        <span style='color: gray; font-size: 11px;'>ID Pedido: {def_ped.get('ID')} | Fecha de registro: {def_ped.get('Fecha')}</span>
                    </div>
                """, unsafe_allow_html=True)
            st.markdown("---")

        if pedidos_deficit_surtible:
            st.markdown("### 🟢 Déficits con Stock Parcial o Total Disponible")
            for sur_ped in pedidos_deficit_surtible:
                p_nom_s = sur_ped.get('Producto')
                c_ped_s = float(str(sur_ped.get('Cantidad', 0)).replace(",", ""))
                st_disp_s = stock_por_producto.get(p_nom_s, 0.0)
                
                if st_disp_s >= c_ped_s:
                    aviso_txt = f"Cantidad lista para entrega: <b>{c_ped_s:g}</b> (Se cubre con el stock actual)."
                else:
                    aviso_txt = f"Cantidad en déficit: <b>{c_ped_s:g}</b>. (Tienes <b>{st_disp_s:g} en stock</b> para entregar parcialmente)."

                st.markdown(f"""
                    <div class="surtible-alert-card">
                        <b>👤 Cliente:</b> {sur_ped.get('Cliente')} <br>
                        <b>🛍️ Producto:</b> {p_nom_s} — {aviso_txt} <br>
                        <span style='color: gray; font-size: 11px;'><i>Puedes entregar lo disponible y el resto se mantendrá pendiente.</i></span>
                    </div>
                """, unsafe_allow_html=True)
            st.markdown("---")

        clientes_disponibles = sorted(list(set(p.get("Cliente") for p in pendientes_activos)))
        filtro_cliente = st.selectbox("🔍 Filtrar por Cliente específico:", ["-- Todos los Clientes --"] + clientes_disponibles)
        
        if filtro_cliente != "-- Todos los Clientes --":
            pendientes_activos = [p for p in pendientes_activos if p.get("Cliente") == filtro_cliente]
        
        st.markdown("---")
        
        for idx, ped in enumerate(pendientes_activos):
            col_info, col_btn1, col_btn2 = st.columns([4.5, 1.75, 1.75])
            
            estado_ped = ped.get('Estado')
            prod_ped = str(ped.get("Producto", ""))
            cant_ped = float(str(ped.get("Cantidad", 0)).replace(",", ""))
            stock_disponible = stock_por_producto.get(prod_ped, 0.0)
            
            if estado_ped == "Por entregar":
                estado_lbl = "📦 Reservado (Listo)"
            elif estado_ped == "Déficit":
                if stock_disponible >= cant_ped:
                    estado_lbl = "🟢 Listo para Entregar (Ya hay stock)"
                elif stock_disponible > 0:
                    estado_lbl = f"🟡 Parcial: Tienes {stock_disponible:g} en stock"
                else:
                    estado_lbl = "🚨 Déficit (Falta Stock)"
            
            with col_info:
                st.markdown(f"**👤 {ped.get('Cliente')}**  \n🛍️ **{prod_ped}** — Cantidad: **{cant_ped:g}** [{estado_lbl}] \n<span style='color: gray; font-size: 11px;'>ID: {ped.get('ID')} | Fecha: {ped.get('Fecha')}</span>", unsafe_allow_html=True)
            
            with col_btn1:
                if estado_ped == "Déficit" and stock_disponible <= 0:
                    st.button("⏳ Sin Stock", key=f"entregar_dis_{ped.get('ID')}_{idx}", disabled=True)
                else:
                    btn_label = "✅ Entregar Parcial" if stock_disponible < cant_ped else "✅ Entregar"
                    if st.button(btn_label, key=f"entregar_{ped.get('ID')}_{idx}"):
                        todos_p = hoja_pedidos.get_all_records()
                        fila_real = None
                        for i, tp in enumerate(todos_p):
                            if str(tp.get("ID")) == str(ped.get("ID")):
                                fila_real = i + 2
                                break
                        if fila_real:
                            cli_con_desc = str(ped.get("Cliente", ""))
                            
                            precio_vta = 0.0
                            inv_actuales = hoja_inv.get_all_records()
                            row_inv_idx = None
                            stock_fisc = 0.0
                            for i, inv_item in enumerate(inv_actuales):
                                if str(inv_item.get("Nombre del Producto", "")).strip() == prod_ped:
                                    row_inv_idx = i + 2
                                    for k, v in inv_item.items():
                                        if "stock" in k.lower() or "cantidad" in k.lower():
                                            try:
                                                stock_fisc = float(str(v).replace(",", ""))
                                            except:
                                                pass
                                        if "precio de venta" in k.lower():
                                            try:
                                                precio_vta = float(str(v).replace("$", "").replace(",", "").strip())
                                            except:
                                                pass
                                    break
                            
                            desc_val = 0.0
                            if "(Desc." in cli_con_desc:
                                try:
                                    desc_str = cli_con_desc.split("(Desc.")[1].split("%)")[0].strip()
                                    desc_val = float(desc_str)
                                except:
                                    pass
                            
                            ahora_mexico = datetime.utcnow() - timedelta(hours=6)
                            col_st_idx = 2
                            for idx_h, h_name in enumerate(headers):
                                if "stock" in h_name.lower():
                                    col_st_idx = idx_h + 1
                                    break
                            
                            if estado_ped == "Por entregar":
                                precio_final = precio_vta * (1.0 - (desc_val / 100.0))
                                total_vta = cant_ped * precio_final
                                hoja_pedidos.update_cell(fila_real, 7, "Entregado")
                                hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_con_desc, prod_ped, "Venta", cant_ped, total_vta])
                                st.success(f"¡Pedido entregado con éxito a {cli_con_desc}!")
                                st.cache_data.clear()
                                st.rerun()
                                
                            elif estado_ped == "Déficit":
                                cant_a_entregar = min(cant_ped, stock_fisc)
                                cant_remanente = cant_ped - cant_a_entregar
                                
                                if cant_a_entregar > 0 and row_inv_idx:
                                    hoja_inv.update_cell(row_inv_idx, col_st_idx, stock_fisc - cant_a_entregar)
                                    
                                    precio_final = precio_vta * (1.0 - (desc_val / 100.0))
                                    total_vta = cant_a_entregar * precio_final
                                    
                                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_con_desc, prod_ped, "Venta", cant_a_entregar, total_vta])
                                    
                                    if cant_remanente > 0:
                                        hoja_pedidos.update_cell(fila_real, 5, cant_remanente)
                                        st.warning(f"⚠️ Se entregaron **{cant_a_entregar:g} unidades** con el stock disponible. Quedan **{cant_remanente:g} unidades** en déficit esperando proveedor.")
                                    else:
                                        hoja_pedidos.update_cell(fila_real, 7, "Entregado")
                                        st.success(f"¡Pedido surtido por completo y entregado a {cli_con_desc}!")
                                        
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
                        
                        if estado_ped == "Por entregar":
                            inv_actuales = hoja_inv.get_all_records()
                            for i, inv_item in enumerate(inv_actuales):
                                if str(inv_item.get("Nombre del Producto", "")).strip() == prod_ped:
                                    st_act = float(str(inv_item.get("Cantidad en Stock", 0)).replace(",", ""))
                                    col_st_idx = 2
                                    for idx_h, h_name in enumerate(headers):
                                        if "stock" in h_name.lower():
                                            col_st_idx = idx_h + 1
                                            break
                                    hoja_inv.update_cell(i + 2, col_st_idx, st_act + cant_ped)
                                    
                                    stock_liberado = st_act + cant_ped
                                    deficits_producto = [
                                        (idx_tp, tp_item) for idx_tp, tp_item in enumerate(todos_p)
                                        if str(tp_item.get("Estado")) == "Déficit" and str(tp_item.get("Producto")) == prod_ped
                                    ]
                                    deficits_producto.sort(key=lambda x: str(x[1].get("Fecha", "")))
                                    
                                    for idx_otro, tp_otro in deficits_producto:
                                        cant_def = float(str(tp_otro.get("Cantidad", 0)).replace(",", ""))
                                        if stock_liberado >= cant_def:
                                            hoja_pedidos.update_cell(idx_otro + 2, 7, "Por entregar")
                                            stock_liberado -= cant_def
                                            hoja_inv.update_cell(i + 2, col_st_idx, stock_liberado)
                                    break
                            st.warning(f"Pedido cancelado. Se devolvieron **{cant_ped:g} unidades** al inventario.")
                        else:
                            st.warning("El pedido en déficit fue cancelado (No hubo movimiento de inventario).")
                            
                        st.cache_data.clear()
                        st.rerun()
            st.divider()
    else:
        st.info("No hay productos 'Por entregar' a clientes en este momento.")

with pestana3:
    st.subheader("Historial de Transacciones")
    
    registros_h = cargar_historial_cache()
    if registros_h:
        def generar_pdf_historial(historial):
            buffer = io.BytesIO()
            # Margen superior incrementado a 55 para dejar espacio libre al logo superior izquierdo
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=55, bottomMargin=40)
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
                try:
                    val_tot = float(raw_tot)
                    tot_fmt = f"${val_tot:,.2f}"
                except:
                    tot_fmt = f"${0.0:,.2f}"

                raw_cant = str(h.get("Cantidad", "0")).replace("$", "").replace(",", "").strip()
                try:
                    val_cant = float(raw_cant)
                    cant_fmt = str(int(val_cant)) if val_cant.is_integer() else f"{val_cant:g}"
                except:
                    cant_fmt = raw_cant

                data.append([
                    Paragraph(str(h.get("Fecha", "")), cell_style),
                    Paragraph(str(h.get("Producto", "")), cell_left),
                    Paragraph(str(h.get("Cliente", "")), cell_left),
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
                df_hist["Total"] = pd.to_numeric(df_hist["Total"].astype(str).str.replace("$", "").str.replace(",", "").str.strip(), errors="coerce").fillna(0)
                df_hist["Total"] = df_hist["Total"].apply(lambda x: f"${x:,.2f}")
            if "Cantidad" in df_hist.columns:
                df_hist["Cantidad"] = pd.to_numeric(df_hist["Cantidad"].astype(str).str.replace("$", "").str.replace(",", "").str.strip(), errors="coerce").fillna(0)
                df_hist["Cantidad"] = df_hist["Cantidad"].apply(lambda x: str(int(x)) if x.is_integer() else f"{x:g}")

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
                df_ventas = df_h[df_h["Compra/Venta"] == "Venta"].copy()
            else:
                df_ventas = df_h.copy()
                
            if not df_ventas.empty:
                try:
                    df_ventas["Fecha_str"] = df_ventas["Fecha"].astype(str).str.strip()
                    df_ventas["Mes"] = df_ventas["Fecha_str"].str.slice(3, 10)
                    df_ventas["Cantidad_num"] = pd.to_numeric(df_ventas["Cantidad"].astype(str).str.replace("$", "").str.replace(",", "").str.strip(), errors="coerce").fillna(0)
                    
                    totales_prod_mes = df_ventas.groupby(["Producto", "Mes"])["Cantidad_num"].sum().reset_index()
                    promedios = totales_prod_mes.groupby("Producto")["Cantidad_num"].mean().reset_index()
                    for _, row in promedios.iterrows():
                        promedios_dict[row["Producto"]] = float(row["Cantidad_num"])
                except:
                    pass

        lista_resurtido = []
        gran_total_inversion = 0.0

        for p in registros_inv:
            nombre = str(p.get("Nombre del Producto", "")).strip()
            stock = float(str(p.get("Cantidad in Stock", 0) or 0).replace(",", ""))
            
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
            # Margen superior incrementado a 55 para dejar espacio libre al logo superior izquierdo
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=55, bottomMargin=40)
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
                
            t = Table(data, colWidths=[140, 50, 70, 60, 60, 65, 95])
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
            elements.append(Spacer(1, 15))
            
            total_style = ParagraphStyle('TotalStyle', parent=styles['Normal'], fontSize=12, textColor=colors.HexColor('#4A1525'), fontName='Helvetica-Bold', alignment=2)
            elements.append(Paragraph(f"Inversión Total Estimada: ${total_inv:,.2f}", total_style))
            
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
