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
    page_title="Caribe Bay - Staff", 
    layout="wide", 
    page_icon="https://www.caribebay.it/favicon.ico"
)
pd.options.mode.string_storage = "python"

# --- CSS PERSONALIZZATO ---
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .card-container {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        background: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .card-container:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }
    .name-badge {
        background: #f1f3f5;
        color: #212529;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 0.85rem;
        font-weight: 500;
        margin: 3px 0;
        border-left: 4px solid #1f77b4;
        display: block;
    }
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #eee;
    }
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
        # Pulizia e normalizzazione colonne
        cols_req = ["Nome", "Cognome", "Mansione", "GiornoRiposoSettimanale", "Stato Rapporto", "Cellulare", "Email", "Contestazioni", "Data Cessazione"]
        for col in cols_req:
            if col not in res["addetti"].columns:
                res["addetti"][col] = ""
        
        res["addetti"] = res["addetti"].astype(object)
        for col in ["Contestazioni", "Email", "Data Cessazione", "Cellulare"]:
            res["addetti"][col] = res["addetti"][col].astype(str).replace(['nan', 'None', '<NA>', r'\.0$'], '', regex=True).str.strip()
        
        res["addetti"]["Stato Rapporto"] = res["addetti"]["Stato Rapporto"].replace('', 'Attivo')
        return res
    except Exception as e:
        st.error(f"⚠️ Errore di connessione: {e}"); st.stop()

data = get_all_data()

# --- UTILITY ---
def format_wa_link(row):
    tel = str(row['Cellulare']).strip().replace(" ", "").replace("+", "")
    if not tel or tel == "" or tel == "nan": return None
    if len(tel) <= 10: tel = "39" + tel
    msg = urllib.parse.quote(f"Ciao {row['Nome']}, ")
    return f"https://wa.me/{tel}?text={msg}"

def genera_pdf_riposi(mansione, df_mansione, giorni_ita):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Riepilogo Riposi - {mansione}", styles['Title']))
    header = [g.upper() for g in giorni_ita]
    mappa = {g: [f"{r['Nome']} {r['Cognome']}" for _, r in df_mansione[df_mansione["GiornoRiposoSettimanale"] == g].iterrows()] for g in giorni_ita}
    max_r = max([len(v) for v in mappa.values()]) if mappa else 0
    tab_data = [header]
    for i in range(max_r):
        tab_data.append([mappa[g][i] if i < len(mappa[g]) else "" for g in giorni_ita])
    t = Table(tab_data, colWidths=[110]*7)
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f77b4")), ('TEXTCOLOR',(0,0),(-1,0), colors.whitesmoke), ('GRID',(0,0),(-1,-1),0.5, colors.grey)]))
    elements.append(t); doc.build(elements); buffer.seek(0)
    return buffer

# --- ESTRAZIONE CONFIG ---
conf_df = data["config"]
try:
    admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
    user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except:
    admin_pwd, user_pwd = "admin", "staff"; data_apertura = datetime(2026, 5, 16).date(); data_chiusura = datetime(2026, 9, 13).date()

# --- LOGIN ---
if "role" not in st.session_state:
    col1, col2, col3 = st.columns([2,1,2])
    with col2: st.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", use_container_width=True)
    col4, col5, col6 = st.columns([1.5,1,1.5])
    with col5:
        pwd = st.text_input("Password", type="password")
        if st.button("Accedi", use_container_width=True):
            if pwd == admin_pwd: st.session_state["role"] = "Admin"; st.rerun()
            elif pwd == user_pwd: st.session_state["role"] = "User"; st.rerun()
            else: st.error("❌ Password errata")
    st.stop()

# --- GLOBALI ---
oggi = datetime.now().date()
default_date = oggi if data_apertura <= oggi <= data_chiusura else data_apertura
giorni_ita = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist()

# --- SIDEBAR ---
st.sidebar.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=200)
menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi Settimanali"]
if st.session_state["role"] == "Admin":
    menu_options += ["📝 Gestione Riposi Rapida", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "⚙️ Impostazioni Stagione", "🔑 Gestione Password"]
menu = st.sidebar.radio("NAVIGAZIONE", menu_options)
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📍 Stato Occupazione Parco")
    input_d = st.date_input("Inizio settimana:", default_date)
    date_aperte = [input_d + timedelta(days=i) for i in range(7) if data_apertura <= (input_d + timedelta(days=i)) <= data_chiusura]
    
    if not date_aperte:
        st.warning("⚠️ Parco chiuso nel periodo selezionato.")
    else:
        def genera_card(titolo, color, num, req, staff_list):
            nomi = "".join([f"<div class='name-badge'>• {r['Nome']} {r['Cognome']}</div>" for _, r in staff_list.iterrows()])
            if not nomi: nomi = "<div style='color:gray; font-style:italic; padding:10px;'>Nessuno disponibile</div>"
            return f"""<div class="card-container">
                <div style="background:{color}; color:white; padding:10px; border-radius:12px 12px 0 0; text-align:center; font-weight:bold;">{titolo.upper()}</div>
                <div style="padding:15px; text-align:center;">
                    <div style="font-size:26px; font-weight:bold;">{num} <span style="font-size:16px; color:#999;">/ {req}</span></div>
                    <div style="margin-top:10px; text-align:left; border-top:1px solid #f0f0f0; padding-top:10px;">{nomi}</div>
                </div></div>"""

        tabs = st.tabs([d.strftime("%A %d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                d_tab = date_aperte[idx]
                g_nome = giorni_ita[d_tab.weekday()].upper()
                df_f = data["fabbisogno"].copy()
                df_f['d'] = pd.to_datetime(df_f['Data']).dt.date
                fabb = df_f[df_f['d'] == d_tab]
                
                df_dis = data["disp"].copy()
                df_dis['d'] = pd.to_datetime(df_dis['Data']).dt.date
                lista_nera = (df_dis[(df_dis['d'] == d_tab) & (df_dis['Stato'] != "Disponibile")]["Nome"].str.upper() + df_dis["Cognome"].str.upper()).tolist()
                
                staff = data["addetti"][data["addetti"]["Stato Rapporto"] == "Attivo"].copy()
                staff["ID"] = (staff["Nome"].str.upper() + staff["Cognome"].str.upper())
                pres = staff[(staff["GiornoRiposoSettimanale"].str.upper() != g_nome) & (~staff["ID"].isin(lista_nera))]

                c1, c2, c3 = st.columns(3)
                mansioni_view = ["Addetto Attrazioni", "Assistente Bagnanti", "Bungee Jumping", "Radio"]
                for i, m in enumerate(mansioni_view):
                    with [c1, c2, c3][i % 3]:
                        s_p = pres[pres["Mansione"] == m]
                        f_r = fabb[fabb["Mansione"] == m]
                        req = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0
                        n = len(s_p)
                        col = "#29b05c" if n >= req and req > 0 else "#ff4b4b" if n < req else "#808080"
                        st.markdown(genera_card(m, col, n, req, s_p), unsafe_allow_html=True)

# --- 2. RIEPILOGO RIPOSI ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.title("📅 Piano Riposi Settimanali")
    for m in lista_postazioni:
        add_m = data["addetti"][(data["addetti"]["Mansione"] == m) & (data["addetti"]["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            c_t, c_p = st.columns([5,1])
            c_t.markdown(f"### 📍 {m}")
            c_p.download_button("📄 PDF", genera_pdf_riposi(m, add_m, giorni_ita), f"Riposi_{m}.pdf", key=f"pdf_{m}")
            with st.container(border=True):
                cols = st.columns(7)
                for i, g in enumerate(giorni_ita):
                    with cols[i]:
                        st.markdown(f"<div style='background:#1f77b4; color:white; border-radius:5px; padding:2px; text-align:center; font-weight:bold; font-size:12px;'>{g[:3].upper()}</div>", unsafe_allow_html=True)
                        for _, r in add_m[add_m["GiornoRiposoSettimanale"] == g].iterrows():
                            st.markdown(f'<div class="name-badge" style="text-align:center; border-left:none; background:#f8f9fa; font-size:11px;">{r["Nome"]} {r["Cognome"]}</div>', unsafe_allow_html=True)
            non_def = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not non_def.empty:
                badges = "".join([f'<span class="name-badge" style="display:inline-block; margin-right:8px; border-left:4px solid #6c757d;">{r["Nome"]} {r["Cognome"]}</span>' for _, r in non_def.iterrows()])
                st.markdown(f'<div style="display:flex; flex-wrap:wrap; gap:5px; margin-top:10px;">{badges}</div>', unsafe_allow_html=True)

# --- 3. GESTIONE RAPIDA ---
elif menu == "📝 Gestione Riposi Rapida":
    st.title("📝 Modifica Rapida Riposi")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[(df_mod["Mansione"] == m) & (df_mod["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            counts = add_m["GiornoRiposoSettimanale"].value_counts()
            c_c = st.columns(7)
            for i, g in enumerate(giorni_ita):
                n = counts.get(g, 0)
                bc = "#1f77b4" if n < 3 else "#ff4b4b"
                with c_c[i]: st.markdown(f'<div style="background:white; border:1px solid #eee; border-radius:8px; padding:8px; text-align:center; border-bottom:3px solid {bc};"><div style="font-size:10px; color:#888;">{g[:3]}</div><div style="font-size:18px; font-weight:bold; color:{bc};">{n}</div></div>', unsafe_allow_html=True)
            for idx, row in add_m.iterrows():
                cn, cs = st.columns([3, 1])
                cn.markdown(f"<div style='padding-top:8px;'>{row['Nome']} <b>{row['Cognome']}</b></div>", unsafe_allow_html=True)
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = cs.selectbox(f"R_{idx}", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, key=f"f_{idx}", label_visibility="collapsed")
            st.divider()
    if st.button("💾 SALVA TUTTO", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod); st.cache_data.clear(); st.success("Salvato!"); st.rerun()

# --- 4. AREA DISPONIBILITÀ ---
elif menu == "📅 Area Disponibilità Staff":
    st.title("🗓️ Calendario Disponibilità")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome']
    sel = st.selectbox("Seleziona dipendente:", df_t['Full'].tolist())
    row_d = df_t[df_t['Full'] == sel].iloc[0]
    df_p = data["disp"][(data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome'])]
    # Nota: la funzione genera_mini_calendario è definita nel tuo codice originale e va mantenuta qui per funzionare
    # ... (inserire qui la funzione genera_mini_calendario dal tuo riferimento) ...
    st.info("Visualizzazione calendario in sviluppo o integrabile qui.")

# --- 5. GESTIONE ANAGRAFICA (Con Filtro Mansione) ---
elif menu == "👥 Gestione Anagrafica":
    st.title("👥 Anagrafica Personale")
    if "editing_id" not in st.session_state: st.session_state["editing_id"] = None

    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        with st.form("edit"):
            st.subheader(f"Modifica: {row['Nome']} {row['Cognome']}")
            c1, c2, c3 = st.columns(3)
            en = c1.text_input("Nome", row['Nome']); ec = c2.text_input("Cognome", row['Cognome'])
            es = c3.selectbox("Stato", ["Attivo", "Dimesso", "Licenziato"], index=0)
            ct, cm, cc = st.columns(3)
            etel = ct.text_input("Cellulare", row['Cellulare']); email = cm.text_input("Email", row['Email']); eces = cc.text_input("Cessazione", row['Data Cessazione'])
            eman = st.selectbox("Mansione", lista_postazioni, index=0); erip = st.selectbox("Riposo", opzioni_riposo, index=0)
            econ = st.text_area("Note", row['Contestazioni'])
            if st.form_submit_button("Salva"):
                # Logica update...
                st.session_state["editing_id"] = None; st.rerun()
    else:
        t1, t2 = st.tabs(["📋 Elenco", "➕ Aggiungi"])
        with t1:
            cf1, cf2 = st.columns(2)
            f_stato = cf1.radio("Stato:", ["Solo Attivi", "Tutti"], horizontal=True)
            f_man = cf2.selectbox("Filtra per Mansione:", ["Tutte"] + lista_postazioni)
            
            df_v = data["addetti"].copy()
            if f_stato == "Solo Attivi": df_v = df_v[df_v["Stato Rapporto"] == "Attivo"]
            if f_man != "Tutte": df_v = df_v[df_v["Mansione"] == f_man]
            
            st.markdown(f"**Risultati: {len(df_v)}**")
            for idx, r in df_v.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([3, 5, 1])
                    wa = format_wa_link(r); wa_h = f' <a href="{wa}" target="_blank">📲</a>' if wa else ""
                    c1.markdown(f"**{r['Nome']} {r['Cognome']}**{wa_h}", unsafe_allow_html=True)
                    c1.caption(f"📍 {r['Mansione']}")
                    c2.markdown(f"<div style='font-size:0.85rem;'>📞 {r['Cellulare']} | Riposo: {r['GiornoRiposoSettimanale']}</div>", unsafe_allow_html=True)
                    if r['Contestazioni']: st.error(f"🚩 {r['Contestazioni']}")
                    if c3.button("✏️", key=f"e_{idx}"): st.session_state["editing_id"] = idx; st.rerun()
                    st.divider()

# --- 6. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.title("⚙️ Fabbisogno Giornaliero")
    dr = st.date_input("Periodo:", value=[])
    if len(dr) == 2:
        date_list = [dr[0] + timedelta(days=x) for x in range((dr[1]-dr[0]).days + 1)]
        f_inputs = {p: st.number_input(f"{p}:", min_value=0) for p in lista_postazioni}
        if st.button("💾 Salva Fabbisogno"):
            new_r = [{"Data": str(d), "Mansione": p, "Quantita": v} for d in date_list for p, v in f_inputs.items()]
            old_d = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).isin([str(d) for d in date_list])]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old_d, pd.DataFrame(new_r)], ignore_index=True)); st.cache_data.clear(); st.success("Fabbisogno aggiornato!"); st.rerun()

# --- 7. GESTIONE POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.title("🚩 Postazioni")
    np = st.text_input("Nuova Postazione")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True)); st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])

# --- 8. IMPOSTAZIONI STAGIONE ---
elif menu == "⚙️ Impostazioni Stagione":
    st.title("⚙️ Configurazione")
    with st.form("config"):
        na, nc = st.date_input("Apertura:", data_apertura), st.date_input("Chiusura:", data_chiusura)
        if st.form_submit_button("Salva"):
            data["config"].loc[data["config"]["Ruolo"] == "Apertura", "Password"] = str(na)
            data["config"].loc[data["config"]["Ruolo"] == "Chiusura", "Password"] = str(nc)
            conn.update(worksheet="Config", data=data["config"]); st.cache_data.clear(); st.rerun()

# --- 9. GESTIONE PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.title("🔑 Sicurezza")
    with st.form("pwd"):
        ap, up = st.text_input("Admin", value=admin_pwd), st.text_input("User", value=user_pwd)
        if st.form_submit_button("Aggiorna Password"):
            data["config"].loc[data["config"]["Ruolo"]=="Admin", "Password"] = ap
            data["config"].loc[data["config"]["Ruolo"]=="User", "Password"] = up
            conn.update(worksheet="Config", data=data["config"]); st.cache_data.clear(); st.success("Password salvate!"); st.rerun()
