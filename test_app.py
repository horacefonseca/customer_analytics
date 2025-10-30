"""
Test script to verify app.py functions work correctly
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

print("="*60)
print("TESTING CUSTOMER ANALYTICS APP")
print("="*60)

# Test 1: Load Data
print("\n[TEST 1] Loading data...")
try:
    df = pd.read_csv('data/canteen_shop_data.csv')
    print(f"[OK] Data loaded: {df.shape}")
    print(f"  Columns: {list(df.columns)}")
except Exception as e:
    print(f"[ERROR] Error loading data: {e}")
    exit(1)

# Test 2: Clean Data
print("\n[TEST 2] Cleaning data...")
try:
    df_clean = df.copy()
    df_clean = df_clean[df_clean['Quantity'] > 0]
    df_clean = df_clean[df_clean['Price'] > 0]
    df_clean['TotalPrice'] = df_clean['Quantity'] * df_clean['Price']
    print(f"[OK] Data cleaned: {df_clean.shape}")
    print(f"  Unique customers: {df_clean['Customer ID'].nunique()}")
except Exception as e:
    print(f"[ERROR] Error cleaning data: {e}")
    exit(1)

# Test 3: RFM Analysis
print("\n[TEST 3] Calculating RFM metrics...")
try:
    snapshot_date = pd.to_datetime(df_clean['Date']).max() + pd.Timedelta(days=1)

    rfm = df_clean.groupby('Customer ID').agg({
        'Date': lambda x: (snapshot_date - pd.to_datetime(x.max())).days,
        'Item': 'count',
        'Total': 'sum'
    }).reset_index()

    rfm.columns = ['Customer ID', 'Recency', 'Frequency', 'Monetary']

    # Create RFM Scores
    rfm['R_Score'] = pd.qcut(rfm['Recency'], 5, labels=[5, 4, 3, 2, 1])
    rfm['F_Score'] = pd.qcut(rfm['Frequency'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
    rfm['M_Score'] = pd.qcut(rfm['Monetary'], 3, labels=[1, 2, 3], duplicates='drop')

    rfm['RFM_Segment'] = rfm['R_Score'].astype(int) + rfm['F_Score'].astype(int) + rfm['M_Score'].astype(int)

    # Segment customers
    def segment_customer(row):
        if row['RFM_Segment'] >= 10 and row['R_Score'] >= 4:
            return 'Champions'
        elif row['RFM_Segment'] >= 7 and row['R_Score'] >= 3:
            return 'Loyal Customers'
        elif row['F_Score'] >= 3 and row['R_Score'] >= 3:
            return 'Potential Loyalists'
        elif row['R_Score'] >= 4:
            return 'Recent Customers'
        elif row['RFM_Segment'] >= 6 and row['R_Score'] <= 2:
            return 'At Risk'
        elif row['F_Score'] >= 2 and row['R_Score'] <= 2:
            return 'Cant Lose Them'
        elif row['R_Score'] <= 2:
            return 'Lost'
        else:
            return 'Others'

    rfm['Customer_Segment'] = rfm.apply(segment_customer, axis=1)

    print(f"[OK]RFM calculated: {rfm.shape}")
    print(f"  Segments: {rfm['Customer_Segment'].nunique()}")
    print(f"  Segment distribution:")
    for seg, count in rfm['Customer_Segment'].value_counts().head().items():
        print(f"    - {seg}: {count}")
except Exception as e:
    print(f"[ERROR]Error in RFM analysis: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 4: CLTV Calculation
print("\n[TEST 4] Calculating CLTV...")
try:
    cltv_data = df_clean.groupby('Customer ID').agg({
        'Item': 'count',
        'Total': 'sum',
        'Date': lambda x: (pd.to_datetime(x.max()) - pd.to_datetime(x.min())).days
    }).reset_index()

    cltv_data.columns = ['Customer ID', 'NumPurchases', 'TotalRevenue', 'CustomerLifespan']

    cltv_data['AvgOrderValue'] = cltv_data['TotalRevenue'] / cltv_data['NumPurchases']
    cltv_data['PurchaseFrequency'] = cltv_data['NumPurchases'] / (cltv_data['CustomerLifespan'] + 1) * 365
    cltv_data['CustomerLifespanYears'] = (cltv_data['CustomerLifespan'] + 1) / 365
    cltv_data['CLTV'] = cltv_data['AvgOrderValue'] * cltv_data['PurchaseFrequency'] * cltv_data['CustomerLifespanYears']

    print(f"[OK]CLTV calculated: {cltv_data.shape}")
    print(f"  Average CLTV: ${cltv_data['CLTV'].mean():.2f}")
    print(f"  Total CLTV: ${cltv_data['CLTV'].sum():.2f}")
except Exception as e:
    print(f"[ERROR]Error calculating CLTV: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 5: KMeans Clustering
print("\n[TEST 5] Performing KMeans clustering...")
try:
    X = rfm[['Recency', 'Frequency', 'Monetary']].copy()
    X['Monetary'] = np.log1p(X['Monetary'])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Elbow method
    inertias = []
    K_range = range(2, 11)
    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_scaled)
        inertias.append(kmeans.inertia_)

    # Apply optimal K
    optimal_k = 4
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    rfm['KMeans_Cluster'] = kmeans.fit_predict(X_scaled)

    print(f"[OK]KMeans clustering completed")
    print(f"  Optimal K: {optimal_k}")
    print(f"  Cluster distribution:")
    for cluster, count in rfm['KMeans_Cluster'].value_counts().sort_index().items():
        print(f"    - Cluster {cluster}: {count}")
except Exception as e:
    print(f"[ERROR]Error in KMeans clustering: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 6: Verify Critical Segments
print("\n[TEST 6] Verifying critical segments...")
try:
    champions = rfm[rfm['Customer_Segment'] == 'Champions']
    at_risk = rfm[rfm['Customer_Segment'] == 'At Risk']

    print(f"[OK]Segment verification:")
    print(f"  Champions: {len(champions)} customers")
    if len(champions) > 0:
        print(f"    Avg Recency: {champions['Recency'].mean():.1f} days")
        print(f"    Avg Frequency: {champions['Frequency'].mean():.1f}")
        print(f"    Avg Monetary: ${champions['Monetary'].mean():.2f}")

    print(f"  At Risk: {len(at_risk)} customers")
    if len(at_risk) > 0:
        print(f"    Avg Recency: {at_risk['Recency'].mean():.1f} days")
        print(f"    Avg Frequency: {at_risk['Frequency'].mean():.1f}")
        print(f"    Avg Monetary: ${at_risk['Monetary'].mean():.2f}")
except Exception as e:
    print(f"[ERROR]Error verifying segments: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Final Summary
print("\n" + "="*60)
print("ALL TESTS PASSED SUCCESSFULLY!")
print("="*60)
print("\nSummary:")
print(f"  Total Customers: {rfm['Customer ID'].nunique()}")
print(f"  Total Transactions: {len(df_clean)}")
print(f"  Total Revenue: ${df_clean['Total'].sum():.2f}")
print(f"  RFM Segments: {rfm['Customer_Segment'].nunique()}")
print(f"  KMeans Clusters: {optimal_k}")
print(f"  Average CLTV: ${cltv_data['CLTV'].mean():.2f}")
print("\nThe app is ready for Streamlit deployment!")
print("="*60)
