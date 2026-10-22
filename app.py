import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import base64
import pandas as pd
import time

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

@st.cache_data(ttl=900)
def cargar_inventario_cache():
    time.sleep(0.5)
    return hoja_inv.get_all_records()

@st.cache_data(ttl=900)
def cargar_pedidos_cache():
    time.sleep(0.5)
    return hoja_pedidos.get_all_records()

@st.cache_data(ttl=900)
def cargar_historial_cache():
    time.sleep(0.5)
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
    "🛒 Pedidos", 
    "📦 Control de Pedidos", 
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
                            id_ped_2 = str(int(datetime.utcnow().timestamp()))
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
        
        cols_a_quitar = [c for c in df_inv.columns if "precio directo" in c.lower() or "directo" in c.lower() or "por surtir" in c.lower() or "por_surtir" in c.lower() or "presentacion" in c.lower() or "presentación" in c.lower()]
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
            
        st.dataframe(df_inv, use_container_width=True)

with pestana2:
    st.subheader("📦 Control de Pedidos y Entregas")
    st.markdown("Filtra por cliente para ver sus artículos pendientes y gestiona cada entrega de forma rápida.")
    
    pedidos_pendientes = cargar_pedidos_cache()
    pendientes_activos = [p for p in pedidos_pendientes if p.get("Estado") in ["Por entregar", "Déficit"]]
    
    if pendientes_activos:
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

        pedidos_deficit_real = []
        pedidos_deficit_surtible = []
        
        for ped in pendientes_activos:
            if ped.get("Estado") == "Déficit":
                p_nom = ped.get("Producto")
                c_ped = float(str(ped.get("Cantidad", 0)).replace(",", ""))
                st_disp = stock_por_producto.get(p_nom, 0.0)
                if st_disp >= c_ped:
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
            st.markdown("### 🟢 Déficits Listos para Entregar (Ya hay Stock)")
            for sur_ped in pedidos_deficit_surtible:
                st.markdown(f"""
                    <div class="surtible-alert-card">
                        <b>👤 Cliente:</b> {sur_ped.get('Cliente')} <br>
                        <b>🛍️ Producto:</b> {sur_ped.get('Producto')} (Cantidad lista para entrega: <b>{sur_ped.get('Cantidad')}</b>) <br>
                        <span style='color: gray; font-size: 11px;'><i>Ya entró mercancía suficiente al inventario para cubrir este pedido. Puedes entregarlo directamente abajo.</i></span>
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
                else:
                    estado_lbl = "🚨 Déficit (Falta Stock)"
            
            with col_info:
                st.markdown(f"**👤 {ped.get('Cliente')}**  \n🛍️ **{prod_ped}** — Cantidad: **{cant_ped:g}** [{estado_lbl}] \n<span style='color: gray; font-size: 11px;'>ID: {ped.get('ID')} | Fecha: {ped.get('Fecha')}</span>", unsafe_allow_html=True)
            
            with col_btn1:
                if estado_ped == "Déficit" and stock_disponible < cant_ped:
                    st.button("⏳ Sin Stock", key=f"entregar_dis_{ped.get('ID')}_{idx}", disabled=True)
                else:
                    if st.button("✅ Entregar", key=f"entregar_{ped.get('ID')}_{idx}"):
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
                            
                            precio_final = precio_vta * (1.0 - (desc_val / 100.0))
                            total_vta = cant_ped * precio_final
                            ahora_mexico = datetime.utcnow() - timedelta(hours=6)
                            
                            col_st_idx = 2
                            for idx_h, h_name in enumerate(headers):
                                if "stock" in h_name.lower():
                                    col_st_idx = idx_h + 1
                                    break
                            
                            if estado_ped == "Por entregar":
                                hoja_pedidos.update_cell(fila_real, 7, "Entregado")
                                hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_con_desc, prod_ped, "Venta", cant_ped, total_vta])
                                st.success(f"¡Pedido entregado con éxito a {cli_con_desc}!")
                                st.cache_data.clear()
                                st.rerun()
                            elif estado_ped == "Déficit":
                                if stock_fisc >= cant_ped and row_inv_idx:
                                    hoja_inv.update_cell(row_inv_idx, col_st_idx, stock_fisc - cant_ped)
                                    hoja_pedidos.update_cell(fila_real, 7, "Entregado")
                                    hoja_hist.append_row([ahora_mexico.strftime("%d-%m-%Y"), ahora_mexico.strftime("%H:%M:%S"), cli_con_desc, prod_ped, "Venta", cant_ped, total_vta])
                                    st.success(f"¡Pedido surtido directamente y entregado a {cli_con_desc}!")
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
                                    break
                            st.warning(f"Pedido cancelado. Se devolvieron **{cant_ped:g} unidades** de {prod_ped} al inventario.")
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
        df_hist = pd.DataFrame(registros_h)
        if not df_hist.empty:
            df_hist = df_hist.iloc[::-1]
            
            if "Total" in df_hist.columns:
                df_hist["Total"] = pd.to_numeric(df_hist["Total"].astype(str).str.replace("$", "").str.replace(",", "").str.strip(), errors="coerce").fillna(0)
                df_hist["Total"] = df_hist["Total"].apply(lambda x: f"${x:,.2f}")
            if "Cantidad" in df_hist.
