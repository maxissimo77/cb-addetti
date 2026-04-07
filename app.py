import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar
import urllib.parse
from io import BytesIO

# --- LIBRERIE PER PDF ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Caribe Bay - Staff Portal", 
    layout="wide", 
    page_icon="https://www.caribebay.it/favicon.ico"
)

# --- STILE CSS PERSONALIZZATO ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #eee; }
    
    /* Card Dashboard */
    .card-dashboard {
        background: white; border-radius: 12px; padding: 20px; 
        border-top: 6px solid #1f77b4; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin-bottom: 20px; transition: transform 0.2s;
    }
    .card-dashboard:hover { transform: translateY(-5px); }
    
    /* Badge Staff */
    .staff-tag {
        background: #f0f7ff; border: 1px solid #cfe2ff; border-radius: 6px;
        padding: 5px 10px; margin: 4px 0; font-size: 0.9em; color: #084298;
        display: block; font-weight: 500;
    }
    
    /* Griglia Riposi */
    .riposo-header {
        background: #1f77b4; color: white; text-align: center; 
        padding: 10px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 0.8em;
    }
    .riposo-cell {
        background: white; border: 1px solid #e9ecef; padding: 10px; 
        min-height: 100px; text-align: center; border-radius: 0 0 8px 8px;
        box-shadow: inset 0 0 5px rgba(0,0,0,0.02);
    }
    
    /* Bottoni */
    .stButton>button { border-radius: 8px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# --- CONNESSIONE E CARICAMENTO DATI ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def get_all_data():
    try:
        res = {
            "addetti": conn.read(worksheet="Addetti"),
            "disp": conn.read(worksheet="Disponibilita"),
            "fabbisogno": conn.read(worksheet="Fabbisogno"),
            "postazioni": conn.read(worksheet="Postazioni"),
            "config": conn.read(worksheet="Config")
        }
        res["addetti"] = res["addetti"].astype(object)
        for col in ["Contestazioni", "Stato Rapporto", "Data Cessazione", "Cellulare", "Email"]:
            if col not in res["addetti"].columns: res["addetti"][col] = ""
        res["addetti"]["Cellulare"] = res["addetti"]["Cellulare"].astype(str).replace(r'\.0$', '', regex=True).replace(['nan', 'None', '<NA>'], '')
        return res
    except Exception as e:
        st.error(f"Errore caricamento dati: {e}"); st.stop()

data = get_all_data()

# --- FUNZIONI UTILITY ---
def format_wa_link(row):
    tel = str(row['Cellulare']).strip().replace(" ", "").replace("+", "")
    if not tel or tel == "nan": return None
    if len(tel) <= 10: tel = "39" + tel
    return f"https://wa.me/{tel}?text={urllib.parse.quote('Ciao ' + str(row['Nome']))}"

def genera_pdf_riposi(mansione, df_mansione, giorni_ita):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"CARIBE BAY - PIANO RIPOSI: {mansione.upper()}", styles['Title']))
    elements.append(Spacer(1, 20))
    
    header = [g.upper() for g in giorni_ita]
    mappa = {g: [f"{r['Nome']} {r['Cognome']}" for _, r in df_mansione[df_mansione["GiornoRiposoSettimanale"] == g].iterrows()] for g in giorni_ita}
    max_rows = max([len(v) for v in mappa.values()]) if mappa else 0
    
    table_data = [header]
    for i in range(max_rows):
        row = [mappa[g][i] if i < len(mappa[g]) else "" for g in giorni_ita]
        table_data.append(row)
    
    t = Table(table_data, colWidths=[105]*7)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f77b4")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- LOGICA LOGIN & CONFIG ---
conf_df = data["config"]
try:
    admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
    user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except:
    admin_pwd, user_pwd = "admin", "staff"
    data_apertura, data_chiusura = datetime(2026,5,16).date(), datetime(2026,9,13).date()

if "role" not in st.session_state:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c2:
        st.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png")
        with st.container(border=True):
            st.subheader("Login Gestione Staff")
            pwd = st.text_input("Password", type="password")
            if st.button("Accedi", use_container_width=True, type="primary"):
                if pwd == admin_pwd: st.session_state["role"] = "Admin"; st.rerun()
                elif pwd == user_pwd: st.session_state["role"] = "User"; st.rerun()
                else: st.error("Password errata")
    st.stop()

# --- VARIABILI GLOBALI ---
giorni_ita = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist()
oggi = datetime.now().date()
default_date = oggi if data_apertura <= oggi <= data_chiusura else data_apertura

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=180)
    st.markdown("---")
    menu = st.radio("SISTEMA", ["📊 Dashboard", "📅 Riepilogo Riposi", "📝 Modifica Rapida", "👥 Anagrafica", "📅 Disponibilità", "⚙️ Impostazioni"])
    if st.button("Logout"): st.session_state.clear(); st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Stato Occupazione")
    sel_date = st.date_input("Data di riferimento:", default_date)
    
    if not (data_apertura <= sel_date <= data_chiusura):
        st.warning("⚠️ Parco Chiuso in questa data.")
    else:
        def norm(s): return str(s).strip().upper() if pd.notna(s) else ""
        
        # Filtro assenti dal foglio Disponibilità
        disp_oggi = data["disp"][pd.to_datetime(data["disp"]['Data']).dt.date == sel_date]
        lista_assenti = (disp_oggi[disp_oggi["Stato"].str.upper() != "DISPONIBILE"]["Nome"] + disp_oggi[disp_oggi["Stato"].str.upper() != "DISPONIBILE"]["Cognome"]).apply(norm).tolist()
        
        # Filtro presenti (No riposo e No assenti)
        staff_attivo = data["addetti"][data["addetti"]["Stato Rapporto"] == "Attivo"].copy()
        giorno_sett_str = giorni_ita[sel_date.weekday()]
        
        presenti = staff_attivo[
            (staff_attivo["GiornoRiposoSettimanale"].apply(norm) != norm(giorno_sett_str)) & 
            (~(staff_attivo["Nome"] + staff_attivo["Cognome"]).apply(norm).isin(lista_assenti))
        ]
        
        fabb_oggi = data["fabbisogno"][pd.to_datetime(data["fabbisogno"]['Data']).dt.date == sel_date]

        cols = st.columns(3)
        for idx, m in enumerate(["Addetto Attrazioni", "Assistente Bagnanti", "Radio"]):
            with cols[idx]:
                s_p = presenti[presenti["Mansione"].apply(norm) == norm(m)]
                f_r = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m)]
                req = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0
                n = len(s_p)
                color = "#29b05c" if n >= req and req > 0 else "#ff4b4b"
                
                st.markdown(f"""
                <div class="card-dashboard" style="border-top-color: {color}">
                    <h3 style="margin:0; color:#555; font-size: 1.1em;">{m}</h3>
                    <h1 style="margin:10px 0; color:{color}; font-size: 2.5em;">{n} <span style="font-size: 0.4em; color: #999;">/ {req}</span></h1>
                    <div style="max-height: 250px; overflow-y: auto; border-top: 1px solid #eee; padding-top: 10px;">
                        {"".join([f'<div class="staff-tag">• {r["Nome"]} {r["Cognome"]}</div>' for _, r in s_p.iterrows()])}
                    </div>
                </div>
                """, unsafe_allow_html=True)

# --- 2. RIEPILOGO RIPOSI (CON PDF) ---
elif menu == "📅 Riepilogo Riposi":
    st.title("📅 Piano Riposi Settimanali")
    for m in lista_postazioni:
        add_m = data["addetti"][(data["addetti"]["Mansione"] == m) & (data["addetti"]["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            with st.container(border=True):
                c1, c2 = st.columns([5,1])
                c1.subheader(f"📍 {m}")
                pdf_file = genera_pdf_riposi(m, add_m, giorni_ita)
                c2.download_button("📄 EXPORT PDF", pdf_file, f"Riposi_{m}.pdf", "application/pdf", key=f"pdf_{m}")
                
                cols_rip = st.columns(7)
                for i, g in enumerate(giorni_ita):
                    with cols_rip[i]:
                        st.markdown(f'<div class="riposo-header">{g[:3].upper()}</div>', unsafe_allow_html=True)
                        chi = add_m[add_m["GiornoRiposoSettimanale"] == g]
                        nomi = "".join([f'<div class="staff-tag" style="font-size:0.8em; padding:2px 5px;">{r["Nome"]} {r["Cognome"]}</div>' for _, r in chi.iterrows()])
                        st.markdown(f'<div class="riposo-cell">{nomi if nomi else " - "}</div>', unsafe_allow_html=True)

# --- 3. MODIFICA RAPIDA ---
elif menu == "📝 Modifica Rapida":
    st.title("📝 Gestione Rapida Turni")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[(df_mod["Mansione"] == m) & (df_mod["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            st.markdown(f"#### {m}")
            for idx, row in add_m.iterrows():
                col1, col2 = st.columns([3, 1])
                col1.write(f"👤 {row['Nome']} **{row['Cognome']}**")
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = col2.selectbox(
                    f"Riposo {idx}", opzioni_riposo, 
                    index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, 
                    key=f"rip_{idx}", label_visibility="collapsed"
                )
            st.divider()
    
    if st.button("💾 SALVA MODIFICHE", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod)
        st.cache_data.clear(); st.success("Dati sincronizzati con Google Sheets!"); st.rerun()

# --- 4. ANAGRAFICA ---
elif menu == "👥 Anagrafica":
    st.title("👥 Gestione Anagrafica")
    tab1, tab2 = st.tabs(["📋 Elenco Staff", "➕ Nuovo Addetto"])
    
    with tab1:
        search = st.text_input("Cerca per nome o cognome...")
        df_view = data["addetti"][data["addetti"]["Stato Rapporto"] == "Attivo"]
        if search:
            df_view = df_view[df_view['Nome'].str.contains(search, case=False) | df_view['Cognome'].str.contains(search, case=False)]
        
        for idx, r in df_view.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 1])
                wa = format_wa_link(r)
                c1.markdown(f"**{r['Nome']} {r['Cognome']}** " + (f"[📲]({wa})" if wa else ""))
                c1.caption(f"Mansione: {r['Mansione']}")
                c2.write(f"📅 Riposo: {r['GiornoRiposoSettimanale']}")
                if c3.button("Dettagli", key=f"det_{idx}"):
                    st.info(f"Dati di contatto: {r['Cellulare']} | {r['Email']}")

    with tab2:
        with st.form("nuovo_staff"):
            c1, c2 = st.columns(2)
            n_nome = c1.text_input("Nome")
            n_cogn = c2.text_input("Cognome")
            n_mans = c1.selectbox("Mansione", lista_postazioni)
            n_ripo = c2.selectbox("Riposo", opzioni_riposo)
            n_cell = c1.text_input("Cellulare")
            n_mail = c2.text_input("Email")
            if st.form_submit_button("Aggiungi a Database"):
                nuovo = pd.DataFrame([{"Nome": n_nome, "Cognome": n_cogn, "Mansione": n_mans, "GiornoRiposoSettimanale": n_ripo, "Stato Rapporto": "Attivo", "Cellulare": n_cell, "Email": n_mail}])
                conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], nuovo], ignore_index=True))
                st.cache_data.clear(); st.success("Aggiunto!"); st.rerun()

# --- 5. DISPONIBILITÀ & IMPOSTAZIONI ---
elif menu == "📅 Disponibilità":
    st.title("📅 Calendario Disponibilità")
    st.info("Seleziona un dipendente per visualizzare o modificare le sue assenze/malattie.")
    # (Inserire qui la logica di visualizzazione calendario mini se desiderata)

elif menu == "⚙️ Impostazioni":
    st.title("⚙️ Configurazione")
    with st.form("config_form"):
        new_ap = st.date_input("Data Apertura Parco", data_apertura)
        new_ch = st.date_input("Data Chiusura Parco", data_chiusura)
        if st.form_submit_button("Salva Configurazione"):
            agg = data["config"].copy()
            agg.loc[agg["Ruolo"] == "Apertura", "Password"] = str(new_ap)
            agg.loc[agg["Ruolo"] == "Chiusura", "Password"] = str(new_ch)
            conn.update(worksheet="Config", data=agg)
            st.cache_data.clear(); st.success("Date aggiornate!"); st.rerun()
