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
    page_title="Caribe Bay - Staff Manager", 
    layout="wide", 
    page_icon="https://www.caribebay.it/favicon.ico"
)
pd.options.mode.string_storage = "python"

# --- CSS PERSONALIZZATO (RESTYLING TROPICAL MODERN) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #f4f7f9;
    }

    h1, h2, h3 {
        color: #0e4f77 !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }

    .card-container {
        border-radius: 20px !important;
        background: #ffffff;
        margin-bottom: 25px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.04) !important;
        overflow: hidden;
        border: 1px solid #eef2f6 !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .card-container:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.08) !important;
    }

    .name-badge {
        background: #f0f7ff;
        color: #1f77b4;
        padding: 6px 14px;
        border-radius: 10px;
        font-size: 0.85rem;
        font-weight: 500;
        margin: 5px 0;
        display: block;
        border: 1px solid #e1effe;
    }

    .metric-box {
        background: #ffffff;
        border-radius: 15px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        border-bottom: 4px solid #1f77b4;
    }

    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #eef2f6;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 18px !important;
        border: 1px solid #eef2f6 !important;
        background-color: #ffffff !important;
        padding: 20px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02) !important;
    }

    .stButton>button {
        border-radius: 10px !important;
        text-transform: uppercase;
        font-weight: 700 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- CONNESSIONE E CARICAMENTO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def get_all_data():
    res = {
        "addetti": conn.read(worksheet="Addetti"),
        "disp": conn.read(worksheet="Disponibilita"),
        "fabbisogno": conn.read(worksheet="Fabbisogno"),
        "postazioni": conn.read(worksheet="Postazioni"),
        "config": conn.read(worksheet="Config")
    }
    # Pulizia stringhe nan
    for col in ["Contestazioni", "Data Cessazione", "Cellulare", "Email"]:
        res["addetti"][col] = res["addetti"][col].astype(str).replace(['nan', 'None', '<NA>', r'\.0$'], '', regex=True).strip()
    return res

data = get_all_data()

# --- UTILITIES ---
def format_wa_link(row):
    tel = str(row['Cellulare']).strip().replace(" ", "").replace("+", "")
    if not tel or tel == "": return None
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
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0e4f77")), ('TEXTCOLOR',(0,0),(-1,0), colors.whitesmoke), ('GRID',(0,0),(-1,-1),0.5, colors.grey)]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- CONFIGURAZIONE ---
conf = data["config"]
admin_pwd = str(conf[conf["Ruolo"] == "Admin"]["Password"].values[0])
user_pwd = str(conf[conf["Ruolo"] == "User"]["Password"].values[0])
data_apertura = pd.to_datetime(conf[conf["Ruolo"] == "Apertura"]["Password"].values[0]).date()
data_chiusura = pd.to_datetime(conf[conf["Ruolo"] == "Chiusura"]["Password"].values[0]).date()

# --- LOGIN ---
if "role" not in st.session_state:
    st.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", width=200)
    pwd = st.text_input("Password", type="password")
    if st.button("Accedi"):
        if pwd == admin_pwd: st.session_state["role"] = "Admin"; st.rerun()
        elif pwd == user_pwd: st.session_state["role"] = "User"; st.rerun()
        else: st.error("Password errata")
    st.stop()

# --- GLOBALI ---
oggi = datetime.now().date()
default_date = oggi if data_apertura <= oggi <= data_chiusura else data_apertura
giorni_ita = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist()

# --- SIDEBAR ---
menu_options = ["📊 Dashboard", "📅 Riepilogo Riposi Settimanali"]
if st.session_state["role"] == "Admin":
    menu_options += ["📝 Gestione Riposi Rapida", "📅 Area Disponibilità Staff", "⚙️ Pianifica Fabbisogno", "👥 Gestione Anagrafica", "🚩 Gestione Postazioni", "⚙️ Impostazioni Stagione", "🔑 Gestione Password"]
menu = st.sidebar.radio("NAVIGAZIONE", menu_options)

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📍 Stato Occupazione Parco")
    input_d = st.date_input("Seleziona data inizio settimana:", default_date)
    date_aperte = [input_d + timedelta(days=i) for i in range(7) if data_apertura <= (input_d + timedelta(days=i)) <= data_chiusura]
    
    if not date_aperte:
        st.warning("Nessuna data di apertura nel range selezionato.")
    else:
        def render_card(titolo, color, n, r, staff_list):
            nomi = "".join([f"<div class='name-badge'>{row['Nome']} {row['Cognome']}</div>" for _, row in staff_list.iterrows()])
            if not nomi: nomi = "<div style='color:#94a3b8; font-style:italic;'>Nessun addetto</div>"
            return f"""<div class="card-container">
                <div style="background:{color}; color:white; padding:12px; text-align:center; font-weight:600;">{titolo.upper()}</div>
                <div style="padding:20px;">
                    <div style="text-align:center; margin-bottom:15px;">
                        <span style="font-size:32px; font-weight:700;">{n}</span><span style="font-size:16px; color:#94a3b8;"> / {r}</span>
                    </div>
                    <div style="border-top:1px solid #f1f5f9; padding-top:10px;">{nomi}</div>
                </div></div>"""

        tabs = st.tabs([d.strftime("%A %d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                d_tab = date_aperte[idx]
                g_nome = giorni_ita[d_tab.weekday()].upper()
                # Filtri logici
                df_f = data["fabbisogno"].copy()
                df_f['d'] = pd.to_datetime(df_f['Data']).dt.date
                fabb = df_f[df_f['d'] == d_tab]
                
                df_dis = data["disp"].copy()
                df_dis['d'] = pd.to_datetime(df_dis['Data']).dt.date
                lista_nera = (df_dis[(df_dis['d'] == d_tab) & (df_dis['Stato'] != "Disponibile")]["Nome"] + df_dis["Cognome"]).str.upper().tolist()
                
                staff_attivi = data["addetti"][data["addetti"]["Stato Rapporto"] == "Attivo"].copy()
                staff_attivi["ID"] = (staff_attivi["Nome"] + staff_attivi["Cognome"]).str.upper()
                presenti = staff_attivi[(staff_attivi["GiornoRiposoSettimanale"].str.upper() != g_nome) & (~staff_attivi["ID"].isin(lista_nera))]

                c1, c2, c3 = st.columns(3)
                for i, m in enumerate(lista_postazioni):
                    with [c1, c2, c3][i % 3]:
                        s_p = presenti[presenti["Mansione"] == m]
                        f_row = fabb[fabb["Mansione"] == m]
                        req = int(f_row["Quantita"].iloc[0]) if not f_row.empty else 0
                        n_pres = len(s_p)
                        colore = "#29b05c" if n_pres >= req and req > 0 else "#ff4b4b" if n_pres < req else "#94a3b8"
                        st.markdown(render_card(m, colore, n_pres, req, s_p), unsafe_allow_html=True)

# --- 2. RIEPILOGO RIPOSI ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.title("📅 Piano Riposi Settimanali")
    for m in lista_postazioni:
        add_m = data["addetti"][(data["addetti"]["Mansione"] == m) & (data["addetti"]["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            ct, cp = st.columns([5,1])
            ct.subheader(f"📍 {m}")
            cp.download_button("Esporta PDF", genera_pdf_riposi(m, add_m, giorni_ita), f"Riposi_{m}.pdf", key=f"pdf_{m}")
            with st.container(border=True):
                cols = st.columns(7)
                for i, g in enumerate(giorni_ita):
                    with cols[i]:
                        st.markdown(f"<div style='background:#0e4f77; color:white; border-radius:6px; padding:3px; text-align:center; font-weight:bold; font-size:11px;'>{g[:3].upper()}</div>", unsafe_allow_html=True)
                        persone = add_m[add_m["GiornoRiposoSettimanale"] == g]
                        for _, r in persone.iterrows():
                            st.markdown(f'<div class="name-badge" style="text-align:center;">{r["Nome"]} {r["Cognome"]}</div>', unsafe_allow_html=True)
            
            nd = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not nd.empty:
                st.markdown("**Senza riposo assegnato:**")
                with st.container(border=True):
                    badges = "".join([f'<span class="name-badge" style="display:inline-block; margin-right:5px;">{r["Nome"]} {r["Cognome"]}</span>' for _, r in nd.iterrows()])
                    st.markdown(f'<div style="display:flex; flex-wrap:wrap;">{badges}</div>', unsafe_allow_html=True)

# --- 3. GESTIONE RAPIDA ---
elif menu == "📝 Gestione Riposi Rapida":
    st.title("📝 Modifica Rapida Riposi")
    df_mod = data["addetti"].copy()
    for m in lista_postazioni:
        add_m = df_mod[(df_mod["Mansione"] == m) & (df_mod["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            counts = add_m["GiornoRiposoSettimanale"].value_counts()
            c_met = st.columns(7)
            for i, g in enumerate(giorni_ita):
                n = counts.get(g, 0)
                col_b = "#1f77b4" if n < 3 else "#ff4b4b"
                with c_met[i]:
                    st.markdown(f'<div class="metric-box" style="border-bottom-color:{col_b};"><b>{g[:3].upper()}</b><br><span style="font-size:20px; color:{col_b};">{n}</span></div>', unsafe_allow_html=True)
            
            for idx, row in add_m.iterrows():
                cn, cs = st.columns([3, 1])
                cn.write(f"{row['Nome']} **{row['Cognome']}**")
                cur_val = row['GiornoRiposoSettimanale']
                new_v = cs.selectbox(" ", opzioni_riposo, index=opzioni_riposo.index(cur_val) if cur_val in opzioni_riposo else 7, key=f"sel_{idx}", label_visibility="collapsed")
                df_mod.at[idx, 'GiornoRiposoSettimanale'] = new_v
            st.divider()
    if st.button("SALVA TUTTO", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod)
        st.cache_data.clear(); st.success("Dati Salvati!"); st.rerun()

# --- 4. DISPONIBILITÀ ---
elif menu == "📅 Area Disponibilità Staff":
    st.title("📅 Disponibilità e Assenze")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Registra Assenza")
        with st.form("form_disp"):
            nomi_lista = (data["addetti"]["Nome"] + " " + data["addetti"]["Cognome"]).tolist()
            a = st.selectbox("Seleziona Addetto", nomi_lista)
            d = st.date_input("Giorno", default_date)
            s = st.selectbox("Motivazione", ["Malattia", "Infortunio", "Permesso", "Disponibile"])
            if st.form_submit_button("Registra"):
                nome, cogn = a.rsplit(' ', 1)
                new_row = pd.DataFrame([{"Nome": nome, "Cognome": cogn, "Data": d.strftime("%Y-%m-%d"), "Stato": s}])
                updated = pd.concat([data["disp"], new_row], ignore_index=True)
                conn.update(worksheet="Disponibilita", data=updated)
                st.cache_data.clear(); st.rerun()
    with c2:
        st.subheader("Storico")
        st.dataframe(data["disp"], use_container_width=True)

# --- 5. ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.title("👥 Anagrafica Staff")
    if "editing_id" not in st.session_state: st.session_state["editing_id"] = None
    
    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        with st.form("edit_form"):
            st.subheader(f"Modifica Profilo: {row['Nome']}")
            c1, c2, c3 = st.columns(3)
            en = c1.text_input("Nome", row['Nome']); ec = c2.text_input("Cognome", row['Cognome'])
            est = c3.selectbox("Stato", ["Attivo", "Dimesso", "Licenziato"], index=0 if row['Stato Rapporto']=="Attivo" else 1)
            c4, c5, c6 = st.columns(3)
            et = c4.text_input("Cellulare", row['Cellulare']); em = c5.text_input("Email", row['Email']); ed = c6.text_input("Data Cessazione", row['Data Cessazione'])
            eman = st.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            erip = st.selectbox("Riposo", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 0)
            econ = st.text_area("Note", row['Contestazioni'])
            if st.form_submit_button("SALVA"):
                data["addetti"].at[idx, 'Nome'] = en; data["addetti"].at[idx, 'Cognome'] = ec
                data["addetti"].at[idx, 'Stato Rapporto'] = est; data["addetti"].at[idx, 'Cellulare'] = et
                data["addetti"].at[idx, 'Email'] = em; data["addetti"].at[idx, 'Data Cessazione'] = ed
                data["addetti"].at[idx, 'Mansione'] = eman; data["addetti"].at[idx, 'GiornoRiposoSettimanale'] = erip
                data["addetti"].at[idx, 'Contestazioni'] = econ
                conn.update(worksheet="Addetti", data=data["addetti"])
                st.cache_data.clear(); st.session_state["editing_id"] = None; st.rerun()
            if st.form_submit_button("ANNULLA"): st.session_state["editing_id"] = None; st.rerun()
    else:
        tab_list, tab_new = st.tabs(["Elenco", "Nuovo Addetto"])
        with tab_list:
            filtro = st.radio("Filtra:", ["Solo Attivi", "Tutti"], horizontal=True)
            df_v = data["addetti"].copy()
            if filtro == "Solo Attivi": df_v = df_v[df_v["Stato Rapporto"] == "Attivo"]
            for i, r in df_v.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3,5,1])
                    wa = format_wa_link(r); wa_h = f' <a href="{wa}" target="_blank">📲</a>' if wa else ""
                    c1.markdown(f"**{r['Nome']} {r['Cognome']}**{wa_h}", unsafe_allow_html=True)
                    c2.write(f"📞 {r['Cellulare']} | 📧 {r['Email']} | Riposo: {r['GiornoRiposoSettimanale']}")
                    if r['Contestazioni']: st.error(f"🚩 {r['Contestazioni']}")
                    if c3.button("✏️", key=f"ed_{i}"): st.session_state["editing_id"] = i; st.rerun()
        with tab_new:
            with st.form("new_add"):
                n1, n2, n3 = st.columns(3)
                nn = n1.text_input("Nome"); nc = n2.text_input("Cognome"); nm = n3.selectbox("Mansione", lista_postazioni)
                ntel = n1.text_input("Cellulare"); nmail = n2.text_input("Email"); nrip = n3.selectbox("Riposo", opzioni_riposo)
                if st.form_submit_button("AGGIUNGI"):
                    new_row = pd.DataFrame([{"Nome":nn, "Cognome":nc, "Mansione":nm, "GiornoRiposoSettimanale":nrip, "Stato Rapporto":"Attivo", "Cellulare":ntel, "Email":nmail}])
                    conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new_row], ignore_index=True))
                    st.cache_data.clear(); st.rerun()

# --- 6. POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.title("🚩 Gestione Postazioni")
    new_p = st.text_input("Nome Postazione")
    if st.button("Aggiungi"):
        df_p = pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": new_p}])], ignore_index=True)
        conn.update(worksheet="Postazioni", data=df_p); st.cache_data.clear(); st.rerun()
    st.dataframe(data["postazioni"])

# --- 7. FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.title("⚙️ Pianifica Fabbisogno")
    with st.form("form_fabb"):
        f1, f2, f3 = st.columns(3)
        fdata = f1.date_input("Data", default_date); fman = f2.selectbox("Mansione", lista_postazioni); fq = f3.number_input("Quantità", 1, 50, 1)
        if st.form_submit_button("Salva"):
            new_f = pd.DataFrame([{"Data": fdata.strftime("%Y-%m-%d"), "Mansione": fman, "Quantita": fq}])
            conn.update(worksheet="Fabbisogno", data=pd.concat([data["fabbisogno"], new_f], ignore_index=True))
            st.cache_data.clear(); st.rerun()
    st.dataframe(data["fabbisogno"])

# --- 8. IMPOSTAZIONI ---
elif menu == "⚙️ Impostazioni Stagione":
    st.title("⚙️ Impostazioni Stagione")
    d1 = st.date_input("Apertura", data_apertura); d2 = st.date_input("Chiusura", data_chiusura)
    if st.button("Aggiorna Date"):
        data["config"].loc[data["config"]["Ruolo"] == "Apertura", "Password"] = d1.strftime("%Y-%m-%d")
        data["config"].loc[data["config"]["Ruolo"] == "Chiusura", "Password"] = d2.strftime("%Y-%m-%d")
        conn.update(worksheet="Config", data=data["config"]); st.cache_data.clear(); st.success("Date Aggiornate")

# --- 9. PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.title("🔑 Cambio Password")
    p1 = st.text_input("Password Admin", value=admin_pwd); p2 = st.text_input("Password Staff", value=user_pwd)
    if st.button("Salva Password"):
        data["config"].loc[data["config"]["Ruolo"] == "Admin", "Password"] = p1
        data["config"].loc[data["config"]["Ruolo"] == "User", "Password"] = p2
        conn.update(worksheet="Config", data=data["config"]); st.cache_data.clear(); st.success("Password salvate")
