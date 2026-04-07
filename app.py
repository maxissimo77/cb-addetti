import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar
import urllib.parse
from io import BytesIO

# --- LIBRERIE PER PDF (Aggiunte) ---
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
        else:
            res["addetti"]["Contestazioni"] = ""
            
        if "Stato Rapporto" not in res["addetti"].columns:
            res["addetti"]["Stato Rapporto"] = "Attivo"
        if "Data Cessazione" not in res["addetti"].columns:
            res["addetti"]["Data Cessazione"] = ""

        if "Cellulare" not in res["addetti"].columns:
            res["addetti"]["Cellulare"] = ""
        else:
            res["addetti"]["Cellulare"] = (
                res["addetti"]["Cellulare"]
                .astype(str)
                .replace(r'\.0$', '', regex=True)
                .replace(['nan', 'None', '<NA>'], '')
            )

        if "Email" not in res["addetti"].columns:
            res["addetti"]["Email"] = ""
        else:
            res["addetti"]["Email"] = (
                res["addetti"]["Email"]
                .astype(str)
                .replace(['nan', 'None', '<NA>'], '')
            )
            
        return res
    except Exception as e:
        st.error(f"⚠️ Errore di connessione API: {e}")
        st.stop()

data = get_all_data()

# --- UTILITY WHATSAPP ---
def format_wa_link(row):
    tel = str(row['Cellulare']).strip().replace(" ", "").replace("+", "")
    if not tel or tel == "" or tel == "nan":
        return None
    if len(tel) <= 10:
        tel = "39" + tel
    
    msg = f"Ciao {row['Nome']}, "
    msg_encoded = urllib.parse.quote(msg)
    return f"https://wa.me/{tel}?text={msg_encoded}"

# --- FUNZIONE GENERAZIONE PDF (Nuova) ---
def genera_pdf_riposi(mansione, df_mansione, giorni_ita):
    buffer = BytesIO()
    # Impostiamo il foglio in orizzontale (landscape) per far stare meglio i 7 giorni
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    
    # Titolo
    elements.append(Paragraph(f"Riepilogo Riposi Settimanali - {mansione}", styles['Title']))
    elements.append(Spacer(1, 20))
    
    # Intestazione Tabella
    header = [g.upper() for g in giorni_ita]
    
    # Mappa delle persone per giorno
    mappa_persone = {g: [f"{r['Nome']} {r['Cognome']}" for _, r in df_mansione[df_mansione["GiornoRiposoSettimanale"] == g].iterrows()] for g in giorni_ita}
    
    # Calcolo righe massime necessarie
    max_rows = max([len(v) for v in mappa_persone.values()]) if mappa_persone else 0
    
    data_tabella = [header]
    for i in range(max_rows):
        fila = []
        for g in giorni_ita:
            persone = mappa_persone[g]
            fila.append(persone[i] if i < len(persone) else "")
        data_tabella.append(fila)
    
    # Creazione Tabella
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
    
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- ESTRAZIONE CONFIGURAZIONE ---
conf_df = data["config"]
conf_df.columns = conf_df.columns.str.strip()

try:
    admin_pwd = str(conf_df[conf_df["Ruolo"] == "Admin"]["Password"].values[0])
    user_pwd = str(conf_df[conf_df["Ruolo"] == "User"]["Password"].values[0])
    data_apertura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Apertura"]["Password"].values[0]).date()
    data_chiusura = pd.to_datetime(conf_df[conf_df["Ruolo"] == "Chiusura"]["Password"].values[0]).date()
except Exception:
    admin_pwd, user_pwd = "admin", "staff"
    data_apertura = datetime(2026, 5, 16).date()
    data_chiusura = datetime(2026, 9, 13).date()

# --- LOGIN ---
if "role" not in st.session_state:
    col_p1, col_p2, col_p3 = st.columns([2, 1, 2])
    with col_p2:
        st.image("https://www.caribebay.it/sites/default/files/caribebay-logo.png", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    col_p4, col_p5, col_p6 = st.columns([1.5, 1, 1.5])
    with col_p5:
        pwd_input = st.text_input("Inserisci Password", type="password")
        if st.button("Accedi", use_container_width=True):
            if pwd_input == admin_pwd: 
                st.session_state["role"] = "Admin"
                st.rerun()
            elif pwd_input == user_pwd: 
                st.session_state["role"] = "User"
                st.rerun()
            else: 
                st.error("❌ Password errata.")
    st.stop()

# --- VARIABILI GLOBALI ---
oggi = datetime.now().date()
default_date = oggi if data_apertura <= oggi <= data_chiusura else data_apertura
mappa_giorni = {"Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3, "Venerdì": 4, "Sabato": 5, "Domenica": 6}
giorni_ita = list(mappa_giorni.keys())
opzioni_riposo = giorni_ita + ["Non Definito"]
lista_postazioni = data["postazioni"]["Nome Postazione"].dropna().unique().tolist() if not data["postazioni"].empty else ["Generico"]

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
            if day == 0:
                html += '<td style="border:1px solid rgba(128,128,128,0.1);"></td>'
            else:
                curr_d = datetime(anno, mese, day).date()
                d_str = curr_d.strftime("%Y-%m-%d")
                is_open = data_apertura <= curr_d <= data_chiusura
                bg, tx, label = "transparent", "inherit", str(day)
                if not is_open:
                    bg, tx, label = "#f0f0f0", "#bfbfbf", f"<span style='text-decoration: line-through;'>{day}</span>"
                else:
                    stato_row = df_persona[df_persona["Data"].astype(str).str.contains(d_str, na=False)]
                    if i == idx_riposo_fisso:
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

menu = st.sidebar.radio("Vai a:", menu_options)
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("Stato Occupazione Postazioni")
    input_d = st.date_input("Inizio visualizzazione (settimana):", default_date)
    data_inizio = input_d
    date_range = [data_inizio + timedelta(days=i) for i in range(7)]
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
            nomi_html = ""
            for _, r in staff_list.iterrows():
                nomi_html += f"<div style='font-size: 13px; border-bottom: 1px solid #f0f0f0; padding: 4px 0; color: #444;'>• {r['Nome']} {r['Cognome']}</div>"
            
            if not nomi_html: nomi_html = "<div style='color:gray; font-size:12px; font-style:italic;'>Nessuno disponibile</div>"
            return f"""
                <div style="border: 1px solid #ddd; border-radius: 10px; margin-bottom: 15px; background: white; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                    <div style="background: {color}; color: white; padding: 8px; border-radius: 10px 10px 0 0; text-align: center; font-weight: bold; font-size: 13px;">{titolo.upper()}</div>
                    <div style="padding: 12px; text-align: center;">
                        <div style="font-size: 22px; font-weight: bold; color: #333;">{num} / {req}</div>
                        <div style="margin-top: 8px; text-align: left; border-top: 1px solid #eee; padding-top: 5px;">{nomi_html}</div>
                    </div>
                </div>
            """

        tabs = st.tabs([d.strftime("%d/%m") for d in date_aperte])
        for idx, t in enumerate(tabs):
            with t:
                d_tab = date_aperte[idx]
                giorno_sett_oggi = norm(giorni_ita[d_tab.weekday()])
                df_f = data["fabbisogno"].copy()
                df_f['d_pure'] = df_f['Data'].apply(to_date_only)
                fabb_oggi = df_f[df_f['d_pure'] == d_tab]
                df_dis = data["disp"].copy()
                df_dis['d_pure'] = df_dis['Data'].apply(to_date_only)
                disp_oggi = df_dis[df_dis['d_pure'] == d_tab]
                disp_oggi["Stato_Norm"] = disp_oggi["Stato"].apply(norm)
                nomi_assenti = disp_oggi[disp_oggi["Stato_Norm"] != "DISPONIBILE"]
                lista_nera_nomi = (nomi_assenti["Nome"].apply(norm) + nomi_assenti["Cognome"].apply(norm)).tolist()
                
                staff_base = data["addetti"].copy()
                staff_base = staff_base[staff_base["Stato Rapporto"] == "Attivo"]
                
                staff_base["ID_UNICO"] = staff_base["Nome"].apply(norm) + staff_base["Cognome"].apply(norm)
                staff_base["RIPOSO_NORM"] = staff_base["GiornoRiposoSettimanale"].apply(norm)
                presenti_effettivi = staff_base[(staff_base["RIPOSO_NORM"] != giorno_sett_oggi) & (~staff_base["ID_UNICO"].isin(lista_nera_nomi))].copy()

                col1, col2, col3 = st.columns(3)
                with col1:
                    m = "Addetto Attrazioni"
                    s_p = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m)]
                    f_r = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m)]; r = int(f_r["Quantita"].iloc[0]) if not f_r.empty else 0; n = len(s_p)
                    c = "#29b05c" if n >= r and r > 0 else "#ff4b4b" if n < r else "#808080"
                    st.markdown(genera_card(m, c, n, r, s_p), unsafe_allow_html=True)
                with col2:
                    m1 = "Assistente Bagnanti"
                    s_p1 = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m1)]
                    f_r1 = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m1)]; r1 = int(f_r1["Quantita"].iloc[0]) if not f_r1.empty else 0; n1 = len(s_p1)
                    c1 = "#29b05c" if n1 >= r1 and r1 > 0 else "#ff4b4b" if n1 < r1 else "#808080"
                    st.markdown(genera_card(m1, c1, n1, r1, s_p1), unsafe_allow_html=True)
                    m2 = "Bungee Jumping"
                    s_p2 = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m2)]
                    f_r2 = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m2)]; r2 = int(f_r2["Quantita"].iloc[0]) if not f_r2.empty else 0; n2 = len(s_p2)
                    c2 = "#29b05c" if n2 >= r2 and r2 > 0 else "#ff4b4b" if n2 < r2 else "#808080"
                    st.markdown(genera_card(m2, c2, n2, r2, s_p2), unsafe_allow_html=True)
                with col3:
                    m3 = "Radio"
                    s_p3 = presenti_effettivi[presenti_effettivi["Mansione"].apply(norm) == norm(m3)]
                    f_r3 = fabb_oggi[fabb_oggi["Mansione"].apply(norm) == norm(m3)]; r3 = int(f_r3["Quantita"].iloc[0]) if not f_r3.empty else 0; n3 = len(s_p3)
                    c3 = "#29b05c" if n3 >= r3 and r3 > 0 else "#ff4b4b" if n3 < r3 else "#808080"
                    st.markdown(genera_card(m3, c3, n3, r3, s_p3), unsafe_allow_html=True)

# --- 2. RIEPILOGO RIPOSI (Aggiornato con PDF) ---
elif menu == "📅 Riepilogo Riposi Settimanali":
    st.header("Riepilogo Giorni di Riposo (Solo Attivi)")
    for m in lista_postazioni:
        add_m = data["addetti"][(data["addetti"]["Mansione"] == m) & (data["addetti"]["Stato Rapporto"] == "Attivo")]
        if not add_m.empty:
            # Layout con titolo a sinistra e bottone PDF a destra
            col_tit, col_pdf = st.columns([5, 1])
            with col_tit:
                st.subheader(f"📍 {m}")
            with col_pdf:
                pdf_data = genera_pdf_riposi(m, add_m, giorni_ita)
                st.download_button(label="📄 Esporta PDF", data=pdf_data, file_name=f"Riposi_{m.replace(' ', '_')}.pdf", mime="application/pdf", key=f"pdf_{m}")
            
            with st.expander(f"Dettagli {m}", expanded=True):
                c_rip = st.columns(7)
                for i, g in enumerate(giorni_ita):
                    with c_rip[i]:
                        st.markdown(f"<div style='text-align:center; background:rgba(128,128,128,0.2); padding:5px; border-radius:5px; margin-bottom:12px;'><b>{g}</b></div>", unsafe_allow_html=True)
                        chi = add_m[add_m["GiornoRiposoSettimanale"] == g]
                        for _, r in chi.iterrows():
                            st.markdown(f"""
                                <div style='text-align: center; background-color: rgba(31, 119, 180, 0.1); padding: 10px 5px; border-radius: 5px; margin: 10px 0px; font-size: 14px; font-weight: 500; border: 1px solid rgba(31, 119, 180, 0.3);'>
                                    {r['Nome']} {r['Cognome']}
                                </div>
                            """, unsafe_allow_html=True)
                
                non_def = add_m[add_m["GiornoRiposoSettimanale"] == "Non Definito"]
                if not non_def.empty:
                    st.markdown("<div style='margin-top: 25px; border-top: 1px solid rgba(128,128,128,0.3); padding-top: 15px;'><b>Riposo Non Definito:</b></div>", unsafe_allow_html=True)
                    html_nd = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; margin-bottom: 20px;">'
                    for _, r in non_def.iterrows():
                        html_nd += f"<div style='border: 2px solid #ffa500; padding: 8px 15px; border-radius: 8px; font-weight: bold; background-color: rgba(255, 165, 0, 0.1); color: #333;'>{r['Nome']} {r['Cognome']}</div>"
                    st.markdown(html_nd + '</div>', unsafe_allow_html=True)

# --- 3. GESTIONE RIPOSI RAPIDA ---
elif menu == "📝 Gestione Riposi Rapida":
    st.header("Gestione Rapida Riposi (Solo Attivi)")
    df_mod = data["addetti"].copy()
    df_attivi = df_mod[df_mod["Stato Rapporto"] == "Attivo"]
    for m in lista_postazioni:
        add_m = df_attivi[df_attivi["Mansione"] == m]
        if not add_m.empty:
            st.markdown(f"### 📍 {m}")
            conteggi = add_m["GiornoRiposoSettimanale"].value_counts()
            cols_c = st.columns(7)
            for i, g in enumerate(giorni_ita):
                n_rip = conteggi.get(g, 0)
                with cols_c[i]: st.markdown(f"<div style='text-align:center; background:rgba(128,128,128,0.05); border: 1px solid rgba(128,128,128,0.1); border-radius:5px; padding:5px;'><small>{g[:3]}</small><br><b style='color:#1f77b4;'>{n_rip}</b></div>", unsafe_allow_html=True)
            for idx, row in add_m.iterrows():
                with st.container():
                    col_nome, col_scelta = st.columns([2, 1])
                    with col_nome: st.markdown(f"""<div style="padding-top: 15px; padding-bottom: 10px; border-bottom: 1px solid #f0f2f6;"><span style="font-size: 16px;">{row['Nome']} <b>{row['Cognome']}</b></span></div>""", unsafe_allow_html=True)
                    with col_scelta:
                        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                        df_mod.at[idx, 'GiornoRiposoSettimanale'] = st.selectbox(f"Riposo {idx}", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7, key=f"r_rap_{idx}", label_visibility="collapsed")
    if st.button("💾 Salva Tutte le Modifiche", type="primary", use_container_width=True):
        conn.update(worksheet="Addetti", data=df_mod); st.cache_data.clear(); st.success("Salvato!"); st.rerun()

# --- 4. AREA DISPONIBILITÀ ---
elif menu == "📅 Area Disponibilità Staff":
    st.header("Calendario Disponibilità Individuale")
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

# --- 5. GESTIONE ANAGRAFICA ---
elif menu == "👥 Gestione Anagrafica":
    st.header("Anagrafica Personale")
    if "editing_id" not in st.session_state: st.session_state["editing_id"] = None
    if st.session_state["editing_id"] is not None:
        idx = st.session_state["editing_id"]
        row = data["addetti"].loc[idx]
        with st.form("edit"):
            st.subheader(f"Modifica: {row['Nome']} {row['Cognome']}")
            c1, c2, c3 = st.columns([2, 2, 1])
            en, ec = c1.text_input("Nome", row['Nome']), c2.text_input("Cognome", row['Cognome'])
            attuale_stato = row['Stato Rapporto'] if 'Stato Rapporto' in row else "Attivo"
            estato = c3.selectbox("Stato", ["Attivo", "Dimesso", "Licenziato"], index=["Attivo", "Dimesso", "Licenziato"].index(attuale_stato) if attuale_stato in ["Attivo", "Dimesso", "Licenziato"] else 0)
            c_tel, c_mail = st.columns(2)
            etel = c_tel.text_input("Cellulare", value=str(row['Cellulare']) if pd.notna(row['Cellulare']) else "")
            email = c_mail.text_input("Email", value=str(row['Email']) if pd.notna(row['Email']) else "")
            c1, c2 = st.columns(2)
            em = c1.selectbox("Mansione", lista_postazioni, index=lista_postazioni.index(row['Mansione']) if row['Mansione'] in lista_postazioni else 0)
            er = c2.selectbox("Riposo", opzioni_riposo, index=opzioni_riposo.index(row['GiornoRiposoSettimanale']) if row['GiornoRiposoSettimanale'] in opzioni_riposo else 7)
            attuale_data_cess = row['Data Cessazione'] if 'Data Cessazione' in row and pd.notna(row['Data Cessazione']) else ""
            edata_cess = st.text_input("Data di uscita (se non attivo)", value=attuale_data_cess)
            val_cont = str(row['Contestazioni']) if 'Contestazioni' in row and pd.notna(row['Contestazioni']) else ""
            e_cont = st.text_area("Lettere di Contestazione", value=val_cont)
            cb1, cb2, _ = st.columns([1,1,2])
            if cb1.form_submit_button("💾 Salva"):
                new_data_row = {"Nome": en, "Cognome": ec, "Mansione": em, "GiornoRiposoSettimanale": er, "Contestazioni": e_cont, "Stato Rapporto": estato, "Data Cessazione": edata_cess, "Cellulare": etel, "Email": email}
                for col, val in new_data_row.items(): data["addetti"].at[idx, col] = val
                conn.update(worksheet="Addetti", data=data["addetti"]); st.cache_data.clear(); st.session_state["editing_id"] = None; st.rerun()
            if cb2.form_submit_button("❌ Annulla"): st.session_state["editing_id"] = None; st.rerun()
    else:
        t1, t2 = st.tabs(["📋 Elenco Staff", "➕ Nuovo Addetto"])
        with t1:
            filtro_lista = st.radio("Mostra:", ["Solo Attivi", "Tutti"], horizontal=True)
            df_lista = data["addetti"] if filtro_lista == "Tutti" else data["addetti"][data["addetti"]["Stato Rapporto"] == "Attivo"]
            for idx, r in df_lista.iterrows():
                disp_addetto = data["disp"][(data["disp"]["Nome"] == r['Nome']) & (data["disp"]["Cognome"] == r['Cognome'])]
                conteggi = disp_addetto["Stato"].value_counts()
                sum_str = f"✅ Disponibile: {conteggi.get('Disponibile', 0)} | 🔵 Permessi: {conteggi.get('Permesso', 0)} | ⚫ Assente: {conteggi.get('Assente', 0)} | 🔘 Malattia: {conteggi.get('Malattia', 0)}"
                with st.container():
                    c1, c2, c3 = st.columns([3, 3, 1])
                    has_cont = 'Contestazioni' in r and pd.notna(r['Contestazioni']) and str(r['Contestazioni']).strip() != ""
                    
                    wa_link = format_wa_link(r)
                    wa_icon = f' <a href="{wa_link}" target="_blank" style="text-decoration:none;">📲</a>' if wa_link else ""
                    
                    nome_label = f"{r['Nome']} {r['Cognome']}{wa_icon}"
                    if r['Stato Rapporto'] != "Attivo": nome_label = f"🚫 {r['Nome']} {r['Cognome']} ({r['Stato Rapporto'].upper()})"
                    
                    c1.markdown(f"**{nome_label}**{' 🚩' if has_cont else ''}", unsafe_allow_html=True)
                    contatti = []
                    if pd.notna(r['Cellulare']) and str(r['Cellulare']).strip() != "": contatti.append(f"📞 {r['Cellulare']}")
                    if pd.notna(r['Email']) and str(r['Email']).strip() != "": contatti.append(f"📧 {r['Email']}")
                    contatti_str = " | ".join(contatti) if contatti else "Nessun recapito"
                    c2.caption(f"{r['Mansione']} | Riposo: {r['GiornoRiposoSettimanale']}\n\n{contatti_str}")
                    if c3.button("✏️", key=f"ed_{idx}"): st.session_state["editing_id"] = idx; st.rerun()
                    st.markdown(f"<div style='font-size: 15px; font-weight: bold; color: #444; margin-top: -10px; margin-bottom: 5px;'>{sum_str}</div>", unsafe_allow_html=True)
                    if has_cont:
                        with st.expander("Vedi contestazioni"): st.warning(r['Contestazioni'])
                    st.divider()
        with t2:
            with st.form("n"):
                c1, c2 = st.columns(2); nn, nc = c1.text_input("Nome"), c2.text_input("Cognome")
                ntel, nmail = c1.text_input("Cellulare"), c2.text_input("Email")
                nm, nr = st.selectbox("Mansione", lista_postazioni), st.selectbox("Riposo", opzioni_riposo)
                ncnt = st.text_area("Contestazioni iniziali")
                if st.form_submit_button("Aggiungi"):
                    new_member = pd.DataFrame([{"Nome":nn, "Cognome":nc, "Mansione":nm, "GiornoRiposoSettimanale":nr, "Contestazioni":ncnt, "Stato Rapporto": "Attivo", "Data Cessazione": "", "Cellulare": ntel, "Email": nmail}])
                    conn.update(worksheet="Addetti", data=pd.concat([data["addetti"], new_member], ignore_index=True))
                    st.cache_data.clear(); st.rerun()

# --- ALTRE SEZIONI ---
elif menu == "⚙️ Pianifica Fabbisogno":
    st.header("Fabbisogno")
    tipo = st.radio("Modalità:", ["Giorno Singolo", "Intervallo"], horizontal=True)
    if tipo == "Giorno Singolo":
        dt = st.date_input("Giorno:", default_date); date_list = [dt]
    else:
        dr = st.date_input("Periodo:", value=[]); date_list = [dr[0] + timedelta(days=x) for x in range((dr[1]-dr[0]).days + 1)] if len(dr) == 2 else []
    if date_list:
        f_inputs = {p: st.number_input(f"{p}:", min_value=0) for p in lista_postazioni}
        if st.button("💾 Salva"):
            new_r = [{"Data": str(d), "Mansione": p, "Quantita": v} for d in date_list for p, v in f_inputs.items()]
            old_d = data["fabbisogno"][~data["fabbisogno"]["Data"].astype(str).isin([str(d) for d in date_list])]
            conn.update(worksheet="Fabbisogno", data=pd.concat([old_d, pd.DataFrame(new_r)], ignore_index=True)); st.cache_data.clear(); st.rerun()

elif menu == "⚙️ Impostazioni Stagione":
    st.header("Configurazione")
    with st.form("s"):
        na, nc = st.date_input("Inizio:", data_apertura), st.date_input("Fine:", data_chiusura)
        if st.form_submit_button("Salva"):
            conf_agg = data["config"].copy()
            conf_agg.loc[conf_agg["Ruolo"] == "Apertura", "Password"] = str(na)
            conf_agg.loc[conf_agg["Ruolo"] == "Chiusura", "Password"] = str(nc)
            conn.update(worksheet="Config", data=conf_agg); st.cache_data.clear(); st.rerun()

elif menu == "🚩 Gestione Postazioni":
    st.header("Postazioni")
    np = st.text_input("Nuova")
    if st.button("Aggiungi"):
        conn.update(worksheet="Postazioni", data=pd.concat([data["postazioni"], pd.DataFrame([{"Nome Postazione": np}])], ignore_index=True)); st.cache_data.clear(); st.rerun()
    st.table(data["postazioni"])

elif menu == "🔑 Gestione Password":
    st.header("Password")
    with st.form("p"):
        ap, up = st.text_input("Admin", value=admin_pwd), st.text_input("User", value=user_pwd)
        if st.form_submit_button("Salva"):
            new_conf = data["config"].copy(); new_conf.loc[new_conf["Ruolo"]=="Admin", "Password"] = ap; new_conf.loc[new_conf["Ruolo"]=="User", "Password"] = up
            conn.update(worksheet="Config", data=new_conf); st.cache_data.clear(); st.rerun()
