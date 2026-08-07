import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar
import urllib.parse
from io import BytesIO

# --- LIBRERIE PER PDF (Originali) ---
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

# --- CSS PERSONALIZZATO PER GRAFICA ACCATTIVANTE ---
st.markdown("""
<style>
    /* Sfondo e font generale */
    .main { background-color: #f8f9fa; }
    
    /* Card moderne per la Dashboard */
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
    
    /* Badge nomi */
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

    /* Pulsanti Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# --- CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARICAMENTO DATI ---
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
        if "Contestazioni" in res["addetti"].columns:
            res["addetti"]["Contestazioni"] = res["addetti"]["Contestazioni"].astype(str).replace(['nan', 'None', '<NA>'], '')
        else: res["addetti"]["Contestazioni"] = ""
        if "Stato Rapporto" not in res["addetti"].columns: res["addetti"]["Stato Rapporto"] = "Attivo"
        if "Data Cessazione" not in res["addetti"].columns: res["addetti"]["Data Cessazione"] = ""
        if "Cellulare" not in res["addetti"].columns: res["addetti"]["Cellulare"] = ""
        else: res["addetti"]["Cellulare"] = res["addetti"]["Cellulare"].astype(str).replace(r'\.0$', '', regex=True).replace(['nan', 'None', '<NA>'], '')
        if "Email" not in res["addetti"].columns: res["addetti"]["Email"] = ""
        else: res["addetti"]["Email"] = res["addetti"]["Email"].astype(str).replace(['nan', 'None', '<NA>'], '')
        return res
    except Exception as e:
        st.error(f"⚠️ Errore di connessione: {e}"); st.stop()

data = get_all_data()

# --- UTILITY WHATSAPP ---
def format_wa_link(row):
    tel = str(row['Cellulare']).strip().replace(" ", "").replace("+", "")
    if not tel or tel == "" or tel == "nan": return None
    if len(tel) <= 10: tel = "39" + tel
    msg = f"Ciao {row['Nome']}, "
    msg_encoded = urllib.parse.quote(msg)
    return f"https://wa.me/{tel}?text={msg_encoded}"

# --- FUNZIONE GENERAZIONE PDF (Originale) ---
def genera_pdf_riposi(mansione, df_mansione, giorni_ita):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Riepilogo Riposi Settimanali - {mansione}", styles['Title']))
    elements.append(Spacer(1, 20))
    header = [g.upper() for g in giorni_ita]
    mappa_persone = {g: [f"{r['Nome']} {r['Cognome']}" for _, r in df_mansione[df_mansione["GiornoRiposoSettimanale"] == g].iterrows()] for g in giorni_ita}
    max_rows = max([len(v) for v in mappa_persone.values()]) if mappa_persone else 0
    data_tabella = [header]
    for i in range(max_rows):
        fila = []
        for g in giorni_ita:
            persone = mappa_persone[g]; fila.append(persone[i] if i < len(persone) else "")
        data_tabella.append(fila)
    t = Table(data_tabella, colWidths=[110]*7)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1f77b4")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t); doc.build(elements); buffer.seek(0)
    return buffer

# --- ESTRAZIONE CONFIGURAZIONE ---
conf_df = data["config"]
conf_df.columns = conf_df.columns.str.strip()
try:
    admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
    user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except:
    admin_pwd, user_pwd = "admin", "staff"; data_apertura = datetime(2026, 5, 16).date(); data_chiusura = datetime(2026, 9, 13).date()

# --- LOGIN ---
if "role" not in st.session_state:
    col_p1, col_p2, col_p3 = st.columns([2, 1, 2])
    with col_p2: st.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    col_p4, col_p5, col_p6 = st.columns([1.5, 1, 1.5])
    with col_p5:
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi", use_container_width=True):
            if pwd_input == admin_pwd: st.session_state["role"] = "Admin"; st.rerun()
            elif pwd_input == user_pwd: st.session_state["role"] = "User"; st.rerun()
            else: st.error("❌ Password errata.")
    st.stop()

# --- VARIABILI GLOBALI ---
oggi = datetime.now().date()
default_date = oggi if data_apertura <= oggi <= data_chiusura else data_apertura
mappa_giorni = {"Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3, "Venerdì": 4, "Sabato": 5, "Domenica": 6}
giorni_ita = list(mappa_giorni.keys()); opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

# CALCOLO DEL PRIMO LUNEDÌ DOPO L'APERTURA
giorni_al_prossimo_lunedi = (0 - data_apertura.weekday()) % 7
if giorni_al_prossimo_lunedi == 0:
    primo_lunedi_effettivo = data_apertura
else:
    primo_lunedi_effettivo = data_apertura + timedelta(days=giorni_al_prossimo_lunedi)

# --- FUNZIONE CALENDARIO ---
def genera_mini_calendario(df_persona, riposo_fisso, anno, mese):
    nomi_mesi_ita = {5: "MAGGIO", 6: "GIUGNO", 7: "LUGLIO", 8: "AGOSTO", 9: "SETTEMBRE"}
    st.markdown(f"<div style='text-align: center; background-color: #1f77b4; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'><b>{nomi_mesi_ita.get(mese, 'Mese')}</b></div>", unsafe_allow_html=True)
    mappa_lower = {k.lower(): v for k, v in mappa_giorni.items()}
    r_pulito = str(riposo_fisso).strip().lower()
    idx_riposo_fisso = mappa_lower.get(r_pulito, -1)
    cal = calendar.monthcalendar(anno, mese)
    html = '<table style="width:100%; border-collapse: collapse; text-align: center; font-size: 11px; table-layout: fixed; border: 1px solid #ddd;">'
    html += '<tr style="background:rgba(128,128,128,0.1);"><th>L</th><th>M</th><th>M</th><th>G</th><th>V</th><th>S</th><th>D</th></tr>'
    for week in cal:
        html += '<tr style="height: 30px;">'
        for i, day in enumerate(week):
            if day == 0: html += '<td style="border:1px solid rgba(128,128,128,0.1);"></td>'
            else:
                curr_d = datetime(anno, mese, day).date(); d_str = curr_d.strftime("%Y-%m-%d")
                is_open = data_apertura <= curr_d <= data_chiusura; bg, tx, label = "transparent", "inherit", str(day)
                if not is_open: bg, tx, label = "#f0f0f0", "#bfbfbf", f"<span style='text-decoration: line-through;'>{day}</span>"
                else:
                    stato_row = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]
                    if i == idx_riposo_fisso and curr_d >= primo_lunedi_effettivo:
                        bg, tx = "#ffa500", "white"
                        if not stato_row.empty:
                            s_val = str(stato_row["Stato"].iloc[0]).upper()
                            if "NON" in s_val: bg, tx = "#ff4b4b", "white"
                            elif "PERMESSO" in s_val: bg, tx = "#00008B", "white"
                            elif "ASSENTE" in s_val: bg, tx = "#000000", "white"
                            elif "MALATTIA" in s_val: bg, tx = "#696969", "white"
                    else:
                        if not stato_row.empty:
                            s_val = str(stato_row["Stato"].iloc[0]).upper()
                            if "NON" in s_val: bg, tx = "#ff4b4b", "white"
                            elif "PERMESSO" in s_val: bg, tx = "#00008B", "white"
                            elif "ASSENTE" in s_val: bg, tx = "#000000", "white"
                            elif "MALATTIA" in s_val: bg, tx = "#696969", "white"
                            elif "DISPONIBILE" in s_val: bg, tx = "#29b05c", "white"
                html += f'<td style="background:{bg}; color:{tx}; border:1px solid rgba(128,128,128,0.2); font-weight:bold;">{label}</td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

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
    st.title("Situazione giornaliera")
    input_d = st.date_input("Inizio visualizzazione (settimana):", default_date)
    date_range = [input_d + timedelta(days=i) for i in range(7)]
    date_aperte = [d for d in date_range if data_apertura <= d <= data_chiusura]
    
    if not date_aperte:
        st.warning(f"⚠️ Parco CHIUSO nel periodo selezionato.")
    else:
        def to_date_only(val):
            try: return pd.to_datetime(val).date()
            except: return None
        def norm(s):
            if pd.isna(s): return ""
            return str(s).strip().upper()
            
        def genera_card(titolo, color, num, req, staff_list):
            nomi_html = "".join([f"<div class='name-badge'>• {r['Nome']} {r['Cognome']}</div>" for _, r in staff_list.iterrows()])
            if not nomi_html: nomi_html = "<div style='color:gray; font-size:12px; font-style:italic; padding:10px;'>Nessuno disponibile</div>"
            req_str = f" <span style='font-size:16px; color:#999;'>/ {req}</span>" if req != "-" else ""
            return f"""
                <div class="card-container">
                    <div style="background: {color}; color: white; padding: 10px; border-radius: 12px 12px 0 0; text-align: center; font-weight: bold; font-size: 0.9rem;">{titolo.upper()}</div>
                    <div style="padding: 15px; text-align: center;">
                        <div style="font-size: 26px; font-weight: bold; color:#333;">{num}{req_str}</div>
                        <div style="margin-top: 10px; text-align: left; border-top: 1px solid #f0f0f0; padding-top: 10px;">{nomi_html}</div>
                    </div>
                </div>
            """

        tabs = st.tabs([d.strftime("%A %d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                d_tab = date_aperte[idx]
                giorno_sett_oggi = norm(giorni_ita[d_tab.weekday()])
                
                df_f = data["fabbisogno"].copy(); df_f['d_pure'] = df_f['Data'].apply(to_date_only)
                fabb_oggi = df_f[df_f['d_pure'] == d_tab]
                
                df_dis = data["disp"].copy(); df_dis['d_pure'] = df_dis['Data'].apply(to_date_only)
                disp_oggi = df_dis[df_dis['d_pure'] == d_tab]
                disp_oggi["Stato_Norm"] = disp_oggi["Stato"].apply(norm)
                lista_nera_nomi = (disp_oggi[disp_oggi["Stato_Norm"] != "DISPONIBILE"]["Nome"].apply(norm) + disp_oggi[disp_oggi["Stato_Norm"] != "DISPONIBILE"]["Cognome"].apply(norm)).tolist()
                
                staff_base = data["addetti"][data["addetti"]["Stato Rapporto"] == "Attivo"].copy()
                staff_base["ID_UNICO"] = staff_base["Nome"].apply(norm) + staff_base["Cognome"].apply(norm)
                staff_base["RIPOSO_NORM"] = staff_base["GiornoRiposoSettimanale"].apply(norm)
                
                # Identifica persone in Malattia
                lista_malattia_nomi = (disp_oggi[disp_oggi["Stato_Norm"] == "MALATTIA"]["Nome"].apply(norm) + disp_oggi[disp_oggi["Stato_Norm"] == "MALATTIA"]["Cognome"].apply(norm)).tolist()
                ammalati_oggi = staff_base[staff_base["ID_UNICO"].isin(lista_malattia_nomi)]
                
                if d_tab >= primo_lunedi_effettivo:
                    presenti_effettivi = staff_base[(staff_base["RIPOSO_NORM"] != giorno_sett_oggi) & (~staff_base["ID_UNICO"].isin(lista_nera_nomi))]
                else:
                    presenti_effettivi = staff_base[~staff_base["ID_UNICO"].isin(lista_nera_nomi)]

                cols = st.columns(len(lista_postazioni) if len(lista_postazioni) <= 4 else 3)
                for idx_p, m in enumerate(lista_postazioni):
                    col_target = cols[idx_p % len(cols)]
                    with col_target:
                        s_p = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m)]
                        f_r = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m)]
                        r = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0
                        n = len(s_p)
                        c = "#29b05c" if n >= r and r > 0 else "#ff4b4b" if n < r else "#808080"
                        st.markdown(genera_card(m, c, n, r, s_p), unsafe_allow_html=True)

                # Visualizzazione speciale per gli Ammalati del giorno
                st.markdown("---")
                st.markdown("### 🤒 Ammalati della giornata")
                if not ammalati_oggi.empty:
                    c_amm = st.columns(3)
                    with c_amm[0]:
                        st.markdown(genera_card("Ammalati / Malattia", "#696969", len(ammalati_oggi), "-", ammalati_oggi), unsafe_allow_html=True)
                else:
                    st.info("Nessun addetto in malattia registrato per questo giorno.")

# --- 2. RIEPILOGO RIPOSI ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.title("Riposi Settimanali")
    
    for m in lista_postazioni:
        add_m = data["addetti"][(data["addetti"]["Mansione"] == m) & (data["addetti"]["Stato Rapporto"] == "Attivo")]
        
        if not add_m.empty:
            col_tit, col_pdf = st.columns([5, 1])
            with col_tit:
                st.markdown(f"### 📍 {m}")
            with col_pdf:
                st.download_button("📄 PDF", genera_pdf_riposi(m, add_m, giorni_ita), f"Riposi_{m}.pdf", "application/pdf", key=f"pdf_{m}")
            
            with st.container(border=True):
                cols = st.columns(7)
                for i, g in enumerate(giorni_ita):
                    with cols[i]:
                        st.markdown(f"""
                            <div style="background:#1f77b4; color:white; border-radius:5px; padding:2px; text-align:center; font-weight:bold; font-size:12px; margin-bottom:10px;">
                                {g[:3].upper()}
                            </div>
                        """, unsafe_allow_html=True)
                        persone_giorno = add_m[add_m["GiornoRiposoSettimanale"] == g]
                        for _, r in persone_giorno.iterrows():
                            st.markdown(f'<div class="name-badge" style="text-align:center; border-left:none; background:#f8f9fa; font-size:11px; margin-bottom:4px;">{r["Nome"]} {r["Cognome"]}</div>', unsafe_allow_html=True)

            non_def = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
            if not non_def.empty:
                st.markdown("<p style='margin-bottom:5px; margin-top:10px; font-weight:bold; color:#666; font-size:0.9rem;'>Senza riposo assegnato:</p>", unsafe_allow_html=True)
                with st.container(border=True):
                    badge_nd_html = ""
                    for _, r in non_def.iterrows():
                        badge_nd_html += f'<span class="name-badge" style="display:inline-block; margin-right:8px; border-left:4px solid #6c757d; padding: 4px 10px;">{r["Nome"]} {r["Cognome"]}</span>'
                    st.markdown(f'<div style="display:flex; flex-wrap:wrap; gap:5px;">{badge_nd_html}</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

# --- 3. GESTIONE RIPOSI RAPIDA ---
elif menu == "📝 Gestione Riposi Rapida":
    st.title("Modifica Rapida Riposi")
    st.info("I box mostrano quanti addetti riposano ogni giorno per la specifica mansione.")
    
    df_mod = data["addetti"].copy()
    
    for m in lista_postazioni:
        add_m = df_mod[(df_mod["Mansione"] == m) & (df_mod["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            conteggi_m = add_m["GiornoRiposoSettimanale"].value_counts()
            
            c_counts = st.columns(7)
            for i, g in enumerate(giorni_ita):
                num = conteggi_m.get(g, 0)
                border_col = "#1f77b4" if num < 3 else "#ff4b4b" 
                with c_counts[i]:
                    st.markdown(f"""
                        <div style="background:white; border:1px solid #eee; border-radius:8px; padding:8px; text-align:center; border-bottom: 3px solid {border_col};">
                            <div style="font-size:10px; font-weight:bold; color:#888; text-transform:uppercase;">{g[:3]}</div>
                            <div style="font-size:18px; font-weight:bold; color:{border_col};">{num}</div>
                        </div>
                    """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                for idx, row in add_m.iterrows():
                    col_nome, col_sel = st.columns([3, 1])
                    col_nome.markdown(f"<div style='padding-top:8px; font-size:0.95rem;'>{row['Nome']} <b>{row['Cognome']}</b></div>", unsafe_allow_html=True)
                    curr_val = row['GiornoRiposoSettimanale']
                    df_mod.at[idx, 'GiornoRiposoSettimanale'] = col_sel.selectbox(
                        f"Rip_{idx}", 
                        opzioni_riposo, 
                        index=opzioni_riposo.index(curr_val) if curr_val in opzioni_riposo else 7,
                        key=f"fast_edit_{idx}",
                        label_visibility="collapsed"
                    )
            st.divider()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 SALVA TUTTE LE MODIFICHE", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod)
        st.cache_data.clear()
        st.success("Modifiche salvate con successo!")
        st.rerun()

# --- 4. AREA DISPONIBILITÀ STAFF ---
elif menu == "📅 Area Disponibilità Staff":
    st.title("Calendario Disponibilità")
    df_t = data["addetti"].copy()
    df_t['Full'] = df_t['Nome'] + " " + df_t['Cognome'] + df_t['Stato Rapporto'].apply(lambda x: " (CESSATO)" if x != "Attivo" else "")
    sel_dip = st.selectbox("Seleziona dipendente:", df_t['Full'].tolist())
    row_d = df_t[df_t['Full'] == sel_dip].iloc[0]
    df_p = data["disp"][(data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome'])]
    c_cal = st.columns(5)
    for idx, m in enumerate([5, 6, 7, 8, 9]):
        with c_cal[idx]: genera_mini_calendario(df_p, row_d['GiornoRiposoSettimanale'], 2026, m)
    with st.expander("Modifica Disponibilità / Assenze"):
        dr = st.date_input("Periodo:", value=[], min_value=data_apertura, max_value=data_chiusura)
        st_r = st.radio("Stato:", ["Disponibile", "NON Disponibile", "Permesso", "Assente", "Malattia"], horizontal=True)
        if st.button("Salva Date") and len(dr) == 2:
            d_list = [str(dr[0] + timedelta(days=x)) for x in range((dr[1]-dr[0]).days + 1)]
            nuovi = pd.DataFrame([{"Nome": row_d['Nome'], "Cognome": row_d['Cognome'], "Data": d, "Stato": st_r} for d in d_list])
            old = data["disp"][~((data["disp"]["Nome"] == row_d['Nome']) & (data["disp"]["Cognome"] == row_d['Cognome']) & (data["disp"]["Data"].astype(str).isin(d_list)))]
            conn.update(worksheet="Disponibilita", data=pd.concat([old, nuovi], ignore_index=True)); st.cache_data.clear(); st.rerun()

# --- 5. PIANIFICA FABBISOGNO ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.title("⚙️ Pianificazione Fabbisogno Personale")
    st.caption("Imposta il numero di addetti necessari per ciascuna mansione in un determinato periodo.")
    
    with st.form("form_fabbisogno"):
        dr_fabb = st.date_input("Seleziona Intervallo Date:", value=[default_date, default_date + timedelta(days=6)], min_value=data_apertura, max_value=data_chiusura)
        st.markdown("---")
        
        fabb_inputs = {}
        cols_f = st.columns(2)
        for idx_p, m in enumerate(lista_postazioni):
            with cols_f[idx_p % 2]:
                fabb_inputs[m] = st.number_input(f"Fabbisogno {m}:", min_value=0, value=1, step=1, key=f"fabb_in_{m}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        submit_fabb = st.form_submit_button("💾 Salva Fabbisogno per il Periodo", use_container_width=True, type="primary")
        
    if submit_fabb:
        if isinstance(dr_fabb, list) or isinstance(dr_fabb, tuple):
            start_d = dr_fabb[0]
            end_d = dr_fabb[1] if len(dr_fabb) > 1 else dr_fabb[0]
        else:
            start_d = end_d = dr_fabb
            
        d_range = [start_d + timedelta(days=x) for x in range((end_d - start_d).days + 1)]
        nuove_righe = []
        for d in d_range:
            d_str = d.strftime("%Y-%m-%d")
            for m, q in fabb_inputs.items():
                nuove_righe.append({"Data": d_str, "Mansione": m, "Quantita": q})
        
        df_fabb_exist = data["fabbisogno"].copy()
        if not df_fabb_exist.empty and "Data" in df_fabb_exist.columns:
            d_str_list = [d.strftime("%Y-%m-%d") for d in d_range]
            df_fabb_exist = df_fabb_exist[~df_fabb_exist["Data"].astype(str).isin(d_str_list)]
            
        df_fabb_updated = pd.concat([df_fabb_exist, pd.DataFrame(nuove_righe)], ignore_index=True)
        conn.update(worksheet="Fabbisogno", data=df_fabb_updated)
        st.cache_data.clear()
        st.success(f"Fabbisogno aggiornato con successo dal {start_d} al {end_d}!")
        st.rerun()

# --- 6. GESTIONE ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.title("Anagrafica")
    
    if "editing_id" not in st.session_state: 
        st.session_state["editing_id"] = None
    if "deleting_id" not in st.session_state:
        st.session_state["deleting_id"] = None

    if st.session_state["deleting_id"] is not None:
        idx_del = st.session_state["deleting_id"]
        row_del = data["addetti"].loc[idx_del]
        st.warning(f"⚠️ **ATTENZIONE:** Sei sicuro di voler eliminare definitivamente **{row_del['Nome']} {row_del['Cognome']}**?")
        dc1, dc2 = st.columns(2)
        if dc1.button("🔥 SÌ, CANCELLA", type="primary", use_container_width=True):
            df_aggiornato = data["addetti"].drop(index=idx_del)
            conn.update(worksheet="Addetti", data=df_aggiornato)
            st.cache_data.clear()
            st.session_state["deleting_id"] = None
            st.success("Collaboratore eliminato!")
            st.rerun()
        if dc2.button("❌ ANNULLA", use_container_width=True):
            st.session_state["deleting_id"] = None
            st.rerun()
            
    elif st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        
        with st.form("edit_form_new"):
            st.subheader(f"Modifica Profilo: {row['Nome']} {row['Cognome']}")
            c1, c2, c3 = st.columns(3)
            en = c1.text_input("Nome", row['Nome'])
            ec = c2.text_input("Cognome", row['Cognome'])
            estato = c3.selectbox("Stato Rapporto", ["Attivo", "Dimesso", "Licenziato"], 
                                   index=["Attivo", "Dimesso", "Licenziato"].index(row['Stato Rapporto']) if row['Stato Rapporto'] in ["Attivo", "Dimesso", "Licenziato"] else 0)
            
            c_tel, c_mail, c_cess = st.columns(3)
            etel = c_tel.text_input("Cellulare", row['Cellulare'])
            email = c_mail.text_input("Email", row['Email'])
            e_data_cess = c_cess.text_input("Data Cessazione (gg/mm/aaaa)", row.get('Data Cessazione', ''))
            
            c_man, c_rip, c_arm = st.columns(3)
            em = c_man.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            er = c_rip.selectbox("Riposo Settimanale", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 0)
            e_armadietto = c_arm.text_input("N° Armadietto", str(row.get('Numero Armadietto', '')))
            
            c_form1, c_form2 = st.columns(2)
            curr_form_val = str(row.get('Formazione', 'No')).strip()
            if curr_form_val not in ["Sì", "No"]: curr_form_val = "No"
            e_formazione = c_form1.selectbox("Formazione Effettuata?", ["Sì", "No"], index=["Sì", "No"].index(curr_form_val))
            e_data_formazione = c_form2.text_input("Data Formazione (gg/mm/aaaa)", str(row.get('Data Formazione', '')))
            
            e_cont = st.text_area("Lettere di Contestazione / Note", row['Contestazioni'])
            
            cb1, cb2 = st.columns(2)
            if cb1.form_submit_button("💾 SALVA MODIFICHE", use_container_width=True):
                data["addetti"].at[idx, 'Nome'] = en
                data["addetti"].at[idx, 'Cognome'] = ec
                data["addetti"].at[idx, 'Stato Rapporto'] = estato
                data["addetti"].at[idx, 'Cellulare'] = etel
                data["addetti"].at[idx, 'Email'] = email
                data["addetti"].at[idx, 'Mansione'] = em
                data["addetti"].at[idx, 'GiornoRiposoSettimanale'] = er
                data["addetti"].at[idx, 'Contestazioni'] = e_cont
                data["addetti"].at[idx, 'Data Cessazione'] = e_data_cess
                data["addetti"].at[idx, 'Formazione'] = e_formazione
                data["addetti"].at[idx, 'Data Formazione'] = e_data_formazione
                data["addetti"].at[idx, 'Numero Armadietto'] = e_armadietto.strip()
                
                conn.update(worksheet="Addetti", data=data["addetti"])
                st.cache_data.clear()
                st.session_state["editing_id"] = None
                st.success("Dati aggiornati correttamente!")
                st.rerun()
            
            if cb2.form_submit_button("❌ ANNULLA", use_container_width=True):
                st.session_state["editing_id"] = None
                st.rerun()
    else:
        t1, t2 = st.tabs(["📋 Elenco Personale", "➕ Aggiungi Nuovo"])
        
        with t1:
            col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
            filtro_stato = col_f1.radio("Filtra Stato:", ["Solo Attivi", "Tutti"], horizontal=True, key="f_stato_anag")
            filtro_man = col_f2.selectbox("Filtra Mansione:", ["Tutte"] + lista_postazioni, key="f_man_anag")
            ordina_per = col_f3.selectbox("Ordina per:", ["Alfabetico", "Più Disponibili", "Più Assenti", "Più Permessi", "Più Malattie"])

            df_display = data["addetti"].copy()
            df_disp_local = data["disp"].copy()
            
            df_disp_local['Nome_Match'] = df_disp_local['Nome'].astype(str).str.upper().str.strip()
            df_disp_local['Cognome_Match'] = df_disp_local['Cognome'].astype(str).str.upper().str.strip()
            df_disp_local['Stato_Match'] = df_disp_local['Stato'].astype(str).str.upper().str.strip()

            stats = df_disp_local.groupby(['Nome_Match', 'Cognome_Match', 'Stato_Match']).size().unstack(fill_value=0)
            for c in ["DISPONIBILE", "ASSENTE", "PERMESSO", "MALATTIA"]:
                if c not in stats.columns: stats[c] = 0

            def get_local_stats(r):
                n, c = str(r['Nome']).upper().strip(), str(r['Cognome']).upper().strip()
                if (n, c) in stats.index:
                    s_row = stats.loc[(n, c)]
                    return pd.Series([s_row["DISPONIBILE"], s_row["ASSENTE"], s_row["PERMESSO"], s_row["MALATTIA"]])
                return pd.Series([0, 0, 0, 0])

            df_display[["C_D", "C_A", "C_P", "C_M"]] = df_display.apply(get_local_stats, axis=1)

            if filtro_stato == "Solo Attivi":
                df_display = df_display[df_display["Stato Rapporto"] == "Attivo"]
            if filtro_man != "Tutte":
                df_display = df_display[df_display["Mansione"] == filtro_man]

            mappa_sort = {
                "Alfabetico": (["Cognome", "Nome"], [True, True]),
                "Più Disponibili": (["C_D", "Cognome"], [False, True]),
                "Più Assenti": (["C_A", "Cognome"], [False, True]),
                "Più Permessi": (["C_P", "Cognome"], [False, True]),
                "Più Malattie": (["C_M", "Cognome"], [False, True])
            }
            s_cols, s_asc = mappa_sort[ordina_per]
            df_display = df_display.sort_values(by=s_cols, ascending=s_asc)
            
            st.markdown(f"**Risultati trovati: {len(df_display)}**")
            st.divider()

            for idx, r in df_display.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([3, 5, 2])
                    
                    wa = format_wa_link(r)
                    wa_html = f' <a href="{wa}" target="_blank" style="text-decoration:none;">📲</a>' if wa else ""
                    
                    nome_style = "color: #333;" if r['Stato Rapporto'] == "Attivo" else "color: #888; text-decoration: line-through;"
                    c1.markdown(f"<span style='{nome_style} font-weight: bold;'>{r['Nome']} {r['Cognome']}</span>{wa_html}", unsafe_allow_html=True)
                    c1.caption(f"📍 {r['Mansione']}")
                    
                    c2.markdown(f"""
                    <div style="display: flex; gap: 4px; margin-top: 5px;">
                        <span title="Disponibile" style="background:#29b05c; color:white; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:bold;">{int(r['C_D'])} D</span>
                        <span title="Assente" style="background:#000; color:white; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:bold;">{int(r['C_A'])} A</span>
                        <span title="Permesso" style="background:#00008B; color:white; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:bold;">{int(r['C_P'])} P</span>
                        <span title="Malattia" style="background:#696969; color:white; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:bold;">{int(r['C_M'])} M</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with c3:
                        cb_e, cb_d = st.columns(2)
                        if cb_e.button("✏️", key=f"btn_edit_{idx}"):
                            st.session_state["editing_id"] = idx
                            st.rerun()
                        if cb_d.button("🗑️", key=f"btn_del_{idx}"):
                            st.session_state["deleting_id"] = idx
                            st.rerun()
                st.divider()

        with t2:
            with st.form("form_add_new"):
                st.subheader("Aggiungi Nuovo Collaboratore")
                ca1, ca2 = st.columns(2)
                new_n = ca1.text_input("Nome *")
                new_c = ca2.text_input("Cognome *")
                
                ca3, ca4, ca5 = st.columns(3)
                new_tel = ca3.text_input("Cellulare")
                new_email = ca4.text_input("Email")
                new_arm = ca5.text_input("N° Armadietto")
                
                ca6, ca7 = st.columns(2)
                new_man = ca6.selectbox("Mansione", lista_postazioni)
                new_rip = ca7.selectbox("Riposo Settimanale", opzioni_riposo)
                
                if st.form_submit_button("➕ Salva Collaboratore", type="primary", use_container_width=True):
                    if new_n and new_c:
                        nuova_persona = pd.DataFrame([{
                            "Nome": new_n.strip(),
                            "Cognome": new_c.strip(),
                            "Mansione": new_man,
                            "GiornoRiposoSettimanale": new_rip,
                            "Stato Rapporto": "Attivo",
                            "Cellulare": new_tel.strip(),
                            "Email": new_email.strip(),
                            "Contestazioni": "",
                            "Data Cessazione": "",
                            "Formazione": "No",
                            "Data Formazione": "",
                            "Numero Armadietto": new_arm.strip()
                        }])
                        conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], nuova_persona], ignore_index=True))
                        st.cache_data.clear()
                        st.success("Collaboratore inserito correttamente!")
                        st.rerun()
                    else:
                        st.error("⚠️ Nome e Cognome sono obbligatori.")

# --- 7. GESTIONE POSTAZIONI ---
elif menu == "🚩 Gestione Postazioni":
    st.title("🚩 Gestione Postazioni / Mansioni")
    st.caption("Aggiungi o rimuovi le postazioni disponibili per lo staff.")
    
    df_post = data["postazioni"].copy()
    st.subheader("Postazioni Attuali")
    st.dataframe(df_post, use_container_width=True)
    
    col_ap1, col_ap2 = st.columns([3, 1])
    nuova_postazione = col_ap1.text_input("Nuova Postazione / Mansione:")
    if col_ap2.button("➕ Aggiungi", type="primary"):
        if nuova_postazione.strip():
            nuova_row = pd.DataFrame([{"Nome Postazione": nuova_postazione.strip()}])
            df_post_new = pd.concat([df_post, nuova_row], ignore_index=True).drop_duplicates()
            conn.update(worksheet="Postazioni", data=df_post_new)
            st.cache_data.clear()
            st.success("Postazione aggiunta!")
            st.rerun()

# --- 8. IMPOSTAZIONI STAGIONE ---
elif menu == "⚙️ Impostazioni Stagione":
    st.title("⚙️ Impostazioni Stagione")
    st.caption("Configura le date ufficiali di apertura e chiusura del parco Caribe Bay.")
    
    with st.form("form_stagione"):
        new_apertura = st.date_input("Data Apertura Parco:", data_apertura)
        new_chiusura = st.date_input("Data Chiusura Parco:", data_chiusura)
        
        if st.form_submit_button("💾 Salva Date Stagione", type="primary"):
            df_c = data["config"].copy()
            df_c.loc[df_c["Ruolo"] == "Apertura", "Password"] = str(new_apertura)
            df_c.loc[df_c["Ruolo"] == "Chiusura", "Password"] = str(new_chiusura)
            conn.update(worksheet="Config", data=df_c)
            st.cache_data.clear()
            st.success("Date della stagione aggiornate!")
            st.rerun()

# --- 9. GESTIONE PASSWORD ---
elif menu == "🔑 Gestione Password":
    st.title("🔑 Gestione Password")
    st.caption("Modifica le password d'accesso per gli utenti Admin e User.")
    
    with st.form("form_pwd"):
        p_admin = st.text_input("Password Admin:", value=admin_pwd)
        p_user = st.text_input("Password User (Staff):", value=user_pwd)
        
        if st.form_submit_button("💾 Aggiorna Password", type="primary"):
            df_c = data["config"].copy()
            df_c.loc[df_c["Ruolo"] == "Admin", "Password"] = str(p_admin)
            df_c.loc[df_c["Ruolo"] == "User", "Password"] = str(p_user)
            conn.update(worksheet="Config", data=df_c)
            st.cache_data.clear()
            st.success("Password aggiornate con successo!")
            st.rerun()
