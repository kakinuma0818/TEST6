# main.py
import streamlit as st
import pandas as pd
import numpy as np
import itertools, math
from datetime import datetime

# ---------------------
# Config / Styling
# ---------------------
st.set_page_config(page_title="競馬投資アプリ", layout="wide")
st.markdown("<style>body{font-family: Helvetica, Arial, sans-serif;}</style>", unsafe_allow_html=True)

MIN_BET_UNIT = 100

# ---------------------
# Helpers: rounding / odds estimate / combos
# ---------------------
def round_unit(x, unit=MIN_BET_UNIT):
    if x <= 0:
        return 0
    return int(math.ceil(x / unit) * unit)

def geom_mean(vals):
    a = 1.0
    for v in vals:
        a *= max(0.001, v)
    return a ** (1.0 / len(vals))

def estimate_combo_odds(names, df, bet_type):
    # approximate combo odds from individual odds (fallback used if needed)
    odds_list = []
    for n in names:
        row = df[df["馬名"]==n]
        odds_list.append(float(row.iloc[0]["オッズ"]) if len(row)>0 else 10.0)
    gm = geom_mean(odds_list)
    if bet_type in ["単勝","複勝"]:
        return float(odds_list[0])
    if bet_type in ["枠連","馬連","ワイド","馬単"]:
        return max(1.0, gm * 1.6)
    if bet_type in ["3連複","3連単"]:
        return max(1.0, gm * 2.5)
    return gm

def generate_combinations_by_method(selected_names, bet_type, method, axis1=None, axis2=None, formation=None):
    names = selected_names[:]
    combos = []
    if bet_type in ["単勝","複勝"]:
        combos = [(n,) for n in names]
    elif bet_type in ["枠連","馬連","ワイド"]:
        if method == "ボックス":
            combos = list(itertools.combinations(names,2))
        elif method == "軸1":
            if not axis1: return []
            combos = [(axis1, other) for other in names if other!=axis1]
        elif method == "フォーメーション" and formation:
            c1 = formation.get("col1", names)
            c2 = formation.get("col2", names)
            combos = [(a,b) for a in c1 for b in c2 if a!=b]
        else:
            combos = list(itertools.combinations(names,2))
    elif bet_type == "馬単":
        if method == "ボックス":
            combos = list(itertools.permutations(names,2))
        elif method == "軸1":
            if not axis1: return []
            combos = [(axis1, other) for other in names if other!=axis1]
        elif method == "フォーメーション" and formation:
            combos = [(a,b) for a in formation.get("col1",names) for b in formation.get("col2",names) if a!=b]
        else:
            combos = list(itertools.permutations(names,2))
    elif bet_type in ["3連複","3連単"]:
        if method == "ボックス":
            combos = list(itertools.combinations(names,3)) if bet_type=="3連複" else list(itertools.permutations(names,3))
        elif method == "軸1":
            if not axis1: return []
            others = [n for n in names if n!=axis1]
            if bet_type=="3連複":
                combos = [tuple(sorted((axis1, *c))) for c in itertools.combinations(others,2)]
                combos = list(dict.fromkeys(combos))
            else:
                combos = [(axis1, b, c) for (b,c) in itertools.permutations(others,2)]
        elif method == "軸2":
            if not axis1 or not axis2: return []
            others = [n for n in names if n not in (axis1,axis2)]
            if bet_type=="3連複":
                combos = [tuple(sorted((axis1, axis2, o))) for o in others]
            else:
                combos = []
                for o in others:
                    combos.append((axis1, axis2, o))
                    combos.append((axis2, axis1, o))
        elif method == "フォーメーション" and formation:
            c1 = formation.get("col1",names)
            c2 = formation.get("col2",names)
            c3 = formation.get("col3",names)
            combos = [(a,b,c) for a in c1 for b in c2 for c in c3 if len({a,b,c})==3]
            if bet_type=="3連複":
                combos = [tuple(sorted(c)) for c in combos]
                combos = list(dict.fromkeys(combos))
    # fallback unique tuples
    combos = [tuple(c) for c in combos]
    return combos

def allocate_by_target(combos, df_horses, total_investment, desired_odds, bet_type, tolerance=0.1):
    results = []
    if not combos:
        return results, 0, 0
    H = total_investment * desired_odds
    est_odds = [estimate_combo_odds(c, df_horses, bet_type) for c in combos]
    N = len(combos)
    raw_bets = [H / (o * N) for o in est_odds]
    rounded = [round_unit(b) for b in raw_bets]
    total_bet = sum(rounded)
    if total_bet > total_investment and total_bet>0:
        scale = total_investment / total_bet
        rounded = [max(MIN_BET_UNIT, round_unit(b*scale)) for b in rounded]
        total_bet = sum(rounded)
    for combo, amt, o in zip(combos, rounded, est_odds):
        expected = amt * o
        note = ""
        if expected < H * (1 - tolerance):
            note = f"下回り: {int(expected)} < {int(H*(1-tolerance))}"
        results.append({"組合せ": combo, "掛け金": int(amt), "推定オッズ": round(o,2), "期待払い戻し": round(expected,1), "注記": note})
    return results, total_bet, H

# ---------------------
# Load data (CSV optional)
# ---------------------
@st.cache_data(ttl=300)
def load_data(path=None):
    if path:
        try:
            df = pd.read_csv(path)
            return df
        except Exception as e:
            st.warning(f"CSV読み込み失敗: {e} → デモデータを使用します")
    demo = [
        {"枠":1,"馬番":1,"馬名":"馬A","性齢":"牡4","斤量":57,"体重":"500kg","騎手":"川田","脚質":"差し","オッズ":3.5,"人気":1,"スコア":85},
        {"枠":1,"馬番":2,"馬名":"馬B","性齢":"牝3","斤量":55,"体重":"480kg","騎手":"武豊","脚質":"逃げ","オッズ":5.0,"人気":2,"スコア":78},
        {"枠":2,"馬番":3,"馬名":"馬C","性齢":"牡5","斤量":57,"体重":"510kg","騎手":"ルメール","脚質":"差し","オッズ":8.0,"人気":3,"スコア":70},
        {"枠":3,"馬番":4,"馬名":"馬D","性齢":"牡6","斤量":58,"体重":"490kg","騎手":"福永","脚質":"先行","オッズ":12.0,"人気":4,"スコア":66},
    ]
    df = pd.DataFrame(demo)
    # add placeholders for AI fields
    ai_fields = ["スピード","パワー","スタミナ","展開","脚質","距離","上がり","近走","コース適性","騎手相性","枠指数","展開隊列","調教","馬体","気配","合計"]
    for f in ai_fields:
        if f not in df.columns:
            df[f] = np.random.randint(40,90, len(df))
    # compute a normalized AI合計 properly later
    return df

# Sidebar CSV path optional
st.sidebar.header("データ読み込み（任意）")
csv_path = st.sidebar.text_input("race CSV path (leave blank to use demo):", "")

df = load_data(csv_path.strip() if csv_path.strip()!="" else None)

# top controls
c1, c2, c3, c4 = st.columns([2,2,2,1])
with c1:
    race_date = st.date_input("日付", datetime.today())
with c2:
    race_course = st.selectbox("競馬場", ["東京","中山","京都","阪神","小倉","中京","福島","新潟"])
with c3:
    race_no = st.selectbox("レース番号", list(range(1,13)))
with c4:
    if st.button("更新 🔄"):
        st.experimental_rerun()

st.markdown(f"### {race_date} {race_course} {race_no}R")

# ---------------------
# Tabs: 出馬表｜スコア｜AI｜馬券｜基本情報
# ---------------------
tabs = st.tabs(["出馬表","スコア","AI","馬券","基本情報"])

# ---------------------
# 出馬表 tab
# ---------------------
with tabs[0]:
    st.subheader("出馬表")
    # left fixed columns
    left_cols = ["枠","馬番","馬名"]
    right_cols = ["性齢","斤量","体重","騎手","脚質","オッズ","人気","スコア","AI合計","AI順位","印"]
    # ensure columns exist
    if "AI合計" not in df.columns:
        df["AI合計"] = (df["スピード"]*1.2 + df["パワー"]*1.0 + df["スタミナ"]*1.0 + df["展開"]*1.3 + df["脚質"]*1.0 + df["距離"]*1.1 + df["上がり"]*1.2 + df["近走"]*1.2)/ (1) 
        # scale to 0-100
        df["AI合計"] = ((df["AI合計"] - df["AI合計"].min()) / (df["AI合計"].max() - df["AI合計"].min() + 1e-6) * 100).round(1)
    df = df.sort_values("馬番").reset_index(drop=True)
    df["AI順位"] = df["AI合計"].rank(ascending=False, method="min").astype(int)
    left_df = df[left_cols].copy()
    right_df = df[right_cols].copy()
    # display side-by-side to simulate fixed left columns
    colL, colR = st.columns([1,5], gap="small")
    with colL:
        st.write(" ")  # spacing
        st.dataframe(left_df, use_container_width=True, height=450)
    with colR:
        st.dataframe(right_df, use_container_width=True, height=450)
    st.caption("※ 左側：枠・馬番・馬名を固定表示する代替レイアウト（横スクロールは右側で行います）")

# ---------------------
# スコア tab
# ---------------------
with tabs[1]:
    st.subheader("スコア（手動調整 -3～+3）")
    df_score = df.copy()
    # ensure columns exist
    base_cols = ["馬名","合計","スピード","パワー","スタミナ","展開","脚質","距離","上がり","近走","コース適性","騎手相性","枠指数","展開隊列"]
    for c in base_cols:
        if c not in df_score.columns:
            df_score[c] = np.random.randint(40,90,len(df_score))
    if "合計" not in df_score.columns:
        # provisional: compute sum with weights (same as AI logic)
        df_score["合計"] = (df_score["スピード"]*30 + df_score["パワー"]*15 + df_score["スタミナ"]*15 + df_score["展開"]*10 + df_score["脚質"]*10 + df_score["上がり"]*10 + df_score["距離"]*10) / 100
    # manual adjustments
    manual = []
    for i, r in df_score.iterrows():
        v = st.selectbox(f"{r['馬名']} 手動", options=[-3,-2,-1,0,1,2,3], index=3, key=f"manual_{i}")
        manual.append(v)
    df_score["手動"] = manual
    # recompute 合計: base合計 (normalized) + 手動 (scaled)
    df_score["合計"] = (df_score["スピード"]*30 + df_score["パワー"]*15 + df_score["スタミナ"]*15 + df_score["展開"]*10 + df_score["脚質"]*10 + df_score["上がり"]*10 + df_score["距離"]*10) / 100
    # normalize to 0-100
    df_score["合計"] = ((df_score["合計"] - df_score["合計"].min()) / (df_score["合計"].max() - df_score["合計"].min() + 1e-6) * 100).round(1) + df_score["手動"]
    # show with name+合計 fixed on left
    left = df_score[["馬名","合計"]]
    right = df_score[[c for c in base_cols if c not in ("馬名","合計")] + ["手動"]]
    colL, colR = st.columns([1.2,4], gap="small")
    with colL:
        st.dataframe(left, use_container_width=True, height=500)
    with colR:
        st.dataframe(right, use_container_width=True, height=500)
    # reflect back to main df
    for i, row in df_score.iterrows():
        df.loc[df["馬名"]==row["馬名"], "スコア"] = row["合計"]

# ---------------------
# AI tab
# ---------------------
with tabs[2]:
    st.subheader("AI（各指数と合計）")
    # ensure AI fields exist
    ai_cols = ["馬名","合計","スピード","パワー","スタミナ","展開","脚質","距離","上がり","近走","コース適性","騎手相性","枠指数","展開隊列","調教","馬体","気配"]
    for c in ai_cols:
        if c not in df.columns:
            df[c] = np.random.randint(40,90,len(df))
    # compute合計 with defined weights (normalized to 0-100)
    weights = {"スピード":30,"パワー":15,"スタミナ":15,"展開":10,"脚質":10,"上がり":10,"距離":10,"近走":12,"コース適性":8,"騎手相性":8,"枠指数":5,"展開隊列":8,"調教":6,"馬体":6,"気配":5}
    # compute raw sum
    df["AI_raw"] = 0
    for k,v in weights.items():
        if k in df.columns:
            df["AI_raw"] += df[k] * v
    # normalize AI_raw to 0-100
    df["合計"] = ((df["AI_raw"] - df["AI_raw"].min()) / (df["AI_raw"].max() - df["AI_raw"].min() + 1e-9) * 100).round(1)
    # build display: fix 馬名 & 合計 left
    left = df[["馬名","合計"]]
    right = df[["スピード","パワー","スタミナ","展開","脚質","距離","上がり","近走","コース適性","騎手相性","枠指数","展開隊列","調教","馬体","気配"]]
    colL, colR = st.columns([1.2,4], gap="small")
    with colL:
        st.dataframe(left, use_container_width=True, height=550)
    with colR:
        st.dataframe(right, use_container_width=True, height=550)
    st.caption("表は左が固定表示（馬名・合計）。右を横スクロールして詳細を確認できます。")

# ---------------------
# 馬券 tab
# ---------------------
with tabs[3]:
    st.subheader("馬券購入（自動配分）")
    # operation order enforced: total -> desired -> bet type -> method -> selection
    total_investment = st.number_input("1) 総投資金額（円）", min_value=100, step=100, value=1000, key="input_total")
    desired_odds = st.number_input("2) 希望払い戻し倍率（例:1.5）", min_value=1.0, step=0.5, value=1.5, key="input_desired")
    # bet type order enforced
    bet_types = ["単勝","複勝","枠連","馬連","馬単","ワイド","3連複","3連単"]
    bet_type = st.selectbox("3) 馬券種類", bet_types)
    methods = ["通常","軸1","軸2","ボックス","フォーメーション"]
    method = st.selectbox("4) 買い方", methods, index=0)
    st.markdown("5) 馬を選択")
    selected = []
    cols = st.columns(2)
    for idx, row in df.iterrows():
        c = cols[idx % 2].checkbox(f"{row['馬番']}: {row['馬名']} (オッズ:{row['オッズ']})", key=f"bet_sel_{idx}")
        if c:
            selected.append(row["馬名"])
    axis1 = axis2 = None
    formation = None
    if method in ("軸1","軸2","フォーメーション"):
        st.markdown("軸 / フォーメーション指定")
        if method in ("軸1","軸2"):
            axis1 = st.selectbox("軸1を選択（空白可）", [""] + selected, index=0)
            if method=="軸2":
                axis2 = st.selectbox("軸2を選択（空白可）", [""] + selected, index=0)
        else:
            if bet_type in ["3連複","3連単"]:
                c1 = st.multiselect("1列目", options=selected)
                c2 = st.multiselect("2列目", options=selected)
                c3 = st.multiselect("3列目", options=selected)
                formation = {"col1": c1 or selected, "col2": c2 or selected, "col3": c3 or selected}
            else:
                c1 = st.multiselect("1列目", options=selected)
                c2 = st.multiselect("2列目", options=selected)
                formation = {"col1": c1 or selected, "col2": c2 or selected}
    tolerance_pct = st.slider("下回り許容率 (%)", min_value=0, max_value=50, value=10, step=1)
    if st.button("自動配分計算"):
        if len(selected)==0:
            st.warning("馬を選択してください。")
        else:
            combos = generate_combinations_by_method(selected, bet_type, method, axis1=axis1 if axis1!="" else None, axis2=axis2 if axis2!="" else None, formation=formation)
            if not combos:
                st.warning("組合せが作れません。軸/選択/フォーメーションを確認してください。")
            else:
                allocs, total_bet, H = allocate_by_target(combos, df, total_investment, desired_odds, bet_type, tolerance=tolerance_pct/100.0)
                st.write(f"目標払い戻し H = {total_investment} × {desired_odds} = {int(H)} 円")
                st.write(f"合計掛け金（計算結果）: {total_bet} 円 (入力投資: {total_investment} 円)")
                if total_bet > total_investment:
                    st.warning("計算上の合計掛け金が入力投資額を超えています。投資額を増やすか希望倍率を下げてください。")
                st.dataframe(pd.DataFrame(allocs), use_container_width=True)

# ---------------------
# 基本情報 tab
# ---------------------
with tabs[4]:
    st.subheader("基本情報（馬一覧 → タップで詳細）")
    # show simple list
    for idx, row in df.iterrows():
        if st.button(f"{row['馬番']}: {row['馬名']}", key=f"detail_{idx}"):
            # show horse detail modal/section
            st.markdown(f"### {row['馬名']} の情報")
            cols_left, cols_right = st.columns([3,2])
            with cols_left:
                st.write(f"性齢: {row.get('性齢','')}")
                # bloodline placeholder - expecting CSV has these columns
                blood = {"父":"", "母":"", "父父":"", "父母":"", "母父":"", "母母":""}
                for k in blood.keys():
                    st.write(f"{k}: {row.get(k,'')}")
                st.write(f"馬主: {row.get('馬主','')}")
                st.write(f"調教師: {row.get('調教師','')}")
                st.write(f"生産者: {row.get('生産者','')}")
                st.write(f"通算成績: {row.get('通算成績','')}")
                st.write("直近のレース成績（CSVに詳細があれば表示）")
                # if past races exist in CSV, they should be loaded separately; here we show a placeholder
                st.write(row.get("過去成績","(CSVにより出力可能)"))
            with cols_right:
                st.write("追加データ")
                st.write(f"コース適性: {row.get('コース適性','')}")
                st.write(f"距離適性: {row.get('距離','')}")
            st.markdown("---")

# ---------------------
# Footer
# ---------------------
st.markdown("---")
st.markdown("注意: 組合せオッズ・期待払い戻しは推定値です。実運用時はJRA等のオッズを参照してください。")
