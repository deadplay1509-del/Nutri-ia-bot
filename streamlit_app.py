import streamlit as st
import pandas as pd
from google import genai
from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt
import io

load_dotenv()
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    # Ensure the official client can pick up the key from the environment
    os.environ.setdefault("GOOGLE_API_KEY", GEMINI_API_KEY)
except KeyError:
    GEMINI_API_KEY = None

# Crear cliente de la nueva librería
client = genai.Client()

st.set_page_config(page_title="Excel + ChatGPT Prototype", layout="wide")
st.title("Excel + ChatGPT — Prototipo local")
st.write("Carga un archivo Excel, aplica limpieza básica, genera insights y pregunta a ChatGPT sobre los datos.")

uploaded_file = st.file_uploader("Sube un archivo Excel (.xlsx, .xls)", type=["xlsx", "xls"])

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error al leer el archivo Excel: {e}")
        st.stop()

    st.subheader("Vista previa")
    st.dataframe(df.head())

    # Limpieza en barra lateral
    st.sidebar.header("Limpieza básica")
    drop_na = st.sidebar.checkbox("Eliminar filas con NA")
    fill_na = st.sidebar.checkbox("Rellenar NA con valor")
    fill_value = None
    if fill_na:
        fill_value = st.sidebar.text_input("Valor para rellenar (cadena)", value="")
    drop_dup = st.sidebar.checkbox("Eliminar duplicados")
    cols = st.sidebar.multiselect("Seleccionar columnas (opcional)", options=list(df.columns))

    if st.sidebar.button("Aplicar limpieza"):
        if cols:
            df = df[cols]
        if drop_na:
            df = df.dropna()
        if fill_na:
            df = df.fillna(fill_value)
        if drop_dup:
            df = df.drop_duplicates()
        st.success("Limpieza aplicada")

    # Guardar df limpio en session_state
    st.session_state['df'] = df

    # Insights
    st.header("Insights automáticos")
    with st.expander("Resumen estadístico y tipos"):
        st.write(df.describe(include='all').transpose())
        st.write("Tipos de columnas:")
        st.write(df.dtypes)

    with st.expander("Análisis por columna"):
        col = st.selectbox("Selecciona columna para ver conteos/visualizaciones", options=[None]+list(df.columns))
        if col:
            vc = df[col].value_counts(dropna=False).head(50)
            st.write(vc)
            fig, ax = plt.subplots(figsize=(8,4))
            vc.plot(kind='bar', ax=ax)
            ax.set_title(f"Top valores en {col}")
            st.pyplot(fig)

    st.download_button("Descargar Excel limpio", data=to_excel_bytes(df), file_name="cleaned.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Chat con ChatGPT
    st.header("Chat con ChatGPT sobre los datos")
    st.write("Escribe una pregunta sobre el dataset (por ejemplo: 'Resume los principales insights' o '¿Qué columnas faltan datos?')")
    question = st.text_input("Pregunta:")
    if st.button("Enviar pregunta a ChatGPT"):
        if not GEMINI_API_KEY:
            st.error("No se encontró GEMINI_API_KEY en .env. Copia .env.template a .env y añade tu clave.")
        elif not question:
            st.warning("Escribe una pregunta primero")
        else:
            # Preparar contexto limitado para evitar enviar dataset grande
            head_csv = df.head(5).to_csv(index=False)
            desc = df.describe(include='all').transpose().to_string()
            dtypes = df.dtypes.to_string()
            user_prompt = (
                f"Pregunta: {question}\n\n"
                f"Resumen de tipos de columna:\n{dtypes}\n\n"
                f"Resumen estadístico (transpuesto):\n{desc}\n\n"
                f"Primeras 5 filas (CSV):\n{head_csv}\n\n"
                "Contesta de forma concisa y proporciona pasos accionables si procede."
            )
            system_msg = (
                "Eres un asistente especializado en análisis de datos tabulares y Excel. "
                "Usa el contexto proporcionado para responder de forma práctica."
            )
            with st.spinner("Consultando la API de Gemini..."):
                try:
                    # Usar la nueva API oficial `google.genai` pasando `contents` como
                    # una cadena simple para evitar errores de validación de Pydantic.
                    full_prompt = (
                        f"{system_msg}\n\n{user_prompt}\n\nDatos del Excel (primeras filas):\n{head_csv}"
                    )
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=full_prompt,
                    )
                    # Intentar varias formas de extraer el texto según formato de respuesta
                    answer = None
                    # Extraer texto de la respuesta probando varios formatos posibles
                    answer = None
                    try:
                        answer = resp.output[0].content[0].text
                    except Exception:
                        try:
                            answer = resp['candidates'][0]['content']
                        except Exception:
                            try:
                                answer = getattr(resp, 'output_text', None)
                            except Exception:
                                answer = None
                    if not answer:
                        answer = str(resp)
                    # Mostrar solo el texto de la respuesta cuando esté disponible
                    display_text = getattr(resp, 'text', None) or getattr(resp, 'output_text', None) or answer
                    st.markdown(display_text)
                except Exception as e:
                    st.error(f"Error al conectar con Gemini: {e}")

else:
    st.info("Sube un archivo Excel para empezar.")
