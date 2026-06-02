import streamlit as st
import numpy as np
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import io

# ==============================================================================
# CONFIGURACIÓN DE LA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="FarmaCosta S.A. - Optimizador de Rutas",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado de CSS
st.markdown("""
    <style>
        .reportview-container { background: #f4f6f9; }
        .main-header { color: #1E3A8A; font-weight: bold; margin-bottom: 20px; }
        .card { 
            background-color: white; 
            padding: 20px; 
            border-radius: 10px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
            margin-bottom: 20px; 
        }
        .metric-card {
            background-color: #E0F2FE;
            border-left: 5px solid #0284C7;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# Factor de conversión métrica estándar para coordenadas geográficas a metros (Región Caribe)
SF = 111000  

# ==============================================================================
# ESTADO DE LA APLICACIÓN (STATE)
# ==============================================================================
# Valores iniciales tomados del caso FarmaCosta S.A.
if "nodos" not in st.session_state:
    st.session_state.nodos = pd.DataFrame({
        "ID": [0, 1, 2, 3, 4, 5],
        "Nombre": [
            "CEDI Vía 40", 
            "Hospital Centro", 
            "Clínica Miramar", 
            "Sede Riomar", 
            "Hosp. Soledad", 
            "Clínica Las Nieves"
        ],
        "Tipo": ["Depósito", "Cliente", "Cliente", "Cliente", "Cliente", "Cliente"],
        "Latitud (Y)": [11.015, 10.978, 11.021, 11.011, 10.916, 10.960],
        "Longitud (X)": [-74.805, -74.786, -74.827, -74.814, -74.764, -74.779],
        "Demanda (kg)": [0, 800, 600, 1100, 1500, 700]
    })

# ==============================================================================
# PANEL LATERAL DE CONFIGURACIÓN
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/delivery-truck.png", width=80)
    st.title("Parámetros del Sistema")
    st.markdown("Ajusta los límites de la flota para el cálculo de rutas.")
    
    cap_maxima = st.number_input(
        "Capacidad Máxima por Camioneta (kg):", 
        min_value=100, 
        max_value=10000, 
        value=1800, 
        step=100
    )
    
    vehiculos_disponibles = st.number_input(
        "Camionetas Disponibles en la Flota:", 
        min_value=1, 
        max_value=20, 
        value=3, 
        step=1
    )
    
    st.markdown("---")
    st.markdown("### Acciones Rápidas")
    
    # Botón para restablecer el caso de prueba original
    if st.button("Restablecer Caso Original"):
        st.session_state.nodos = pd.DataFrame({
            "ID": [0, 1, 2, 3, 4, 5],
            "Nombre": ["CEDI Vía 40", "Hospital Centro", "Clínica Miramar", "Sede Riomar", "Hosp. Soledad", "Clínica Las Nieves"],
            "Tipo": ["Depósito", "Cliente", "Cliente", "Cliente", "Cliente", "Cliente"],
            "Latitud (Y)": [11.015, 10.978, 11.021, 11.011, 10.916, 10.960],
            "Longitud (X)": [-74.805, -74.786, -74.827, -74.814, -74.764, -74.779],
            "Demanda (kg)": [0, 800, 600, 1100, 1500, 700]
        })
        st.rerun()

    # Botón para limpiar todos los clientes (dejar solo el CEDI)
    if st.button("Limpiar todos los clientes"):
        st.session_state.nodos = pd.DataFrame({
            "ID": [0],
            "Nombre": ["CEDI Principal"],
            "Tipo": ["Depósito"],
            "Latitud (Y)": [11.015],
            "Longitud (X)": [-74.805],
            "Demanda (kg)": [0]
        })
        st.rerun()

# ==============================================================================
# TITULO PRINCIPAL DE LA APP
# ==============================================================================
st.markdown("<h1 class='main-header'>🚚 Optimizador Logístico de Rutas VRP - FarmaCosta S.A.</h1>", unsafe_allow_html=True)
st.markdown("Planifica y optimiza de forma inteligente el ruteo de tus vehículos utilizando la heurística de ahorros de **Clarke y Wright**.")

# ==============================================================================
# SECCIONES EN PESTAÑAS (TABS)
# ==============================================================================
tab_gestion, tab_analisis, tab_mapa_interactivo = st.tabs([
    "📂 Gestión de Nodos (CEDI & Clientes)", 
    "📊 Resultados de Optimización", 
    "🗺️ Mapa Interactivo de Rutas"
])

# ------------------------------------------------------------------------------
# PESTAÑA 1: GESTIÓN DE NODOS (CEDI Y CLIENTES)
# ------------------------------------------------------------------------------
with tab_gestion:
    st.markdown("### Ubicaciones Actuales")
    st.markdown("Puedes modificar los nombres, coordenadas y demandas directamente en la tabla editable a continuación:")
    
    # Editor de datos nativo e intuitivo
    df_editado = st.data_editor(
        st.session_state.nodos,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "ID": st.column_config.NumberColumn("ID", disabled=True),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Depósito", "Cliente"]),
            "Nombre": st.column_config.TextColumn("Nombre del Nodo", required=True),
            "Latitud (Y)": st.column_config.NumberColumn("Latitud (Y)", format="%.6f", required=True),
            "Longitud (X)": st.column_config.NumberColumn("Longitud (X)", format="%.6f", required=True),
            "Demanda (kg)": st.column_config.NumberColumn("Demanda (kg)", min_value=0, required=True),
        }
    )
    
    # Validar que siempre exista exactamente un depósito
    depositos = df_editado[df_editado["Tipo"] == "Depósito"]
    if len(depositos) == 0:
        st.error("⚠️ Debe existir al menos un nodo tipo 'Depósito' (CEDI) como origen.")
    elif len(depositos) > 1:
        st.warning("⚠️ Se detectaron múltiples depósitos. El sistema utilizará el primero de la lista (ID con menor valor) como CEDI oficial.")
    
    # Botón para guardar los cambios en memoria de sesión
    if st.button("Aplicar y Actualizar Nodos", use_container_width=True):
        # Corregir IDs de manera incremental
        df_editado = df_editado.reset_index(drop=True)
        df_editado["ID"] = df_editado.index
        
        # El depósito debe tener demanda 0
        df_editado.loc[df_editado["Tipo"] == "Depósito", "Demanda (kg)"] = 0
        
        st.session_state.nodos = df_editado
        st.success("✅ ¡Base de datos de nodos actualizada de forma exitosa!")
        st.rerun()

    # Formulario rápido para agregar nuevos clientes de forma individual
    with st.expander("➕ Añadir Nodo mediante Formulario Rápido"):
        with st.form("form_nuevo_nodo"):
            col1, col2, col3 = st.columns(3)
            with col1:
                nuevo_nombre = st.text_input("Nombre del Punto", placeholder="Ej. Clínica del Norte")
                tipo_nodo = st.selectbox("Tipo de Nodo", ["Cliente", "Depósito"])
            with col2:
                nueva_lat = st.number_input("Latitud (Y)", format="%.6f", value=11.000)
                nueva_lon = st.number_input("Longitud (X)", format="%.6f", value=-74.800)
            with col3:
                nueva_demanda = st.number_input("Demanda del Cliente (kg)", min_value=0, value=500, step=50)
            
            submit_btn = st.form_submit_button("Registrar Punto en el Sistema")
            
            if submit_btn:
                if nuevo_nombre.strip() == "":
                    st.error("El nombre del nodo no puede estar vacío.")
                else:
                    nuevo_id = int(st.session_state.nodos["ID"].max() + 1) if len(st.session_state.nodos) > 0 else 0
                    fila_nueva = pd.DataFrame([{
                        "ID": nuevo_id,
                        "Nombre": nuevo_nombre,
                        "Tipo": tipo_nodo,
                        "Latitud (Y)": nueva_lat,
                        "Longitud (X)": nueva_lon,
                        "Demanda (kg)": 0 if tipo_nodo == "Depósito" else nueva_demanda
                    }])
                    st.session_state.nodos = pd.concat([st.session_state.nodos, fila_nueva], ignore_index=True)
                    st.success(f"📍 '{nuevo_nombre}' agregado correctamente.")
                    st.rerun()

# ==============================================================================
# LÓGICA DE ALGORITMO Y CÁLCULOS
# ==============================================================================
# Construir la estructura de datos para resolver el problema
df_nodos_activos = st.session_state.nodos.copy()
num_nodos = len(df_nodos_activos)

# Buscar el depósito principal (CEDI)
idx_deposito = df_nodos_activos[df_nodos_activos["Tipo"] == "Depósito"].index
if len(idx_deposito) > 0:
    depot_idx = idx_deposito[0]
else:
    depot_idx = 0  # Fallback por seguridad

# Reorganizar el DataFrame de forma que el depósito sea siempre la posición indexada [0]
if depot_idx != 0 and num_nodos > 0:
    # Mover el depósito al principio
    depot_row = df_nodos_activos.iloc[[depot_idx]]
    clientes_rows = df_nodos_activos.drop(depot_idx)
    df_nodos_activos = pd.concat([depot_row, clientes_rows]).reset_index(drop=True)
    df_nodos_activos["ID"] = df_nodos_activos.index

# Calcular Matriz de Distancias (Metros)
matriz_distancias = np.zeros((num_nodos, num_nodos))
for i in range(num_nodos):
    for j in range(num_nodos):
        lat_i, lon_i = df_nodos_activos.loc[i, "Latitud (Y)"], df_nodos_activos.loc[i, "Longitud (X)"]
        lat_j, lon_j = df_nodos_activos.loc[j, "Latitud (Y)"], df_nodos_activos.loc[j, "Longitud (X)"]
        dist_grados = np.sqrt((lat_i - lat_j)**2 + (lon_i - lon_j)**2)
        matriz_distancias[i, j] = dist_grados * SF

# Definición del Algoritmo de Ahorros Clarke-Wright adaptado para el depósito dinámico [0]
def resolver_cvrp_clarke_wright_dinamico(df, dist_matrix, cap_max):
    n = len(df)
    if n <= 1:
        return []
    
    demandas = df["Demanda (kg)"].values
    ahorros = []
    
    # Calcular ahorros relativos al nodo indexado en 0 (CEDI)
    for i in range(1, n):
        for j in range(i + 1, n):
            s = dist_matrix[0, i] + dist_matrix[0, j] - dist_matrix[i, j]
            ahorros.append((s, i, j))
            
    # Ordenar ahorros de mayor a menor
    ahorros.sort(key=lambda x: x[0], reverse=True)
    
    # Inicializar rutas individuales (CEDI -> Cliente -> CEDI)
    rutas = [[0, i, 0] for i in range(1, n)]
    
    for s, i, j in ahorros:
        ruta_i = None
        ruta_j = None
        
        # Localizar a qué rutas pertenecen los nodos i y j
        for r in rutas:
            if r[1] == i and len(r) == 3:
                ruta_i = r
            elif r[-2] == i and r[1] != i:
                ruta_i = r
                
            if r[1] == j and len(r) == 3:
                ruta_j = r
            elif r[1] == j and r[-2] != j:
                ruta_j = r
        
        # Validar posibilidad de fusión
        if ruta_i and ruta_j and (ruta_i != ruta_j):
            nodos_i = ruta_i[1:-1]
            nodos_j = ruta_j[1:-1]
            demanda_total = sum(demandas[nodo] for nodo in (nodos_i + nodos_j))
            
            if demanda_total <= cap_max:
                if ruta_i[-2] == i and ruta_j[1] == j:
                    nueva_ruta = [0] + nodos_i + nodos_j + [0]
                    rutas.remove(ruta_i)
                    rutas.remove(ruta_j)
                    rutas.append(nueva_ruta)
                elif ruta_j[-2] == j and ruta_i[1] == i:
                    nueva_ruta = [0] + nodos_j + nodos_i + [0]
                    rutas.remove(ruta_i)
                    rutas.remove(ruta_j)
                    rutas.append(nueva_ruta)
                    
    return rutas

# Resolver sólo si hay clientes disponibles en el set
rutas_optimas = []
error_mensaje = ""
if num_nodos > 1:
    # Comprobar si hay demandas que excedan la capacidad máxima individualmente
    clientes_excedidos = df_nodos_activos[df_nodos_activos["Demanda (kg)"] > cap_maxima]
    if not clientes_excedidos.empty:
        error_mensaje = f"⚠️ Error: Hay clientes cuya demanda supera la capacidad máxima de la camioneta ({cap_maxima} kg): {', '.join(clientes_excedidos['Nombre'].tolist())}."
    else:
        rutas_optimas = resolver_cvrp_clarke_wright_dinamico(df_nodos_activos, matriz_distancias, cap_maxima)
else:
    error_mensaje = "📍 Registre clientes en la base de datos para generar y optimizar la planeación de ruteo."

# ------------------------------------------------------------------------------
# PESTAÑA 2: RESULTADOS DE OPTIMIZACIÓN
# ------------------------------------------------------------------------------
with tab_analisis:
    if error_mensaje:
        st.error(error_mensaje)
    else:
        st.markdown("### Resumen Ejecutivo de Flota")
        
        # Cálculo de Métricas Consolidadas
        distancia_total_flota = 0
        camionetas_utilizadas = len(rutas_optimas)
        carga_total_repartida = df_nodos_activos["Demanda (kg)"].sum()
        
        datos_tabla_rutas = []
        
        for idx, ruta in enumerate(rutas_optimas):
            nombres_ruta = [df_nodos_activos.loc[node, "Nombre"] for node in ruta]
            carga_ruta = sum(df_nodos_activos.loc[node, "Demanda (kg)"] for node in ruta)
            
            dist_ruta = 0
            for k in range(len(ruta) - 1):
                dist_ruta += matriz_distancias[ruta[k], ruta[k+1]]
            
            distancia_total_flota += dist_ruta
            
            datos_tabla_rutas.append({
                "Vehículo": f"Camioneta #{idx + 1}",
                "Trayectoria": " ➡️ ".join(nombres_ruta),
                "Carga Transportada (kg)": carga_ruta,
                "Porcentaje Capacidad": f"{(carga_ruta/cap_maxima)*100:.1f}%",
                "Distancia (km)": round(dist_ruta/1000, 3)
            })

        # Renderizar Tarjetas de Métricas Clave
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.markdown(f"<div class='metric-card'><h4>Distancia Total</h4><h2>{distancia_total_flota/1000:.2f} km</h2></div>", unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"<div class='metric-card'><h4>Vehículos Requeridos</h4><h2>{camionetas_utilizadas} / {vehiculos_disponibles}</h2></div>", unsafe_allow_html=True)
        with col_m3:
            st.markdown(f"<div class='metric-card'><h4>Carga Entregada</h4><h2>{carga_total_repartida} kg</h2></div>", unsafe_allow_html=True)
        with col_m4:
            cap_promedio_uso = np.mean([ (sum(df_nodos_activos.loc[node, "Demanda (kg)"] for node in r)/cap_maxima)*100 for r in rutas_optimas ]) if rutas_optimas else 0
            st.markdown(f"<div class='metric-card'><h4>Eficiencia Flota</h4><h2>{cap_promedio_uso:.1f}%</h2></div>", unsafe_allow_html=True)
        
        if camionetas_utilizadas > vehiculos_disponibles:
            st.error(f"🚨 Alerta Logística: Se requieren {camionetas_utilizadas} camionetas, pero solo tienes {vehiculos_disponibles} vehículos disponibles. Se recomienda reconfigurar la flota, incrementar la capacidad o priorizar entregas.")

        st.markdown("### Tabla Detallada por Vehículo")
        df_resultados = pd.DataFrame(datos_tabla_rutas)
        st.dataframe(df_resultados, use_container_width=True, hide_index=True)
        
        # Descarga de Reportes
        col_desc1, col_desc2 = st.columns(2)
        with col_desc1:
            # Reporte en formato CSV
            csv = df_resultados.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Programación en CSV",
                data=csv,
                file_name='planeacion_rutas_farmacosta.csv',
                mime='text/csv',
                use_container_width=True
            )
        with col_desc2:
            # Reporte en Excel usando buffer de bytes
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_resultados.to_excel(writer, index=False, sheet_name='PlanRutas')
            excel_data = output.getvalue()
            st.download_button(
                label="📥 Descargar Programación en Excel",
                data=excel_data,
                file_name='planeacion_rutas_farmacosta.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True
            )

        # Gráfico estático auxiliar con Matplotlib
        st.markdown("### Esquema Gráfico Euclidiano 2D")
        col_plot, col_matriz = st.columns([2, 1])
        
        with col_plot:
            fig, ax = plt.subplots(figsize=(10, 7))
            colores_plot = ['#FF5733', '#33C1FF', '#2ECC71', '#9B59B6', '#F39C12', '#16A085']
            
            # Dibujar el depósito
            ax.scatter(
                df_nodos_activos.loc[0, "Longitud (X)"], df_nodos_activos.loc[0, "Latitud (Y)"],
                color='red', marker='s', s=180, edgecolor='black', zorder=5, label='CEDI (Depósito)'
            )
            
            # Dibujar los clientes
            if len(df_nodos_activos) > 1:
                ax.scatter(
                    df_nodos_activos.loc[1:, "Longitud (X)"], df_nodos_activos.loc[1:, "Latitud (Y)"],
                    color='#34495E', marker='o', s=100, edgecolor='white', zorder=4, label='Clientes/Hospitales'
                )
            
            # Graficar trayectorias
            for idx, r in enumerate(rutas_optimas):
                color = colores_plot[idx % len(colores_plot)]
                x_coords = [df_nodos_activos.loc[nodo, "Longitud (X)"] for nodo in r]
                y_coords = [df_nodos_activos.loc[nodo, "Latitud (Y)"] for nodo in r]
                
                # Líneas de conexión
                ax.plot(x_coords, y_coords, color=color, linewidth=2.5, alpha=0.8, label=f'Ruta #{idx+1}')
                
                # Agregar etiquetas de nombres de clientes
                for n in r[1:-1]:
                    ax.text(
                        df_nodos_activos.loc[n, "Longitud (X)"] + 0.001,
                        df_nodos_activos.loc[n, "Latitud (Y)"] + 0.001,
                        f"{df_nodos_activos.loc[n, 'Nombre']}\n({df_nodos_activos.loc[n, 'Demanda (kg)']} kg)",
                        fontsize=8, fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none')
                    )
            
            ax.set_title("Trayectoria Euclidiana de Despachos", fontsize=12, fontweight='bold')
            ax.set_xlabel("Longitud (X)")
            ax.set_ylabel("Latitud (Y)")
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.legend()
            st.pyplot(fig)
            
        with col_matriz:
            st.markdown("#### Matriz O-D de Referencia (Metros)")
            df_dist_matrix = pd.DataFrame(
                matriz_distancias,
                columns=df_nodos_activos["Nombre"],
                index=df_nodos_activos["Nombre"]
            ).round(1)
            st.dataframe(df_dist_matrix, use_container_width=True)

# ------------------------------------------------------------------------------
# PESTAÑA 3: MAPA INTERACTIVO DE RUTAS (FOLIUM)
# ------------------------------------------------------------------------------
with tab_mapa_interactivo:
    if error_mensaje:
        st.error(error_mensaje)
    else:
        st.markdown("### Mapa Geográfico de Despacho")
        st.markdown("Este mapa interactivo muestra las rutas reales sobrepuestas en la geografía. Puedes hacer zoom y dar clic en los pines para ver más información.")
        
        # Calcular centro geográfico del mapa
        lat_centro = df_nodos_activos["Latitud (Y)"].mean()
        lon_centro = df_nodos_activos["Longitud (X)"].mean()
        
        # Crear mapa base folium
        m = folium.Map(location=[lat_centro, lon_centro], zoom_start=12, control_scale=True)
        
        # Marcador del CEDI
        folium.Marker(
            location=[df_nodos_activos.loc[0, "Latitud (Y)"], df_nodos_activos.loc[0, "Longitud (X)"]],
            popup=f"<b>CEDI Principal: {df_nodos_activos.loc[0, 'Nombre']}</b><br>Punto de Origen y Retorno",
            tooltip=df_nodos_activos.loc[0, "Nombre"],
            icon=folium.Icon(color="red", icon="home", prefix="fa")
        ).add_to(m)
        
        # Colores HTML asignados a rutas
        colores_folium = ["red", "blue", "green", "purple", "orange", "darkred", "lightred", "darkblue", "darkgreen"]
        
        # Dibujar cada ruta y sus paradas en el mapa interactivo
        for idx, r in enumerate(rutas_optimas):
            color_ruta = colores_folium[idx % len(colores_folium)]
            puntos_coordenadas = []
            
            for orden, nodo in enumerate(r):
                lat = df_nodos_activos.loc[nodo, "Latitud (Y)"]
                lon = df_nodos_activos.loc[nodo, "Longitud (X)"]
                nombre = df_nodos_activos.loc[nodo, "Nombre"]
                demanda = df_nodos_activos.loc[nodo, "Demanda (kg)"]
                puntos_coordenadas.append([lat, lon])
                
                # Si no es el depósito, colocar pin del cliente con detalles de entrega
                if nodo != 0:
                    folium.Marker(
                        location=[lat, lon],
                        popup=f"<b>Cliente:</b> {nombre}<br><b>Demanda:</b> {demanda} kg<br><b>Ruta:</b> Camioneta #{idx+1}<br><b>Secuencia:</b> {orden}",
                        tooltip=f"{nombre} ({demanda} kg)",
                        icon=folium.Icon(color=color_ruta, icon="shopping-cart", prefix="fa")
                    ).add_to(m)
            
            # Dibujar la línea de la trayectoria
            folium.PolyLine(
                locations=puntos_coordenadas,
                color=color_ruta,
                weight=4.5,
                opacity=0.85,
                tooltip=f"Trayecto de Camioneta #{idx + 1}"
            ).add_to(m)
        
        # Renderizar mapa en Streamlit
        st_folium(m, width="100%", height=550)
