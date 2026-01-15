import os
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State
import plotly.express as px

BASE_DATA_DIR = "db_counts"

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def list_databases():
    return sorted(
        d for d in os.listdir(BASE_DATA_DIR)
        if os.path.isdir(os.path.join(BASE_DATA_DIR, d))
    )


def list_dates(db):
    path = os.path.join(BASE_DATA_DIR, db)
    return sorted(
        f.rsplit("_", 1)[-1].replace(".csv", "")
        for f in os.listdir(path)
        if f.endswith(".csv")
    )


def load_db_date(db, date):
    path = os.path.join(BASE_DATA_DIR, db, f"{db}_{date}.csv")
    df = pd.read_csv(path)
    return df[["collection_name", "document_count"]]


# -------------------------------------------------
# Dash App
# -------------------------------------------------
app = Dash(__name__)
app.title = "Database Comparison Analysis"

# -------------------------------------------------
# GLOBAL CSS (Dash 3.x SAFE)
# -------------------------------------------------
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
        body {
            background-color: #0f172a;
            color: #e5e7eb;
        }

        .dark-dropdown .Select-control {
            background-color: #020617 !important;
            color: #e5e7eb !important;
            border: 1px solid #334155 !important;
        }

        .dark-dropdown .Select-menu-outer {
            background-color: #020617 !important;
            border: 1px solid #334155 !important;
        }

        .dark-dropdown .Select-option {
            background-color: #020617 !important;
            color: #e5e7eb !important;
        }

        .dark-dropdown .Select-option.is-focused {
            background-color: #1e293b !important;
        }

        .dark-dropdown .Select-option.is-selected {
            background-color: #334155 !important;
        }

        .dark-dropdown .Select-value-label {
            color: #e5e7eb !important;
        }

        .dark-dropdown .Select--multi .Select-value {
            background-color: #1e293b !important;
            border: 1px solid #475569 !important;
            color: #e5e7eb !important;
        }

        /* 🔧 FIX: typed text + placeholder color */
        .dark-dropdown .Select-input > input {
            color: #e5e7eb !important;
        }

        .dark-dropdown .Select-placeholder {
            color: #94a3b8 !important;
        }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

# -------------------------------------------------
# Data
# -------------------------------------------------
dbs = list_databases()
default_db = dbs[0]
dates = list_dates(default_db)

# -------------------------------------------------
# Layout
# -------------------------------------------------
app.layout = html.Div(
    style={
        "minHeight": "100vh",
        "padding": "20px",
        "fontFamily": "Inter, system-ui"
    },
    children=[

        html.H2("Multi-Database Collection Comparison"),

        html.P(
            "All values are absolute. "
            "For each collection: Red = highest value, Green = lowest value.",
            style={"color": "#94a3b8", "marginBottom": "12px"}
        ),

        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "2fr 1fr",
                "gap": "12px",
                "marginBottom": "20px"
            },
            children=[
                dcc.Dropdown(
                    id="db-select",
                    options=[{"label": d, "value": d} for d in dbs],
                    value=[default_db],
                    multi=True,
                    placeholder="Select databases",
                    className="dark-dropdown"
                ),
                dcc.Dropdown(
                    id="date-select",
                    options=[{"label": d, "value": d} for d in dates],
                    value=dates[-1],
                    placeholder="Select date",
                    className="dark-dropdown"
                )
            ]
        ),

        dcc.Graph(id="chart"),

        html.H4("Comparison Table", style={"marginTop": "24px"}),

        html.Div(id="comparison-table"),

        html.Br(),

        html.Button(
            "Download Comparison CSV",
            id="download-btn",
            n_clicks=0,
            style={
                "backgroundColor": "#020617",
                "color": "#e5e7eb",
                "border": "1px solid #334155",
                "padding": "8px 14px",
                "borderRadius": "6px",
                "cursor": "pointer"
            }
        ),

        dcc.Download(id="download-csv")
    ]
)


# -------------------------------------------------
# Callbacks
# -------------------------------------------------
@app.callback(
    Output("chart", "figure"),
    Output("comparison-table", "children"),
    Input("db-select", "value"),
    Input("date-select", "value")
)
def update_dashboard(selected_dbs, date):
    if not selected_dbs or not date:
        return {}, ""

    frames = []

    for db in selected_dbs:
        df = load_db_date(db, date)
        df["database"] = db
        frames.append(df)

    combined = pd.concat(frames)

    # -----------------------------
    # Chart
    # -----------------------------
    fig = px.bar(
        combined,
        x="collection_name",
        y="document_count",
        color="database",
        barmode="group",
        title="Document Counts per Collection"
    )

    fig.update_layout(
        plot_bgcolor="#020617",
        paper_bgcolor="#020617",
        font_color="#e5e7eb",
        legend_title_text="Database",
        xaxis_title="Collection",
        yaxis_title="Document Count"
    )

    # -----------------------------
    # Smart comparison table
    # -----------------------------
    table_df = combined.pivot_table(
        index="collection_name",
        columns="database",
        values="document_count",
        fill_value=0
    ).reset_index()

    header = html.Tr(
        [html.Th("Collection", style={"border": "1px solid #334155", "padding": "8px"})] +
        [html.Th(db, style={"border": "1px solid #334155", "padding": "8px"})
         for db in selected_dbs]
    )

    rows = []

    for _, row in table_df.iterrows():
        values = [row[db] for db in selected_dbs]
        max_val = max(values)
        min_val = min(values)

        cells = [
            html.Td(
                row["collection_name"],
                style={"border": "1px solid #334155", "padding": "6px"}
            )
        ]

        for db in selected_dbs:
            val = row[db]

            if max_val == min_val:
                color = "#94a3b8"
            elif val == max_val:
                color = "#dc2626"
            elif val == min_val:
                color = "#16a34a"
            else:
                color = "#e5e7eb"

            cells.append(
                html.Td(
                    int(val),
                    style={
                        "border": "1px solid #334155",
                        "padding": "6px",
                        "fontWeight": "600",
                        "color": color
                    }
                )
            )

        rows.append(html.Tr(cells))

    table = html.Table(
        [header] + rows,
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "marginTop": "12px",
            "fontSize": "13px",
            "backgroundColor": "#020617"
        }
    )

    return fig, table


# -------------------------------------------------
# Download callback
# -------------------------------------------------
@app.callback(
    Output("download-csv", "data"),
    Input("download-btn", "n_clicks"),
    State("db-select", "value"),
    State("date-select", "value"),
    prevent_initial_call=True
)
def download_csv(n_clicks, selected_dbs, date):
    if not selected_dbs or not date:
        return None

    frames = []

    for db in selected_dbs:
        df = load_db_date(db, date)
        df = df.rename(columns={"document_count": db})
        frames.append(df)

    merged = frames[0]
    for df in frames[1:]:
        merged = merged.merge(df, on="collection_name", how="outer")

    merged = merged.fillna(0).astype({db: int for db in selected_dbs})

    filename = f"comparison_{date}.csv"

    return dcc.send_data_frame(merged.to_csv, filename, index=False)


# -------------------------------------------------
# Run
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
