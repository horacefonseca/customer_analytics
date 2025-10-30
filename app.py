"""
Customer Analytics Dashboard
CLTV, RFM Analysis, and KMeans Clustering

Streamlit deployment for canteen shop customer segmentation
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from mpl_toolkits.mplot3d import Axes3D
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Customer Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .insight-box {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 5px solid #1f77b4;
        margin: 1rem 0;
    }
    .metric-card {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# Set plotting style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Cache data loading and processing
@st.cache_data
def load_and_process_data():
    """Load and process the canteen sales data"""
    # Load data
    df = pd.read_csv('data/canteen_shop_data.csv')

    # Clean data
    df = df[df['Quantity'] > 0]
    df = df[df['Price'] > 0]
    df['TotalPrice'] = df['Quantity'] * df['Price']

    return df

@st.cache_data
def calculate_rfm(df):
    """Calculate RFM metrics and segments"""
    snapshot_date = pd.to_datetime(df['Date']).max() + pd.Timedelta(days=1)

    rfm = df.groupby('Customer ID').agg({
        'Date': lambda x: (snapshot_date - pd.to_datetime(x.max())).days,
        'Item': 'count',
        'Total': 'sum'
    }).reset_index()

    rfm.columns = ['Customer ID', 'Recency', 'Frequency', 'Monetary']

    # Create RFM Scores
    rfm['R_Score'] = pd.qcut(rfm['Recency'], 5, labels=[5, 4, 3, 2, 1])
    rfm['F_Score'] = pd.qcut(rfm['Frequency'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
    rfm['M_Score'] = pd.qcut(rfm['Monetary'], 3, labels=[1, 2, 3], duplicates='drop')

    rfm['RFM_Score'] = rfm['R_Score'].astype(str) + rfm['F_Score'].astype(str) + rfm['M_Score'].astype(str)
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

    return rfm

@st.cache_data
def calculate_cltv(df):
    """Calculate Customer Lifetime Value"""
    cltv_data = df.groupby('Customer ID').agg({
        'Item': 'count',
        'Total': 'sum',
        'Date': lambda x: (pd.to_datetime(x.max()) - pd.to_datetime(x.min())).days
    }).reset_index()

    cltv_data.columns = ['Customer ID', 'NumPurchases', 'TotalRevenue', 'CustomerLifespan']

    cltv_data['AvgOrderValue'] = cltv_data['TotalRevenue'] / cltv_data['NumPurchases']
    cltv_data['PurchaseFrequency'] = cltv_data['NumPurchases'] / (cltv_data['CustomerLifespan'] + 1) * 365
    cltv_data['CustomerLifespanYears'] = (cltv_data['CustomerLifespan'] + 1) / 365
    cltv_data['CLTV'] = cltv_data['AvgOrderValue'] * cltv_data['PurchaseFrequency'] * cltv_data['CustomerLifespanYears']

    return cltv_data

@st.cache_data
def perform_kmeans_clustering(rfm):
    """Perform KMeans clustering on RFM data"""
    X = rfm[['Recency', 'Frequency', 'Monetary']].copy()
    X['Monetary'] = np.log1p(X['Monetary'])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Calculate inertias for elbow method
    inertias = []
    K_range = range(2, 11)
    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_scaled)
        inertias.append(kmeans.inertia_)

    # Apply optimal K
    optimal_k = 4
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    rfm_copy = rfm.copy()
    rfm_copy['KMeans_Cluster'] = kmeans.fit_predict(X_scaled)

    # Name clusters
    cluster_profiles = rfm_copy.groupby('KMeans_Cluster')[['Recency', 'Frequency', 'Monetary']].mean()

    def name_cluster(cluster_id, profiles):
        profile = profiles.loc[cluster_id]
        if profile['Frequency'] > profiles['Frequency'].quantile(0.75) and profile['Monetary'] > profiles['Monetary'].quantile(0.75):
            return 'VIP Champions'
        elif profile['Recency'] < profiles['Recency'].quantile(0.25) and profile['Monetary'] > profiles['Monetary'].median():
            return 'Recent Big Spenders'
        elif profile['Frequency'] <= profiles['Frequency'].quantile(0.25) and profile['Monetary'] <= profiles['Monetary'].quantile(0.25):
            return 'Low Engagement'
        else:
            return 'Regular Customers'

    rfm_copy['Cluster_Name'] = rfm_copy['KMeans_Cluster'].apply(lambda x: name_cluster(x, cluster_profiles))

    return rfm_copy, inertias, K_range

# Main app
def main():
    # Header
    st.markdown('<h1 class="main-header">Customer Analytics Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("### 📊 CLTV, RFM Analysis, and KMeans Clustering")

    # Load data
    with st.spinner('Loading and processing data...'):
        df = load_and_process_data()
        rfm = calculate_rfm(df)
        cltv_data = calculate_cltv(df)
        rfm_with_clusters, inertias, K_range = perform_kmeans_clustering(rfm)

    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Analysis",
        ["📈 Executive Summary", "🎯 RFM Analysis", "💰 CLTV Analysis",
         "🔍 KMeans Clustering", "📊 Comparative Analysis", "💡 Business Recommendations"]
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Dataset Overview")
    st.sidebar.metric("Total Transactions", f"{len(df):,}")
    st.sidebar.metric("Unique Customers", f"{df['Customer ID'].nunique():,}")
    st.sidebar.metric("Date Range", f"{df['Date'].min()} to {df['Date'].max()}")
    st.sidebar.metric("Total Revenue", f"£{df['Total'].sum():,.2f}")

    # Page routing
    if page == "📈 Executive Summary":
        show_executive_summary(df, rfm_with_clusters, cltv_data)
    elif page == "🎯 RFM Analysis":
        show_rfm_analysis(rfm)
    elif page == "💰 CLTV Analysis":
        show_cltv_analysis(cltv_data)
    elif page == "🔍 KMeans Clustering":
        show_kmeans_analysis(rfm_with_clusters, inertias, K_range)
    elif page == "📊 Comparative Analysis":
        show_comparative_analysis(rfm_with_clusters)
    elif page == "💡 Business Recommendations":
        show_business_recommendations(rfm_with_clusters, cltv_data)

def show_executive_summary(df, rfm, cltv_data):
    """Executive Summary with 3 Core Insights"""
    st.header("Executive Summary: Three Core Actionable Insights")

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Customers", f"{len(rfm):,}")
    with col2:
        st.metric("Avg CLTV", f"£{cltv_data['CLTV'].mean():.2f}")
    with col3:
        champions = len(rfm[rfm['Customer_Segment'] == 'Champions'])
        st.metric("Champions", f"{champions}")
    with col4:
        at_risk = len(rfm[rfm['Customer_Segment'] == 'At Risk'])
        st.metric("At Risk", f"{at_risk}")

    st.markdown("---")

    # Insight 1: High-Value Customer Profile
    st.markdown("## 🏆 Insight 1: High-Value Customer Profile and Retention Strategy")

    champions_rfm = rfm[rfm['Customer_Segment'] == 'Champions']
    vip_cluster = rfm[rfm['Cluster_Name'] == 'VIP Champions']

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Champions (RFM)")
        st.markdown(f"""
        - **Count**: {len(champions_rfm)} customers
        - **Avg Recency**: {champions_rfm['Recency'].mean():.1f} days
        - **Avg Frequency**: {champions_rfm['Frequency'].mean():.1f} purchases
        - **Avg Monetary**: £{champions_rfm['Monetary'].mean():.2f}
        - **Total Revenue**: £{champions_rfm['Monetary'].sum():,.2f}
        """)

    with col2:
        st.markdown("### VIP Champions (KMeans)")
        st.markdown(f"""
        - **Count**: {len(vip_cluster)} customers
        - **Avg Recency**: {vip_cluster['Recency'].mean():.1f} days
        - **Avg Frequency**: {vip_cluster['Frequency'].mean():.1f} purchases
        - **Avg Monetary**: £{vip_cluster['Monetary'].mean():.2f}
        - **Total Revenue**: £{vip_cluster['Monetary'].sum():,.2f}
        """)

    st.markdown('<div class="insight-box">', unsafe_allow_html=True)
    st.markdown("""
    **Conclusion**: Focus on **Retention & Loyalty**
    - Provide VIP treatment and exclusive offers
    - Implement loyalty rewards program
    - Maintain high lifetime value and prevent churn
    - These customers represent the most stable and profitable revenue stream
    """)
    st.markdown('</div>', unsafe_allow_html=True)

    # Insight 2: Churn Risk
    st.markdown("## ⚠️ Insight 2: Churn Risk and Win-Back Priority")

    at_risk_rfm = rfm[rfm['Customer_Segment'] == 'At Risk']
    low_engagement = rfm[rfm['Cluster_Name'] == 'Low Engagement']

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### At Risk (RFM)")
        st.markdown(f"""
        - **Count**: {len(at_risk_rfm)} customers
        - **Avg Recency**: {at_risk_rfm['Recency'].mean():.1f} days (⚠️ High)
        - **Avg Frequency**: {at_risk_rfm['Frequency'].mean():.1f} purchases
        - **Avg Monetary**: £{at_risk_rfm['Monetary'].mean():.2f}
        - **Revenue at Risk**: £{at_risk_rfm['Monetary'].sum():,.2f}
        """)

    with col2:
        st.markdown("### Low Engagement (KMeans)")
        st.markdown(f"""
        - **Count**: {len(low_engagement)} customers
        - **Avg Recency**: {low_engagement['Recency'].mean():.1f} days
        - **Avg Frequency**: {low_engagement['Frequency'].mean():.1f} purchases
        - **Avg Monetary**: £{low_engagement['Monetary'].mean():.2f}
        - **Potential Recovery**: £{low_engagement['Monetary'].sum():,.2f}
        """)

    st.markdown('<div class="insight-box">', unsafe_allow_html=True)
    st.markdown("""
    **Conclusion**: Implement **Win-Back Campaigns**
    - Focus marketing spend on re-engagement
    - Offer special discounts and personalized emails
    - These are valuable customers on the verge of becoming "Lost"
    - Recovery effort is justified by their historical value
    """)
    st.markdown('</div>', unsafe_allow_html=True)

    # Insight 3: CLTV and Pareto Principle
    st.markdown("## 💎 Insight 3: Customer Lifetime Value and Pareto Principle")

    cltv_clean = cltv_data[cltv_data['CLTV'] <= cltv_data['CLTV'].quantile(0.99)]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total CLTV", f"£{cltv_clean['CLTV'].sum():,.2f}")
    with col2:
        st.metric("Avg CLTV per Customer", f"£{cltv_clean['CLTV'].mean():.2f}")
    with col3:
        st.metric("Median CLTV", f"£{cltv_clean['CLTV'].median():.2f}")

    # Pareto Chart
    sorted_cltv = cltv_clean.sort_values('CLTV', ascending=False).copy()
    sorted_cltv['CumulativePercent'] = (sorted_cltv['CLTV'].cumsum() / sorted_cltv['CLTV'].sum()) * 100
    sorted_cltv['CustomerPercent'] = (np.arange(1, len(sorted_cltv) + 1) / len(sorted_cltv)) * 100

    # Find 20/80 point
    idx_20 = int(len(sorted_cltv) * 0.2)
    cltv_at_20 = sorted_cltv.iloc[idx_20]['CumulativePercent']

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(sorted_cltv['CustomerPercent'], sorted_cltv['CumulativePercent'],
            color='#00BFA5', linewidth=3, label='Cumulative CLTV')
    ax.plot([0, 100], [0, 100], 'k--', alpha=0.3, label='Perfect Equality')
    ax.axvline(20, color='red', linestyle=':', alpha=0.7, linewidth=2)
    ax.axhline(cltv_at_20, color='red', linestyle=':', alpha=0.7, linewidth=2)
    ax.fill_between([0, 20], [0, 0], [cltv_at_20, cltv_at_20], alpha=0.2, color='red')
    ax.set_xlabel('Cumulative % of Customers', fontweight='bold', fontsize=12)
    ax.set_ylabel('Cumulative % of Total CLTV', fontweight='bold', fontsize=12)
    ax.set_title('Pareto Principle: CLTV Concentration', fontweight='bold', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.text(20, cltv_at_20 + 5, f'{cltv_at_20:.1f}%', fontsize=12, fontweight='bold', color='red')
    st.pyplot(fig)
    plt.close()

    st.markdown('<div class="insight-box">', unsafe_allow_html=True)
    st.markdown(f"""
    **Conclusion**: Validate **Pareto Principle** and Budget Allocation
    - Top 20% of customers account for **{cltv_at_20:.1f}%** of total CLTV
    - CLTV quantifies total worth for acquisition cost assessment
    - Heavily prioritize top-tier customers identified by RFM/KMeans
    - Use CLTV metrics to justify marketing spend and CAC targets
    """)
    st.markdown('</div>', unsafe_allow_html=True)

def show_rfm_analysis(rfm):
    """RFM Analysis Page"""
    st.header("🎯 RFM Analysis")
    st.markdown("Recency, Frequency, Monetary (RFM) segmentation analysis")

    # RFM Distribution
    st.subheader("RFM Metrics Distribution")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    axes[0].hist(rfm['Recency'], bins=30, color='#FF7043', edgecolor='black', alpha=0.7)
    axes[0].axvline(rfm['Recency'].median(), color='red', linestyle='--', linewidth=2)
    axes[0].set_title('Recency Distribution', fontweight='bold')
    axes[0].set_xlabel('Days Since Last Purchase')
    axes[0].set_ylabel('Number of Customers')

    axes[1].hist(rfm['Frequency'], bins=30, color='#00BFA5', edgecolor='black', alpha=0.7)
    axes[1].axvline(rfm['Frequency'].median(), color='red', linestyle='--', linewidth=2)
    axes[1].set_title('Frequency Distribution', fontweight='bold')
    axes[1].set_xlabel('Number of Purchases')
    axes[1].set_ylabel('Number of Customers')

    axes[2].hist(np.log10(rfm['Monetary']), bins=30, color='#FFC107', edgecolor='black', alpha=0.7)
    axes[2].axvline(np.log10(rfm['Monetary'].median()), color='red', linestyle='--', linewidth=2)
    axes[2].set_title('Monetary Distribution (Log)', fontweight='bold')
    axes[2].set_xlabel('Log10(Total Spend)')
    axes[2].set_ylabel('Number of Customers')

    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # Customer Segments Distribution (Essential Visualization 1)
    st.subheader("📊 Customer Segments Distribution")

    segment_counts = rfm['Customer_Segment'].value_counts()
    segment_pct = (segment_counts / len(rfm) * 100).round(1)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors_palette = ['#FF7043', '#00BFA5', '#FFC107', '#42A5F5', '#AB47BC', '#66BB6A', '#FFA726', '#EC407A']
    bars = ax.barh(segment_counts.index, segment_counts.values, color=colors_palette[:len(segment_counts)])
    ax.set_xlabel('Number of Customers', fontweight='bold', fontsize=12)
    ax.set_ylabel('Segment', fontweight='bold', fontsize=12)
    ax.set_title('Customer Segments Distribution', fontweight='bold', fontsize=14)

    for i, (count, pct) in enumerate(zip(segment_counts.values, segment_pct.values)):
        ax.text(count, i, f' {count} ({pct}%)', va='center', fontweight='bold')

    st.pyplot(fig)
    plt.close()

    # Segment Metric Heatmap (Essential Visualization 2)
    st.subheader("🔥 Segment Metric Heatmap")

    segment_metrics = rfm.groupby('Customer_Segment')[['Recency', 'Frequency', 'Monetary']].mean()
    segment_metrics_normalized = (segment_metrics - segment_metrics.min()) / (segment_metrics.max() - segment_metrics.min())

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(segment_metrics_normalized.T, annot=True, fmt='.2f', cmap='RdYlGn_r',
                linewidths=2, cbar_kws={'label': 'Normalized Score'}, ax=ax, annot_kws={'fontsize': 11, 'fontweight': 'bold'})
    ax.set_title('RFM Metrics by Customer Segment (Normalized)', fontweight='bold', fontsize=14)
    ax.set_xlabel('Customer Segment', fontweight='bold', fontsize=12)
    ax.set_ylabel('RFM Metric', fontweight='bold', fontsize=12)
    st.pyplot(fig)
    plt.close()

    # Segment Summary Table
    st.subheader("Segment Summary Statistics")
    segment_summary = rfm.groupby('Customer_Segment').agg({
        'Recency': 'mean',
        'Frequency': 'mean',
        'Monetary': ['mean', 'sum'],
        'Customer ID': 'count'
    }).round(2)
    segment_summary.columns = ['Avg Recency', 'Avg Frequency', 'Avg Monetary', 'Total Revenue', 'Count']
    st.dataframe(segment_summary.style.background_gradient(cmap='YlOrRd', subset=['Total Revenue']))

def show_cltv_analysis(cltv_data):
    """CLTV Analysis Page"""
    st.header("💰 Customer Lifetime Value (CLTV) Analysis")

    cltv_clean = cltv_data[cltv_data['CLTV'] <= cltv_data['CLTV'].quantile(0.99)]

    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total CLTV", f"£{cltv_clean['CLTV'].sum():,.2f}")
    with col2:
        st.metric("Mean CLTV", f"£{cltv_clean['CLTV'].mean():.2f}")
    with col3:
        st.metric("Median CLTV", f"£{cltv_clean['CLTV'].median():.2f}")
    with col4:
        st.metric("Max CLTV", f"£{cltv_clean['CLTV'].max():.2f}")

    # CLTV Distribution (Essential Visualization 5)
    st.subheader("📊 CLTV Distribution")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(cltv_clean['CLTV'], bins=50, color='#00BFA5', edgecolor='black', alpha=0.7)
    ax.axvline(cltv_clean['CLTV'].mean(), color='red', linestyle='--', linewidth=2,
               label=f'Mean: £{cltv_clean["CLTV"].mean():.2f}')
    ax.axvline(cltv_clean['CLTV'].median(), color='blue', linestyle='--', linewidth=2,
               label=f'Median: £{cltv_clean["CLTV"].median():.2f}')
    ax.set_xlabel('Customer Lifetime Value (£)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Number of Customers', fontweight='bold', fontsize=12)
    ax.set_title('CLTV Distribution', fontweight='bold', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)
    plt.close()

    # Cumulative CLTV Distribution (Essential Visualization 4)
    st.subheader("📈 Cumulative CLTV Distribution (Pareto Analysis)")

    sorted_cltv = cltv_clean.sort_values('CLTV', ascending=False).copy()
    sorted_cltv['CumulativePercent'] = (sorted_cltv['CLTV'].cumsum() / sorted_cltv['CLTV'].sum()) * 100
    sorted_cltv['CustomerPercent'] = (np.arange(1, len(sorted_cltv) + 1) / len(sorted_cltv)) * 100

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(sorted_cltv['CustomerPercent'], sorted_cltv['CumulativePercent'],
            color='#00BFA5', linewidth=3, label='Cumulative CLTV')
    ax.plot([0, 100], [0, 100], 'k--', alpha=0.3, label='Perfect Equality')
    ax.axvline(20, color='red', linestyle=':', alpha=0.5, linewidth=2, label='20% Mark')
    ax.axhline(80, color='red', linestyle=':', alpha=0.5, linewidth=2, label='80% Mark')
    ax.fill_between([0, 100], [0, 100], sorted_cltv['CustomerPercent'].values[::-1], alpha=0.1, color='orange')
    ax.set_xlabel('Cumulative % of Customers', fontweight='bold', fontsize=12)
    ax.set_ylabel('Cumulative % of Total CLTV', fontweight='bold', fontsize=12)
    ax.set_title('Cumulative CLTV Distribution (Pareto)', fontweight='bold', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.legend()
    st.pyplot(fig)
    plt.close()

    # Customer Value Segments
    st.subheader("🎯 Customer Value Segments")

    cltv_quartiles = pd.qcut(cltv_clean['CLTV'], q=4, labels=['Low Value', 'Medium Value', 'High Value', 'Top Value'])
    segment_counts = cltv_quartiles.value_counts().sort_index()

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#FFC107', '#FF7043', '#42A5F5', '#00BFA5']
    bars = ax.bar(segment_counts.index, segment_counts.values, color=colors, edgecolor='black', linewidth=2)
    ax.set_title('Customer Value Segments', fontweight='bold', fontsize=14)
    ax.set_xlabel('CLTV Segment', fontweight='bold', fontsize=12)
    ax.set_ylabel('Number of Customers', fontweight='bold', fontsize=12)

    for i, v in enumerate(segment_counts.values):
        ax.text(i, v, f'{v}', ha='center', va='bottom', fontweight='bold', fontsize=12)

    st.pyplot(fig)
    plt.close()

def show_kmeans_analysis(rfm, inertias, K_range):
    """KMeans Clustering Analysis Page"""
    st.header("🔍 KMeans Clustering Analysis")

    # Elbow Method
    st.subheader("📉 Elbow Method for Optimal K")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(K_range, inertias, 'bo-', linewidth=2, markersize=10)
    ax.axvline(x=4, color='red', linestyle='--', alpha=0.7, linewidth=2, label='Optimal K=4')
    ax.set_xlabel('Number of Clusters (K)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Inertia (Within-Cluster Sum of Squares)', fontweight='bold', fontsize=12)
    ax.set_title('Elbow Method: Finding Optimal Number of Clusters', fontweight='bold', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_xticks(K_range)
    st.pyplot(fig)
    plt.close()

    # Revenue by KMeans Cluster (Essential Visualization 3)
    st.subheader("💰 Revenue by KMeans Cluster")

    cluster_revenue = rfm.groupby('KMeans_Cluster')['Monetary'].sum().sort_values(ascending=False)
    cluster_counts = rfm['KMeans_Cluster'].value_counts().sort_index()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    colors = ['#FF7043', '#00BFA5', '#FFC107', '#42A5F5']
    bars1 = ax1.bar(range(len(cluster_revenue)), cluster_revenue.values,
                    color=[colors[i] for i in cluster_revenue.index], edgecolor='black', linewidth=2)
    ax1.set_xticks(range(len(cluster_revenue)))
    ax1.set_xticklabels([f'Cluster {i}' for i in cluster_revenue.index])
    ax1.set_title('Total Revenue by KMeans Cluster', fontweight='bold', fontsize=14)
    ax1.set_ylabel('Total Revenue (£)', fontweight='bold', fontsize=12)

    for i, (idx, v) in enumerate(cluster_revenue.items()):
        ax1.text(i, v, f'£{v/1000:.0f}K', ha='center', va='bottom', fontweight='bold', fontsize=11)

    bars2 = ax2.bar(range(len(cluster_counts)), cluster_counts.values,
                    color=colors, edgecolor='black', linewidth=2)
    ax2.set_xticks(range(len(cluster_counts)))
    ax2.set_xticklabels([f'Cluster {i}' for i in range(len(cluster_counts))])
    ax2.set_title('Customer Distribution by Cluster', fontweight='bold', fontsize=14)
    ax2.set_ylabel('Number of Customers', fontweight='bold', fontsize=12)

    for i, v in enumerate(cluster_counts.values):
        ax2.text(i, v, f'{v}', ha='center', va='bottom', fontweight='bold', fontsize=11)

    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # 3D Cluster Visualization
    st.subheader("🌐 3D Cluster Visualization")

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    for i in range(4):
        cluster_data = rfm[rfm['KMeans_Cluster'] == i]
        ax.scatter(cluster_data['Recency'],
                  cluster_data['Frequency'],
                  np.log1p(cluster_data['Monetary']),
                  c=colors[i],
                  label=f'Cluster {i}: {cluster_data["Cluster_Name"].iloc[0]}',
                  alpha=0.6,
                  s=50,
                  edgecolor='black',
                  linewidth=0.5)

    ax.set_xlabel('Recency (days)', fontweight='bold', fontsize=11)
    ax.set_ylabel('Frequency (purchases)', fontweight='bold', fontsize=11)
    ax.set_zlabel('Log(Monetary)', fontweight='bold', fontsize=11)
    ax.set_title('KMeans Clustering (3D View)', fontweight='bold', fontsize=14)
    ax.legend(loc='upper right', fontsize=10)

    st.pyplot(fig)
    plt.close()

    # Cluster Summary
    st.subheader("📊 Cluster Summary Statistics")

    cluster_summary = rfm.groupby(['KMeans_Cluster', 'Cluster_Name']).agg({
        'Recency': 'mean',
        'Frequency': 'mean',
        'Monetary': ['mean', 'sum'],
        'Customer ID': 'count'
    }).round(2)
    cluster_summary.columns = ['Avg Recency', 'Avg Frequency', 'Avg Monetary', 'Total Revenue', 'Count']
    st.dataframe(cluster_summary.style.background_gradient(cmap='YlGnBu'))

def show_comparative_analysis(rfm):
    """Comparative Analysis Page"""
    st.header("📊 Comparative Analysis: RFM vs KMeans")

    # RFM Segments vs KMeans Clusters (Essential Visualization 7)
    st.subheader("🔄 RFM Segments vs KMeans Clusters Cross-Tabulation")

    crosstab = pd.crosstab(rfm['Customer_Segment'], rfm['KMeans_Cluster'])

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.heatmap(crosstab, annot=True, fmt='d', cmap='YlOrRd', ax=ax,
                cbar_kws={'label': 'Customer Count'}, linewidths=2,
                annot_kws={'fontsize': 12, 'fontweight': 'bold'})
    ax.set_title('RFM Segments vs KMeans Clusters', fontweight='bold', fontsize=14)
    ax.set_xlabel('KMeans Cluster', fontweight='bold', fontsize=12)
    ax.set_ylabel('RFM Segment', fontweight='bold', fontsize=12)
    st.pyplot(fig)
    plt.close()

    st.markdown("""
    This heatmap shows the convergence between rule-based RFM segments and data-driven KMeans clusters.
    Strong alignment confirms that both methods identify similar customer groups, validating the segmentation.
    """)

    # Recency vs Log(Monetary) Scatter (Essential Visualization 6)
    st.subheader("🎯 Recency vs Monetary by Cluster")

    fig, ax = plt.subplots(figsize=(12, 8))
    colors_cluster = ['#FF7043', '#00BFA5', '#FFC107', '#42A5F5']

    for i in range(4):
        cluster_data = rfm[rfm['KMeans_Cluster'] == i]
        ax.scatter(cluster_data['Recency'],
                  np.log1p(cluster_data['Monetary']),
                  c=colors_cluster[i],
                  label=f'Cluster {i}: {cluster_data["Cluster_Name"].iloc[0]}',
                  alpha=0.6,
                  s=100,
                  edgecolor='black',
                  linewidth=0.5)

    ax.set_xlabel('Recency (Days Since Last Purchase)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Log(Monetary Value)', fontweight='bold', fontsize=12)
    ax.set_title('Recency vs Monetary: Customer Action Space', fontweight='bold', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Add quadrant lines
    median_recency = rfm['Recency'].median()
    median_monetary = np.log1p(rfm['Monetary'].median())
    ax.axvline(median_recency, color='gray', linestyle='--', alpha=0.5)
    ax.axhline(median_monetary, color='gray', linestyle='--', alpha=0.5)

    st.pyplot(fig)
    plt.close()

    st.markdown("""
    **Action Space Mapping:**
    - **Low Recency + High Monetary** (Bottom Right): Retain and nurture
    - **High Recency + Low Monetary** (Top Left): Let go or minimal investment
    - **Low Recency + Low Monetary** (Bottom Left): Upsell opportunity
    - **High Recency + High Monetary** (Top Right): Win-back priority
    """)

    # Segment Comparison
    st.subheader("📈 Segment Performance Comparison")

    col1, col2 = st.columns(2)

    with col1:
        segment_monetary = rfm.groupby('Customer_Segment')['Monetary'].mean().sort_values(ascending=True)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh(range(len(segment_monetary)), segment_monetary.values, color='#00BFA5', alpha=0.7, edgecolor='black')
        ax.set_yticks(range(len(segment_monetary)))
        ax.set_yticklabels(segment_monetary.index)
        ax.set_title('Avg Monetary by RFM Segment', fontweight='bold')
        ax.set_xlabel('Average Monetary (£)', fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        st.pyplot(fig)
        plt.close()

    with col2:
        cluster_monetary = rfm.groupby('Cluster_Name')['Monetary'].mean().sort_values(ascending=True)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh(range(len(cluster_monetary)), cluster_monetary.values, color='#FF7043', alpha=0.7, edgecolor='black')
        ax.set_yticks(range(len(cluster_monetary)))
        ax.set_yticklabels(cluster_monetary.index)
        ax.set_title('Avg Monetary by KMeans Cluster', fontweight='bold')
        ax.set_xlabel('Average Monetary (£)', fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        st.pyplot(fig)
        plt.close()

def show_business_recommendations(rfm, cltv_data):
    """Business Recommendations Page"""
    st.header("💡 Business Recommendations & Action Plan")

    st.markdown("## Strategic Priorities Based on Data Analysis")

    # Priority 1: Champions
    st.markdown("### 🏆 Priority 1: Retain Champions and VIP Customers")

    champions = rfm[rfm['Customer_Segment'] == 'Champions']
    vip = rfm[rfm['Cluster_Name'] == 'VIP Champions']

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Champions Count", f"{len(champions)}")
    with col2:
        st.metric("VIP Count", f"{len(vip)}")
    with col3:
        revenue = champions['Monetary'].sum() + vip['Monetary'].sum()
        st.metric("Combined Revenue", f"£{revenue:,.2f}")

    st.markdown("""
    **Recommended Actions:**
    - ✅ Implement VIP loyalty program with exclusive benefits
    - ✅ Provide priority customer service and early access to new products
    - ✅ Personalized thank-you communications and rewards
    - ✅ Quarterly check-ins to ensure satisfaction
    - ✅ Referral incentives to leverage their networks

    **Expected Outcome:** Maintain 95%+ retention rate, increase lifetime value by 15-20%
    """)

    # Priority 2: Win-Back At Risk
    st.markdown("### ⚠️ Priority 2: Win-Back At-Risk and Low Engagement Customers")

    at_risk = rfm[rfm['Customer_Segment'] == 'At Risk']
    low_engagement = rfm[rfm['Cluster_Name'] == 'Low Engagement']

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("At Risk Count", f"{len(at_risk)}")
    with col2:
        st.metric("Low Engagement Count", f"{len(low_engagement)}")
    with col3:
        potential = at_risk['Monetary'].sum() + low_engagement['Monetary'].sum()
        st.metric("Revenue at Risk", f"£{potential:,.2f}")

    st.markdown("""
    **Recommended Actions:**
    - ✅ Launch targeted email campaign with special 20-30% discount offers
    - ✅ Send personalized "We miss you" messages
    - ✅ Survey to understand reasons for disengagement
    - ✅ Limited-time exclusive offers to create urgency
    - ✅ Re-onboarding program highlighting new products/services

    **Expected Outcome:** Recover 30-40% of at-risk customers, generate £{:,.2f} in recovered revenue
    """.format(potential * 0.35))

    # Priority 3: Grow Loyal Customers
    st.markdown("### 📈 Priority 3: Grow Loyal Customers and Regular Customers")

    loyal = rfm[rfm['Customer_Segment'] == 'Loyal Customers']
    regular = rfm[rfm['Cluster_Name'] == 'Regular Customers']

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Loyal Count", f"{len(loyal)}")
    with col2:
        st.metric("Regular Count", f"{len(regular)}")
    with col3:
        revenue = loyal['Monetary'].sum() + regular['Monetary'].sum()
        st.metric("Current Revenue", f"£{revenue:,.2f}")

    st.markdown("""
    **Recommended Actions:**
    - ✅ Upsell and cross-sell campaigns based on purchase history
    - ✅ Bundle offers to increase average order value
    - ✅ Increase purchase frequency through subscription models
    - ✅ Educational content about complementary products
    - ✅ Gamification and engagement programs

    **Expected Outcome:** Increase average order value by 10-15%, boost purchase frequency by 20%
    """)

    # CLTV-Based Budget Allocation
    st.markdown("### 💰 CLTV-Based Budget Allocation")

    cltv_clean = cltv_data[cltv_data['CLTV'] <= cltv_data['CLTV'].quantile(0.99)]
    avg_cltv = cltv_clean['CLTV'].mean()

    st.markdown(f"""
    **Customer Acquisition Cost (CAC) Recommendations:**
    - Average CLTV: £{avg_cltv:.2f}
    - Recommended Max CAC (30% of CLTV): £{avg_cltv * 0.3:.2f}
    - Target CAC for Champions: £{avg_cltv * 0.5:.2f} (higher tolerance)
    - Target CAC for Regular Customers: £{avg_cltv * 0.2:.2f}

    **Marketing Budget Allocation:**
    - 50% - Champion/VIP Retention
    - 30% - At-Risk Win-Back Campaigns
    - 15% - Loyal Customer Growth
    - 5% - Experimental New Customer Acquisition
    """)

    # Implementation Timeline
    st.markdown("### 📅 Implementation Timeline")

    timeline_df = pd.DataFrame({
        'Phase': ['Month 1-2', 'Month 3-4', 'Month 5-6', 'Ongoing'],
        'Priority Actions': [
            'Launch VIP program, Start at-risk campaigns',
            'Implement loyalty rewards, Analyze win-back results',
            'Scale successful campaigns, Optimize based on data',
            'Continuous monitoring and refinement'
        ],
        'Expected Impact': [
            'Stabilize top-tier customers',
            'Recover 20-30% of at-risk',
            'Increase overall revenue by 15%',
            'Sustained growth and optimization'
        ]
    })

    st.table(timeline_df)

# Run the app
if __name__ == "__main__":
    main()
