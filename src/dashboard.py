"""Dashboard visualization module.

Note: This is a simple dashboard placeholder.
For full functionality, implement with Streamlit or migrate to Next.js.
"""

import json
import sys

try:
    import pandas as pd
    import streamlit as st
except ImportError:
    print("Streamlit not installed. Install with: pip install streamlit pandas")
    sys.exit(1)

from src.storage import TrackDatabase


def main():
    """Streamlit dashboard main function."""
    st.set_page_config(
        page_title="AI Visibility Tracker",
        page_icon="\U0001F4CA",
        layout="wide"
    )

    st.title("\U0001F4CA AI Visibility Tracker")

    # Load database
    db = TrackDatabase()

    # KPI row
    stats = db.get_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Runs", stats['total_runs'])
    with col2:
        st.metric("Total Queries", stats['total_records'])
    with col3:
        st.metric("Unique Models", stats['unique_models'])
    with col4:
        st.metric("Mentions Detected", stats['total_mentions'])

    st.divider()

    # Brand selection
    # TODO: Extract unique brands from data
    st.subheader("Brand Analysis")

    brand = st.selectbox(
        "Select brand to analyze",
        ["Nike", "Adidas", "Reebok", "New Balance", "Under Armour", "Puma"]
    )

    days = st.sidebar.slider("Days of history", 7, 90, 30)

    # Get trends
    trends = db.get_trends(brand, days)

    if trends:
        df = pd.DataFrame(trends)

        st.subheader(f"Trends for {brand}")

        # Line chart
        if not df.empty and 'date' in df.columns:
            chart_data = df.pivot_table(
                index='date',
                columns='model_name',
                values='mention_count',
                aggfunc='sum'
            ).fillna(0)
            st.line_chart(chart_data)

        # Model comparison
        model_stats = db.get_model_statistics(brand, days)
        if model_stats:
            st.subheader("Model Comparison")
            model_df = pd.DataFrame(model_stats)
            st.dataframe(
                model_df,
                column_config={
                    "mention_rate_pct": st.column_config.ProgressColumn(
                        "Mention Rate",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                    )
                },
                hide_index=True
            )
    else:
        st.info(f"No data found for {brand} in the last {days} days.")

    st.divider()

    # Raw data view
    with st.expander("View Raw Data"):
        mentions = db.get_all_mentions(days)
        if mentions:
            st.write(f"Total mentions: {len(mentions)}")

            # Show sample
            for m in mentions[:10]:
                st.markdown(f"**{m['model_name']}** - {m['detected_at']}:")
                st.json(json.loads(m['mentions_json']) if m['mentions_json'] else {})
        else:
            st.write("No mentions detected in the selected period.")

    # Export button
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export CSV"):
            db.export_to_csv(f"exports/{brand}_{days}days.csv")
            st.success(f"Exported to exports/{brand}_{days}days.csv")
    with col2:
        if st.button("Export JSON"):
            db.export_to_json(f"exports/{brand}_{days}days.json")
            st.success(f"Exported to exports/{brand}_{days}days.json")


if __name__ == "__main__":
    main()
