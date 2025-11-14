import streamlit as st

st.title("Dashboard F1 Pitstop Strategy - Test")

st.sidebar.header("Configuración")
track = st.sidebar.selectbox("Circuito", ["Bahrain"], index=0)

st.write("Dashboard de prueba funcionando correctamente.")

# Simular algunas pestañas básicas
tab1, tab2 = st.tabs(["Datos", "Análisis"])

with tab1:
    st.write("Pestaña de datos")

with tab2:
    st.write("Pestaña de análisis")

st.success("¡El dashboard se cargó exitosamente!")
