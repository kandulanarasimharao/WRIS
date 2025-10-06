import os, glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import linregress, norm

# ========= SETTINGS =========
BASE_DIR = r"AndhraPradesh"   # 👈 change this path if needed
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========= HELPERS =========
def clean_df(df):
    df = df.copy()
    df['dataTime'] = pd.to_datetime(df['dataTime'], errors='coerce')
    df['dataValue'] = pd.to_numeric(df['dataValue'], errors='coerce')
    return df.dropna(subset=['dataTime','dataValue'])

def trend_info(ts):
    ts = ts.dropna()
    if len(ts) < 3: return np.nan, np.nan
    x = np.arange(len(ts))
    res = linregress(x, ts.values)
    return res.slope * 12, res.pvalue  # slope per year

def mann_kendall_test(x):
    x = np.array(x.dropna())
    n = len(x)
    if n < 3: return np.nan
    s = sum(np.sign(x[j]-x[i]) for i in range(n-1) for j in range(i+1,n))
    var_s = (n*(n-1)*(2*n+5))/18
    z = (s-1 if s>0 else s+1 if s<0 else 0)/np.sqrt(var_s)
    return 2*(1 - norm.cdf(abs(z)))

# ========= PROCESS FILES =========
summary_rows = []
folders = [os.path.join(BASE_DIR, "Manual"), os.path.join(BASE_DIR, "Telemetry")]

for folder in folders:
    for f in glob.glob(os.path.join(folder, "*.xls*")):
        try:
            xls = pd.ExcelFile(f)
        except Exception as e:
            print("⚠️ Could not open:", f, e)
            continue

        info = {}
        if "Info" in xls.sheet_names:
            try:
                info_df = pd.read_excel(f, sheet_name="Info", header=None)
                for _, row in info_df.iterrows():
                    if len(row.dropna())>=2:
                        k = str(row.iloc[0]).strip().lower()
                        info[k] = row.iloc[1]
            except Exception as e:
                print("⚠️ Could not parse Info sheet in", f, e)

        if "Data" not in xls.sheet_names:
            print("⚠️ Skipping (no Data sheet):", f)
            continue

        try:
            df = clean_df(pd.read_excel(f, sheet_name="Data"))
        except Exception as e:
            print("⚠️ Could not read Data sheet in", f, e)
            continue

        if df.empty: 
            print("⚠️ No usable data in:", f)
            continue

        df_monthly = df.set_index("dataTime").resample("M").mean(numeric_only=True)

        slope, pval = trend_info(df_monthly["dataValue"])
        mk_p = mann_kendall_test(df_monthly["dataValue"])

        if len(df_monthly) >= 3:
            z = (df_monthly["dataValue"] - df_monthly["dataValue"].mean())/df_monthly["dataValue"].std()
            anomaly_months = int((z.abs()>2).sum())
        else:
            anomaly_months = 0

        # ---- District handling ----
        district_val = (
            info.get("district") or
            info.get("District") or
            info.get("districtname") or
            info.get("District Name")
        )
        if not district_val:
            # take from filename prefix
            district_val = os.path.basename(f).split("_")[0]

        # Always append with full set of keys
        summary_rows.append({
            "station_file": os.path.basename(f),
            "source": os.path.basename(folder),  # manual or telemetry
            "station_name": info.get("stationname",""),
            "district": str(district_val),
            "lat": pd.to_numeric(info.get("latitude",np.nan), errors="coerce"),
            "lon": pd.to_numeric(info.get("longitude",np.nan), errors="coerce"),
            "monthly_points": int(len(df_monthly)),
            "mean_level": float(df_monthly["dataValue"].mean()) if not df_monthly.empty else np.nan,
            "trend_slope_m_per_year": slope,
            "trend_pval": pval,
            "mk_pval": mk_p,
            "anomaly_months": anomaly_months
        })

# ========= SAVE SUMMARIES =========
summary_df = pd.DataFrame(summary_rows)

print("\n=== Debug Info ===")
print("Summary DF shape:", summary_df.shape)
print("Columns:", list(summary_df.columns))
print(summary_df.head(), "\n")

summary_df.to_csv(os.path.join(OUTPUT_DIR,"station_summary.csv"), index=False)

# ========= DISTRICT SUMMARY =========
if not summary_df.empty and all(col in summary_df.columns for col in 
    ["district","station_file","trend_slope_m_per_year","anomaly_months"]):
    
    district_summary = summary_df.groupby("district").agg(
        n_stations=("station_file","count"),
        mean_slope=("trend_slope_m_per_year","mean"),
        mean_anomalies=("anomaly_months","mean")
    ).reset_index()
    
    district_summary.to_csv(os.path.join(OUTPUT_DIR,"district_summary.csv"), index=False)
    print("✅ District summary saved:", os.path.join(OUTPUT_DIR,"district_summary.csv"))
else:
    print("⚠️ No valid data to create district summary.")
    district_summary = pd.DataFrame()

# ========= MAPS & PLOTS =========
if not summary_df.empty:
    if "lat" in summary_df.columns and "lon" in summary_df.columns:
        plt.figure(figsize=(7,6))
        sc = plt.scatter(summary_df["lon"], summary_df["lat"], 
                         c=summary_df["trend_slope_m_per_year"], cmap="coolwarm", s=80)
        plt.colorbar(sc, label="Trend slope (m/year)")
        plt.title("Groundwater trend per station")
        plt.xlabel("Longitude"); plt.ylabel("Latitude"); plt.grid(True)
        plt.savefig(os.path.join(OUTPUT_DIR,"trend_map.png"), dpi=200)

        plt.figure(figsize=(7,6))
        sc = plt.scatter(summary_df["lon"], summary_df["lat"], 
                         c=summary_df["anomaly_months"], cmap="plasma", s=80)
        plt.colorbar(sc, label="Anomaly months")
        plt.title("Groundwater anomalies per station")
        plt.xlabel("Longitude"); plt.ylabel("Latitude"); plt.grid(True)
        plt.savefig(os.path.join(OUTPUT_DIR,"anomaly_map.png"), dpi=200)

    if not district_summary.empty:
        plt.figure(figsize=(10,5))
        district_summary.sort_values("mean_slope").plot(
            x="district", y="mean_slope", kind="barh", legend=False, ax=plt.gca())
        plt.xlabel("Mean slope (m/year)")
        plt.title("Average groundwater trend per district")
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR,"district_trend_barchart.png"), dpi=200)

        plt.figure(figsize=(10,5))
        district_summary.sort_values("mean_anomalies").plot(
            x="district", y="mean_anomalies", kind="barh", legend=False, ax=plt.gca(), color="orange")
        plt.xlabel("Mean anomaly months")
        plt.title("Average groundwater anomalies per district")
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR,"district_anomaly_barchart.png"), dpi=200)

print("\n✅ Processing complete")
print("Outputs saved in:", OUTPUT_DIR)
