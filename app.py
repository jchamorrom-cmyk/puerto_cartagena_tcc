import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Logística portuaria", layout="wide")

@st.cache_data
def cargar():
    ruta = Path(__file__).parent / "puerto_limpio.csv"
    return pd.read_csv(ruta, parse_dates=["Hora_Llegada", "Hora_Atraque"])

df = cargar()

# ---------- Barra lateral: filtros y supuestos ----------
st.sidebar.header("Filtros")
rango = st.sidebar.date_input(
    "Rango de fechas",
    (df["Hora_Llegada"].min().date(), df["Hora_Llegada"].max().date()),
)
if len(rango) != 2:
    st.info("Selecciona la fecha inicial y la final.")
    st.stop()
f_ini, f_fin = rango

cargas = st.sidebar.multiselect("Tipo de carga", sorted(df["Tipo_Carga"].unique()),
                                default=sorted(df["Tipo_Carga"].unique()))
climas = st.sidebar.multiselect("Condición climática", sorted(df["Condicion_Climatica"].unique()),
                                default=sorted(df["Condicion_Climatica"].unique()))

st.sidebar.header("Supuestos")
umbral = st.sidebar.slider("Umbral de demora crítica (h)", 1.0, 8.0, 4.0, 0.5)
n_muelles = st.sidebar.slider("Número de muelles", 1, 8, 4)

d = df[
    (df["Hora_Llegada"].dt.date >= f_ini) & (df["Hora_Llegada"].dt.date <= f_fin)
    & df["Tipo_Carga"].isin(cargas) & df["Condicion_Climatica"].isin(climas)
].copy()

st.title("Optimización logística portuaria - Puerto de Cartagena")

if d.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

# ---------- KPIs ----------
d["Critica"] = d["Tiempo_Espera_Horas"] > umbral
tpe = d["Tiempo_Espera_Horas"].mean()
horas_periodo = max((d["Hora_Atraque"].max() - d["Hora_Llegada"].min()).total_seconds() / 3600, 1)
ocupacion = d["Tiempo_Muelle_Horas"].sum() / (n_muelles * horas_periodo) * 100
cont = d[d["TEUs_Ocupados"] > 0]
eficiencia = cont["TEUs_por_Hora"].mean() if not cont.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tiempo promedio de espera (h)", f"{tpe:.2f}")
c2.metric("Ocupación de muelles", f"{ocupacion:.1f} %")
c3.metric("Eficiencia (TEUs/h)", f"{eficiencia:.0f}")
c4.metric("Demoras críticas", int(d["Critica"].sum()))

# ---------- Alertas ----------
if ocupacion > 100:
    st.error("Ocupación superior al 100 %: con ese número de muelles hay saturación.")
elif ocupacion > 85:
    st.warning("Ocupación alta (más de 85 %): riesgo de cuello de botella.")
if d["Critica"].sum() > 0:
    st.error(f"{int(d['Critica'].sum())} buques superaron las {umbral} h de espera.")
else:
    st.success("Sin demoras críticas con los filtros actuales.")

# ---------- Gráficos ----------
g1, g2 = st.columns(2)
horas = d.groupby("Hora_Dia").size().reindex(range(24), fill_value=0).reset_index()
horas.columns = ["Hora del día", "Llegadas"]
g1.plotly_chart(px.line(horas, x="Hora del día", y="Llegadas", markers=True,
                        title="Llegadas por hora del día (horas pico)"), use_container_width=True)

diario = d.groupby("Fecha")["Tiempo_Espera_Horas"].mean().reset_index()
fig = px.line(diario, x="Fecha", y="Tiempo_Espera_Horas", markers=True,
              title="Espera promedio por día (h)")
fig.add_hline(y=umbral, line_dash="dash", line_color="red", annotation_text="Umbral")
g2.plotly_chart(fig, use_container_width=True)

g3, g4 = st.columns(2)
por_carga = d.groupby("Tipo_Carga")["Tiempo_Espera_Horas"].mean().reset_index()
g3.plotly_chart(px.bar(por_carga, x="Tipo_Carga", y="Tiempo_Espera_Horas",
                       title="Espera promedio por tipo de carga (h)"), use_container_width=True)
por_clima = d.groupby("Condicion_Climatica")["Tiempo_Espera_Horas"].mean().reset_index()
g4.plotly_chart(px.bar(por_clima, x="Condicion_Climatica", y="Tiempo_Espera_Horas",
                       title="Espera promedio por clima (h)", color="Tiempo_Espera_Horas",
                       color_continuous_scale="Reds"), use_container_width=True)

# ---------- Tabla de demoras críticas ----------
st.subheader("Buques con demora crítica")
cols = ["ID_Registro", "Buque", "Tipo_Carga", "Hora_Llegada", "Tiempo_Espera_Horas", "Condicion_Climatica"]
st.dataframe(d[d["Critica"]][cols].sort_values("Tiempo_Espera_Horas", ascending=False),
             use_container_width=True)
