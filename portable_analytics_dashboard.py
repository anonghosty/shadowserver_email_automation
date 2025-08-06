import dash
from dash import Dash, html, dcc, dash_table, clientside_callback, ClientsideFunction
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os
import glob
import re
from dotenv import load_dotenv

# === Load environment variables ===
load_dotenv()

# Initialize the Dash app with external stylesheets
app = dash.Dash(__name__, external_stylesheets=[
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'
])

# Set path to the 'statistical_data' folder
base_dir = 'statistical_data'

# Get a list of all organization folders
org_folders = [folder for folder in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, folder))]

def load_csv_files(org_name, dates):
    folder_path = os.path.join(base_dir, org_name)
    data = []
    
    for date in dates:
        pattern = os.path.join(folder_path, f"*{date}*.csv")
        files = glob.glob(pattern)
        
        for file in files:
            df = pd.read_csv(file)
            df['Date'] = date
            data.append(df)
    
    return pd.concat(data, ignore_index=True), files

def extract_category_counts(df):
    categories_split = df['category'].str.split(',')
    all_counts = []

    for idx, categories in enumerate(categories_split):
        for category in categories:
            category = category.strip()
            match = re.match(r'([a-zA-Z0-9_]+)\[(\d+)\]', category)
            if match:
                category_name = match.group(1)
                count = int(match.group(2))
                all_counts.append((category_name, count, df.loc[idx, 'Date']))

    count_df = pd.DataFrame(all_counts, columns=['Category', 'Count', 'Date'])
    return count_df

# Professional CSS styles
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            :root {
                --primary-color: #1a365d;
                --secondary-color: #2d3748;
                --accent-color: #3182ce;
                --success-color: #38a169;
                --warning-color: #d69e2e;
                --danger-color: #e53e3e;
                --white: #ffffff;
                --gray-50: #f7fafc;
                --gray-100: #edf2f7;
                --gray-200: #e2e8f0;
                --gray-300: #cbd5e0;
                --gray-400: #a0aec0;
                --gray-500: #718096;
                --gray-600: #4a5568;
                --gray-700: #2d3748;
                --gray-800: #1a202c;
                --gray-900: #171923;
                --border-radius: 8px;
                --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
                --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
                --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            }
            
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background-color: var(--gray-50);
                color: var(--gray-900);
                line-height: 1.5;
                -webkit-font-smoothing: antialiased;
                -moz-osx-font-smoothing: grayscale;
            }
            
            /* Layout components */
            .container {

                margin: 0 auto;
                padding: 0 1.5rem;
            }
            
            .card {
                background: var(--white);
                border: 1px solid var(--gray-200);
                border-radius: var(--border-radius);
                box-shadow: var(--shadow);
                transition: box-shadow 0.15s ease-in-out;
            }
            
            .card:hover {
                box-shadow: var(--shadow-md);
            }
            
            .card-header {
                padding: 1.5rem;
                border-bottom: 1px solid var(--gray-200);
                background: var(--gray-50);
                border-radius: var(--border-radius) var(--border-radius) 0 0;
            }
            
            .card-body {
                padding: 1.5rem;
            }
            
            /* Typography */
            .heading-1 {
                font-size: 2.25rem;
                font-weight: 700;
                line-height: 1.2;
                color: var(--gray-900);
                margin-bottom: 0.5rem;
            }
            
            .heading-2 {
                font-size: 1.875rem;
                font-weight: 600;
                line-height: 1.3;
                color: var(--gray-800);
                margin-bottom: 1rem;
            }
            
            .heading-3 {
                font-size: 1.5rem;
                font-weight: 600;
                line-height: 1.4;
                color: var(--gray-800);
                margin-bottom: 0.75rem;
            }
            
            .heading-4 {
                font-size: 1.25rem;
                font-weight: 600;
                line-height: 1.4;
                color: var(--gray-700);
                margin-bottom: 0.5rem;
            }
            
            .text-muted {
                color: var(--gray-500);
                font-size: 1rem;
                line-height: 1.6;
            }
            
            /* Header */
            .header {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
                color: var(--white);
                padding: 3rem 0;
                margin-bottom: 2rem;
            }
            
            .header-content {
                text-align: center;
            }
            
            .header-title {
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
                letter-spacing: -0.025em;
            }
            
            .header-subtitle {
                font-size: 1.125rem;
                opacity: 0.9;
                font-weight: 400;
            }
            
            /* Form elements */
            .form-group {
                margin-bottom: 1.5rem;
            }
            
            .form-label {
                display: block;
                font-weight: 500;
                color: var(--gray-700);
                margin-bottom: 0.5rem;
                font-size: 0.875rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            
            /* Custom dropdown styles */
            .Select-control {
                background: var(--white) !important;
                border: 1px solid var(--gray-300) !important;
                border-radius: var(--border-radius) !important;
                color: var(--gray-900) !important;
                min-height: 44px !important;
                font-size: 0.9rem !important;
                transition: all 0.15s ease-in-out !important;
            }
            
            .Select-control:hover {
                border-color: var(--gray-400) !important;
            }
            
            .Select-control.is-focused {
                border-color: var(--accent-color) !important;
                box-shadow: 0 0 0 3px rgba(49, 130, 206, 0.1) !important;
                outline: none !important;
            }
            
            .Select-menu {
                background: var(--white) !important;
                border: 1px solid var(--gray-200) !important;
                border-radius: var(--border-radius) !important;
                box-shadow: var(--shadow-lg) !important;
                z-index: 1000 !important;
            }
            
            .Select-option {
                color: var(--gray-700) !important;
                background: transparent !important;
                padding: 0.75rem 1rem !important;
                font-size: 0.9rem !important;
                border-bottom: 1px solid var(--gray-100) !important;
                transition: background-color 0.15s ease-in-out !important;
            }
            
            .Select-option:hover,
            .Select-option.is-focused {
                background: var(--gray-50) !important;
                color: var(--gray-900) !important;
            }
            
            .Select-option.is-selected {
                background: var(--accent-color) !important;
                color: var(--white) !important;
            }
            
            .Select-placeholder {
                color: var(--gray-400) !important;
                font-size: 0.9rem !important;
            }
            
            .Select-value-label {
                color: var(--gray-900) !important;
                font-size: 0.9rem !important;
            }
            
            /* Grid layouts */
            .grid {
                display: grid;
                gap: 2rem;
            }
            
            .grid-cols-1 {
                grid-template-columns: 1fr;
            }
            
            @media (min-width: 768px) {
                .md\\:grid-cols-2 {
                    grid-template-columns: repeat(2, 1fr);
                }
                .md\\:grid-cols-3 {
                    grid-template-columns: repeat(3, 1fr);
                }
            }
            
            @media (min-width: 1024px) {
                .lg\\:grid-cols-4 {
                    grid-template-columns: repeat(4, 1fr);
                }
            }
            
            /* Status indicators */
            .status-indicator {
                display: inline-flex;
                align-items: center;
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            
            .status-success {
                background: rgba(56, 161, 105, 0.1);
                color: var(--success-color);
            }
            
            .status-warning {
                background: rgba(214, 158, 46, 0.1);
                color: var(--warning-color);
            }
            
            .status-danger {
                background: rgba(229, 62, 62, 0.1);
                color: var(--danger-color);
            }
            
            /* Table styles */
            .dash-table-container {
                border-radius: var(--border-radius);
                overflow: hidden;
                border: 1px solid var(--gray-200);
            }
            
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner table {
                font-family: 'Inter', sans-serif !important;
                border-collapse: collapse !important;
            }
            
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner table thead th {
                background: var(--gray-100) !important;
                color: var(--gray-700) !important;
                font-weight: 600 !important;
                font-size: 0.75rem !important;
                text-transform: uppercase !important;
                letter-spacing: 0.05em !important;
                padding: 1rem 0.75rem !important;
                border-bottom: 2px solid var(--gray-200) !important;
                border-right: 1px solid var(--gray-200) !important;
            }
            
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner table tbody td {
                padding: 0.75rem !important;
                border-bottom: 1px solid var(--gray-200) !important;
                border-right: 1px solid var(--gray-200) !important;
                color: var(--gray-700) !important;
                font-size: 0.875rem !important;
            }
            
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner table tbody tr:hover {
                background: var(--gray-50) !important;
            }
            
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner table tbody tr:nth-child(even) {
                background: rgba(247, 250, 252, 0.5) !important;
            }
            
            /* Loading states */
            .loading-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 3rem;
                color: var(--gray-500);
            }
            
            .loading-spinner {
                width: 24px;
                height: 24px;
                border: 3px solid var(--gray-200);
                border-top-color: var(--accent-color);
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-bottom: 1rem;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            /* Error states */
            .error-container {
                text-align: center;
                padding: 3rem;
                color: var(--gray-500);
            }
            
            .error-icon {
                width: 48px;
                height: 48px;
                margin: 0 auto 1rem;
                color: var(--gray-400);
            }
            
            /* Charts */
            .chart-container {
                background: var(--white);
                border-radius: var(--border-radius);
                overflow: hidden;
                box-shadow: var(--shadow);
            }
            
            /* Responsive utilities */
            .sr-only {
                position: absolute;
                width: 1px;
                height: 1px;
                padding: 0;
                margin: -1px;
                overflow: hidden;
                clip: rect(0, 0, 0, 0);
                white-space: nowrap;
                border: 0;
            }
            
            /* Professional spacing */
            .space-y-4 > * + * {
                margin-top: 1rem;
            }
            
            .space-y-6 > * + * {
                margin-top: 1.5rem;
            }
            
            .space-y-8 > * + * {
                margin-top: 2rem;
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
'''
cert_name = os.getenv("cert_name", "default-cert")
# Professional layout
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H1(cert_name, className="header-title"),
            html.P("Aggregated Threat Intelligence and Security Analytics", className="header-subtitle")
        ], className="header-content")
    ], className="header"),
    
    # Main container
    html.Div([
        # Controls section
        html.Div([
            html.Div([
                # Organization selector
                html.Div([
                    html.Label("Organization Selection", className="form-label"),
                    dcc.Dropdown(
                        id='org-dropdown',
                        options=[{'label': org, 'value': org} for org in org_folders],
                        value=org_folders[0] if org_folders else None,
                        multi=True,
                        placeholder="Select organizations to analyze",
                        className="professional-dropdown"
                    )
                ], className="form-group"),
                
                # Date selector
                html.Div([
                    html.Label("Date Range Selection", className="form-label"),
                    dcc.Dropdown(
                        id='date-dropdown',
                        options=[],
                        value=[],
                        multi=True,
                        placeholder="Select date range for analysis",
                        className="professional-dropdown"
                    )
                ], className="form-group"),
                
                # Category selector
                html.Div([
                    html.Label("Category Filters", className="form-label"),
                    dcc.Dropdown(
                        id='category-dropdown',
                        options=[],
                        multi=True,
                        placeholder="Filter by specific threat categories",
                        className="professional-dropdown"
                    )
                ], className="form-group"),
            ], className="card-body")
        ], className="card", style={"margin-bottom": "2rem"}),
        
        # Results section
        dcc.Loading(
            id="loading",
            type="default",
            color="#3182ce",
            children=[
                # Data table section
                html.Div([
                    html.Div([
                        html.H2("Data Summary", className="heading-3")
                    ], className="card-header"),
                    html.Div(
                        id='data-table',
                        className="card-body"
                    )
                ], className="card", style={"margin-bottom": "2rem"}),
                
                # Charts section
                html.Div([
                    html.Div([
                        html.H2("Analytics Overview", className="heading-3")
                    ], className="card-header"),
                    html.Div([
                        html.Div(
                            id='charts-container',
                            className="grid grid-cols-1 md:grid-cols-2"
                        )
                    ], className="card-body")
                ], className="card")
            ]
        )
    ], className="container"),
    
    # Footer
    html.Div([
        html.Div([
            html.P(
                [
                    f"© 2025 {cert_name}. ",
                    html.Span("Documentation: "),
                    html.A(
                        "https://anonghosty.github.io/shadowserver_email_automation/",
                        href="https://anonghosty.github.io/shadowserver_email_automation/",
                        target="_blank",
                        style={"color": "inherit", "text-decoration": "underline"}
                    )
                ],
                style={
                    "text-align": "center",
                    "color": "var(--gray-500)",
                    "font-size": "0.875rem",
                    "padding": "2rem 0"
                }
            )

        ], className="container")
    ], style={
        "border-top": "1px solid var(--gray-200)",
        "margin-top": "3rem",
        "background": "var(--gray-50)"
    })
])

# Callback to update date dropdown
@app.callback(
    Output('date-dropdown', 'options'),
    Output('date-dropdown', 'value'),
    Input('org-dropdown', 'value')
)
def update_date_dropdown(org_names):
    if isinstance(org_names, str):
        org_names = [org_names]
    
    if not org_names:
        return [], []

    files = []
    for org_name in org_names:
        files.extend(glob.glob(os.path.join(base_dir, org_name, "*.csv")))
    
    dates = set(file.split('_')[-1].split('.')[0] for file in files)
    date_options = [{'label': date, 'value': date} for date in sorted(dates, reverse=True)]
    return date_options, []

# Callback to update category dropdown
@app.callback(
    Output('category-dropdown', 'options'),
    Output('category-dropdown', 'value'),
    Input('org-dropdown', 'value'),
    Input('date-dropdown', 'value')
)
def update_category_dropdown(org_names, dates):
    if not dates or not org_names:
        return [], []

    if isinstance(org_names, str):
        org_names = [org_names]

    all_category_counts = []
    for org_name in org_names:
        try:
            df, files = load_csv_files(org_name, dates)
            count_df = extract_category_counts(df)
            all_category_counts.append(count_df)
        except Exception as e:
            continue

    if not all_category_counts:
        return [], []

    full_category_df = pd.concat(all_category_counts, ignore_index=True)
    categories = sorted(full_category_df['Category'].unique())
    
    category_options = [{'label': category, 'value': category} for category in categories]
    
    return category_options, [category_options[0]['value']] if category_options else []

# Main callback to update dashboard
@app.callback(
    [Output('data-table', 'children'),
     Output('charts-container', 'children')],
    [Input('org-dropdown', 'value'),
     Input('date-dropdown', 'value'),
     Input('category-dropdown', 'value')]
)
def update_dashboard(org_names, selected_dates, selected_categories):
    if not selected_dates or not org_names:
        return html.Div([
            html.Div([
                html.H3("No Data Selected", className="heading-4"),
                html.P("Please select organizations and date ranges to begin analysis.", className="text-muted")
            ], className="loading-container")
        ]), []

    if isinstance(org_names, str):
        org_names = [org_names]

    charts = []
    all_tables = []
    
    for org_name in org_names:
        try:
            df, files = load_csv_files(org_name, selected_dates)
            count_df = extract_category_counts(df)

            if isinstance(selected_categories, str):
                selected_categories = [selected_categories]

            if selected_categories:
                count_df = count_df[count_df['Category'].isin(selected_categories)]

            if count_df.empty:
                continue

            # Create summary table
            summed_count_df = count_df.groupby(['Category', 'Date'], as_index=False)['Count'].sum()
            pivot_df = summed_count_df.pivot(index='Category', columns='Date', values='Count').reset_index()

            date_columns = sorted([col for col in pivot_df.columns if col != 'Category'], reverse=True)
            pivot_df = pivot_df[['Category'] + date_columns]

            # Calculate trends
            if len(selected_dates) > 1:
                for i in range(1, len(date_columns)):
                    date_col = date_columns[i]
                    prev_date_col = date_columns[i - 1]
                    pivot_df[f'Change ({prev_date_col} to {date_col})'] = pivot_df[date_col] - pivot_df[prev_date_col]

            # Professional table
            table = dash_table.DataTable(
                columns=[{"name": col, "id": col, "type": "numeric" if col != "Category" else "text"} for col in pivot_df.columns],
                data=pivot_df.head(50).to_dict('records'),
                style_table={
                    'overflowX': 'auto',
                    'border': 'none'
                },
                style_header={
                    'fontWeight': '600',
                    'textTransform': 'uppercase',
                    'fontSize': '12px',
                    'letterSpacing': '0.05em'
                },
                style_cell={
                    'fontFamily': 'Inter, sans-serif',
                    'fontSize': '14px',
                    'padding': '12px',
                    'textAlign': 'left'
                },
                style_data_conditional=[
                    {
                        'if': {'column_id': col, 'filter_query': f'{{{col}}} > 0'},
                        'backgroundColor': 'rgba(56, 161, 105, 0.1)',
                        'color': '#2d7738'
                    } for col in pivot_df.columns if 'Change' in col
                ] + [
                    {
                        'if': {'column_id': col, 'filter_query': f'{{{col}}} < 0'},
                        'backgroundColor': 'rgba(229, 62, 62, 0.1)',
                        'color': '#c53030'
                    } for col in pivot_df.columns if 'Change' in col
                ],
                page_size=15,
                sort_action="native",
                filter_action="native",
                export_format="xlsx",
                export_headers="display"
            )

            all_tables.append(html.Div([
                html.H4(f"{org_name} Summary", className="heading-4", style={"margin-bottom": "1rem"}),
                table
            ], style={"margin-bottom": "2rem"}))

            # Create professional chart
            comparison_data = []
            for date in selected_dates:
                file_data = load_csv_files(org_name, [date])[0]
                file_count_df = extract_category_counts(file_data)
                summed_file_count_df = file_count_df.groupby('Category', as_index=False)['Count'].sum()
                summed_file_count_df['Date'] = date
                comparison_data.append(summed_file_count_df)

            comparison_df = pd.concat(comparison_data)
            if selected_categories:
                comparison_df = comparison_df[comparison_df['Category'].isin(selected_categories)]

            if comparison_df.empty:
                continue

            # Professional chart with clean styling
            figure = px.bar(
                comparison_df, 
                x='Category', 
                y='Count', 
                color='Date',
                barmode='group',
                title=f'{org_name} - Threat Analysis',
                color_discrete_sequence=['#3182ce', '#38a169', '#d69e2e', '#e53e3e', '#805ad5']
            )
            
            figure.update_layout(
                template="simple_white",
                font_family="Inter",
                title_font_size=16,
                title_font_weight=600,
                title_x=0,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    font_size=12
                ),
                margin=dict(t=60, b=40, l=40, r=40),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    title_font_size=12,
                    tickfont_size=11,
                    gridcolor='#e2e8f0'
                ),
                yaxis=dict(
                    title_font_size=12,
                    tickfont_size=11,
                    gridcolor='#e2e8f0'
                )
            )
            
            figure.update_traces(
                marker_line_width=0,
                opacity=0.85
            )

            charts.append(html.Div([
                dcc.Graph(
                    figure=figure,
                    config={
                        'displayModeBar': True,
                        'displaylogo': False,
                        'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']
                    },
                    className="chart-container"
                )
            ], className="card"))

        except Exception as e:
            charts.append(html.Div([
                html.Div([
                    html.H4(f"Error Loading {org_name}", className="heading-4"),
                    html.P(f"Unable to process data: {str(e)}", className="text-muted")
                ], className="error-container")
            ], className="card"))

    return html.Div(all_tables) if all_tables else html.Div([
        html.P("No data available for the selected criteria.", className="text-muted", style={"text-align": "center"})
    ]), charts

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)