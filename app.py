import streamlit as st
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Nature's Select - Sistema de Inventario",
    page_icon="🌿",
    layout="wide"
)

# Estilos CSS personalizados para la identidad de Nature's Select
st.markdown("""
    <style>
    .main {
        background-color: #FAFAFA;
    }
    h1, h2, h3 {
        font-family: 'Montserrat', sans-serif;
        color: #263238;
    }
    .stButton>button {
        background-color: #2E7D32;
        color: white;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #1B5E20;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Título principal
st.title("🌿 Nature's Select - Control de Inventario y Pedidos")

# Simulación de carga de datos (Reemplazar con tu conexión real a Google Sheets / gspread)
@st.cache_data
def cargar_inventario():
    # Datos de ejemplo basados en tu estructura actual
    data = {
        "Nombre del Producto": [
            "Ashwagandha plb. 200g", 
            "Cacao en Polvo 200g", 
            "Cacao en trozos 500g", 
            "Curcuma en plb. 150g", 
            "Spirulina en Pastilla 500g",
            "Jengibre de plb. 150g",
            "Magnesio 250g",
            "Matcha 125g",
            "Raíz de maca 200g",
            "Te chai 75g"
        ],
        "Cantidad en Stock": [6, 5, 3, 3, 7, 2, 3, 4, 4, 5],
        "Por entregar": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "Precio de Venta": [320.00, 220.00, 265.00, 165.00, 235.00, 129.00, 279.00, 230.00, 179.00, 199.00],
        "Imagen 1": ["https://...", "https://...", "https://...", "https://...", "https://...", "https://...", "https://...", "https://...", "https://...", "https://..."],
        "Imagen 2": ["https://...", "https://...", "https://...", "https://...", "https://...", "https://...", "https://...", "https://...", "https://...", "https://..."],
        "beneficios": [
            "Ayuda a reducir el estrés y la ansiedad...",
            "Alto contenido de antioxidantes...",
            "Ideal como snack saludable...",
            "Potente antiinflamatorio natural...",
            "Gran fuente de proteínas...",
            "Estimula la digestión...",
            "Contribuye al funcionamiento muscular...",
            "Acelera el metabolismo...",
            "Potencia la energía física y mental...",
            "Propiedades digestivas y antiinflamatorias..."
        ]
    }
    return pd.DataFrame(data)

df_inventario = cargar_inventario()

# Pestañas de navegación de la aplicación
pestanas = st.tabs([
    "Registrar Pedido", 
    "Pedidos", 
    "Historial", 
    "Resurtido", 
    "Nuevo Producto", 
    "Catálogo Web WhatsApp"
])

# --- PESTAÑA 1: REGISTRAR PEDIDO ---
with pestanas[0]:
    st.header("Registrar Pedido o Movimiento")
    
    # Selección de producto
    producto_seleccionado = st.selectbox(
        "Selecciona Producto", 
        df_inventario["Nombre del Producto"].tolist()
    )
    
    # Obtener datos del producto seleccionado
    prod_info = df_inventario[df_inventario["Nombre del Producto"] == producto_seleccionado].iloc[0]
    
    st.info(f"📦 **Existencia Física Actual:** {prod_info['Cantidad en Stock']} unidades")
    
    # Tipo de transacción
    tipo_transaccion = st.radio(
        "Tipo de Transacción", 
        [
            "Venta / Pedido de Cliente", 
            "Devolución de Cliente (Reingreso)", 
            "Salida Especial (Muestra / Merma / Consumo Propio)", 
            "Compra (Entrada de Proveedor)"
        ]
    )
    
    nombre_cliente = st.text_input("Nombre del Cliente * (Obligatorio)")
    descuento = st.number_input("Descuento aplicable (%)", min_value=0.0, max_value=100.0, value=0.0)
    cantidad = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
    
    if st.button("Registrar en el Sistema"):
        if not nombre_cliente and "Venta" in tipo_transaccion:
            st.error("Por favor, ingresa el nombre del cliente.")
        else:
            st.success(f"¡Transacción registrada exitosamente para {producto_seleccionado}!")

    st.markdown("---")
    
    # --- SECCIÓN: ESTADO ACTUAL DEL INVENTARIO (MODIFICADA) ---
    st.subheader("Estado Actual del Inventario")
    
    # Excluimos las columnas de imágenes y beneficios para una vista limpia
    columnas_ocultas = ['Imagen 1', 'Imagen 2', 'beneficios', 'imagen1', 'imagen2']
    columnas_a_mostrar = [col for col in df_inventario.columns if col not in columnas_ocultas]
    
    # Mostramos la tabla filtrada ocupando todo el ancho disponible
    st.dataframe(
        df_inventario[columnas_a_mostrar], 
        use_container_width=True,
        hide_index=True
    )

# --- PESTAÑA 2: PEDIDOS ---
with pestanas[1]:
    st.header("Gestión de Pedidos Activos")
    st.write("Aquí puedes visualizar y dar seguimiento a los pedidos pendientes de entrega.")

# --- PESTAÑA 3: HISTORIAL ---
with pestanas[2]:
    st.header("Historial de Movimientos")
    st.write("Registro detallado de entradas, salidas y ventas anteriores.")

# --- PESTAÑA 4: RESURTIDO ---
with pestanas[3]:
    st.header("Sugerencias de Resurtido")
    st.write("Análisis de stock mínimo y alertas para reabastecimiento de productos.")

# --- PESTAÑA 5: NUEVO PRODUCTO ---
with pestanas[4]:
    st.header("Dar de Alta un Nuevo Producto")
    with st.form("form_nuevo_producto"):
        nuevo_nombre = st.text_input("Nombre del Producto")
        nuevo_stock = st.number_input("Stock Inicial", min_value=0, value=0)
        nuevo_precio = st.number_input("Precio de Venta ($)", min_value=0.0, value=0.0)
        nuevo_beneficio = st.text_area("Beneficios / Descripción")
        link_img1 = st.text_input("URL Imagen 1 (GitHub)")
        link_img2 = st.text_input("URL Imagen 2 (GitHub)")
        
        submit_producto = st.form_submit_button("Guardar Producto")
        if submit_producto:
            st.success(f"Producto '{nuevo_nombre}' agregado correctamente.")

# --- PESTAÑA 6: CATÁLOGO WEB WHATSAPP ---
with pestanas[5]:
    st.header("Configuración del Catálogo Web")
    st.write("Enlace directo a tu repositorio de GitHub Pages y vista previa del carrito de WhatsApp.")
    st.markdown("[🔗 Ver Catálogo en Línea (GitHub Pages)](https://ruiseartmg.github.io/inventario-suplementos/)")
